"""Shared helpers for the cross-section archive build.

All scripts are run as `python -I script.py <args>`; each script inserts its own
directory on sys.path to import this module (scripts dir only, never data dirs).
"""
import json, os, re, math, unicodedata

UNITS_XS = "cm2/molecule"
UNITS_QY = "dimensionless"

LICENSES = {
    "tuvx": "Apache-2.0 (NCAR TUV-x repository); underlying data from the cited publications",
    "mainz2013": "CC-BY-4.0 (Zenodo record 10.5281/zenodo.6951, MPI-Mainz UV/VIS Spectral Atlas snapshot 2013-06-24); cite Keller-Rudek et al. 2013 and the original paper",
    "leiden": "No license stated by the Leiden photodissociation database; site asks users to cite Heays et al. 2017 / Hrodmarsson & van Dishoeck 2023 and the original sources",
    "bremen": "No license stated (IUP Bremen MolSpec lab download page); cite the originating publication",
    "cfa": "No license stated (Harvard-Smithsonian CfA AMP molecular database); cite the originating publication",
}

# Canonical formula aliases (source formula -> canonical) for per-species totals.
ALIASES = {
    "HCHO": "CH2O", "H2CO": "CH2O", "HONO": "HONO", "HNO2": "HONO",
    "CH3COCH3": "CH3COCH3", "ACETONE": "CH3COCH3",
    "CLO": "ClO", "BRO": "BrO", "BRONO2": "BrONO2", "CL2O2": "ClOOCl", "Cl2O2": "ClOOCl",
    "HO2NO2": "HO2NO2", "HNO4": "HO2NO2", "CHOCHO": "CHOCHO", "HCOCHO": "CHOCHO",
    "CH3BR": "CH3Br", "CH3CL": "CH3Cl", "CHBR3": "CHBr3", "CH2BR2": "CH2Br2",
    "CFCL3": "CFCl3", "CFC-11": "CFCl3", "CF2CL2": "CF2Cl2", "CFC-12": "CF2Cl2",
    "CFC113": "CF2ClCFCl2", "CFC-113": "CF2ClCFCl2", "CFC114": "CF2ClCF2Cl", "CFC-114": "CF2ClCF2Cl",
    "CFC115": "CF3CF2Cl", "CFC-115": "CF3CF2Cl", "HCFC22": "CHClF2", "HCFC141b": "CH3CFCl2",
    "HCFC142b": "CH3CF2Cl", "H1301": "CF3Br", "H2402": "CF2BrCF2Br",
    "CF2O": "COF2", "CCl2O": "COCl2", "CClFO": "COFCl", "COFCl": "COFCl",
}


ALIASES.update({
    "CH3COCH3": "CH3C(O)CH3", "ACETONE": "CH3C(O)CH3", "HONO2": "HNO3", "CHClF2": "CHF2Cl", "HCFC22": "CHF2Cl",
    "CF2BrCl": "CF2ClBr", "H2CO": "CH2O", "HCHO": "CH2O",
})
TRADE = re.compile(r"\((?:CFC|HCFC|HFC|HFE|HCFE|PFC|Halon|halon)[- ]?[^)]*\)$")


def canon_species(s):
    if s is None:
        return None
    s = s.strip()
    s = TRADE.sub("", s).strip()
    return ALIASES.get(s, s)


def slug(s, maxlen=120):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9.+=\-]+", "_", s).strip("_")
    return s[:maxlen]


def parse_T(s):
    """'298K' -> 298.0 ; '293-298K' -> [293, 298] ; 'room temperature' -> None"""
    if s is None:
        return None
    s = str(s)
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*K", s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return [min(a, b), max(a, b)]
    m = re.search(r"(\d+(?:\.\d+)?)\s*K", s)
    if m:
        return float(m.group(1))
    return None


def finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def num(x):
    """Return a JSON-safe number keeping full parsed precision (python float repr is round-trip exact)."""
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e15:
        return x  # keep float (json writes 298.0)
    return x


