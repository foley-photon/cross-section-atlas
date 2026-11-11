"""Tests of scripts/build_data.py on a small synthetic archive written to a temporary folder: which datasets are kept
and which skipped, cleaning, thinning to MAX_POINTS, rounding, species merging, the index fields the page reads, a
rebuild that gives the same bytes, and the output passing the site's data checks (scripts/selftest.mjs). One test
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
        self.assertEqual(self.summary, '3 species, 5 datasets (3 skipped), spectra %.1f MB in 5 files, index %.2f MB' % (
            sum(os.path.getsize(os.path.join(self.out, 's', '%05d.json' % i)) for i in range(1, 6)) / 1e6,
            os.path.getsize(os.path.join(self.out, 'index.json')) / 1e6))

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
        for f in ['index.json'] + ['s/%05d.json' % i for i in range(1, 6)]:
            self.assertEqual(Path(self.out, f).read_bytes(), Path(out2, f).read_bytes(), f)

    def test_archive_date(self):
        self.assertEqual(B.archive_date({'schema': 'x', 'date': '2026-11-07'}), '2026-11-07')
        self.assertEqual(B.archive_date({'schema': 'one row', 'made': '2026-11-07', 'n': 3}), '2026-11-07', 'the 2026-11-07 archive')
        self.assertEqual(B.archive_date({'schema': 'x'}), '')

    def test_licenses_as_the_sources_state_them(self):
        s = B.SOURCES
        self.assertEqual(s['bremen']['license'], 'No license stated; the files ask that the paper be cited.')
        self.assertEqual(s['cfa']['license'], 'No license stated; cite the publications.')
        self.assertTrue(all('research use' not in v['license'] for v in s.values()))

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
