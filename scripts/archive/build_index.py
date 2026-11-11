"""Build clean/index.json and size statistics.
usage: python -I build_index.py <clean_dir> <stats_out_json>
"""
import sys, os, json, glob, gzip, collections, re

clean, stats_out = sys.argv[1:3]
MAXPTS = 2000
DROP_KEYS = {"data", "extra", "comments"}


def resample(data, n=MAXPTS):
    """Index-bin average to at most n points (size estimate only; not written)."""
    if len(data) <= n:
        return data
    out = []
    L = len(data)
    for i in range(n):
        a, b = i * L // n, (i + 1) * L // n
        seg = data[a:b]
        out.append([sum(r[0] for r in seg) / len(seg), sum(r[1] for r in seg) / len(seg)])
    return out


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


rows = []
tot = collections.Counter()
for kind, pattern in (("xs", "xs/*/*.json"), ("qy", "qy/*/*.json"), ("flux", "flux/*.json")):
    for f in sorted(glob.glob(os.path.join(clean, pattern))):
        size = os.path.getsize(f)
        rec = json.load(open(f, encoding="utf-8"))
        data = rec["data"]
        dbytes = len(dumps(data).encode("utf-8"))
        rs = resample(data)
        rsbytes = len(dumps(rs).encode("utf-8"))
        # extras with arrays (tuvx parameter rows, error columns) - resample proportionally in estimate
        extra_bytes = len(dumps(rec.get("extra", {})).encode("utf-8")) if rec.get("extra") else 0
        frac = min(1.0, MAXPTS / max(1, len(data)))
        est = size - dbytes + rsbytes - extra_bytes * (1 - frac)
        rec_rs = dict(rec); rec_rs["data"] = rs
        gz = len(gzip.compress(dumps(rec_rs).encode("utf-8"), 6))
        tot[f"{kind}_bytes"] += size
        tot[f"{kind}_bytes_resampled_est"] += est
        tot[f"{kind}_gzip_resampled_est"] += gz
        tot[f"{kind}_n"] += 1
        row = {k: v for k, v in rec.items() if k not in DROP_KEYS}
        row["path"] = os.path.relpath(f, clean).replace("\\", "/")
        row["bytes"] = size
        if rec.get("extra"):
            row["extra_keys"] = sorted(rec["extra"].keys())
        row["has_comments"] = bool(rec.get("comments"))
        rows.append(row)

xs = [r for r in rows if r["path"].startswith("xs/")]
qy = [r for r in rows if r["path"].startswith("qy/")]
fl = [r for r in rows if r["path"].startswith("flux/")]
per_source = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    k = r["path"].split("/")[0]
    per_source[r["source"]][k] += 1
    per_source[r["source"]]["points"] += r["n_points"]
    per_source[r["source"]]["recommended"] += int(r["recommended"])
per_species = collections.defaultdict(lambda: collections.Counter())
for r in xs:
    s = r.get("species_canonical") or r["species"]
    per_species[s]["xs"] += 1
    per_species[s][r["source"]] += 1
    per_species[s]["recommended_xs"] += int(r["recommended"])
for r in qy:
    s = r.get("species_canonical") or r["species"]
    per_species[s]["qy"] += 1

index = {
    "schema": "one row per dataset; full data in the JSON file named by 'path' (relative to clean/)",
    "date": "2026-11-07",
    "n_datasets": {"cross_sections": len(xs), "quantum_yields": len(qy), "solar_flux": len(fl)},
    "totals_per_source": {k: dict(v) for k, v in sorted(per_source.items())},
    "totals_per_species": {k: dict(v) for k, v in sorted(per_species.items(), key=lambda kv: (-kv[1]["xs"], kv[0]))},
    "datasets": rows,
}
with open(os.path.join(clean, "index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

top = sorted(per_species.items(), key=lambda kv: (-kv[1]["xs"], kv[0]))[:100]
CHECK = ["O3", "NO2", "CH2O", "H2O", "O2", "N2O", "SO2", "Cl2", "HONO", "CH3I", "Br2", "I2", "ClO", "BrO", "HCHO", "NO3",
         "N2O5", "H2O2", "CO2", "N2", "CH4", "NH3", "HCl", "HBr"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import canon_species

check = {}
for s in CHECK:
    c = canon_species(s)
    recs = [r for r in xs if (r.get("species_canonical") or r["species"]) == c]
    recd = [r for r in recs if r["recommended"]]
    check[s] = {"canonical": c, "n_datasets": len(recs), "n_recommended": len(recd),
                "recommended_ids": [r["id"] for r in recd][:12],
                "sources": dict(collections.Counter(r["source"] for r in recs))}

stats = {
    "totals": dict(tot),
    "total_clean_bytes_all_files": sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, fn in os.walk(clean) for f in fn),
    "index_bytes": os.path.getsize(os.path.join(clean, "index.json")),
    "top100_species": [[k, v["xs"], {s: v[s] for s in ("tuvx", "mainz2013", "leiden", "bremen", "cfa") if v[s]}, v["recommended_xs"]] for k, v in top],
    "check_species": check,
    "per_source": {k: dict(v) for k, v in per_source.items()},
}
with open(stats_out, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=1)
print(json.dumps({k: stats[k] for k in ("totals", "total_clean_bytes_all_files", "index_bytes", "per_source")}, indent=1))
