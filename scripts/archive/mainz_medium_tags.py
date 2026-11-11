"""Set lambda_medium from Mainz filename tags '(air)'/'(vac)' when comments did not state it.
usage: python -I mainz_medium_tags.py <clean_dir>"""
import sys, os, glob, json, re
n = 0
for f in glob.glob(os.path.join(sys.argv[1], "xs", "mainz2013", "*.json")) + glob.glob(os.path.join(sys.argv[1], "qy", "mainz2013", "*.json")):
    r = json.load(open(f, encoding="utf-8"))
    tag = (r.get("tags") or {}).get("filename_tag", "")
    if r["lambda_medium"] != "unknown" or not tag:
        continue
    toks = [t.strip().lower() for t in tag.split(",")]
    med = "air" if "air" in toks else "vacuum" if ("vac" in toks or "vacuum" in toks) else None
    if med:
        r["lambda_medium"] = med
        r["lambda_medium_basis"] = f"Mainz filename tag '({tag})'"
        json.dump(r, open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        n += 1
print("updated", n)
