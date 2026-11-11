"""Verify / fill DOIs for the hand-entered Bremen and CfA references via the public Crossref API,
then patch the clean JSON files.  usage: python -I doi_check.py <clean_dir>
"""
import sys, os, json, glob, re, difflib, time, urllib.request, urllib.parse, urllib.error

clean = sys.argv[1]
UA = {"User-Agent": "cdfoley-xsec-archive/1.0 (data curation script)"}


def get(url):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1)); continue
            raise
    raise RuntimeError("rate limited")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


files = sorted(glob.glob(os.path.join(clean, "xs", "bremen", "*.json")) + glob.glob(os.path.join(clean, "xs", "cfa", "*.json")))
refs = {}
for f in files:
    r = json.load(open(f, encoding="utf-8"))["reference"]
    key = (r.get("title"), r.get("year"))
    refs.setdefault(key, {"ref": r, "files": []})["files"].append(f)

results = {}
for (title, year), v in refs.items():
    r = v["ref"]
    out = {"title": title, "given_doi": r.get("doi")}
    prev = r.get("doi_check", "")
    if prev.startswith(("verified", "filled")):
        out["status"] = "verified" if prev.startswith("verified") else "filled"
        out["crossref_doi"] = r.get("doi"); out["score"] = None
        results[f"{title} ({year})"] = out
        continue
    if prev.startswith("WARNING") or "404" in prev:
        out["rejected_doi"] = r.get("doi")
        r["doi"] = None
    try:
        if r.get("doi"):
            w = get("https://api.crossref.org/works/" + urllib.parse.quote(r["doi"]))["message"]
            t = (w.get("title") or [""])[0]
            out.update(crossref_title=t, score=round(sim(t, title), 3), status="verified" if sim(t, title) > 0.8 else "MISMATCH")
        else:
            q = urllib.parse.urlencode({"query.bibliographic": f"{title} {r.get('authors','')} {r.get('journal','')}", "rows": 3})
            items = get("https://api.crossref.org/works?" + q)["message"]["items"]
            best = max(items, key=lambda w: sim((w.get("title") or [""])[0], title)) if items else None
            if best:
                t = (best.get("title") or [""])[0]
                s = sim(t, title)
                yr = (best.get("issued", {}).get("date-parts") or [[None]])[0][0]
                out.update(crossref_title=t, crossref_doi=best.get("DOI"), crossref_year=yr, score=round(s, 3),
                           status="filled" if s > 0.85 and (year is None or yr is None or abs(yr - year) <= 1) else "no-confident-match")
            else:
                out["status"] = "no-result"
    except Exception as e:
        out["status"] = f"error: {e}"
    results[f"{title} ({year})"] = out
    time.sleep(1.5)

for (title, year), v in refs.items():
    res = results[f"{title} ({year})"]
    for f in v["files"]:
        rec = json.load(open(f, encoding="utf-8"))
        ref = rec["reference"]
        if res.get("rejected_doi"):
            ref["doi"] = None
        if res["status"] == "verified":
            if not ref.get("doi_check", "").startswith("verified"):
                ref["doi_check"] = "verified against Crossref title"
        elif res["status"] == "filled":
            ref["doi"] = res["crossref_doi"] or ref.get("doi")
            ref["doi_check"] = f"filled from Crossref bibliographic match (title similarity {res['score']})"
        elif res["status"] == "MISMATCH":
            ref["doi_check"] = f"WARNING: given DOI resolves to a different title on Crossref: {res.get('crossref_title')}"
        else:
            ref["doi_check"] = "not found on Crossref (" + res["status"] + ")"
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

os.makedirs(os.path.join(clean, "_logs"), exist_ok=True)
with open(os.path.join(clean, "_logs", "doi_check.json"), "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1, ensure_ascii=False)
for k, v in results.items():
    print(v["status"], "|", k[:90], "|", v.get("crossref_doi") or v.get("given_doi"), v.get("score"))
