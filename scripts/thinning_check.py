"""How far the thinned spectra the page shows are from the archive's full spectra at the laser lines.

    python scripts/thinning_check.py CLEAN_DIR DATA_DIR [--worst N]

CLEAN_DIR is the archive's clean/ folder, DATA_DIR a data/ folder that scripts/build_data.py wrote from it. For every
dataset that was thinned (np < n0) and every laser line of the page (site/js/xsec.js LASER_LINES, and the 253.65 nm
mercury line) inside its range, σ is interpolated linearly in the full spectrum and in the thinned one, and the
relative difference is reported: percentiles, the share above 1 % and 10 %, and the worst cases. This is the error of
the plotted curve; at the laser lines the page's table uses the full-resolution values build_data.py stores (meta "at").
Standard library only.
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_data import LASER_NM, interp, read_json  # noqa: E402

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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('clean'); ap.add_argument('data'); ap.add_argument('--worst', type=int, default=12)
    a = ap.parse_args(argv)
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
