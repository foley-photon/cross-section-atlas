"""Build the data files the page reads (data/species.json, data/sp/, data/s/, data/who.json, data/coarse.json and
data/index.json) from a cleaned cross-section archive.

    python scripts/build_data.py CLEAN_DIR OUT_DIR [--built YYYY-MM-DD]

CLEAN_DIR is the clean/ folder the archive scripts in scripts/archive/ write (clean/index.json and one JSON file per
dataset); OUT_DIR is the page's data/ folder (on the site, beta/cross-sections/data). Writes OUT_DIR/index.json
(species and dataset metadata, no spectra) and OUT_DIR/s/<n>.json (one spectrum each, which the page loads when it is
shown). Each spectrum is thinned to at most MAX_POINTS points, keeping its shape on a log σ scale (largest-triangle
buckets), so peaks and band heads survive; shorter spectra are kept whole. For a thinned spectrum the index also holds
σ of the full spectrum at each laser line of the page (LASER_NM), because narrow windows between bands can fall between
the kept points. Non-positive and non-finite σ are dropped.

Beside index.json, which holds everything and is what the page read up to version 1.0.4, the same metadata are written
in pieces, so that the page can start without reading all of it:

    species.json     the species list: [key, formula, name, CAS number, number of datasets] each, and the meta block
                     without the lists of skipped datasets. The page's search and its molecule buttons need only this.
    sp/<key>.json    one species' entry of index.json (its datasets), loaded when the species is chosen. A key that
                     differs from an earlier one only by case (CO, Co), or that Windows cannot hold as a file name,
                     gets a suffix; the species list then names the file in a sixth field.
    who.json         for "Who absorbs here?": at each laser line, one dataset per species (pick_key says which) and its
                     σ there, strongest first. The value is the one the page's own table gives for that dataset.
                     Line-intensity lists and values below 1e-40 cm² (underflow in the source) are left out.
    coarse.json      the same for any wavelength, coarsely: for each species and each WHO_BIN nm wide bin, the mean of σ
                     over the bin in the dataset chosen for the bin, as round(100 log10 σ).

index.json is written exactly as before, so a copy of the page that reads only index.json keeps working.

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

# "Who absorbs here?": bin width of the coarse table (nm), and what counts as room temperature when one dataset per
# species is chosen (280 to 300 K, as in defaultSets() of site/js/app.js; distances are measured from 296 K)
WHO_BIN = 2
ROOM_K = (280, 300)
T_REF = 296
# names Windows keeps for devices: no file may be called this, whatever its extension
RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % i for i in range(1, 10)} | {'lpt%d' % i for i in range(1, 10)}

# MPI-Mainz files whose columns are not σ(λ): σ against temperature at one wavelength, fit parameters, dσ/dT
NOT_SIGMA = re.compile(r'\((?:T dependence|parameters|T-gradient)\)')
UPPER = re.compile(r'\(upper limits?\)')

# "Who absorbs here?": what a file name says about a dataset, for the choice of one dataset per species (pick_key).
# Line lists: integrated line intensities (cm² molecule⁻¹ cm⁻¹), which the atlas plots but must not rank as σ.
WHO_SKIP = re.compile(r'\(line intensities\)')
# Electron energy loss spectra, (e,e): σ derived from electron scattering, at a resolution far below an optical one.
EE = '(e,e)'
# Lists of band maxima, minima, shoulders or band heads: the points are separate measurements, not a spectrum.
PEAKS = re.compile(r'\((?:[^()]*,)?(?:max|min|peaks(?:-[^(),]*)?|band peaks|band heads)(?:,[^()]*)?\)')
# One isotopologue of the species, (15NH3), (33SO2), (16O18O), (O13CS): the tag is made of atoms with a mass number.
ISO = re.compile(r'\((?=[^()]*\d{2}[CNOS])((?:(?:\d{2})?[CNOSH]\d?)+)\)$')
# Points further apart than this around a wavelength (nm): the value there is an interpolation across a gap.
WIDE_NM = 5
# Values below this (cm²) are numerical underflow in the source files, not cross sections: left out of the tables.
FLOOR = 1e-40
COARSE_FLOOR = -4000                                  # the same floor as a coarse value, round(100 log10 σ)
# Structure around a laser line: where the largest σ among a dataset's points within SPREAD_NM of the line is at least
# SPREAD_MIN times the smallest, the value at the line depends on the resolution and on exactly where the line sits.
SPREAD_NM = 0.25
SPREAD_MIN = 2
SPREAD_TOP = 10000                                    # a larger ratio is written as this


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


def authors_short(a):
    """'Serdyuchenko et al.' from an author list: the first author's surname, and 'et al.' past two authors. The same
    as authorsShort() in site/js/xsec.js; the site's data check compares the two on every label in who.json."""
    names = [x.strip() for x in re.split(r',\s*(?:and\s+)?|\s+and\s+', str(a or ''))]
    names = [x for x in names if x]
    if not names:
        return ''

    def sur(x):
        if 'et al' in x:
            x = re.sub(r'\s*et al\.?', '', x, count=1)
        return re.split(r'\s+', x)[-1]
    if len(names) == 1:
        return sur(names[0]) + ' et al.' if 'et al' in names[0] else sur(names[0])
    if len(names) == 2:
        return sur(names[0]) + ' and ' + sur(names[1])
    return sur(names[0]) + ' et al.'


