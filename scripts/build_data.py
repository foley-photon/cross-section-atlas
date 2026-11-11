"""Build the data files the page reads (data/index.json and data/s/<n>.json) from a cleaned cross-section archive.

    python scripts/build_data.py CLEAN_DIR OUT_DIR [--built YYYY-MM-DD]

CLEAN_DIR is the clean/ folder the archive scripts in scripts/archive/ write (clean/index.json and one JSON file per
dataset); OUT_DIR is the page's data/ folder (on the site, beta/cross-sections/data). Writes OUT_DIR/index.json
(species and dataset metadata, no spectra) and OUT_DIR/s/<n>.json (one spectrum each, which the page loads when it is
shown). Each spectrum is thinned to at most MAX_POINTS points, keeping its shape on a log σ scale (largest-triangle
buckets), so peaks and band heads survive; shorter spectra are kept whole. For a thinned spectrum the index also holds
σ of the full spectrum at each laser line of the page (LASER_NM), because narrow windows between bands can fall between
the kept points. Non-positive and non-finite σ are dropped.

Left out (listed in meta.skipped, with the reason in meta.skipped_why): datasets not in cm² molecule⁻¹, datasets the
archive's checks flagged, MPI-Mainz files that are not σ against wavelength (σ against temperature at one wavelength,
fit parameters, temperature gradients), the O₂–O₂ collision-induced absorption (O4, cm⁵ molecule⁻²), and datasets with
no point left. Points of an MPI-Mainz file that lie more than a factor of two outside the wavelength range in its file
name are dropped and named in the dataset's note.

--built sets the build date written to index.json (default: today, UTC), so that a rebuild can be compared byte for
byte with an earlier one.

The data are not part of this repository (see README.md); this script is how the site's copy is made. Standard
library only.
"""
import argparse, bisect, datetime, json, math, os, re, sys, unicodedata

MAX_POINTS = 2000

# the page's laser lines (LASER_LINES in site/js/xsec.js; a test checks that the two lists agree)
LASER_NM = [118.2, 121.567, 157.6, 193.3, 212.8, 222, 248.4, 266, 308, 351.1, 354.7, 405, 532.1]

SOURCES = {
    'tuvx': {'short': 'TUV-x', 'name': 'NCAR TUV-x photolysis data (cross sections, quantum yields, solar flux)', 'url': 'https://github.com/NCAR/tuv-x',
             'license': 'Apache License 2.0.', 'cite': 'the TUV-x data files and the original papers each file names.'},
    'mainz2013': {'short': 'MPI-Mainz 2013', 'name': 'The MPI-Mainz UV/VIS Spectral Atlas of Gaseous Molecules of Atmospheric Interest, 2013 snapshot',
                  'url': 'https://doi.org/10.5281/zenodo.6951', 'license': 'CC BY 4.0 (Zenodo record).',
                  'cite': 'H. Keller-Rudek, G. K. Moortgat, R. Sander and R. Sörensen, Earth Syst. Sci. Data 5, 365–373 (2013), doi:10.5194/essd-5-365-2013, and the original papers.'},
    'leiden': {'short': 'Leiden', 'name': 'Leiden database of photodissociation and photoionization cross sections', 'url': 'https://home.strw.leidenuniv.nl/~ewine/photo/',
               'license': 'No license stated; the database asks users to cite it and the original sources.',
               'cite': 'A. N. Heays, A. D. Bosman and E. F. van Dishoeck, Astron. Astrophys. 602, A105 (2017), doi:10.1051/0004-6361/201628742, and the original papers.'},
    'bremen': {'short': 'IUP Bremen', 'name': 'Institute of Environmental Physics, University of Bremen, molecular spectroscopy data', 'url': 'https://www.iup.uni-bremen.de/gruppen/molspec/databases/',
               'license': 'No license stated; the files ask that the paper be cited.', 'cite': 'the original papers named with each dataset.'},
    'cfa': {'short': 'Harvard CfA', 'name': 'Harvard–Smithsonian Center for Astrophysics molecular spectroscopy database', 'url': 'https://lweb.cfa.harvard.edu/amp/ampdata/cfamols.html',
            'license': 'No license stated; cite the publications.', 'cite': 'the original papers named with each dataset.'},
}

