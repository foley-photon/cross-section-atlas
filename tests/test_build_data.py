"""Tests of scripts/build_data.py on a small synthetic archive written to a temporary folder: which datasets are kept
and which skipped, cleaning, thinning to MAX_POINTS, rounding, species merging, the index fields the page reads, the
split files (species list, one file per species, the "Who absorbs here?" tables and the rule that picks one dataset per
species), a rebuild that gives the same bytes, and the output passing the site's data checks (scripts/selftest.mjs),
which work the split files out again in JavaScript. One test
compares the thinning with resample() in site/js/xsec.js point for point. The Node tests need Node on the PATH and are
skipped without it. Standard library only.

    python -m unittest discover -s tests -v
"""
import json, math, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import build_data as B  # noqa: E402

NODE = shutil.which('node')


def row(id_, species, data, **kw):
    """One dataset of the archive: its index row and its file."""
    r = {'id': id_, 'species': species, 'species_canonical': kw.pop('canonical', species), 'name': kw.pop('name', ''), 'cas': kw.pop('cas', None),
         'source': kw.pop('source', 'mainz2013'), 'path': f'xs/test/{id_.replace(":", "_")}.json', 'T_K': kw.pop('T', 298.0),
         'units': kw.pop('units', 'cm2/molecule'), 'kind': kw.pop('kind', 'cross_section'), 'lambda_medium': kw.pop('med', 'unknown'),
         'recommended': kw.pop('rec', False), 'notes': kw.pop('notes', None),
         'reference': kw.pop('ref', {'authors': 'A. Author and B. Author', 'year': 1999, 'title': 'A synthetic spectrum', 'journal': 'J. Test 1, 1 (1999)', 'doi': None})}
    assert not kw, kw
    return r, data


