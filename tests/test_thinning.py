"""Tests of the thinning in scripts/build_data.py (resample, thin_buckets, max_points): a thinned spectrum covers the
whole range where its source has data, and keeps the band peaks and the valleys between them everywhere.

The case that broke it: the Leiden CO table (Heays et al. 2017) has 840 722 points, all but about 700 of them in a
line-resolved stretch from 90.8 to 108.7 nm. Buckets of equal point count gave that stretch all 2000 kept points but
one, and the plot drew a straight line from 108.7 to 166.6 nm, over the B ← X band at 115 nm and the A ← X bands from
130 to 155 nm. The synthetic case below has the same shape. With the archive at hand, the real file is tested too:

    XSEC_CLEAN=<archive>/clean python -m unittest discover -s tests -v

(the test is skipped without it; the data are not part of this repository). Standard library only.
"""
import bisect, math, os, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import build_data as B  # noqa: E402


def gap_excess(raw_x, kept_x, mx):
    """For each pair of neighboring kept points: (b - a) - (the widest gap of the raw data between a and b), and the
    bound the thinning promises for it, two cell widths at b (the cells are 1/(mx // 4) of the range in log λ).
    Returns the pairs that break the bound, as (excess, a, b, bound)."""
    span = math.log(raw_x[-1] / raw_x[0]) / max(1, mx // B.THIN_PER_CELL)
    bad = []
    for a, b in zip(kept_x, kept_x[1:]):
        i = bisect.bisect_left(raw_x, a); j = bisect.bisect_left(raw_x, b)
        raw = max((raw_x[t + 1] - raw_x[t] for t in range(i, j)), default=0.0)
        bound = 2 * b * span + 1e-9
        if (b - a) - raw > bound:
            bad.append(((b - a) - raw, a, b, bound))
    return bad


def co_like(dense=120000):
    """A spectrum shaped like the Leiden CO table: a smooth stretch of 161 points from 10 to 90 nm, a line-resolved
    stretch of `dense` points from 90.8 to 108.7 nm (lines 0.02 nm apart, σ from 1e-19 to 1e-16 cm²), and 0.25 nm
    steps from 108.75 to 166.5 nm with Gaussian bands at 115 nm and every 3 nm from 130 to 154 nm on a floor of
    1e-21 cm². Returns the points and the wavelengths of the band maxima of the sparse stretch."""
    d = [[10 + 0.5 * i, 1e-17 * (1 + 0.5 * math.sin(i / 9))] for i in range(161)]
    h = (108.7 - 90.8) / (dense - 1)
    for i in range(dense):
        x = 90.8 + i * h
        d.append([x, 1e-19 + 1e-16 * math.sin(math.pi * x / 0.02) ** 8])
    centers = [115.0] + [130.0 + 3 * k for k in range(9)]
    sparse = [108.75 + 0.25 * i for i in range(232)]
    for x in sparse:
        d.append([x, 1e-21 + sum(1.5e-17 * math.exp(-((x - c) / 0.4) ** 2 / 2) for c in centers)])
    peaks = [min(sparse, key=lambda x: abs(x - c)) for c in centers]
    return d, peaks


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d, cls.peaks = co_like()
        cls.xs = [p[0] for p in cls.d]
        cls.k = B.resample(cls.d, 2000)

    def test_length_and_order(self):
        self.assertEqual(len(self.k), 2000)
        self.assertEqual((self.k[0], self.k[-1]), (self.d[0], self.d[-1]))
        self.assertTrue(all(b[0] >= a[0] for a, b in zip(self.k, self.k[1:])))

    def test_no_gap_where_the_source_has_points(self):
        bad = gap_excess(self.xs, [p[0] for p in self.k], 2000)
        self.assertEqual(bad, [], 'kept points further apart than the data gaps plus two cells')
        # the widest gap of the kept points, where the source has a point every 0.5 nm or closer, is under 1.5 nm
        self.assertLess(max(b[0] - a[0] for a, b in zip(self.k, self.k[1:])), 1.5)

    def test_sparse_bands_kept(self):
        kept = {p[0] for p in self.k}
        for x in self.peaks:
            self.assertIn(x, kept, 'the band maximum at %g nm' % x)
        # the sparse stretches cost little and are kept nearly whole (a cell that also holds dense points can lose one)
        self.assertGreaterEqual(sum(1 for p in self.k if p[0] > 108.72), sum(1 for p in self.d if p[0] > 108.72) - 2)
        self.assertGreaterEqual(sum(1 for p in self.k if p[0] < 90.5), sum(1 for p in self.d if p[0] < 90.5) - 2)

    def test_dense_stretch_keeps_peaks_and_valleys(self):
        # in every 0.5 nm of the line-resolved stretch, the kept points reach within a factor of 2 of the largest σ
        # and of the smallest (the valleys between the lines matter on a log axis)
        for w in range(182, 216):
            lo, hi = w * 0.5, w * 0.5 + 0.5
            raw = [p[1] for p in self.d if lo <= p[0] < hi]; kept = [p[1] for p in self.k if lo <= p[0] < hi]
            self.assertTrue(kept, '%g-%g nm' % (lo, hi))
            self.assertGreater(max(kept), max(raw) / 2, '%g-%g nm: peaks' % (lo, hi))
            self.assertLess(min(kept), min(raw) * 2, '%g-%g nm: valleys' % (lo, hi))

    def test_buckets(self):
        b = B.thin_buckets(self.xs, 2000)
        self.assertEqual(len(b), 1998)
        self.assertEqual((b[0][0], b[-1][1]), (1, len(self.xs) - 1))
        self.assertTrue(all(s < e for s, e in b) and all(p[1] == q[0] for p, q in zip(b, b[1:])), 'buckets tile the inside points')

    def test_uniform_spectrum_as_before(self):
        # a spectrum on an even grid over a narrow range: the cells hold about as many points each, so the buckets are
        # about as wide as before (5 points for 10 000 to 2000; at most 8) and the narrow spike survives
        d = [[200 + i * 0.01, 1e-18 * (1.5 + math.sin(i / 50))] for i in range(10000)]
        d[6543][1] = 4e-17
        k = B.resample(d, 2000)
        self.assertIn(d[6543], k)
        self.assertLessEqual(max(e - s for s, e in B.thin_buckets([p[0] for p in d], 2000)), 8)
        kx = [p[0] for p in k]; ky = [p[1] for p in k]
        worst = max(abs(B.interp(kx, ky, x) / y - 1) for i, (x, y) in enumerate(d) if abs(i - 6543) > 12)
        self.assertLess(worst, 0.01)

    def test_max_points(self):
        self.assertEqual([B.max_points(n) for n in (100, 2001, 50000, 50001, 200000, 3626767)], [2000, 2000, 2000, 2000, 4000, 5000])


@unittest.skipUnless(os.environ.get('XSEC_CLEAN') and os.path.isfile(os.path.join(os.environ.get('XSEC_CLEAN', ''), 'index.json')),
                     'set XSEC_CLEAN to the archive\'s clean/ folder to test the Leiden CO table')
class LeidenCO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clean = os.environ['XSEC_CLEAN']
        row = next(r for r in B.read_json(os.path.join(clean, 'index.json'))['datasets'] if r['id'] == 'leiden:CO')
        cls.d = B.clean_points(B.read_json(os.path.join(clean, row['path']))['data'])
        cls.xs = [p[0] for p in cls.d]

    def check(self, mx):
        k = B.resample(self.d, mx)
        kx = [p[0] for p in k]
        self.assertEqual(len(k), mx)
        self.assertEqual(gap_excess(self.xs, kx, mx), [])
        # the source has a point at least every 1.6 nm from 6.2 to 166.6 nm: the kept ones are never 3 nm apart
        self.assertLess(max(b - a for a, b in zip(kx, kx[1:])), 3)
        # B ← X near 115 nm: the maximum of the table there (1.3e-17 cm² at 115.03 nm) is kept, and so are nearly all the
        # points of the A ← X bands from 130 to 155 nm
        top = max((p for p in self.d if 114 < p[0] < 116), key=lambda p: p[1])
        self.assertIn(top, k)
        raw = sum(1 for x in self.xs if 130 <= x <= 155); kept = sum(1 for x in kx if 130 <= x <= 155)
        self.assertGreaterEqual(kept, 0.9 * raw, '%d of %d points from 130 to 155 nm' % (kept, raw))

    def test_2000(self):
        self.check(2000)

    def test_as_built(self):
        self.assertEqual(B.max_points(len(self.d)), 5000)
        self.check(B.max_points(len(self.d)))


if __name__ == '__main__':
    unittest.main()