def make_record(**kw):
    data = kw.pop("data")
    data = [[float(a), float(b)] for a, b in data]
    data.sort(key=lambda r: r[0])
    outliers = []
    if kw.get("units", UNITS_XS) == UNITS_XS:
        # physically impossible values (|sigma| > 1e-11 cm2; sharp atomic/molecular lines can legitimately exceed 1e-14) are source typos; drop and record them
        outliers = [r for r in data if abs(r[1]) > 1e-11]
        if data and len(outliers) > 0.5 * len(data):
            # the whole dataset is not in cm2/molecule (e.g. optical densities or relative units)
            kw["units"] = "relative/unknown (source values are not cm2/molecule)"
            kw["notes"] = ((kw.get("notes") or "") + " Most values exceed 1e-11, so the source values are not absolute cross sections in cm2/molecule (e.g. optical density or relative units); see comments.").strip()
            outliers = []
        elif outliers:
            data = [r for r in data if abs(r[1]) <= 1e-11]
            kw["n_dropped_rows"] = kw.get("n_dropped_rows", 0) + len(outliers)
            kw["notes"] = ((kw.get("notes") or "") + f" Dropped {len(outliers)} row(s) with |sigma|>1e-11 cm2 as source errors: {outliers[:5]}.").strip()
    lam = [r[0] for r in data]
    rec = {
        "id": kw["id"],
        "species": kw["species"],
        "species_canonical": canon_species(kw["species"]),
        "name": kw.get("name"),
        "cas": kw.get("cas"),
        "source": kw["source"],
        "file": kw["file"],
        "T_K": kw.get("T_K"),
        "lambda_nm": [min(lam), max(lam)] if lam else None,
        "n_points": len(data),
        "units": kw.get("units", UNITS_XS),
        "lambda_medium": kw.get("lambda_medium", "unknown"),
        "reference": kw.get("reference") or {"authors": None, "year": None, "title": None, "journal": None, "doi": None},
        "recommended": bool(kw.get("recommended", False)),
        "license": kw.get("license") or LICENSES[kw["source"]],
        "n_dropped_rows": kw.get("n_dropped_rows", 0),
    }
    for k in ("kind", "category", "comments", "notes", "original_axis", "resolution", "phase",
              "compilation_citation", "original_references", "extra", "uncertainty", "lambda_medium_basis", "tags"):
        if kw.get(k) not in (None, "", [], {}):
            rec[k] = kw[k]
    rec["data"] = data
    return rec


def write_record(rec, outdir):
    os.makedirs(outdir, exist_ok=True)
    fn = slug(rec["id"].split(":", 1)[1]) + ".json"
    path = os.path.join(outdir, fn)
    if os.path.exists(path):
        base = path[:-5]
        i = 2
        while os.path.exists(f"{base}__{i}.json"):
            i += 1
        path = f"{base}__{i}.json"
        rec["id"] = rec["id"] + f"__{i}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


def parse_numeric_rows(lines, decimal_comma=False, min_cols=2):
    """Yield (list_of_floats) for numeric lines; return (rows, n_dropped) where dropped counts
    non-empty lines that started looking like data (first token numeric) but failed to parse fully,
    plus non-finite rows."""
    rows, dropped = [], 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if decimal_comma:
            parts = re.split(r"[\t;]+|\s{2,}|\s", s)
            parts = [p.replace(",", ".") for p in parts if p != ""]
        else:
            parts = [p for p in re.split(r"[\s,;]+", s) if p != ""]
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            # count as dropped only once data has started and the line begins with a number
            # (a data row with junk); header/footer prose is not counted
            if rows:
                try:
                    float(parts[0])
                    dropped += 1
                except (ValueError, IndexError):
                    pass
            continue
        if len(vals) < min_cols or not all(math.isfinite(v) for v in vals):
            if rows:
                dropped += 1
            continue
        rows.append(vals)
    return rows, dropped


JPL_EVALS = {
    "94": ("W.B. DeMore et al.", 1994, "Chemical Kinetics and Photochemical Data for Use in Stratospheric Modeling, Evaluation Number 11", "JPL Publication 94-26", None),
    "97": ("W.B. DeMore et al.", 1997, "Chemical Kinetics and Photochemical Data for Use in Stratospheric Modeling, Evaluation Number 12", "JPL Publication 97-4", None),
    "02": ("S.P. Sander et al.", 2003, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation Number 14", "JPL Publication 02-25", None),
    "06": ("S.P. Sander et al.", 2006, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation Number 15", "JPL Publication 06-2", None),
    "10": ("S.P. Sander et al.", 2011, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation Number 17", "JPL Publication 10-6", None),
    "11": ("S.P. Sander et al.", 2011, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation Number 17", "JPL Publication 10-6", None),
    "15": ("J.B. Burkholder et al.", 2015, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation No. 18", "JPL Publication 15-10", None),
    "19": ("J.B. Burkholder et al.", 2019, "Chemical Kinetics and Photochemical Data for Use in Atmospheric Studies, Evaluation No. 19", "JPL Publication 19-5", None),
}


def jpl_reference(tag):
    a, y, t, j, d = JPL_EVALS[tag]
    return {"authors": a, "year": y, "title": t, "journal": j, "doi": d}


def empty_ref():
    return {"authors": None, "year": None, "title": None, "journal": None, "doi": None}