def wavy(n, a=200.0, h=0.01):
    """n points of a smooth positive spectrum, a spike at n//3."""
    d = [[a + i * h, 1e-18 * (1.5 + math.sin(i / 37))] for i in range(n)]
    d[n // 3][1] = 5e-17
    return d


def write_archive(clean, rows):
    os.makedirs(os.path.join(clean, 'xs', 'test'), exist_ok=True)
    for r, data in rows:
        with open(os.path.join(clean, r['path']), 'w', encoding='utf-8') as f:
            json.dump({**r, 'data': data}, f)
    with open(os.path.join(clean, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump({'schema': 'one row per dataset', 'date': '2026-11-07', 'datasets': [r for r, _ in rows]}, f)


ROWS = [
    row('mainz2013:O3_big', 'O3', wavy(5000), name='ozone', cas='10028-15-6'),
    row('bremen:O3_small', 'O3', [[250.0, 1.1e-17], [260.0, 1.2e-17], [255.0, 1.15e-17]], source='bremen', T=[290, 300], med='vacuum'),
    row('mainz2013:HCHO_a', 'HCHO', [[300.12346, 3.123456e-20], [301.0, None], [302.0, float('nan')], [303.0, -1e-21], [304.0, 0.0], [305.0, 2e-20]],
        canonical='CH2O', name='formaldehyde', ref={'authors': 'C. Author', 'year': '2001', 'title': 't', 'journal': None, 'doi': '10.1/x'}),
    row('tuvx:H2CO_b', 'H2CO', [[310.0, 1e-20], [320.0, 2e-20]], canonical='CH2O', source='tuvx', cas='50-00-0', rec=True, T=None),
    row('mainz2013:ClNO2_rel', 'ClNO2', [[300.0, 1.0], [310.0, 0.5]], units='relative'),
    row('mainz2013:NO2_bad', 'NO2', [[300.0, 1e-19], [310.0, 2e-19]], notes='QA FLAG: values about 25x too large'),
    row('mainz2013:X_empty', 'X', [[300.0, -1.0], [310.0, 0.0]]),
    row('mainz2013:O3_qy', 'O3', [[300.0, 0.9], [310.0, 0.8]], kind='quantum_yield', units='dimensionless'),
    row('cfa:CH3C(O)OONO2', 'CH3C(O)OONO2', [[200.0, 1e-18]], source='cfa'),
]


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='xs-build-')
        cls.clean = os.path.join(cls.tmp, 'clean'); cls.out = os.path.join(cls.tmp, 'data')
        write_archive(cls.clean, ROWS)
        os.makedirs(os.path.join(cls.out, 's'))
        Path(cls.out, 's', '00099.json').write_text('[]')          # a spectrum file of an earlier build
        Path(cls.out, 's', 'keep.txt').write_text('not mine')       # anything else is left alone
        cls.summary = B.build(cls.clean, cls.out, built='2026-11-11')
        cls.index = json.loads(Path(cls.out, 'index.json').read_text(encoding='utf-8'))
        cls.sets = {x['id']: x for s in cls.index['species'] for x in s['sets']}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def spectrum(self, id_):
        return json.loads(Path(self.out, 's', self.sets[id_]['f'] + '.json').read_text())

    def test_kept_and_skipped(self):
        self.assertEqual(sorted(self.sets), ['bremen:O3_small', 'cfa:CH3C(O)OONO2', 'mainz2013:HCHO_a', 'mainz2013:O3_big', 'tuvx:H2CO_b'])
        self.assertEqual(self.index['meta']['skipped'], ['mainz2013:ClNO2_rel', 'mainz2013:NO2_bad', 'mainz2013:X_empty'])
        self.assertEqual(self.index['meta']['skipped_why'], {'mainz2013:ClNO2_rel': 'units are not cm2/molecule',
                                                             'mainz2013:NO2_bad': 'flagged by the archive checks', 'mainz2013:X_empty': 'no point left'})
        size = lambda *f: os.path.getsize(os.path.join(self.out, *f))
        self.assertEqual(self.summary, '3 species, 5 datasets (3 skipped), spectra %.1f MB in 5 files, index %.2f MB; '
                         'species list %.1f kB, 3 species files %.2f MB, who %.1f kB, coarse %.1f kB' % (
            sum(size('s', '%05d.json' % i) for i in range(1, 6)) / 1e6, size('index.json') / 1e6, size('species.json') / 1e3,
            sum(size('sp', f) for f in os.listdir(os.path.join(self.out, 'sp'))) / 1e6, size('who.json') / 1e3, size('coarse.json') / 1e3))

    def test_meta(self):
        m = self.index['meta']
        self.assertEqual((m['built'], m['archive'], m['max_points']), ('2026-11-11', '2026-11-07', 2000))
        self.assertEqual(sorted(m['sources']), ['bremen', 'cfa', 'mainz2013', 'tuvx'])
        self.assertEqual(m['sources']['mainz2013']['license'], 'CC BY 4.0 (Zenodo record).')

    def test_thinning(self):
        x = self.sets['mainz2013:O3_big']; d = self.spectrum('mainz2013:O3_big')
        self.assertEqual((x['np'], x['n0'], len(d)), (2000, 5000, 2000))
        self.assertEqual(d[0], [200.0, 1.5e-18])                                       # the first point
        self.assertEqual(d[-1][0], round(200 + 4999 * 0.01, 4))
        self.assertIn([round(200 + (5000 // 3) * 0.01, 4), 5e-17], d, 'the spike survives')
        self.assertEqual(x['l'], [200.0, 249.99])

    def test_full_resolution_values_at_the_laser_lines(self):
        # stored for the thinned dataset only: σ of the full spectrum (linear interpolation) at each line in its range
        x = self.sets['mainz2013:O3_big']
        full = [p for p in wavy(5000)]
        xs = [p[0] for p in full]; ys = [p[1] for p in full]
        self.assertEqual(sorted(x['at'], key=float), ['212.8', '222', '248.4'])
        for k, v in x['at'].items():
            self.assertEqual(v, B.sig(B.interp(xs, ys, float(k))), k)
        self.assertNotIn('at', self.sets['bremen:O3_small'])

    def test_cleaning_sorting_rounding(self):
        self.assertEqual(self.spectrum('bremen:O3_small'), [[250.0, 1.1e-17], [255.0, 1.15e-17], [260.0, 1.2e-17]])
        # None, NaN, negative and zero σ dropped; σ to 5 significant figures, λ to 1e-4 nm
        self.assertEqual(self.spectrum('mainz2013:HCHO_a'), [[300.1235, 3.1235e-20], [305.0, 2e-20]])
        h = self.sets['mainz2013:HCHO_a']
        self.assertEqual((h['np'], h['n0'], h['l']), (2, 2, [300.12, 305.0]))

    def test_species_and_fields(self):
        sp = {s['k']: s for s in self.index['species']}
        self.assertEqual(list(sp), ['CH2O', 'O3', 'CH3C_O_OONO2'], 'most datasets first, then by formula')
        self.assertEqual((sp['CH2O']['f'], sp['CH2O']['n'], sp['CH2O']['cas']), ('CH2O', 'formaldehyde', '50-00-0'))
        self.assertEqual([x['id'] for x in sp['CH2O']['sets']], ['mainz2013:HCHO_a', 'tuvx:H2CO_b'])
        b = self.sets['tuvx:H2CO_b']
        self.assertEqual((b['T'], b['rec'], b['med'], b['src']), (None, True, 'unknown', 'tuvx'))
        self.assertEqual(self.sets['bremen:O3_small']['T'], [290, 300])
        self.assertEqual(self.sets['bremen:O3_small']['med'], 'vacuum')
        h = self.sets['mainz2013:HCHO_a']
        self.assertEqual(h['ref'], {'a': 'C. Author', 'y': '2001', 't': 't', 'j': '', 'doi': '10.1/x'})
        self.assertEqual(h['y'], 2001, 'a year given as text becomes a number')
        self.assertEqual(sorted(x['f'] for x in self.sets.values()), ['00001', '00002', '00003', '00004', '00005'])

    def test_old_files(self):
        self.assertFalse(Path(self.out, 's', '00099.json').exists(), 'a spectrum of an earlier build is removed')
        self.assertTrue(Path(self.out, 's', 'keep.txt').exists(), 'other files are left alone')

    def test_rebuild_gives_the_same_bytes(self):
        out2 = os.path.join(self.tmp, 'data2')
        B.build(self.clean, out2, built='2026-11-11')
        for f in ['index.json', 'species.json', 'who.json', 'coarse.json'] + ['s/%05d.json' % i for i in range(1, 6)] + ['sp/%s.json' % k for k in ('CH2O', 'O3', 'CH3C_O_OONO2')]:
            self.assertEqual(Path(self.out, f).read_bytes(), Path(out2, f).read_bytes(), f)

    def test_index_json_is_what_it_was_before_the_split(self):
        # the page up to 1.0.4 reads only index.json: its fields and their order are unchanged
        self.assertEqual(list(self.index), ['meta', 'species'])
        self.assertEqual(list(self.index['meta']), ['built', 'archive', 'max_points', 'sources', 'skipped', 'skipped_why'])
        self.assertEqual(list(self.index['species'][0]), ['k', 'f', 'n', 'cas', 'sets'])
        self.assertEqual(list(self.sets['mainz2013:O3_big']), ['id', 'f', 'src', 'T', 'l', 'np', 'n0', 'rec', 'med', 'res', 'ref', 'y', 'note', 'at'])
        self.assertEqual(list(self.sets['bremen:O3_small']), ['id', 'f', 'src', 'T', 'l', 'np', 'n0', 'rec', 'med', 'res', 'ref', 'y', 'note'])

    def test_species_list_and_species_files(self):
        slim = json.loads(Path(self.out, 'species.json').read_text(encoding='utf-8'))
        self.assertEqual(slim['species'], [['CH2O', 'CH2O', 'formaldehyde', '50-00-0', 2], ['O3', 'O3', 'ozone', '10028-15-6', 2], ['CH3C_O_OONO2', 'CH3C(O)OONO2', '', '', 1]])
        m = dict(self.index['meta']); del m['skipped'], m['skipped_why']; m['sets'] = 5
        self.assertEqual(slim['meta'], m)
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, 'sp'))), ['CH2O.json', 'CH3C_O_OONO2.json', 'O3.json'])
        for s in self.index['species']:
            self.assertEqual(json.loads(Path(self.out, 'sp', s['k'] + '.json').read_text(encoding='utf-8')), s)

    def test_who_at_the_laser_lines(self):
        who = json.loads(Path(self.out, 'who.json').read_text(encoding='utf-8'))
        self.assertEqual(who['lines'], [B.js_key(x) for x in B.LASER_NM])
        self.assertEqual(who['built'], '2026-11-11')
        big = self.sets['mainz2013:O3_big']; small = self.sets['bremen:O3_small']
        # 248.4 nm: of the two ozone datasets only the 5000-point spectrum (200 to 249.99 nm) reaches it; it is thinned,
        # so the value is the stored one of its full spectrum
        # (the synthetic spectrum swings by a factor of 2 within 0.25 nm, which the row carries after two nulls)
        self.assertEqual(who['at']['248.4'], [[big['f'], big['at']['248.4'], None, None, 2]])
        self.assertEqual(who['at']['212.8'], [[big['f'], big['at']['212.8'], None, None, 2]])
        self.assertEqual(who['sets'][big['f']], ['O3', 'Author and Author (1999)', 298.0, 'mainz2013', 0])
        # 308 nm: formaldehyde's two-point file reaches from 300.12 to 305 nm, so its nearest point is 3 nm away: no value;
        # the TUV-x file (310 and 320 nm) does not reach 308 nm either
        self.assertEqual(who['at']['308'], [])
        self.assertNotIn(small['f'], who['sets'], 'only the datasets that stand for a species are named')

    def test_coarse_bins(self):
        c = json.loads(Path(self.out, 'coarse.json').read_text(encoding='utf-8'))
        self.assertEqual(c['bin'], 2)
        big = self.sets['mainz2013:O3_big']
        small = self.sets['bremen:O3_small']
        # ozone's 5000-point spectrum over 200 to 249.99 nm has the bin centers 201 to 249 (bins 100 to 124), its three
        # points over 250 to 260 nm the centers 251 to 259 (bins 125 to 129). Formaldehyde and the others have fewer than
        # three points: no coarse values
        self.assertEqual([(r[0], r[1], len(r[2])) for r in c['runs']], [(big['f'], 100, 25), (small['f'], 125, 5)])
        # 250 to 252 nm on the line from 1.1e-17 at 250 nm to 1.15e-17 at 255 nm: the mean is 1.11e-17, round(100 × -16.9547)
        self.assertEqual(c['runs'][1][2][0], -1695)
        # the mean of the full spectrum over 200 to 202 nm, by the trapezoid rule on its 201 points
        d = wavy(5000)[:201]
        mean = sum(0.5 * (d[i][1] + d[i + 1][1]) * (round(d[i + 1][0], 4) - round(d[i][0], 4)) for i in range(200)) / 2
        self.assertEqual(c['runs'][0][2][0], math.floor(100 * math.log10(mean) + 0.5))
        self.assertEqual(sorted(c['sets']), sorted([big['f'], small['f']]))

    def test_archive_date(self):
        self.assertEqual(B.archive_date({'schema': 'x', 'date': '2026-11-07'}), '2026-11-07')
        self.assertEqual(B.archive_date({'schema': 'one row', 'made': '2026-11-07', 'n': 3}), '2026-11-07', 'the 2026-11-07 archive')
        self.assertEqual(B.archive_date({'schema': 'x'}), '')

    def test_licenses_as_the_sources_state_them(self):
        s = B.SOURCES
        self.assertEqual(s['bremen']['license'], 'No license stated; the files ask that the paper be cited.')
        self.assertEqual(s['cfa']['license'], 'No license stated; cite the publications.')
        self.assertTrue(all('research use' not in v['license'] for v in s.values()))

    def test_who_helpers(self):
        self.assertEqual(B.authors_short('A. Serdyuchenko, V. Gorshelev, M. Weber, W. Chehade, and J. P. Burrows'), 'Serdyuchenko et al.')
        self.assertEqual(B.authors_short('L.T Molina and M.J. Molina'), 'Molina and Molina')
        self.assertEqual(B.authors_short('S.P. Sander et al.'), 'Sander et al.')
        self.assertEqual(B.authors_short(None), '')
        self.assertEqual(B.ref_label({'a': '', 'y': 2026, 'lab': 'Xx steps'}), 'Xx steps (2026)')
        self.assertEqual(B.ref_label({'a': '', 'y': '', 't': 'A title that runs on for rather more than fifty characters in all'}), 'A title that runs on for rather more than fifty ch…')
        self.assertEqual(B.ref_label({'a': '', 'y': ''}), 'unknown')
        self.assertEqual([B.t_rank(T) for T in (298.0, 280, [250, 285], None, 301, 273, [200, 250], [100, 400])], [(0, 0), (0, 0), (0, 0), (1, 0), (2, 5), (2, 23), (2, 46), (0, 0)])
        self.assertEqual(B.file_stems(['CO', 'O3', 'Co', 'co', 'Co_2', 'NUL', 'C2H5O2+']), ['CO', 'O3', 'Co_2', 'co_3', 'Co_2_2', 'NUL_2', 'C2H5O2+'])
        # bin means: a ramp from 1e-20 at 200 nm to 3e-20 at 202 nm averages 2e-20; a step at a bin edge belongs to the next bin
        self.assertEqual(B.bin_means([200.0, 201.0, 202.0], [1e-20, 2e-20, 3e-20]), {100: -1970})
        self.assertEqual(B.bin_means([200.0, 202.0, 202.0, 204.0], [1e-20, 1e-20, 4e-20, 4e-20]), {100: -2000, 101: -1940})
        self.assertEqual(B.bin_means([199.0, 202.0, 205.0], [1e-20] * 3), {99: -2000, 100: -2000, 101: -2000, 102: -2000})
        self.assertEqual(B.bin_means([200.0, 200.4, 200.8], [1e-20] * 3), {})
        # the value at a line as the page's table gives it
        row = {'np': 3, 'n0': 3, 'id': 'a'}
        self.assertEqual(B.page_value(row, [240.0, 250.0, 260.0], [1e-18, 2e-18, 4e-18], 248.4), (1.84e-18, None))
        self.assertIsNone(B.page_value(row, [240.0, 250.0, 260.0], [1e-18, 2e-18, 4e-18], 266))
        self.assertEqual(B.page_value({'np': 1, 'n0': 1, 'id': 'a'}, [193.0], [5e-19], 193.3), (5e-19, 193.0), 'a single point within 1 nm')
        self.assertIsNone(B.page_value({'np': 1, 'n0': 1, 'id': 'a'}, [192.0], [5e-19], 193.3))
        self.assertEqual(B.page_value({'np': 2000, 'n0': 9000, 'id': 'a', 'at': {'248.4': 7e-20}}, [200.0, 250.0, 300.0], [1e-18] * 3, 248.4), (7e-20, None), 'a thinned dataset: the stored value')
        self.assertIsNone(B.page_value({'np': 2000, 'n0': 9000, 'id': 'a', 'at': {'248.4': 7e-20}}, [200.0, 250.0, 300.0], [1e-18] * 3, 266))
        # a list of band maxima is read point by point, never interpolated: the nearest point within 1 nm, or nothing
        peaks = {'np': 3, 'n0': 3, 'id': 'mainz2013:RbI_Davidovits(1967)_1007K_241,265,330nm(max)'}
        self.assertIsNone(B.page_value(peaks, [241.0, 265.0, 330.0], [5e-17, 6e-17, 2e-17], 248.4))
        self.assertEqual(B.page_value(peaks, [241.0, 265.0, 330.0], [5e-17, 6e-17, 2e-17], 266), (6e-17, 265.0))

    def test_what_a_file_name_says(self):
        peak = lambda i: bool(B.PEAKS.search(i))   # noqa: E731
        for tag in ('max', 'max,min', 'min,max', 'sh,max', 'max,sol', 'peaks', 'peaks-1cm-1', 'band peaks', 'band peaks,rec', 'band heads', 'max,min,rec', 'max,av'):
            self.assertTrue(peak('mainz2013:Xx_A(2000)_298K_241,265nm(%s)' % tag), tag)
        for tag in ('rec', 'sol', 'smoo', 'meas', '2nm', 'e,e', 'int-c', 'maximal'):
            self.assertFalse(peak('mainz2013:Xx_A(2000)_298K_240-270nm(%s)' % tag), tag)
        for tag in ('15NH3', '33SO2', '16O2', '16O18O', '14N15NO', 'O13CS', 'OC34S'):
            self.assertEqual(B.iso_tag('mainz2013:Xx_A(2000)_298K_240-270nm(%s)' % tag), tag)
        for i in ('mainz2013:CH2O_Co(2005)_298K_350.877-355.871nm(150Torr)', 'mainz2013:(CD3)2C=CD2_Bertrand(1975)_298K_123.6nm', 'mainz2013:O2_Yoshino(1992)_300K_179.2-180.2nm(12-0)',
                  'mainz2013:OClO_Bogumil(2003)_293K_292-458nm(2nm)', 'mainz2013:CF2Cl2(CFC-12)_Au(1997)_298K_6.2-207nm(e,e)', 'mainz2013:Limonene(C10H16)_Smialek(2012)_298K_116-285nm',
                  'mainz2013:(15NH3)_first(2000)_298K_200-210nm'):
            self.assertEqual(B.iso_tag(i), '', i)
        self.assertTrue(B.WHO_SKIP.search('mainz2013:H2O_Coheur(2002),Fally(2003)_290K_396-755nm(line intensities)'))
        # the gap between the points around a wavelength, and the widest step that reaches into a bin
        xs = [177.12, 206.64, 207.0, 212.0, 217.01]
        self.assertAlmostEqual(B.gap_at(xs, 193.3), 29.52)
        self.assertEqual(B.gap_at(xs, 207.0), 0.0, 'at a point')
        self.assertEqual(B.gap_at(xs, 217.01), 0.0, 'the last point')
        self.assertIsNone(B.gap_at(xs, 170)); self.assertIsNone(B.gap_at(xs, 220))
        self.assertAlmostEqual(B.gap_in(xs, 206, 208), 29.52); self.assertAlmostEqual(B.gap_in(xs, 208, 210), 5.0); self.assertAlmostEqual(B.gap_in(xs, 206.8, 207.0), 0.36)
        self.assertEqual([B.is_wide(g) for g in (None, 0.0, 5.0, 5.0000004, 5.01, 29.52)], [False, False, False, False, True, True])
        # the spread of σ close to a line: the largest over the smallest value among the points within 0.25 nm, a whole
        # number from 2 up; None with fewer than three points there, or a ratio below 2
        bx = [193.0, 193.1, 193.2, 193.3, 193.4, 193.5, 193.6]; by = [1e-21, 2e-22, 1e-23, 6.3e-22, 5e-23, 5e-22, 9e-21]
        self.assertEqual(B.spread_at(bx, by, 193.3), 63, '6.3e-22 / 1e-23 over 193.1 to 193.5 nm')
        self.assertEqual(B.spread_at(bx, [1e-21, 1e-21, 1.2e-21, 1.5e-21, 1.9e-21, 1e-21, 1e-21], 193.3), None, 'below a factor of two')
        self.assertEqual(B.spread_at(bx, [1e-21, 1e-21, 1e-21, 1.5e-21, 2e-21, 1e-21, 1e-21], 193.3), 2)
        self.assertEqual(B.spread_at([190.0, 193.3, 196.0], [1e-21, 1e-19, 1e-17], 193.3), None, 'one point within 0.25 nm')
        self.assertEqual(B.spread_at(bx, [1e-21, 1e-30, 1e-21, 1e-21, 1e-21, 1e-21, 1e-21], 193.3), 10000, 'written as 10 000 at most')
        self.assertEqual(B.spread_at(bx, [1e-21, 1e-45, 1e-21, 1e-21, 1.1e-21, 1e-21, 1e-21], 193.3), None, 'underflow does not count')
        self.assertEqual(B.who_flags({'id': 'a(e,e)', 'rec': True}), 5); self.assertEqual(B.who_flags({'id': 'a_241,265nm(max)', 'rec': False, 'ul': True}), 10)

    def test_key_and_rounding_helpers(self):
        self.assertEqual(B.key_of('CH3C(O)OONO2'), 'CH3C_O_OONO2')
        self.assertEqual(B.key_of('O3'), 'O3')
        self.assertEqual(B.key_of('C2H5O2+'), 'C2H5O2+')
        self.assertEqual(B.key_of('()'), 'x')
        self.assertEqual(B.sig(1.234567e-19), 1.2346e-19)
        self.assertTrue(B.skip({'units': 'cm2/molecule', 'notes': 'QA FLAG x'}))
        self.assertFalse(B.skip({'units': 'cm2/molecule', 'notes': None}))

    def test_command_line(self):
        out3 = os.path.join(self.tmp, 'data3')
        r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_data.py'), self.clean, out3, '--built', '2026-11-11'],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith('3 species, 5 datasets (3 skipped)'))
        self.assertEqual(Path(out3, 'index.json').read_bytes(), Path(self.out, 'index.json').read_bytes())
        bad = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_data.py'), self.clean, out3, '--built', 'today'], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)

    def test_thinning_check(self):
        import thinning_check as T
        res = T.check(self.clean, self.out)
        # the one thinned dataset (200-249.99 nm) covers 212.8, 222 and 248.4 nm
        self.assertEqual(sorted(r[2] for r in res), [212.8, 222, 248.4])
        self.assertTrue(all(r[1] == 'mainz2013:O3_big' and r[0] < 0.01 for r in res), res)

    @unittest.skipUnless(NODE, 'node is not on the PATH')
    def test_output_passes_the_site_data_checks(self):
        out4 = os.path.join(self.tmp, 'data4')                      # a fresh build: no stray files in s/
        B.build(self.clean, out4, built='2026-11-11')
        r = subprocess.run([NODE, str(ROOT / 'scripts' / 'selftest.mjs'), str(ROOT / 'site'), '--data-dir', out4],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('data: 3 species, 5 datasets, 0 problem(s)', r.stdout)

    @unittest.skipUnless(NODE, 'node is not on the PATH')
    def test_thinning_matches_the_page_engine(self):
        d = wavy(7321, a=120.0, h=0.0137)
        for i in range(0, len(d), 97):
            d[i][1] *= 1 + (i % 7) / 3                       # some structure on top
        js = ("import * as X from './site/js/xsec.js'; let s=''; process.stdin.on('data', (c) => s += c);"
              "process.stdin.on('end', () => process.stdout.write(JSON.stringify(X.resample(JSON.parse(s), 2000))));")
        r = subprocess.run([NODE, '--input-type=module', '-e', js], input=json.dumps(d), capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), B.resample(d, 2000))


RULES = [
    # σ against temperature at one wavelength, fit parameters, dσ/dT: not σ(λ)
    row('mainz2013:O2_Hong(2011)_1059-1745K_219nm(T dependence)', 'O2', [[1059.0, 1e-21], [1745.0, 2e-20]], T=[1059.0, 1745.0]),
    row('mainz2013:CH2O_ChanceOrphal(2011)_223.15-293.15K_300-385nm(parameters)', 'CH2O', [[25919.6, 1e-20], [33299.5, 2e-20]]),
    row('mainz2013:CH2O_MellerMoortgat(2000)_223-323K_249.38-356.56nm(T-gradient)', 'CH2O', [[249.38, 1e-23], [356.56, 2e-24]]),
    # O2-O2 collision-induced absorption, cm5 molecule-2
    row('mainz2013:O4_Spiering(2010)_296K_753-771nm', 'O4', [[753.0, 3e-47], [771.0, 1e-46]]),
    # a point far outside the range of the file name, and a file with no point inside it
    row('mainz2013:HO2_Lightfoot(1988)_298K_210-227.5nm', 'HO2', [[21.0, 4.4e-18], [200.0, 4.8e-18], [220.0, 3.7e-18], [227.5, 3e-18]]),
    row('mainz2013:CFCl3_ColeDexter(1978)_298K_6.5-10nm', 'CFCl3', [[225.0, 1e-20]]),
    row('mainz2013:H2SO4_Hintze(2003)_403K_140-170nm(upper limits)', 'H2SO4', [[140.0, 1e-18], [170.0, 1e-18]]),
    # references given only as free text, and two references run together in the journal field
    row('mainz2013:O3_Bass(1984)_203K_245-340nm', 'O3', [[245.0, 1e-17], [340.0, 1e-20]],
        ref={'authors': None, 'year': 1984, 'title': None, 'journal': None, 'doi': None,
             'citation_text': 'A.M. Bass (1984), personal communication to R. Meller, Max-Planck-Institut f\u00fcr Chemie, Mainz'}),
    row('mainz2013:C2N2_LISA-unpubl(1999)_293K_185-225nm', 'C2N2', [[185.0, 1e-19], [225.0, 1e-21]],
        ref={'authors': None, 'year': 1999, 'title': None, 'journal': None, 'doi': None, 'citation_text': 'http://example.org/DiffuseUVdata/'}),
    row('mainz2013:X_Ganne(1998)_298K_200-300nm', 'Xq', [[200.0, 1e-18], [300.0, 1e-19]],
        ref={'authors': None, 'year': 1998, 'title': None, 'journal': None, 'doi': None,
             'citation_text': 'J.P. Ganne and J. Malicet, \u00e2\u0080\u009cKinetic study\u00e2\u0080\u009d, Proc. (1998)'}),
    row('tuvx:Br2_1', 'Br2', [[320.0, 7.6e-22], [330.0, 3.1e-21]], source='tuvx', T=None,
        ref={'authors': None, 'year': 1964, 'title': None, 'journal': None, 'doi': None, 'citation_text': 'Chem. 68, p. 2263 (1964).'}),
    row('mainz2013:O3_Vigroux(1952,1953)_291K_230.5-311.2nm', 'O3', [[230.5, 1e-17], [311.2, 1e-19]],
        ref={'authors': 'E. Vigroux', 'year': 1953, 'title': 'Absorption', 'doi': None,
             'journal': 'Compt. Rend. 234, 2529 (1952).E. Vigroux, Ann. Phys. 8, 709 (1953); (1983).J . Brion, J. Phys. 45 (1984)'}),
]


def flat(a, b, v, n=7):
    """n points of a flat spectrum from a to b nm (7 points over 240 to 270 nm are 5 nm apart: not a gap)."""
    return [[a + (b - a) * i / (n - 1), v] for i in range(n)]


REF = lambda who, year: {'authors': who, 'year': year, 'title': 't', 'journal': 'j', 'doi': None}   # noqa: E731
# One species per step of the rule that picks a dataset: every pair covers 248.4 nm (and 266 nm), and the σ of each
# dataset tells which one was taken. The dataset that must win is the first of each pair.
PICK = [
    # a measured value before upper limits, although those are recommended and newer
    row('mainz2013:Aa_Old(1970)_240K_240-270nm', 'Aa', flat(240, 270, 1e-18), T=240.0, ref=REF('A. Old', 1970)),
    row('mainz2013:Aa_New(2020)_298K_240-270nm(upper limits)', 'Aa', flat(240, 270, 9e-18), rec=True, ref=REF('B. New', 2020)),
    # a spectrum before a single point at the line
    row('mainz2013:Bb_Spec(1980)_200K_240-270nm', 'Bb', flat(240, 270, 2e-18), T=200.0, ref=REF('A. Spec', 1980)),
    row('mainz2013:Bb_Point(2015)_298K_248nm', 'Bb', [[248.0, 9e-18]], rec=True, ref=REF('B. Point', 2015)),
    # room temperature, then no temperature given, then the nearest to 296 K
    row('mainz2013:Cc_Room(1960)_285K_240-270nm', 'Cc', flat(240, 270, 3e-18), T=285.0, ref=REF('A. Room', 1960)),
    row('tuvx:Cc_none', 'Cc', flat(240, 270, 9e-18), source='tuvx', T=None, rec=True, ref=REF('B. None', 2020)),
    row('tuvx:Dd_none', 'Dd', flat(240, 270, 4e-18), source='tuvx', T=None, ref=REF('A. None', 1960)),
    row('mainz2013:Dd_Cold(2020)_273K_240-270nm', 'Dd', flat(240, 270, 9e-18), T=273.0, rec=True, ref=REF('B. Cold', 2020)),
    row('mainz2013:Ee_Warm(1960)_305K_240-270nm', 'Ee', flat(240, 270, 5e-18), T=305.0, ref=REF('A. Warm', 1960)),
    row('mainz2013:Ee_Cold(2020)_273K_240-270nm', 'Ee', flat(240, 270, 9e-18), T=273.0, rec=True, ref=REF('B. Cold', 2020)),
    # recommended before newer; newer before more points; more points; and a range that reaches room temperature
    row('mainz2013:Ff_Rec(1990)_298K_240-270nm', 'Ff', flat(240, 270, 6e-18), rec=True, ref=REF('A. Rec', 1990)),
    row('mainz2013:Ff_New(2020)_298K_240-270nm', 'Ff', flat(240, 270, 9e-18, 50), ref=REF('B. New', 2020)),
    row('mainz2013:Gg_New(2011)_298K_240-270nm', 'Gg', flat(240, 270, 7e-18), ref=REF('A. New', 2011)),
    row('mainz2013:Gg_Old(2006)_298K_240-270nm', 'Gg', flat(240, 270, 9e-18, 50), ref=REF('B. Old', 2006)),
    row('mainz2013:Hh_Many(2000)_298K_240-270nm', 'Hh', flat(240, 270, 8e-18, 50), ref=REF('A. Many', 2000)),
    row('mainz2013:Hh_Few(2000)_298K_240-270nm', 'Hh', flat(240, 270, 9e-18), ref=REF('B. Few', 2000)),
    row('mainz2013:Ii_Range(1970)_250-285K_240-270nm', 'Ii', flat(240, 270, 8.5e-18), T=[250.0, 285.0], ref=REF('A. Range', 1970)),
    row('mainz2013:Ii_Warm(2020)_301K_240-270nm', 'Ii', flat(240, 270, 9e-18), T=301.0, rec=True, ref=REF('B. Warm', 2020)),
    # each wavelength has its own choice: Jj's room-temperature file ends at 255 nm, so at 266 nm the cold one stands in;
    # two keys that differ only by case; and a point measured 0.3 nm from a line
    row('mainz2013:Jj_Room(2000)_298K_240-255nm', 'Jj', flat(240, 255, 1.5e-18), ref=REF('A. Room', 2000)),
    row('mainz2013:Jj_Cold(2000)_220K_240-270nm', 'Jj', flat(240, 270, 2.5e-18), T=220.0, ref=REF('B. Cold', 2000)),
    row('mainz2013:CO_A(2000)_298K_240-270nm', 'CO', flat(240, 270, 1e-22), ref=REF('A. Co', 2000)),
    row('mainz2013:Co_B(2001)_298K_240-270nm', 'Co', flat(240, 270, 1e-16), ref=REF('B. Cobalt', 2001)),   # another file name: the test archive may sit on a case-blind disk
    row('mainz2013:Kk_Point(1975)_298K_193nm', 'Kk', [[193.0, 4.4e-19]], ref=REF('A. Point and B. Point', 1975)),
    # optical absorption before an electron energy loss spectrum, although that one is at room temperature, recommended and newer
    row('mainz2013:Ll_Opt(1960)_200K_240-270nm', 'Ll', flat(240, 270, 1.1e-18), T=200.0, ref=REF('A. Opt', 1960)),
    row('mainz2013:Ll_EE(2020)_298K_240-270nm(e,e)', 'Ll', flat(240, 270, 9e-18, 50), rec=True, ref=REF('B. Ee', 2020)),
    # points 5 nm apart before points 15 nm apart
    row('mainz2013:Mm_Dense(1960)_200K_240-270nm', 'Mm', flat(240, 270, 1.2e-18), T=200.0, ref=REF('A. Dense', 1960)),
    row('mainz2013:Mm_Sparse(2020)_298K_240-270nm', 'Mm', flat(240, 270, 9e-18, 3), rec=True, ref=REF('B. Sparse', 2020)),
    # a spectrum before a list of band maxima, which has a point 0.4 nm from the line
    row('mainz2013:Nn_Spec(1960)_200K_240-270nm', 'Nn', flat(240, 270, 1.3e-18), T=200.0, ref=REF('A. Spec', 1960)),
    row('mainz2013:Nn_Max(2020)_298K_241,248,265nm(max)', 'Nn', [[241.0, 9e-18], [248.0, 9e-18], [265.0, 9e-18]], rec=True, ref=REF('B. Max', 2020)),
    # the natural sample before one isotopologue
    row('mainz2013:Pp_Nat(1960)_273K_240-270nm', 'Pp', flat(240, 270, 1.4e-18), T=273.0, ref=REF('A. Nat', 1960)),
    row('mainz2013:Pp_Iso(2020)_298K_240-270nm(15NH3)', 'Pp', flat(240, 270, 9e-18, 50), rec=True, ref=REF('B. Iso', 2020)),
    # where a weak dataset is all there is, it stands and says what it is: an isotopologue; a sparse electron energy
    # loss spectrum; band maxima (no value between them: 248.4 nm lies between 241 and 265 nm)
    row('mainz2013:Qq_Only(2000)_298K_240-270nm(34SO2)', 'Qq', flat(240, 270, 1.6e-18), ref=REF('A. Only', 2000)),
    row('mainz2013:Rr_EE(2000)_298K_240-270nm(e,e)', 'Rr', flat(240, 270, 1.7e-18, 3), ref=REF('A. Loss', 2000)),
    row('mainz2013:Ss_Max(1967)_1007K_241,265,330nm(max)', 'Ss', [[241.0, 5e-17], [265.0, 6e-17], [330.0, 2e-17]], T=1007.0, ref=REF('A. Peak', 1967)),
    # a spectrum with a narrow band beside the line: σ ranges over a factor of 12 within 0.25 nm of 248.4 nm
    row('mainz2013:Vv_Band(2001)_298K_240-270nm', 'Vv', [[240.0, 1e-20], [245.0, 1e-20], [248.2, 1e-20], [248.3, 1.2e-19], [248.4, 1e-20], [248.5, 1e-20],
                                                         [248.6, 1e-20], [250.0, 1e-20], [255.0, 1e-20], [260.0, 1e-20], [265.0, 1e-20], [270.0, 1e-20]], ref=REF('A. Band', 2001)),
    # never listed: line intensities, which are not σ, and underflow values
    row('mainz2013:Tt_Lines(2002)_290K_240-270nm(line intensities)', 'Tt', flat(240, 270, 3e-26, 50), T=290.0, ref=REF('A. Lines', 2002)),
    row('leiden:Uu', 'Uu', flat(240, 270, 8e-323), source='leiden', T=None, ref=REF('A. Tiny', 2017)),
]


class Who(unittest.TestCase):
    """One dataset per species for "Who absorbs here?": the rule, step by step, on an archive made for it."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='xs-who-')
        clean = os.path.join(cls.tmp, 'clean'); cls.out = os.path.join(cls.tmp, 'data')
        write_archive(clean, PICK)
        B.build(clean, cls.out, built='2026-11-11')
        cls.index = json.loads(Path(cls.out, 'index.json').read_text(encoding='utf-8'))
        cls.who = json.loads(Path(cls.out, 'who.json').read_text(encoding='utf-8'))
        cls.coarse = json.loads(Path(cls.out, 'coarse.json').read_text(encoding='utf-8'))
        cls.slim = json.loads(Path(cls.out, 'species.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def at(self, nm):
        return [(self.who['sets'][r[0]][0], r[1]) for r in self.who['at'][nm]]

    def test_the_rule_step_by_step(self):
        # strongest first; each σ is that of the dataset the rule must take
        self.assertEqual(self.at('248.4'), [('Co', 1e-16), ('Ii', 8.5e-18), ('Hh', 8e-18), ('Gg', 7e-18), ('Ff', 6e-18), ('Ee', 5e-18), ('Dd', 4e-18),
                                            ('Cc', 3e-18), ('Bb', 2e-18), ('Rr', 1.7e-18), ('Qq', 1.6e-18), ('Jj', 1.5e-18), ('Pp', 1.4e-18), ('Nn', 1.3e-18),
                                            ('Mm', 1.2e-18), ('Ll', 1.1e-18), ('Aa', 1e-18), ('Vv', 1e-20), ('CO', 1e-22)])

    def test_weak_datasets_say_what_they_are(self):
        f = {x['id']: x['f'] for s in self.index['species'] for x in s['sets']}
        rows = {self.who['sets'][r[0]][0]: r for r in self.who['at']['248.4']}
        iso, ee, peaks = f['mainz2013:Qq_Only(2000)_298K_240-270nm(34SO2)'], f['mainz2013:Rr_EE(2000)_298K_240-270nm(e,e)'], f['mainz2013:Ss_Max(1967)_1007K_241,265,330nm(max)']
        self.assertEqual(self.who['sets'][iso], ['Qq', 'Only (2000)', 298.0, 'mainz2013', 0, '34SO2'], 'the isotopologue is named')
        self.assertEqual(rows['Qq'], [iso, 1.6e-18])
        self.assertEqual(self.who['sets'][ee], ['Rr', 'Loss (2000)', 298.0, 'mainz2013', 4], 'flag 4: electron energy loss')
        self.assertEqual(rows['Rr'], [ee, 1.7e-18, None, 15.0], 'interpolated between points 15 nm apart')
        # a structured spectrum carries the spread of σ close to the line, after two nulls; away from the band it does not
        band = f['mainz2013:Vv_Band(2001)_298K_240-270nm']
        self.assertEqual(rows['Vv'], [band, 1e-20, None, None, 12])
        self.assertIn([band, 1e-20], self.who['at']['266'])
        # band maxima: nothing between the bands at 248.4 nm; at 266 nm the maximum listed at 265 nm, with its wavelength
        self.assertNotIn('Ss', rows)
        self.assertIn([peaks, 6e-17, 265.0], self.who['at']['266'])
        self.assertEqual(self.who['sets'][peaks][4], 8, 'flag 8: a list of band maxima')
        self.assertNotIn(peaks, self.coarse['sets'], 'band maxima have no coarse values')
        # the coarse runs carry the gap: Rr's is marked, Qq's is not
        runs = {self.coarse['sets'][r[0]][0]: r for r in self.coarse['runs']}
        self.assertEqual(runs['Rr'][3:], [1]); self.assertEqual(len(runs['Qq']), 3)
        # line intensities and underflow values are in the atlas and in no table
        for sid in ('mainz2013:Tt_Lines(2002)_290K_240-270nm(line intensities)', 'leiden:Uu'):
            self.assertIn(sid, f)
            self.assertNotIn(f[sid], self.who['sets']); self.assertNotIn(f[sid], self.coarse['sets'])
        self.assertFalse({'Tt', 'Uu'} & {self.who['sets'][r[0]][0] for rs in self.who['at'].values() for r in rs})

    def test_each_wavelength_has_its_own_choice(self):
        got = dict(self.at('266'))
        self.assertEqual(got['Jj'], 2.5e-18, 'the room-temperature file ends at 255 nm')
        self.assertEqual(got['Bb'], 2e-18)
        self.assertEqual(len(got), 20)
        # in the coarse table Jj changes dataset where the room-temperature file ends: its last bin center is 255 nm
        f = {x['id']: x['f'] for s in self.index['species'] for x in s['sets']}
        runs = [r for r in self.coarse['runs'] if self.coarse['sets'][r[0]][0] == 'Jj']
        room, cold = f['mainz2013:Jj_Room(2000)_298K_240-255nm'], f['mainz2013:Jj_Cold(2000)_220K_240-270nm']
        self.assertEqual([(r[0], r[1], len(r[2])) for r in runs], [(room, 120, 8), (cold, 128, 7)])
        self.assertEqual(set(runs[0][2]), {math.floor(100 * math.log10(1.5e-18) + 0.5)})

    def test_flags_points_and_labels(self):
        f = {x['id']: x['f'] for s in self.index['species'] for x in s['sets']}
        # a single point 0.3 nm from the ArF line: listed with its own wavelength
        self.assertEqual(self.who['at']['193.3'], [[f['mainz2013:Kk_Point(1975)_298K_193nm'], 4.4e-19, 193.0]])
        self.assertEqual(self.who['sets'][f['mainz2013:Kk_Point(1975)_298K_193nm']], ['Kk', 'Point and Point (1975)', 298.0, 'mainz2013', 0])
        self.assertEqual(self.who['sets'][f['mainz2013:Ff_Rec(1990)_298K_240-270nm']][4], 1, 'recommended')
        # upper limits stand for a species only where it has nothing else: Aa's are never chosen here
        self.assertNotIn(f['mainz2013:Aa_New(2020)_298K_240-270nm(upper limits)'], self.who['sets'])
        self.assertNotIn(f['mainz2013:Aa_New(2020)_298K_240-270nm(upper limits)'], self.coarse['sets'])
        # a single point has no coarse values
        self.assertNotIn(f['mainz2013:Kk_Point(1975)_298K_193nm'], self.coarse['sets'])

    def test_keys_that_differ_only_by_case(self):
        rows = {r[0]: r for r in self.slim['species']}
        self.assertEqual(rows['CO'], ['CO', 'CO', '', '', 1])
        self.assertEqual(rows['Co'], ['Co', 'Co', '', '', 1, 'Co_2'], 'the second of the two names its file')
        names = sorted(os.listdir(os.path.join(self.out, 'sp')))
        self.assertEqual(len(names), 23)
        self.assertEqual(len({n.lower() for n in names}), 23, 'no two files that a case-blind disk would merge')
        self.assertEqual(json.loads(Path(self.out, 'sp', 'Co_2.json').read_text(encoding='utf-8'))['k'], 'Co')
        self.assertEqual(json.loads(Path(self.out, 'sp', 'CO.json').read_text(encoding='utf-8'))['k'], 'CO')

    def test_species_files_of_an_earlier_build_are_removed(self):
        Path(self.out, 'sp', 'Zz.json').write_text('{}')
        Path(self.out, 'sp', 'keep.txt').write_text('not mine')
        B.build(os.path.join(self.tmp, 'clean'), self.out, built='2026-11-11')
        self.assertFalse(Path(self.out, 'sp', 'Zz.json').exists())
        self.assertTrue(Path(self.out, 'sp', 'keep.txt').exists())
        os.remove(Path(self.out, 'sp', 'keep.txt'))

    @unittest.skipUnless(NODE, 'node is not on the PATH')
    def test_the_page_side_works_out_the_same_tables(self):
        # scripts/selftest.mjs makes species.json, sp/, who.json and coarse.json again in JavaScript from index.json and
        # the spectra, and fails where this build's files differ
        r = subprocess.run([NODE, str(ROOT / 'scripts' / 'selftest.mjs'), str(ROOT / 'site'), '--data-dir', self.out],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('split files: species.json, sp/, who.json and coarse.json agree with index.json and the spectra', r.stdout)
        self.assertIn('boot: pass', r.stdout)

    @unittest.skipUnless(NODE, 'node is not on the PATH')
    def test_labels_match_the_page_engine(self):
        refs = [{'a': 'A. Serdyuchenko, V. Gorshelev, M. Weber, W. Chehade, and J. P. Burrows', 'y': 2014}, {'a': 'L.T Molina and M.J. Molina', 'y': 1986},
                {'a': 'S.P. Sander et al.', 'y': '2011'}, {'a': 'G. von Helden', 'y': ''}, {'a': '', 'y': 1999, 'lab': 'LISA-unpubl'},
                {'a': '', 'y': '', 't': 'A title that runs on for rather more than fifty characters in all'}, {'a': '', 'y': ''},
                {'a': 'J. Malicet, D. Daumont, J. Charbonnier, C. Parisse, A. Chakir and J. Brion', 'y': 1995}, {'a': 'A. B. Meinel and  C. D.  Meinel,and E. F. Third', 'y': 1}]
        js = ("import * as X from './site/js/xsec.js'; let s=''; process.stdin.on('data', (c) => s += c);"
              "process.stdin.on('end', () => process.stdout.write(JSON.stringify(JSON.parse(s).map(X.refLabel))));")
        r = subprocess.run([NODE, '--input-type=module', '-e', js], input=json.dumps(refs), capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [B.ref_label(x) for x in refs])


class Rules(unittest.TestCase):
    """What is left out, dropped, labeled and filled in on the way from the archive to the page."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='xs-rules-')
        clean = os.path.join(cls.tmp, 'clean'); cls.out = os.path.join(cls.tmp, 'data')
        write_archive(clean, RULES)
        # the TUV-x file header the page shows in place of a reference
        p = os.path.join(clean, 'xs', 'test', 'tuvx_Br2_1.json'); ds = json.loads(Path(p).read_text(encoding='utf-8'))
        ds['comments'] = 'Br2 Absorption cross section, from\nSeery, D.J. and D. Britton, J. Phys.\nChem. 68, p. 2263 (1964).'
        Path(p).write_text(json.dumps(ds), encoding='utf-8')
        B.build(clean, cls.out, built='2026-11-11')
        cls.index = json.loads(Path(cls.out, 'index.json').read_text(encoding='utf-8'))
        cls.sets = {x['id']: x for s in cls.index['species'] for x in s['sets']}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_left_out(self):
        why = self.index['meta']['skipped_why']
        self.assertEqual(sorted(why), sorted([r['id'] for r, _ in RULES[:4]] + ['mainz2013:CFCl3_ColeDexter(1978)_298K_6.5-10nm']))
        self.assertTrue(why['mainz2013:O2_Hong(2011)_1059-1745K_219nm(T dependence)'].startswith('not sigma against wavelength'))
        self.assertEqual(why['mainz2013:O4_Spiering(2010)_296K_753-771nm'], 'O2-O2 collision-induced absorption, cm5/molecule2')
        self.assertTrue(why['mainz2013:CFCl3_ColeDexter(1978)_298K_6.5-10nm'].startswith('no point left (all far outside'))
        self.assertNotIn('O4', [s['f'] for s in self.index['species']])

    def test_points_far_outside_the_file_name_range(self):
        x = self.sets['mainz2013:HO2_Lightfoot(1988)_298K_210-227.5nm']
        self.assertEqual((x['np'], x['n0'], x['l']), (3, 3, [200.0, 227.5]))
        self.assertTrue(x['note'].startswith('Left out: a point at 21 nm, far outside the 210\u2013227.5 nm of the file name.'), x['note'])
        self.assertEqual(B.name_range('mainz2013:HN3_Okabe(1968)_298K_139.5, 156.5,190.0nm'), (139.5, 190.0))
        self.assertEqual(B.name_range('mainz2013:O2_Hong(2011)_1059-1745K_219nm(T dependence)'), (219.0, 219.0))
        self.assertIsNone(B.name_range('leiden:O2'))

    def test_upper_limits(self):
        x = self.sets['mainz2013:H2SO4_Hintze(2003)_403K_140-170nm(upper limits)']
        self.assertIs(x['ul'], True)
        self.assertTrue(x['note'].startswith('Upper limits, not measured cross sections.'))
        self.assertNotIn('ul', self.sets['mainz2013:HO2_Lightfoot(1988)_298K_210-227.5nm'])

    def test_free_text_references(self):
        bass = self.sets['mainz2013:O3_Bass(1984)_203K_245-340nm']['ref']
        self.assertEqual((bass['a'], bass['y']), ('A.M. Bass', 1984))
        self.assertTrue(bass['c'].startswith('A.M. Bass (1984), personal communication'))
        self.assertNotIn('lab', bass)
        lisa = self.sets['mainz2013:C2N2_LISA-unpubl(1999)_293K_185-225nm']['ref']
        self.assertEqual((lisa['a'], lisa['lab'], lisa['c']), ('', 'LISA-unpubl', 'http://example.org/DiffuseUVdata/'))
        ganne = self.sets['mainz2013:X_Ganne(1998)_298K_200-300nm']['ref']
        self.assertEqual(ganne['a'], 'J.P. Ganne and J. Malicet')
        self.assertIn('\u201cKinetic study\u201d', ganne['c'], 'curly quotes put back')
        tuv = self.sets['tuvx:Br2_1']['ref']
        self.assertEqual(tuv['lab'], 'TUV-x Br2_1')
        self.assertEqual(tuv['c'], 'TUV-x file header: Br2 Absorption cross section, from Seery, D.J. and D. Britton, J. Phys. Chem. 68, p. 2263 (1964).')

    def test_run_together_journal_field(self):
        j = self.sets['mainz2013:O3_Vigroux(1952,1953)_291K_230.5-311.2nm']['ref']['j']
        self.assertEqual(j, 'Compt. Rend. 234, 2529 (1952); E. Vigroux, Ann. Phys. 8, 709 (1953); (1983); J. Brion, J. Phys. 45 (1984)')

    def test_helpers(self):
        self.assertEqual([B.js_key(x) for x in (266, 266.0, 212.8, 121.567)], ['266', '266', '212.8', '121.567'])
        self.assertEqual(B.authors_from('W. Schneider and G. von Helden, personal communication (1991)'), 'W. Schneider and G. von Helden')
        self.assertEqual(B.authors_from('Harvard-Smithsonian Center for Astrophysics Database'), '')
        self.assertEqual(B.interp([1.0, 2.0, 2.0, 3.0], [1.0, 2.0, 5.0, 5.0], 2.0), 5.0, 'at a step, the value after it')
        self.assertIsNone(B.interp([1.0, 2.0], [1.0, 2.0], 2.5))

    @unittest.skipUnless(NODE, 'node is not on the PATH')
    def test_output_passes_the_site_data_checks(self):
        r = subprocess.run([NODE, str(ROOT / 'scripts' / 'selftest.mjs'), str(ROOT / 'site'), '--data-dir', self.out],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main()
