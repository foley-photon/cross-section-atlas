"""Write SHA256SUMS (sha256sum-compatible) for every file under a directory.
usage: python -I sha256sums.py <dir> <out_file>"""
import sys, os, hashlib

root, out = sys.argv[1:3]
outabs = os.path.abspath(out)
lines = []
for dp, dn, fn in os.walk(root):
    dn.sort()
    for f in sorted(fn):
        p = os.path.join(dp, f)
        if os.path.abspath(p) == outabs:
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        lines.append(f"{h.hexdigest()}  {os.path.relpath(p, root).replace(os.sep, '/')}")
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(lines) + "\n")
print(len(lines), "files hashed ->", out)