def ref_label(ref):
    """'Sander et al. (2011)': the short label of a dataset's reference (the fields reference() writes), as refLabel()
    in site/js/xsec.js: the authors, else the label made from the file name, else the start of the title."""
    t = ref.get('t') or ''
    a = authors_short(ref.get('a')) or ref.get('lab') or ((t[:50] + ('…' if len(t) > 50 else '')) if t else 'unknown')
    return '%s (%s)' % (a, ref['y']) if ref.get('y') else a


def t_rank(T):
    """(class, distance) of a dataset's temperature for the choice of one dataset per species: class 0 at room
    temperature (a value in ROOM_K, or a range that overlaps it), 1 when the source gives no temperature, 2 otherwise,
    with the distance from T_REF (0 for a range that contains it)."""
    if T is None:
        return (1, 0)
    lo, hi = (T[0], T[1]) if isinstance(T, list) else (T, T)
    if lo <= ROOM_K[1] and hi >= ROOM_K[0]:
        return (0, 0)
    return (2, 0 if lo <= T_REF <= hi else min(abs(lo - T_REF), abs(hi - T_REF)))


def is_points(row):
    """True for a dataset whose points are separate measurements: one or two points, or a list of band maxima."""
    return row['np'] < 3 or bool(PEAKS.search(row['id']))


def iso_tag(id_):
    """The isotopologue a file name ends in ('15NH3'), or ''."""
    m = ISO.search(id_)
    return m.group(1) if m else ''


def who_flags(row):
    """What who.json and coarse.json say of a dataset beside its label: 1 recommended, 2 upper limits, 4 electron
    energy loss, 8 a list of band maxima."""
    return (1 if row['rec'] else 0) + (2 if row.get('ul') else 0) + (4 if EE in row['id'] else 0) + (8 if PEAKS.search(row['id']) else 0)


def gap_at(xs, nm):
    """The distance in nm between the two points of sorted xs that bracket nm (0 at a point); None outside the data."""
    i = bisect.bisect_right(xs, nm)
    if i == 0 or (i == len(xs) and nm > xs[-1]):
        return None
    return 0.0 if xs[i - 1] == nm or i == len(xs) else xs[i] - xs[i - 1]


def gap_in(xs, lo, hi):
    """The widest step in nm between neighboring points of sorted xs among the steps that reach into lo to hi."""
    a = max(bisect.bisect_right(xs, lo) - 1, 0); b = min(bisect.bisect_left(xs, hi), len(xs) - 1)
    return max((xs[i + 1] - xs[i] for i in range(a, b)), default=0.0)


def spread_at(xs, ys, nm):
    """How far σ ranges close to a laser line: the largest over the smallest value among the points of the spectrum
    (xs sorted, ys) within SPREAD_NM of nm, rounded to a whole number (at most SPREAD_TOP); None where fewer than three
    points lie there or the ratio is below SPREAD_MIN. Values below FLOOR are underflow and do not count. The same
    arithmetic as spreadAt() in scripts/selftest.mjs."""
    v = [y for y in ys[bisect.bisect_left(xs, nm - SPREAD_NM):bisect.bisect_right(xs, nm + SPREAD_NM)] if y >= FLOOR]
    if len(v) < 3:
        return None
    r = max(v) / min(v)
    return min(int(math.floor(r + 0.5)), SPREAD_TOP) if r >= SPREAD_MIN else None


def is_wide(gap):
    """True when points that far apart (nm) count as a gap; a hair above WIDE_NM, so that a 5 nm grid is not one."""
    return gap is not None and gap > WIDE_NM + 1e-6


def pick_key(row, wide=False):
    """Sort key of a dataset (its index row) among those of one species that have a value at a wavelength; the smallest
    is the one "Who absorbs here?" shows. wide says that the dataset's points lie more than WIDE_NM apart around that
    wavelength. In order: measured values before upper limits; optical absorption before electron energy loss; points
    no more than WIDE_NM apart around the wavelength; a spectrum before a list of separate points (one or two points,
    or band maxima); the natural sample before a single isotopologue; room temperature, then no temperature given,
    then the temperature nearest 296 K; recommended by an evaluation; the most recent year; the most points in the
    source; and the id, so that the choice never depends on the order of the archive. The same rule as pickBefore()
    in scripts/selftest.mjs."""
    c, d = t_rank(row['T'])
    return (1 if row.get('ul') else 0, 1 if EE in row['id'] else 0, 1 if wide else 0, 1 if is_points(row) else 0, 1 if ISO.search(row['id']) else 0,
            c, d, 0 if row['rec'] else 1, -(row['y'] or 0), -row['n0'], row['id'])


