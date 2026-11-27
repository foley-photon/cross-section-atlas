"""How far the thinned spectra the page shows are from the archive's full spectra: at the laser lines, and in how they
cover the wavelength range.

    python scripts/thinning_check.py CLEAN_DIR DATA_DIR [--worst N]
    python scripts/thinning_check.py CLEAN_DIR DATA_DIR --gaps [--before OLD_DATA_DIR] [--worst N]

CLEAN_DIR is the archive's clean/ folder, DATA_DIR a data/ folder that scripts/build_data.py wrote from it. For every
dataset that was thinned (np < n0) and every laser line of the page (site/js/xsec.js LASER_LINES, and the 253.65 nm
mercury line) inside its range, σ is interpolated linearly in the full spectrum and in the thinned one, and the
relative difference is reported: percentiles, the share above 1 % and 10 %, and the worst cases. This is the error of
the plotted curve; at the laser lines the page's table uses the full-resolution values build_data.py stores (meta "at").

--gaps scans every dataset instead: the widest gap between two neighboring points as shipped, and for a thinned
dataset how much wider that is than the widest gap of the full spectrum over the same stretch (the excess: a gap the
thinning made, where the source has points). It lists the largest excesses, and with --before (a data folder built
earlier, from the same archive) the same for that folder and the datasets whose widest gap shrank by more than 5 nm or
20 %. The thinning keeps two cells of its log-λ grid as the bound (build_data.thin_buckets); the line "over the bound"
counts the datasets that break it. Standard library only.
"""
import argparse, bisect, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_data import LASER_NM, THIN_PER_CELL, interp, read_json  # noqa: E402

LINES = sorted(LASER_NM + [253.65])


def full_spectrum(clean, path):
    """The archive's points as scripts/build_data.py reads them (finite, σ > 0, sorted), before thinning."""
    out = []
    for p in read_json(os.path.join(clean, path))['data']:
        if len(p) < 2 or p[0] is None or p[1] is None:
            continue
        x, y = float(p[0]), float(p[1])
        if math.isfinite(x) and math.isfinite(y) and y > 0:
            out.append((x, y))
    return sorted(out)


def check(clean, data):
    rows = {r['id']: r for r in read_json(os.path.join(clean, 'index.json'))['datasets']}
    index = read_json(os.path.join(data, 'index.json'))
    out = []
    for sp in index['species']:
        for x in sp['sets']:
            if x['n0'] <= x['np']:
                continue
            o = full_spectrum(clean, rows[x['id']]['path'])
            s = read_json(os.path.join(data, 's', x['f'] + '.json'))
            ox, oy = [p[0] for p in o], [p[1] for p in o]
            sx, sy = [p[0] for p in s], [p[1] for p in s]
            for line in LINES:
                a, b = interp(ox, oy, line), interp(sx, sy, line)
                if a and b is not None:
                    out.append((abs(b / a - 1), x['id'], line, a, b, x['n0'], x['np']))
    return out


def widest(xs):
    """The widest gap between neighboring wavelengths of xs, and where: (gap, low end, high end)."""
    return max(((b - a, a, b) for a, b in zip(xs, xs[1:])), default=(0.0, None, None))


