#!/usr/bin/env bash
# Make sure the version on origin/main has its tag and GitHub release. The site copies releases only, so a version
# bumped and pushed without one is released here (README.md, "Making a release"). Works on origin/main,
# never on local commits. Needs GH_TOKEN and a git identity; run from the repository root.
set -euo pipefail
git fetch -q origin main --tags
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git show origin/main:CITATION.cff > "$tmp/CITATION.cff"
git show origin/main:CHANGELOG.md > "$tmp/CHANGELOG.md"
V=$(python scripts/release.py --root "$tmp" current)
if out=$(gh release view "v$V" --json tagName 2>&1); then
    echo "v$V is released"
    exit 0
fi
case "$out" in
    *"release not found"*) ;;
    *) echo "::error::gh release view v$V: $out"; exit 1 ;;
esac
if git rev-parse -q --verify "refs/tags/v$V" > /dev/null; then
    echo "v$V is tagged but has no release"
else
    commit=$(git log -1 --format=%H origin/main -- CITATION.cff)
    git tag -a "v$V" -m "Absorption Cross-Section Atlas v$V" "$commit"
    git push origin "refs/tags/v$V"
fi
python scripts/release.py --root "$tmp" notes "$V" > "$tmp/notes.md"
gh release create "v$V" --verify-tag --title "v$V" --notes-file "$tmp/notes.md"
echo "::notice::Made the missing release v$V"
