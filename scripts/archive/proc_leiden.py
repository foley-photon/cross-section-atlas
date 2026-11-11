"""Process Leiden photodissociation DB combined text files -> clean JSON (photoabsorption column).
usage: python -I proc_leiden.py <extracted_txt_root> <clean_dir> <bundle_date>
"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import make_record, write_record, parse_numeric_rows, LICENSES

root, clean, bundle_date = sys.argv[1:4]
SRC = "leiden"
COMP = ("A.N. Heays, A.D. Bosman, and E.F. van Dishoeck, Photodissociation and photoionisation of atoms and molecules of "
        "astrophysical interest, A&A 602, A105 (2017), doi:10.1051/0004-6361/201628742; H.R. Hrodmarsson and E.F. van Dishoeck, "
        "Photodissociation and photoionization of molecules of astronomical interest: updates to the Leiden photodissociation and "
        "ionization cross section database, A&A 675, A25 (2023), doi:10.1051/0004-6361/202346645")
REF = {"authors": "A.N. Heays, A.D. Bosman, E.F. van Dishoeck", "year": 2017,
       "title": "Photodissociation and photoionisation of atoms and molecules of astrophysical interest",
       "journal": "Astron. Astrophys. 602, A105", "doi": "10.1051/0004-6361/201628742",
       "note": "Compilation reference; the original measurements/calculations are listed in original_references and must also be cited."}

mapping = {}
for line in open(os.path.join(root, "_unzip_map.tsv"), encoding="utf-8"):
    a, b = line.rstrip("\n").split("\t")
    mapping[b] = a
n = 0
log = []
for local, orig in sorted(mapping.items()):
    if not local.endswith(".txt"):
        continue
    species = orig.replace("\\", "/").split("/")[-2]
    p = os.path.join(root, *local.split("/"))
    lines = open(p, encoding="latin-1").read().splitlines()
    hdr = [l for l in lines if l.startswith("#")]
    colline = [l for l in hdr if re.match(r"#\s*wavelength\s+\w", l)]
    cols = colline[-1].lstrip("#").split() if colline else ["wavelength", "photoabsorption"]
    if "photoabsorption" in cols:
        ci, kind_col = cols.index("photoabsorption"), "photoabsorption"
    elif "photoionisation" in cols:
        ci, kind_col = cols.index("photoionisation"), "photoionisation"
    else:
        log.append((orig, "no usable column", cols)); continue
    rows, dropped = parse_numeric_rows([l for l in lines if not l.startswith("#")])
    data = [[r[0], r[ci]] for r in rows if len(r) > ci]
    dropped += sum(1 for r in rows if len(r) <= ci)
    refs = []
    for l in hdr:
        if l.lower().startswith("# references:"):
            for item in l.split(":", 1)[1].split(","):
                item = item.strip()
                if not item:
                    continue
                parts = item.split(None, 1)
                refs.append({"key": parts[0], "doi_or_url": parts[1] if len(parts) > 1 else None})
    for l in hdr:
        m = re.match(r"#\s*([0-9.]+\s*-\s*[0-9.]+)\s+(\S+)\s+(10\.\S+|http\S+)", l)
        if m:
            refs.append({"key": m.group(2), "doi_or_url": m.group(3), "lambda_range_nm": m.group(1).replace(" ", "")})
        m = re.match(r"#\s*(Photodissociation|Photoionization|Photoionisation|Photoabsorption) source:\s*(.+)$", l, re.I)
        if m:
            refs.append({"key": m.group(2).strip(), "doi_or_url": None, "role": m.group(1).lower()})
    # dedupe
    seen, urefs = set(), []
    for r in refs:
        k = (r["key"], r.get("doi_or_url"), r.get("lambda_range_nm"))
        if k not in seen:
            seen.add(k); urefs.append(r)
    comments = "\n".join(l.lstrip("# ").rstrip() for l in hdr)[:6000]
    rec = make_record(
        id=f"{SRC}:{species}", species=species, name=None, source=SRC,
        file=orig.lstrip("./").replace("../", ""), T_K=None, lambda_medium="unknown",
        lambda_medium_basis="Leiden documentation does not state air or vacuum (VUV data are conventionally vacuum wavelengths)",
        reference=REF, recommended=False, n_dropped_rows=dropped, data=data, kind="cross_section",
        comments=comments, compilation_citation=COMP, original_references=urefs,
        notes=(f"Column used: {kind_col} (total photoabsorption unless noted). Other columns in the source "
               f"({', '.join(c for c in cols[1:] if c != kind_col)}) are kept only in raw/. Text bundle dated {bundle_date}."),
    )
    write_record(rec, os.path.join(clean, "xs", SRC))
    n += 1
print("written", n, "problems", log)