def page_value(row, xs, ys, nm):
    """σ of one dataset at a laser line as the page's table gives it (tableValue() in site/js/xsec.js), from the
    points as shipped (xs, ys): (σ, None), or (σ, λ of the point) for a dataset of one or two points or a list of
    band maxima, whose nearest point within 1 nm is used; None where the dataset has no value. A thinned dataset gives the stored value of its
    full spectrum (row['at']). An interpolated value is kept to 8 figures, so that the four the page shows round as the
    table's own value does."""
    if is_points(row):
        i = min(range(len(xs)), key=lambda q: abs(xs[q] - nm))
        return (ys[i], xs[i]) if abs(xs[i] - nm) <= 1 else None
    if row['n0'] > row['np']:
        v = (row.get('at') or {}).get(js_key(nm))
        return (v, None) if v is not None else None
    v = interp(xs, ys, nm)
    return (float('%.8g' % v), None) if v is not None else None


def bin_means(xs, ys, w=WHO_BIN):
    """{bin number j: round(100 log10 of the mean σ over the bin)} for every bin [jw, (j+1)w] nm whose center lies inside
    the spectrum. The mean is the trapezoid integral of the linear interpolation over the part of the bin inside the
    data, divided by its width. The same arithmetic, step for step, as binMeans() in scripts/selftest.mjs."""
    out = {}
    for j in range(int(math.floor(xs[0] / w)), int(math.floor(xs[-1] / w)) + 1):
        c = (j + 0.5) * w
        if not (xs[0] <= c <= xs[-1]):
            continue
        lo = max(j * w, xs[0]); hi = min((j + 1) * w, xs[-1])
        if hi > lo:
            px = lo; py = interp(xs, ys, lo); area = 0.0
            for i in range(bisect.bisect_right(xs, lo), bisect.bisect_right(xs, hi)):
                area += 0.5 * (py + ys[i]) * (xs[i] - px); px = xs[i]; py = ys[i]
            area += 0.5 * (py + interp(xs, ys, hi)) * (hi - px)
            m = area / (hi - lo)
        else:
            m = interp(xs, ys, c)
        out[j] = int(math.floor(100 * math.log10(m) + 0.5))
    return out


def file_stems(keys):
    """A file name (without .json) for each species key, in order: the key itself, or the key with _2, _3, … when an
    earlier name differs from it only by case or when Windows keeps the name for a device."""
    taken = set(); out = []
    for k in keys:
        stem = k; n = 1
        while stem.lower() in taken or stem.lower() in RESERVED:
            n += 1; stem = '%s_%d' % (k, n)
        taken.add(stem.lower()); out.append(stem)
    return out


def dump(obj, path):
    """Write obj as compact JSON; returns the file's size in bytes."""
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
    return os.path.getsize(path)


