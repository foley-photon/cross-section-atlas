"""Tests of scripts/release.py on a copy of this repository's CHANGELOG.md, CITATION.cff and package.json."""
import json, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import release as R  # noqa: E402


class Release(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='xs-release-'))
        for f in ('CHANGELOG.md', 'CITATION.cff', 'package.json'):
            shutil.copy(ROOT / f, self.tmp / f)
        self.v = R.current(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_versions_agree(self):
        pkg = json.loads((self.tmp / 'package.json').read_text(encoding='utf-8'))['version']
        self.assertEqual('.'.join(map(str, self.v)), pkg)

    def test_bump_patch(self):
        a, b, c = self.v
        new = R.bump(self.tmp, 'Fixed a label.\nSecond line', today='2027-01-02')
        self.assertEqual(new, f'{a}.{b}.{c + 1}')
        cff = (self.tmp / 'CITATION.cff').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'^ {0,2}version: "([^"]+)"$', cff, re.M), [new, new])
        self.assertEqual(re.findall(r'^ {0,2}date-released: "([^"]+)"$', cff, re.M), ['2027-01-02', '2027-01-02'])
        self.assertEqual(json.loads((self.tmp / 'package.json').read_text(encoding='utf-8'))['version'], new)
        self.assertEqual(R.notes(self.tmp, new), '- Fixed a label.\n- Second line\n')
        log = (self.tmp / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertLess(log.index(f'## {new} - 2027-01-02'), log.index(f'## {a}.{b}.{c} - '))

    def test_bump_minor_and_major(self):
        a, b, c = self.v
        self.assertEqual(R.bump(self.tmp, 'x', part='minor', today='2027-01-02'), f'{a}.{b + 1}.0')
        self.assertEqual(R.bump(self.tmp, 'y', part='major', today='2027-01-03'), f'{a + 1}.0.0')

    def test_empty_note_and_unknown_version(self):
        with self.assertRaises(SystemExit):
            R.bump(self.tmp, '  \n ')
        with self.assertRaises(SystemExit):
            R.notes(self.tmp, '9.9.9')

    def test_notes_of_the_current_version(self):
        v = '.'.join(map(str, self.v))
        r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'release.py'), '--root', str(self.tmp), 'notes', v],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith('First release as its own repository.'))


if __name__ == '__main__':
    unittest.main()
