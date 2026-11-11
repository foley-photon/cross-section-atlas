"""Process the MPI-Mainz UV/VIS Spectral Atlas 2013-06-24 Zenodo snapshot -> clean JSON.
usage: python -I proc_mainz.py <extracted_root> <clean_dir>
"""
import sys, os, re, json, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import make_record, write_record, parse_T, UNITS_QY, LICENSES, empty_ref

root, clean = sys.argv[1:3]
SRC = "mainz2013"
COMPILATION = ("H. Keller-Rudek, G.K. Moortgat, R. Sander, and R. Sörensen, The MPI-Mainz UV/VIS Spectral Atlas of "
               "Gaseous Molecules of Atmospheric Interest, Earth Syst. Sci. Data 5, 365-373 (2013), doi:10.5194/essd-5-365-2013; "
               "snapshot doi:10.5281/zenodo.6951")


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_index(path):
    txt = open(path, encoding="latin-1").read()
    meta = {}
    for block in re.split(r"<HR>", txt):
        m = re.search(r'<a href="([^"]+)">', block)
        if not m:
            continue
        href = html.unescape(m.group(1))
        fields = {}
        for k, v in re.findall(r"<TR><TD>([A-Z]+): </TD><TD>(.*?)</TD></TR>", block, re.S):
            fields[k] = v
        # comments: rows after COMMENTS with empty first cell
        cm = re.search(r"<TD>COMMENTS: </TD><TD>.*?</TD></TR>(.*?)</TABLE>", block, re.S)
        comments = []
        if cm:
            for v in re.findall(r"<TR><TD></TD><TD>(.*?)</TD></TR>", cm.group(1), re.S):
                comments.append(strip_tags(v))
        fields["COMMENTS_TEXT"] = "\n".join(c for c in comments if c)
        meta[href.replace("\\", "/")] = fields
    return meta


def parse_bib(bib, quotation):
    r = empty_ref()
    b = strip_tags(bib)
    r["citation_text"] = b
    m = re.match(r'^(.*?),?\s*"(.+?),?"\s*,?\s*(.*)$', b, re.S)
    if m:
        r["authors"] = m.group(1).strip().rstrip(",")
        r["title"] = m.group(2).strip().rstrip(",")
        r["journal"] = m.group(3).strip()
    my = re.search(r"\((\d{4})\)", quotation or "")
    if my:
        r["year"] = int(my.group(1))
    else:
        ys = re.findall(r"\((\d{4})\)", b)
        if ys:
            r["year"] = int(ys[-1])
    md = re.search(r"(10\.\d{4,9}/\S+)", b)
    if md:
        r["doi"] = md.group(1).rstrip(".,;")
    return r


def medium_from(comments):
    c = comments or ""
    if re.search(r"vacuum wavelength|wavelengths? (?:in|are in|given in) vacuum|in vacuo|vac\. wavelength", c, re.I):
        return "vacuum", "dataset comment states vacuum wavelengths"
    if re.search(r"air wavelength|wavelengths? (?:in|are in|given in) (?:standard )?air", c, re.I):
        return "air", "dataset comment states air wavelengths"
    return "unknown", None


PM = re.compile(r"^\s*([0-9.]+)\s+\(?\s*([0-9.]+)\s*(?:\xb1|\+/-|\+-)?\s*([0-9.]+)?\s*\)?\s*[eE]\s*([-+]?\d+)\s*$")
NUMRE = r"[-+]?[0-9.]+(?:[eE][-+]?\d+)?"
CENTER_RANGE = re.compile(r"^\s*([0-9.]+)\s+([0-9.]+)\s*-\s*([0-9.]+)\s+(" + NUMRE + r")\s*$")
BAND = re.compile(r"^\s*(\d+)\s*,\s*(\d+)\s+([0-9.]+)\s+(" + NUMRE + r")(?:\s+" + NUMRE + r")*\s*$")
PM_NOEXP = re.compile(r"^\s*([0-9.]+)\s+(" + NUMRE + r")\s*(?:\xb1|\+/-)\s*(" + NUMRE + r")\s*(?:\(.*\))?\s*$")
RANGE = re.compile(r"^\s*([0-9.]+)\s*-\s*([0-9.]+)\s+([-+0-9.eE]+)\s*$")


