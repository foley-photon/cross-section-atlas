"""Safely extract a zip: strip absolute/.. components, sanitize Windows-invalid chars,
de-duplicate case-insensitive collisions. Writes a mapping TSV (archive name -> local path)."""
import sys, zipfile, os, re
zpath, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
bad = re.compile(r'[<>:"|?*\x00-\x1f]')
seen = {}
rows = []
with zipfile.ZipFile(zpath) as z:
    for info in z.infolist():
        if info.is_dir():
            continue
        parts = [p for p in info.filename.replace(chr(92), '/').split('/') if p not in ('', '.', '..')]
        parts = [bad.sub('_', p).rstrip(' .') or '_' for p in parts]
        rel = '/'.join(parts)
        key = rel.lower()
        if key in seen:
            seen[key] += 1
            base, ext = os.path.splitext(rel)
            rel = f"{base}__dup{seen[key]}{ext}"
        else:
            seen[key] = 0
        dest = os.path.join(outdir, *rel.split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with z.open(info) as src, open(dest, 'wb') as dst:
            while True:
                b = src.read(1 << 20)
                if not b: break
                dst.write(b)
        rows.append((info.filename, rel))
with open(os.path.join(outdir, '_unzip_map.tsv'), 'w', encoding='utf-8') as f:
    for a, b in rows:
        f.write(f"{a}\t{b}\n")
changed = sum(1 for a, b in rows if a.lstrip('./') != b)
print(f"extracted {len(rows)} files, {changed} renamed")