# MPI-Mainz files whose columns are not σ(λ): σ against temperature at one wavelength, fit parameters, dσ/dT
NOT_SIGMA = re.compile(r'\((?:T dependence|parameters|T-gradient)\)')
UPPER = re.compile(r'\(upper limits?\)')


def read_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def key_of(formula):
    """File-safe key for a species: the formula with anything but letters, digits, +, - replaced."""
    k = unicodedata.normalize('NFKD', formula)
    return re.sub(r'[^A-Za-z0-9+\-]+', '_', k).strip('_') or 'x'


def resample(d, mx=MAX_POINTS):
    """At most mx points of d ([[λ, σ], ...] sorted by λ): the first and last, and in each bucket between them the point
    that spans the largest triangle (λ, log10 σ) with the point kept before it and the mean of the next bucket.
    The same algorithm as resample() in site/js/xsec.js."""
    if len(d) <= mx:
        return d
    ly = [math.log10(max(p[1], 1e-40)) for p in d]
    out = [d[0]]; a = 0; n = len(d)
    bucket = (n - 2) / (mx - 2)
    for i in range(mx - 2):
        s = int(i * bucket) + 1; e = min(int((i + 1) * bucket) + 1, n - 1)
        ns = min(int((i + 1) * bucket) + 1, n - 1); ne = min(int((i + 2) * bucket) + 1, n)
        cnt = max(1, ne - ns)
        ax = sum(d[j][0] for j in range(ns, ne)) / cnt; ay = sum(ly[j] for j in range(ns, ne)) / cnt
        best, area = s, -1.0
        for j in range(s, e):
            ar = abs((d[a][0] - ax) * (ly[j] - ly[a]) - (d[a][0] - d[j][0]) * (ay - ly[a]))
            if ar > area:
                area, best = ar, j
        out.append(d[best]); a = best
    out.append(d[-1])
    return out