def parse_file(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        txt = raw.decode("utf-16")
    else:
        txt = raw.decode("latin-1").replace("\x00", "")
    header_lines, rows, extra_rows, unc, dropped = [], [], [], [], 0
    notes = set()
    for line in txt.splitlines():
        s = line.strip()
        if not s:
            continue
        parts = [p for p in re.split(r"[\s;]+", s) if p]
        m = RANGE.match(s)
        if m:
            try:
                lo, hi, v = float(m.group(1)), float(m.group(2)), float(m.group(3))
                if hi > lo:
                    rows.append([(lo + hi) / 2, v])
                    notes.add("wavelength-interval rows stored at the interval midpoint")
                    continue
            except ValueError:
                pass
        try:
            vals = [float(p) for p in parts]
            if len(vals) >= 2:
                rows.append(vals)
                continue
            else:
                dropped += 1
                continue
        except ValueError:
            pass
        m = PM.match(s)
        if m:
            lam = float(m.group(1)); a = float(m.group(2)); e = int(m.group(4))
            rows.append([lam, a * 10 ** e] + ([float(m.group(3)) * 10 ** e] if m.group(3) else []))
            notes.add("values parsed from '(value ± error)eN' notation; third column = stated error")
            continue
        m = CENTER_RANGE.match(s)
        if m:
            rows.append([float(m.group(1)), float(m.group(4))])
            notes.add("rows given as 'centre  lower - upper  value'; stored at the stated centre wavelength")
            continue
        m = BAND.match(s)
        if m:
            rows.append([float(m.group(3)), float(m.group(4))])
            notes.add("band-peak rows with (v',v'') labels; label column dropped")
            continue
        m = PM_NOEXP.match(s)
        if m:
            rows.append([float(m.group(1)), float(m.group(2)), float(m.group(3))])
            notes.add("values parsed from 'value ± error' notation; third column = stated error")
            continue
        m = RANGE.match(s)
        if m:
            try:
                lo, hi, v = float(m.group(1)), float(m.group(2)), float(m.group(3))
                rows.append([(lo + hi) / 2, v])
                notes.add("wavelength-interval rows stored at the interval midpoint")
                continue
            except ValueError:
                pass
        try:
            float(parts[0].replace(",", "."))
            dropped += 1  # starts like data but not parseable
        except ValueError:
            header_lines.append(s)
    return rows, dropped, header_lines, sorted(notes)


def run(kind):
    idx = os.path.join(root, "cross_sections.html" if kind == "xs" else "quantum_yields.html")
    meta = parse_index(idx)
    base = os.path.join(root, "cross_sections" if kind == "xs" else "quantum_yields")
    n = 0; missing_meta = 0; empty = []
    for dp, dn, fns in os.walk(base):
        for fn in sorted(fns):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            md = meta.get(rel)
            if md is None:
                missing_meta += 1
                md = {}
            rows, dropped, hdr, notes = parse_file(p)
            if not rows:
                empty.append(rel)
                continue
            formula = strip_tags(md.get("CHEMFORMULA", "")) or fn.split("_")[0]
            channel = None
            mch = re.match(r"^(.*?)\{(.+)\}$", formula)
            if mch:
                formula, channel = mch.group(1), mch.group(2)
            comments = md.get("COMMENTS_TEXT", "")
            medium, mbasis = medium_from(comments)
            ncols = max(len(r) for r in rows)
            data = [[r[0], r[1]] for r in rows]
            extra = {}
            if ncols > 2:
                hl = " | ".join(hdr)
                cols = [[(r[i] if len(r) > i else None) for r in rows] for i in range(2, ncols)]
                label = "stated error/uncertainty" if re.search(r"err|uncert|dev|sigma", hl, re.I) or any("±" in x for x in notes) else "unlabelled additional column(s)"
                extra["extra_columns"] = {"label": label, "header_lines": hdr[:5], "values": cols}
            tag = re.findall(r"\(([^()]*)\)\.txt$", fn)
            rec_flag = bool(tag and re.search(r"(^|,)\s*rec\s*(,|$)", tag[0]))
            category = strip_tags(md.get("CATEGORY", ""))
            sub = strip_tags(md.get("SUBCATEGORY", ""))
            if sub and sub != "---":
                category = f"{category}/{sub}"
            if channel:
                extra["channel"] = channel
            if hdr and "extra_columns" not in extra:
                extra["header_lines"] = hdr[:5]
            rec = make_record(
                id=f"{SRC}:{'qy_' if kind == 'qy' else ''}{fn[:-4]}", species=formula,
                name=strip_tags(md.get("CHEMNAME", "")) or None, source=SRC, file=rel,
                T_K=parse_T(md.get("TEMPERATURE")) if md.get("TEMPERATURE") else parse_T(fn),
                units=UNITS_QY if kind == "qy" else "cm2/molecule",
                lambda_medium=medium, lambda_medium_basis=mbasis,
                reference=parse_bib(md.get("BIBLIOGRAPHY", ""), md.get("QUOTATION", "")),
                recommended=rec_flag, n_dropped_rows=dropped, data=data,
                kind="quantum_yield" if kind == "qy" else "cross_section",
                category=category or None, comments=comments or None,
                notes="; ".join(notes) or None, compilation_citation=COMPILATION,
                extra=extra or None,
                tags={"filename_tag": tag[0]} if tag else None,
            )
            write_record(rec, os.path.join(clean, kind, SRC))
            n += 1
    return n, missing_meta, empty


res = {}
for kind in ("xs", "qy"):
    n, mm, empty = run(kind)
    res[kind] = {"written": n, "missing_metadata": mm, "no_numeric_rows": empty}
    print(kind, "written", n, "missing meta", mm, "empty", len(empty))
with open(os.path.join(clean, "_logs", "mainz_log.json"), "w", encoding="utf-8") as f:
    json.dump(res, f, indent=1, ensure_ascii=False)