def excess(full, kept, np_):
    """How much wider the gaps between neighboring kept wavelengths are than the widest gap of the full spectrum (sorted
    wavelengths) over the same stretch: (worst excess, low end, high end, widest full gap there, bound there, whether
    any gap breaks the bound). The bound is two cells of the thinning's log-λ grid at the high end (thin_buckets), with
    1e-3 nm to spare for the wavelengths rounded to 4 decimals."""
    lo, hi = kept[0], kept[-1]
    cell = math.log(hi / lo) / max(1, np_ // THIN_PER_CELL) if 0 < lo < hi else 0.0
    worst = (0.0, None, None, 0.0, 0.0); over = False
    for a, b in zip(kept, kept[1:]):
        i = bisect.bisect_left(full, a - 6e-5); j = bisect.bisect_right(full, b + 6e-5) - 1
        raw = max((full[t + 1] - full[t] for t in range(i, j)), default=0.0)
        e = (b - a) - raw; bound = 2 * b * cell
        if e > worst[0]:
            worst = (e, a, b, raw, bound)
        if e > bound + 1e-3:
            over = True
    return worst + (over,)


def gaps(clean, data, before=None):
    """For every dataset of the data folder (and of the one built before, by dataset id): its widest gap as shipped, and
    for a thinned dataset the excess over the full spectrum (excess()). Returns [(id, now, before)], each a dict or None."""
    rows = {r['id']: r for r in read_json(os.path.join(clean, 'index.json'))['datasets']}
    sets = lambda d: {x['id']: x for sp in read_json(os.path.join(d, 'index.json'))['species'] for x in sp['sets']}
    now = sets(data); old = sets(before) if before else {}
    out = []
    for id_, x in now.items():
        full = None; res = []
        for d, m in ((data, x), (before, old.get(id_))):
            if m is None:
                res.append(None); continue
            s = [p[0] for p in read_json(os.path.join(d, 's', m['f'] + '.json'))]
            g = {'np': m['np'], 'n0': m['n0'], 'gap': widest(s), 'excess': None}
            if m['n0'] > m['np']:
                if full is None:
                    full = [p[0] for p in full_spectrum(clean, rows[id_]['path'])]
                g['excess'] = excess(full, s, m['np'])
            res.append(g)
        out.append((id_, res[0], res[1]))
    return out


def report_gaps(res, worst, before):
    """Print what gaps() found."""
    def top(k, label):
        th = [(x[k + 1]['excess'], x[0], x[k + 1]) for x in res if x[k + 1] and x[k + 1]['excess']]
        print(f'{label}: {sum(1 for x in res if x[k + 1])} datasets, {len(th)} thinned, {sum(1 for e, _, _ in th if e[5])} with a gap over the bound')
        for e, i, g in sorted(th, key=lambda t: -t[0][0])[:worst]:
            print(f'  {i}: kept points {e[1]:g} to {e[2]:g} nm, {e[2] - e[1]:.3g} nm apart where the source is at most {e[3]:.3g} nm apart '
                  f'(excess {e[0]:.3g} nm, bound {e[4]:.3g} nm; {g["np"]} of {g["n0"]} points)')
    top(0, 'now')
    if not before:
        return
    top(1, 'before')
    both = [(i, a, b) for i, a, b in res if a and b]
    for word, sign in (('shrank', 1), ('grew', -1)):
        ch = [(sign * (b['gap'][0] - a['gap'][0]), i, a, b) for i, a, b in both]
        ch = [c for c in ch if c[0] > 5 or c[0] > 0.2 * c[3]['gap'][0]]
        print(f'widest gap {word} by more than 5 nm or 20 %: {len(ch)} datasets')
        for d, i, a, b in sorted(ch, key=lambda c: -c[0])[:worst]:
            print(f'  {i}: {b["gap"][0]:.4g} nm ({b["gap"][1]:g} to {b["gap"][2]:g}) before, {a["gap"][0]:.4g} nm ({a["gap"][1]:g} to {a["gap"][2]:g}) now; '
                  f'{b["np"]} -> {a["np"]} of {a["n0"]} points')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('clean'); ap.add_argument('data'); ap.add_argument('--worst', type=int, default=12)
    ap.add_argument('--gaps', action='store_true', help='check how the thinned spectra cover their range, for every dataset')
    ap.add_argument('--before', help='with --gaps: a data folder built earlier, to compare with')
    a = ap.parse_args(argv)
    if a.gaps:
        res = gaps(a.clean, a.data, a.before)
        report_gaps(res, a.worst, a.before)
        return 1 if any(x[1] and x[1]['excess'] and x[1]['excess'][5] for x in res) else 0
    res = check(a.clean, a.data)
    if not res:
        print('no thinned dataset covers a laser line'); return 0
    e = sorted(r[0] for r in res)
    pct = lambda q: e[min(len(e) - 1, int(round(q / 100 * (len(e) - 1))))]
    print(f'{len(res)} pairs of a thinned dataset and a laser line in its range')
    print('relative difference: ' + ', '.join(f'p{q} {pct(q):.2%}' for q in (50, 90, 95, 99)))
    print(f'above 1 %: {sum(x > 0.01 for x in e) / len(e):.1%}; above 10 %: {sum(x > 0.1 for x in e) / len(e):.1%}')
    for r in sorted(res, reverse=True)[:a.worst]:
        print(f'{r[1]} at {r[2]} nm: full {r[3]:.4g}, thinned {r[4]:.4g} cm² ({r[4] / r[3]:.3g}x; {r[6]} of {r[5]} points kept)')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
