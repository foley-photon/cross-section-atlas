"""Survey Mainz data file layouts: column counts, non-numeric lines."""
import sys, os, collections, re
root = sys.argv[1]
ncols = collections.Counter()
examples = {}
nonnum = collections.Counter()
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith('.txt'):
            continue
        p = os.path.join(dp, f)
        with open(p, 'rb') as fh:
            raw = fh.read()
        txt = raw.decode('latin-1')
        cols = collections.Counter()
        bad = 0
        for line in txt.splitlines():
            s = line.strip()
            if not s:
                continue
            parts = re.split(r'[\s,;]+', s)
            try:
                [float(x) for x in parts]
                cols[len(parts)] += 1
            except ValueError:
                bad += 1
                nonnum[s[:60]] += 1
        key = tuple(sorted(cols))
        ncols[key] += 1
        examples.setdefault(key, []).append(os.path.relpath(p, root))
for k, v in ncols.most_common():
    print(k, v, examples[k][:3])
print('--- top non-numeric lines')
for k, v in nonnum.most_common(40):
    print(v, repr(k))
