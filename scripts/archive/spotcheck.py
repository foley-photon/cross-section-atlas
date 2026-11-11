"""Spot-check sigma at reference wavelengths. usage: python -I spotcheck.py <clean_dir> <out_json>"""
import sys, os, json, glob, bisect

clean, out = sys.argv[1:3]
idx = json.load(open(os.path.join(clean, "index.json"), encoding="utf-8"))["datasets"]


def load(path):
    return json.load(open(os.path.join(clean, path), encoding="utf-8"))["data"]


def interp(d, x):
    xs = [r[0] for r in d]
    i = bisect.bisect_left(xs, x)
    if i == 0 or i >= len(xs):
        if i < len(xs) and abs(xs[i] - x) < 1e-6:
            return d[i][1], 0.0
        return None, None
    x0, y0 = d[i - 1]; x1, y1 = d[i]
    gap = x1 - x0
    if gap > 2.0:
        return None, gap
    return y0 + (y1 - y0) * (x - x0) / gap if gap else y0, gap


def roomT(t):
    if t is None:
        return True
    if isinstance(t, list):
        return t[1] >= 285 and t[0] <= 305
    return 285 <= t <= 305


CHECKS = [
    ("O3", 253.65, 1.13e-17, "point"),
    ("NO2", 400.0, 6e-19, "point"),
    ("O2", 121.6, 1e-20, "point"),
    ("Cl2", 330.0, 2.6e-19, "peak300-360"),
    ("H2O", 121.6, 1.4e-17, "point"),
]
res = {}
for sp, lam, refv, mode in CHECKS:
    hits = []
    for r in idx:
        if not r["path"].startswith("xs/") or (r.get("species_canonical") or r["species"]) != sp:
            continue
        if not r["lambda_nm"] or not roomT(r["T_K"]):
            continue
        if mode == "point":
            if not (r["lambda_nm"][0] <= lam <= r["lambda_nm"][1]):
                continue
            v, gap = interp(load(r["path"]), lam)
            if v is None:
                continue
            hits.append({"id": r["id"], "T_K": r["T_K"], "rec": r["recommended"], "sigma": v, "grid_gap_nm": gap, "ratio": v / refv})
        else:
            if r["lambda_nm"][1] < 300 or r["lambda_nm"][0] > 360:
                continue
            d = [p for p in load(r["path"]) if 300 <= p[0] <= 360]
            if len(d) < 3:
                continue
            pk = max(d, key=lambda p: p[1])
            hits.append({"id": r["id"], "T_K": r["T_K"], "rec": r["recommended"], "peak_nm": pk[0], "sigma": pk[1], "ratio": pk[1] / refv})
    res[f"{sp} @ {lam} ({mode})"] = {"reference": refv, "n": len(hits), "hits": sorted(hits, key=lambda h: (not h["rec"], h["id"]))}
json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
for k, v in res.items():
    rs = [h["ratio"] for h in v["hits"]]
    rs.sort()
    med = rs[len(rs) // 2] if rs else None
    print(f"== {k}: ref {v['reference']:.3g}, n={v['n']}, median ratio={med}")
    for h in v["hits"][:40]:
        print("   ", ("REC " if h["rec"] else "    ") + h["id"][:70].ljust(70), h["T_K"], "%.3e" % h["sigma"], "ratio %.2f" % h["ratio"], ("peak %.2f" % h["peak_nm"]) if "peak_nm" in h else ("gap %.3g" % h["grid_gap_nm"]))
