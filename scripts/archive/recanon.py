"""Re-apply canon_species to species_canonical in every clean JSON. usage: python -I recanon.py <clean_dir>"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import canon_species
n = 0
for f in glob.glob(os.path.join(sys.argv[1], "**", "*.json"), recursive=True):
    if os.path.basename(f) == "index.json" or "_logs" in f:
        continue
    r = json.load(open(f, encoding="utf-8"))
    c = canon_species(r["species"])
    if r.get("species_canonical") != c:
        r["species_canonical"] = c
        json.dump(r, open(f, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        n += 1
print("updated", n)