def interp(xs, ys, x):
    """σ at x by linear interpolation in sorted xs (at a repeated wavelength, the value after the step), as sigmaAt() in
    site/js/xsec.js; None outside the data."""
    i = bisect.bisect_right(xs, x)
    if i == 0 or (i == len(xs) and x > xs[-1]):
        return None
    if i == len(xs):
        return ys[-1]
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def js_key(x):
    """The key the page looks a laser line up by: the number as JavaScript prints it (266, not 266.0)."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def sig(x):
    """σ to 5 significant figures; λ is kept as given (rounded to 1e-4 nm)."""
    return float('%.5g' % x)


def skip_reason(r):
    """Why a dataset is left out, or '' when it is kept."""
    if r.get('units') != 'cm2/molecule':
        return 'units are not cm2/molecule'
    if 'QA FLAG' in str(r.get('notes') or ''):
        return 'flagged by the archive checks'
    if r.get('source') == 'mainz2013' and NOT_SIGMA.search(r['id']):
        return 'not sigma against wavelength (temperature table, fit parameters or temperature gradient)'
    if (r.get('species_canonical') or r.get('species')) == 'O4':
        return 'O2-O2 collision-induced absorption, cm5/molecule2'
    return ''


def skip(r):
    """True for a dataset that is left out (skip_reason)."""
    return bool(skip_reason(r))


def name_range(id_):
    """The wavelength range in an MPI-Mainz file name (_245-340nm, _210nm, _477.3,532.2,577.2nm), or None."""
    m = re.search(r'_(\d+(?:\.\d*)?(?:\s*[-,]\s*\d+(?:\.\d*)?)*)\s?nm', id_)
    if not m:
        return None
    v = [float(x) for x in re.split(r'\s*[-,]\s*', m.group(1)) if x]
    return (min(v), max(v)) if v else None


def clean_points(raw):
    """Finite points with σ > 0, as floats, sorted by wavelength."""
    out = []
    for p in raw:
        if len(p) < 2 or p[0] is None or p[1] is None:
            continue
        x, y = float(p[0]), float(p[1])
        if math.isfinite(x) and math.isfinite(y) and y > 0:
            out.append([x, y])
    return sorted(out, key=lambda p: p[0])


def year_of(ref):
    y = ref.get('year')
    if isinstance(y, int):
        return y
    return int(y) if str(y or '').isdigit() else None


def archive_date(idx):
    """The date of the archive's index.json: its 'date' field, or in the 2026-11-07 archive (which names that field
    differently) the first top-level field that holds an ISO date."""
    if idx.get('date'):
        return idx['date']
    return next((v for v in idx.values() if isinstance(v, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', v)), '')


def demojibake(s):
    """Curly quotes and dashes that were decoded as Latin-1 somewhere upstream (â, 0x80, 0x9c for “) put back."""
    return re.sub('â\u0080[\u0080-¿]', lambda m: m.group(0).encode('latin-1').decode('utf-8'), s)


def journal(j):
    """The journal field as the page shows it: two run-together references ('(1983).J . Brion') separated."""
    j = re.sub(r'\)\.(?=[A-Z])', '); ', str(j or ''))
    return re.sub(r'\b([A-Z]) \.', r'\1.', j)


CUT = re.compile(r'\s*\(\d{4}\)|,\s*\d{4}\b|,?\s*(?:personal|private|unpublished|Ph\.?\s?D|in:|Report)\b|,\s*[“"]|\s+[“"]', re.I)
NAMES = re.compile(r"^(?:[A-Z][a-z]?\.(?:\s?-?[A-Z][a-z]?\.)*\s?(?:(?:von|van|de|der|le)\s)?[A-Z][\w'\-]+(?:,\s*(?:and\s+)?|\s+and\s+|$))+$")


def authors_from(text):
    """The author list at the start of a free-text citation ('A.M. Bass (1984), personal communication ...'), or ''."""
    c = re.sub(r'\s+', ' ', text).strip()
    m = CUT.search(c)
    head = c[:m.start()].strip(' ,') if m else ''
    return head if head and len(head) < 200 and NAMES.match(head) else ''


def reference(r, ds):
    """The reference fields the page shows: a (authors), y, t (title), j (journal), doi, and where the source gives no
    authors or title, c (its citation text) and lab (a short label for the dataset list) when no authors are found."""
    ref = r.get('reference') or {}
    out = {'a': ref.get('authors') or '', 'y': ref.get('year') or '', 't': ref.get('title') or '', 'j': journal(ref.get('journal')), 'doi': ref.get('doi') or ''}
    if out['a'] or out['t']:
        return out
    if r.get('source') == 'tuvx':
        text = re.sub(r'\s+', ' ', str(ds.get('comments') or '')).strip()
        if text:
            out['c'] = 'TUV-x file header: ' + (text if len(text) <= 300 else text[:300].rsplit(' ', 1)[0] + ' …')
        out['lab'] = 'TUV-x ' + r['id'].split(':', 1)[-1]
        return out
    text = demojibake(re.sub(r'\s+', ' ', str(ref.get('citation_text') or '')).strip())
    if text:
        out['c'] = text if len(text) <= 400 else text[:400].rsplit(' ', 1)[0] + ' …'
        out['a'] = authors_from(text)
    if not out['a']:
        m = re.search(r'_([^_(]+)\(\d{4}', r['id'])
        out['lab'] = m.group(1) if m else r['id'].split(':', 1)[-1]
    return out


def build(clean, out, built=None):
    """Write out/index.json and out/s/*.json from the archive in clean; returns the summary line."""
    built = built or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    idx = read_json(os.path.join(clean, 'index.json'))
    rows = [r for r in idx['datasets'] if r.get('kind') == 'cross_section']
    species = {}; skipped = []; why = {}
    sdir = os.path.join(out, 's')
    os.makedirs(sdir, exist_ok=True)
    for f in os.listdir(sdir):                        # only the spectrum files this script writes
        if re.fullmatch(r'\d{5}\.json', f):
            os.remove(os.path.join(sdir, f))
    total = 0; nfile = 0
    for r in rows:
        reason = skip_reason(r)
        if reason:
            skipped.append(r['id']); why[r['id']] = reason; continue
        ds = read_json(os.path.join(clean, r['path']))
        data = clean_points(ds['data'])
        notes = []
        rg = name_range(r['id']) if r.get('source') == 'mainz2013' else None
        if rg and data:
            far = [p[0] for p in data if p[0] < rg[0] / 2 or p[0] > rg[1] * 2]
            if far:
                data = [p for p in data if not (p[0] < rg[0] / 2 or p[0] > rg[1] * 2)]
                notes.append('Left out: %s at %s nm, far outside the %g–%g nm of the file name.' % (
                    'a point' if len(far) == 1 else '%d points' % len(far), ', '.join('%g' % x for x in far[:5]), rg[0], rg[1]))
        if not data:
            skipped.append(r['id']); why[r['id']] = 'no point left' + (' (all far outside the wavelength range of the file name)' if notes else ''); continue
        upper = bool(UPPER.search(r['id']))
        if upper:
            notes.insert(0, 'Upper limits, not measured cross sections.')
        orig = len(data)
        full_x = [p[0] for p in data]; full_y = [p[1] for p in data]
        data = [[round(l, 4), sig(s)] for l, s in resample(data)]
        f = r.get('species_canonical') or r['species']; k = key_of(f)
        sp = species.setdefault(k, {'k': k, 'f': f, 'n': r.get('name') or '', 'cas': r.get('cas') or '', 'sets': []})
        if not sp['n'] and r.get('name'): sp['n'] = r['name']
        if not sp['cas'] and r.get('cas'): sp['cas'] = r['cas']
        nfile += 1; fid = '%05d' % nfile
        src_notes = str(r.get('notes') or '').strip()
        note = ' '.join(notes + ([src_notes] if src_notes else []))
        row = {
            'id': r['id'], 'f': fid, 'src': r['source'], 'T': r.get('T_K'), 'l': [round(data[0][0], 2), round(data[-1][0], 2)], 'np': len(data), 'n0': orig,
            'rec': bool(r.get('recommended')), 'med': r.get('lambda_medium') or 'unknown', 'res': r.get('resolution') or '',
            'ref': reference(r, ds),
            'y': year_of(r.get('reference') or {}),
            'note': note[:400],
        }
        if upper:
            row['ul'] = True
        if len(data) < orig:                         # thinned: σ of the full spectrum at the laser lines
            at = {}
            for nm in LASER_NM:
                v = interp(full_x, full_y, nm)
                if v is not None:
                    at[js_key(nm)] = sig(v)
            if at:
                row['at'] = at
        sp['sets'].append(row)
        p = os.path.join(sdir, fid + '.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, separators=(',', ':'))
        total += os.path.getsize(p)
    used = sorted({s['src'] for sp in species.values() for s in sp['sets']})
    index = {'meta': {'built': built, 'archive': archive_date(idx), 'max_points': MAX_POINTS,
                      'sources': {k: SOURCES.get(k, {'short': k, 'name': k}) for k in used}, 'skipped': skipped, 'skipped_why': why},
             'species': sorted(species.values(), key=lambda s: (-len(s['sets']), s['f']))}
    with open(os.path.join(out, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(',', ':'))
    return '%d species, %d datasets (%d skipped), spectra %.1f MB in %d files, index %.2f MB' % (
        len(species), sum(len(s['sets']) for s in species.values()), len(skipped), total / 1e6, nfile,
        os.path.getsize(os.path.join(out, 'index.json')) / 1e6)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('clean', help='the archive\'s clean/ folder (with index.json)')
    ap.add_argument('out', help='the page\'s data/ folder to write')
    ap.add_argument('--built', help='build date for index.json, YYYY-MM-DD (default: today, UTC)')
    a = ap.parse_args(argv)
    if a.built and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', a.built):
        ap.error('--built must be YYYY-MM-DD')
    print(build(a.clean, a.out, a.built))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