def build(clean, out, built=None):
    """Write out/index.json, out/s/*.json, out/species.json, out/sp/*.json, out/who.json and out/coarse.json from the
    archive in clean; returns the summary line."""
    built = built or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    idx = read_json(os.path.join(clean, 'index.json'))
    rows = [r for r in idx['datasets'] if r.get('kind') == 'cross_section']
    species = {}; skipped = []; why = {}
    sdir = os.path.join(out, 's')
    os.makedirs(sdir, exist_ok=True)
    for f in os.listdir(sdir):                        # only the spectrum files this script writes
        if re.fullmatch(r'\d{5}\.json', f):
            os.remove(os.path.join(sdir, f))
    spdir = os.path.join(out, 'sp')
    os.makedirs(spdir, exist_ok=True)
    for f in os.listdir(spdir):                       # only the species files this script writes
        if f.endswith('.json'):
            os.remove(os.path.join(spdir, f))
    total = 0; nfile = 0
    at_line = {}; coarse = {}; picked = {}            # (species key, line) and (species key, bin) → the best dataset so far
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
        # "Who absorbs here?": this dataset's value at each laser line and in each coarse bin, kept where it is the
        # species' best dataset there (pick_key). Line lists are not σ and stay out; so do underflow values. The gap
        # between the points around a wavelength is that of the points as shipped, so that the site's check can work
        # the choice out again.
        sx = [p[0] for p in data]; sy = [p[1] for p in data]; points = is_points(row)
        for nm in LASER_NM if not WHO_SKIP.search(r['id']) else []:
            v = page_value(row, sx, sy, nm)
            if v is None or v[0] < FLOOR:
                continue
            gap = None if points else gap_at(sx, nm)
            key = pick_key(row, is_wide(gap))
            if (k, nm) not in at_line or key < at_line[(k, nm)][0]:
                at_line[(k, nm)] = (key, fid, v + ((float('%.3g' % gap),) if is_wide(gap) else ()), None if points else spread_at(sx, sy, nm))
        if not points and not WHO_SKIP.search(r['id']):
            # a thinned dataset: the mean of its full spectrum, with the wavelengths rounded as the page's are, so that
            # the bins it covers are those of the shipped points. Which bins count (the floor) is decided on the
            # shipped points, which the site's check has too; a full-spectrum mean below the floor is then written
            # as null, and the page shows no value there.
            thinned = len(data) < orig
            shipped = bin_means(sx, sy)
            for j, v in (bin_means([round(x, 4) for x in full_x], full_y) if thinned else shipped).items():
                if shipped.get(j, v) < COARSE_FLOOR:
                    continue
                if v < COARSE_FLOOR:
                    v = None
                wide = is_wide(gap_in(sx, max(j * WHO_BIN, sx[0]), min((j + 1) * WHO_BIN, sx[-1])))
                key = pick_key(row, wide)
                if (k, j) not in coarse or key < coarse[(k, j)][0]:
                    coarse[(k, j)] = (key, fid, v, wide)
        picked[fid] = [k, ref_label(row['ref']), row['T'], row['src'], who_flags(row)] + ([iso_tag(r['id'])] if iso_tag(r['id']) else [])
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
    # the same metadata in pieces: the species list, and one file per species
    splist = index['species']; nsets = sum(len(s['sets']) for s in splist)
    stems = file_stems([s['k'] for s in splist])
    slim = {'meta': {**{k: v for k, v in index['meta'].items() if k not in ('skipped', 'skipped_why')}, 'sets': nsets},
            'species': [[s['k'], s['f'], s['n'], s['cas'], len(s['sets'])] + ([stem] if stem != s['k'] else []) for s, stem in zip(splist, stems)]}
    n_slim = dump(slim, os.path.join(out, 'species.json'))
    n_sp = sum(dump(s, os.path.join(spdir, stem + '.json')) for s, stem in zip(splist, stems))
    # who.json: per laser line, [file number of the dataset, σ], then the wavelength of the point for a list of
    # separate points, or null and the gap in nm where the value is interpolated between points more than WIDE_NM
    # apart (else null), and after those the spread of σ close to the line where the spectrum is structured there
    # (spread_at); strongest first. coarse.json: runs of bins with the same dataset, [file number, first bin, values], and
    # a 1 after the values where the points are that far apart
    order = {s['k']: i for i, s in enumerate(splist)}
    at = {}; used = set()
    for nm in LASER_NM:
        rows_nm = sorted(((v[0], k, fid, v[1:], band) for (k, n), (_, fid, v, band) in at_line.items() if n == nm), key=lambda x: (-x[0], order[x[1]]))
        at[js_key(nm)] = [[fid, s] + ([None, rest[1] if len(rest) > 1 else None, band] if band is not None else
                                      list(rest) if len(rest) > 1 or rest[0] is not None else []) for s, _, fid, rest, band in rows_nm]
        used.update(x[2] for x in rows_nm)
    who = {'built': built, 'lines': [js_key(nm) for nm in LASER_NM], 'sets': {f: picked[f] for f in sorted(used)}, 'at': at}
    n_who = dump(who, os.path.join(out, 'who.json'))
    runs = []; used = set()
    for (k, j), (_, fid, v, wide) in sorted(coarse.items(), key=lambda x: (order[x[0][0]], x[0][1])):
        last = runs[-1] if runs else None
        if last and last[0] == fid and last[1] + len(last[2]) == j and (len(last) > 3) == wide:
            last[2].append(v)
        else:
            runs.append([fid, j, [v]] + ([1] if wide else []))
        used.add(fid)
    n_coarse = dump({'built': built, 'bin': WHO_BIN, 'sets': {f: picked[f] for f in sorted(used)}, 'runs': runs}, os.path.join(out, 'coarse.json'))
    return '%d species, %d datasets (%d skipped), spectra %.1f MB in %d files, index %.2f MB; species list %.1f kB, %d species files %.2f MB, who %.1f kB, coarse %.1f kB' % (
        len(species), nsets, len(skipped), total / 1e6, nfile,
        os.path.getsize(os.path.join(out, 'index.json')) / 1e6, n_slim / 1e3, len(splist), n_sp / 1e6, n_who / 1e3, n_coarse / 1e3)


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
