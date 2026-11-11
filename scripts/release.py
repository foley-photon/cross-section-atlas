"""Version bookkeeping for a release: CHANGELOG.md, CITATION.cff and package.json.

    python scripts/release.py current                          print the version in CITATION.cff
    python scripts/release.py bump --note TEXT [--part P]      next version (P = patch, minor or major; default patch):
                                                               a CHANGELOG entry dated today (UTC) with one line per line
                                                               of TEXT, and the version and date in CITATION.cff and
                                                               package.json; prints the new version
    python scripts/release.py notes VERSION                    print that version's CHANGELOG entry (release notes)

--root DIR works on another checkout (the tests use it). Standard library only.
"""
import argparse, datetime, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = re.compile(r'^( {0,2})(version|date-released): "[^"]*"$', re.M)     # the tool's own fields (indent 0 or 2)


def current(root):
    m = re.search(r'^version: "(\d+)\.(\d+)\.(\d+)"$', (root / 'CITATION.cff').read_text(encoding='utf-8'), re.M)
    if not m:
        raise SystemExit('no version in CITATION.cff')
    return tuple(int(x) for x in m.groups())


def bump(root, note, part='patch', today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    a, b, c = current(root)
    new = {'patch': f'{a}.{b}.{c + 1}', 'minor': f'{a}.{b + 1}.0', 'major': f'{a + 1}.0.0'}[part]
    lines = [ln.strip() for ln in note.strip().splitlines() if ln.strip()]
    if not lines:
        raise SystemExit('the release note is empty')
    cff = (root / 'CITATION.cff').read_text(encoding='utf-8')
    cff = VER.sub(lambda m: f'{m.group(1)}{m.group(2)}: "{new if m.group(2) == "version" else today}"', cff)
    (root / 'CITATION.cff').write_text(cff, encoding='utf-8', newline='\n')
    log = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
    entry = f'## {new} - {today}\n\n' + ''.join(f'- {ln}\n' for ln in lines) + '\n'
    k = log.index('\n## ') + 1
    (root / 'CHANGELOG.md').write_text(log[:k] + entry + log[k:], encoding='utf-8', newline='\n')
    pk = root / 'package.json'
    if pk.exists():
        t = pk.read_text(encoding='utf-8')
        pk.write_text(re.sub(r'("version": ")[^"]*(")', lambda m: m.group(1) + new + m.group(2), t, count=1), encoding='utf-8', newline='\n')
    return new


def notes(root, version):
    log = (root / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(rf'^## {re.escape(version)} - [^\n]*\n(.*?)(?=^## |\Z)', log, re.S | re.M)
    if not m:
        raise SystemExit(f'no CHANGELOG entry for {version}')
    return m.group(1).strip() + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(ROOT))
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('current')
    b = sub.add_parser('bump'); b.add_argument('--note', required=True); b.add_argument('--part', choices=['patch', 'minor', 'major'], default='patch')
    n = sub.add_parser('notes'); n.add_argument('version')
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.cmd == 'current':
        print('.'.join(map(str, current(root))))
    elif args.cmd == 'bump':
        print(bump(root, args.note, args.part))
    else:
        sys.stdout.write(notes(root, args.version))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')      # release notes can hold any character, whatever the console's code page
    sys.exit(main())
