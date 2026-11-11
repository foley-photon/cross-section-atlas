"""Process NCAR TUV-x data files -> clean JSON.
usage: python -I proc_tuvx.py <tuvx_root> <clean_dir> <commit_sha> <tag>
"""
import sys, os, re, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import netCDF4
from xs_common import make_record, write_record, jpl_reference, empty_ref, parse_T, UNITS_QY, LICENSES

root, clean, sha, tag = sys.argv[1:5]
SRC = "tuvx"
LIC = LICENSES[SRC] + f"; TUV-x {tag} commit {sha}"

NAME_FIX = {  # filename stem -> (formula, name)
    "1-C4H9ONO2": ("1-C4H9ONO2", "n-butyl nitrate"), "2-C4H9ONO2": ("2-C4H9ONO2", "2-butyl nitrate"),
    "ACETONE": ("CH3COCH3", "acetone"), "BRONO2": ("BrONO2", "bromine nitrate"), "BRO": ("BrO", "bromine monoxide"),
    "CF2CL2": ("CF2Cl2", "CFC-12"), "CFC-113": ("CF2ClCFCl2", "CFC-113"), "CFC113": ("CF2ClCFCl2", "CFC-113"),
    "CFC-114": ("CF2ClCF2Cl", "CFC-114"), "CFC114": ("CF2ClCF2Cl", "CFC-114"), "CFC-115": ("CF3CF2Cl", "CFC-115"),
    "CFC115": ("CF3CF2Cl", "CFC-115"), "CFC-11": ("CFCl3", "CFC-11"), "CFC-12": ("CF2Cl2", "CFC-12"),
    "CFCL3": ("CFCl3", "CFC-11"), "CH2BR2": ("CH2Br2", "dibromomethane"), "CH3BR": ("CH3Br", "bromomethane"),
    "CH3CL": ("CH3Cl", "chloromethane"), "CHBR3": ("CHBr3", "bromoform"), "CL2O2": ("ClOOCl", "chlorine peroxide"),
    "Cl2O2": ("ClOOCl", "chlorine peroxide"), "CLO": ("ClO", "chlorine monoxide"), "H1301": ("CF3Br", "Halon-1301"),
    "H2402": ("CF2BrCF2Br", "Halon-2402"), "HCFC141b": ("CH3CFCl2", "HCFC-141b"), "HCFC142b": ("CH3CF2Cl", "HCFC-142b"),
    "HCFC22": ("CHClF2", "HCFC-22"), "HNO2": ("HONO", "nitrous acid"), "HO2NO2": ("HO2NO2", "peroxynitric acid"),
    "HNO4": ("HO2NO2", "peroxynitric acid"), "Hydroxyacetone": ("CH3COCH2OH", "hydroxyacetone"),
    "MVK": ("CH3COCH=CH2", "methyl vinyl ketone"), "Methacrolein": ("CH2=C(CH3)CHO", "methacrolein"),
    "perfluoro 1-iodopropane": ("C3F7I", "perfluoro-1-iodopropane"), "t-butyl-nitrite": ("(CH3)3CONO", "t-butyl nitrite"),
    "nC3H7ONO2": ("n-C3H7ONO2", "n-propyl nitrate"), "NO3-(aq)": ("NO3-(aq)", "aqueous nitrate"),
    "CH3CH2ONO2": ("C2H5ONO2", "ethyl nitrate"), "CH3CHONO2CH3": ("i-C3H7ONO2", "isopropyl nitrate"),
    "CH3CH3NNO": ("(CH3)2NNO", "N-nitrosodimethylamine"), "CF2O": ("COF2", "carbonyl fluoride"),
    "CCl2O": ("COCl2", "phosgene"), "CClFO": ("COFCl", "carbonyl chlorofluoride"), "COF2": ("COF2", "carbonyl fluoride"),
    "CH2CHCHO": ("CH2=CHCHO", "acrolein"), "PAN": ("CH3C(O)OONO2", "peroxyacetyl nitrate"),
    "PPN": ("C2H5C(O)OONO2", "peroxypropionyl nitrate"), "HOCH2CHO": ("HOCH2CHO", "glycolaldehyde"),
    "CHOCHO": ("CHOCHO", "glyoxal"),
}


def parse_stem(fn):
    stem = fn[:-3]
    m = re.match(r"^(.*?)_(JPL\d\d|\d+|tyndall|Mills|mills|temp_JPL06|JPL06_base|JPL06_218K|JPL06_298K|2H_O3P|H2_O1D|H_OH)$", stem)
    sp = m.group(1) if m else stem
    variant = m.group(2) if m else ""
    channel = None
    if "-" in sp and sp.split("-")[0] in ("CHOCHO", "NO3") and not sp.endswith("(aq)"):
        sp, channel = sp.split("-", 1)
    return stem, sp, variant, channel


def decode(s):
    return s if isinstance(s, str) else str(s)


def ref_from(fn, hdr):
    m = re.search(r"JPL(\d\d)", fn)
    if m and m.group(1) in ("06", "10", "19"):
        return jpl_reference(m.group(1)), True, f"JPL tag in filename ({m.group(0)})"
    h = hdr or ""
    m = re.search(r"JPL Publication (\d\d)[-, ]", h)
    if m and m.group(1) in ("94", "97", "19", "06", "10", "15", "02"):
        return jpl_reference(m.group(1)), True, f"header cites JPL Publication {m.group(1)}"
    m = re.search(r"JPL[ -]?(?:20)?(\d\d)(?!\d)", h)
    if m:
        y = m.group(1)
        key = {"06": "06", "11": "10", "10": "10", "97": "97", "94": "94", "02": "02", "15": "15", "19": "19"}.get(y)
        if key:
            return jpl_reference(key), True, f"header cites JPL evaluation ({m.group(0)})"
    if re.search(r"IUPAC", h, re.I):
        r = empty_ref()
        r["authors"] = "IUPAC Task Group on Atmospheric Chemical Kinetic Data Evaluation"
        my = re.search(r"IUPAC[ .-]*(\d{2,4})", h)
        if my:
            y = int(my.group(1))
            r["year"] = y + 1900 if y < 100 and y > 50 else (y + 2000 if y < 100 else y)
        r["title"] = "IUPAC evaluated data sheet (as cited in TUV-x header)"
        return r, True, "header cites IUPAC evaluation"
    # Mainz-style bibliography block
    r = empty_ref()
    mb = re.search(r"Bibliography:\s*(.+?)(?:\nComments:|\Z)", h, re.S)
    txt = mb.group(1).strip() if mb else None
    if not txt:
        # first line that looks like a citation
        for line in h.splitlines():
            if re.search(r"(19|20)\d\d", line) and re.search(r"J\.|Res\.|Chem|Phys|Lett|Sci", line):
                txt = line.strip()
                break
    if txt:
        r["title"] = None
        r["citation_text"] = re.sub(r"\s+", " ", txt)[:600]
        my = re.findall(r"(?:19|20)\d\d", txt)
        if my:
            r["year"] = int(my[-1])
    return r, False, None


def tuv_types():
    types = {}
    for cfg in [os.path.join(root, "data", "photolysis_rate_constants.json"), os.path.join(root, "examples", "tuv_5_4.json")]:
        txt = open(cfg, encoding="utf-8").read()
        try:
            o = json.loads(txt)
        except Exception:
            o = json.loads("{" + txt + "}")

        def walk(o, parent_type=None):
            if isinstance(o, dict):
                t = o.get("type")
                nd = o.get("netcdf files")
                if t and nd:
                    for it in nd:
                        fn = it.get("file path") if isinstance(it, dict) else it
                        types.setdefault(os.path.basename(fn), set()).add(t)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(o)
    return {k: sorted(v) for k, v in types.items()}


TYPES = tuv_types()
skipped = []
written = []


def process_nc(path, kind):
    fn = os.path.basename(path)
    d = netCDF4.Dataset(path)
    gattr = {k: decode(d.getncattr(k)) for k in d.ncattrs()}
    var = [k for k in d.variables if k.endswith("parameters")]
    wlk = [k for k in d.variables if k == "wavelength"]
    if not wlk or not var:
        skipped.append((fn, "no wavelength axis (polynomial/Taylor coefficients only; see TUV-x source)"))
        return
    v = d.variables[var[0]]
    hdr = decode(v.getncattr("hdr")) if "hdr" in v.ncattrs() else ""
    vunits = decode(v.getncattr("units")) if "units" in v.ncattrs() else None
    wl = np.array(d.variables["wavelength"][:], dtype=float)
    P = np.array(v[:], dtype=float)
    if P.ndim == 1:
        P = P[None, :]
    if P.shape[1] != wl.size and P.shape[0] == wl.size:
        P = P.T
    T = np.array(d.variables["temperature"][:], dtype=float) if "temperature" in d.variables else None
    stem, sp, variant, channel = parse_stem(fn)
    formula, name = NAME_FIX.get(sp, (sp, None))
    ref, rec_flag, rec_basis = ref_from(fn, hdr)
    ttypes = TYPES.get(fn, [])
    is_qy = kind == "qy"
    lo, hi = (0.0, 10.0) if is_qy else (1e-32, 1e-13)

    def valid(row):
        nz = np.abs(row[np.isfinite(row) & (row != 0)])
        return nz.size > 0 and lo <= np.median(nz) <= hi

    series = []  # (label, T_K, row)
    if T is not None and T.size == P.shape[0] and T.size > 1:
        for i in range(T.size):
            series.append((f"{int(round(T[i]))}K", float(T[i]), P[i]))
        extra = None
    else:
        Tk = float(T[0]) if T is not None and T.size == 1 else parse_T(re.search(r"Temperature:\s*([^\n]+)", hdr).group(1)) if re.search(r"Temperature:\s*([^\n]+)", hdr) else None
        if Tk is None:
            m = re.search(r"(?:at|,)\s*(\d{3})\s*K", hdr)
            Tk = float(m.group(1)) if m else None
        series.append(("", Tk, P[0]))
        extra = None
        if P.shape[0] > 1:
            extra = {"tuvx_parameter_rows": [[float(x) for x in P[i]] for i in range(1, P.shape[0])],
                     "note": "Additional TUV-x parameter rows (temperature-dependence coefficients) on the same wavelength grid; "
                             "row 0 is the reference cross section. Meaning depends on the TUV-x cross-section type: " + ", ".join(ttypes or ["(not referenced in configs)"])}
    for label, Tk, row in series:
        if not valid(row):
            skipped.append((fn + (f" [{label}]" if label else ""), "parameter row 0 is not a cross section/quantum yield (coefficients only)"))
            continue
        mask = np.isfinite(row) & np.isfinite(wl)
        data = [[float(a), float(b)] for a, b in zip(wl[mask], row[mask])]
        dropped = int((~mask).sum())
        notes = []
        if formula == "NO3-(aq)":
            notes.append("Aqueous-phase nitrate (converted molar absorptivity); not a gas-phase cross section.")
        if "x1000" in hdr and is_qy:
            mx = max(r[1] for r in data)
            notes.append(f"Header mentions original file values x1000; stored values max={mx:g} (as in NetCDF).")
        idbase = stem + (f"_{label}" if label else "")
        rec = make_record(
            id=f"{SRC}:{idbase}", species=formula, name=name, source=SRC,
            file=f"data/{'cross_sections' if not is_qy else 'quantum_yields'}/{fn}",
            T_K=Tk, units=UNITS_QY if is_qy else "cm2/molecule", lambda_medium="unknown",
            reference=ref, recommended=rec_flag, license=LIC, n_dropped_rows=dropped, data=data,
            kind="quantum_yield" if is_qy else "cross_section",
            comments=hdr.strip()[:4000] or None,
            notes=" ".join(notes) or None,
            extra=dict(extra or {}, **({"tuvx_types": ttypes} if ttypes else {}), **({"channel": channel} if channel else {}),
                       **({"netcdf_global_attrs": gattr} if gattr else {}), **({"recommended_basis": rec_basis} if rec_basis else {}),
                       **({"netcdf_units": vunits} if vunits else {})),
        )
        out = os.path.join(clean, "qy" if is_qy else "xs", SRC)
        written.append(write_record(rec, out))


for p in sorted(glob.glob(os.path.join(root, "data", "cross_sections", "*.nc"))):
    process_nc(p, "xs")
for p in sorted(glob.glob(os.path.join(root, "data", "quantum_yields", "*.nc"))):
    process_nc(p, "qy")

# ---- solar flux text files
FLUX = {
    "atlas3_1994_317_a.dat": ("W m-2 nm-1", {"authors": "ATLAS-3 SUSIM team (NRL)", "year": 1994, "title": "ATLAS-3 SUSIM solar spectrum, 13 Nov 1994", "journal": None, "doi": None}),
    "neckel.flx": ("photons cm-2 s-1 nm-1", {"authors": "H. Neckel and D. Labs", "year": 1984, "title": "The Solar Radiation Between 3300 and 12500 A", "journal": "Solar Physics 90, 205-258", "doi": "10.1007/BF00173953"}),
    "sao2010.solref.converted": ("W m-2 nm-1", {"authors": "K. Chance and R.L. Kurucz", "year": 2010, "title": "An improved high-resolution solar reference spectrum for earth's atmosphere measurements in the ultraviolet, visible, and near infrared", "journal": "J. Quant. Spectrosc. Radiat. Transfer 111, 1289-1295", "doi": "10.1016/j.jqsrt.2010.01.036"}),
    "susim_hi.flx": ("W m-2 nm-1", {"authors": "SUSIM SL2 team (NRL)", "year": None, "title": "SUSIM Spacelab-2 high resolution (0.15 nm) solar irradiance", "journal": None, "doi": None}),
}
for fn, (units, ref) in FLUX.items():
    p = os.path.join(root, "data", "profiles", "solar", fn)
    lines = open(p, encoding="latin-1").read().splitlines()
    hdr = "\n".join(l for l in lines if l.startswith("#"))
    from xs_common import parse_numeric_rows
    rows, dropped = parse_numeric_rows([l for l in lines if not l.startswith("#")])
    data = [[r[0], r[1]] for r in rows]
    rec = make_record(id=f"{SRC}:solar_{fn}", species="solar", name="extraterrestrial solar irradiance", source=SRC,
                      file=f"data/profiles/solar/{fn}", T_K=None, units=units, lambda_medium="unknown",
                      reference=ref, recommended=False, license=LIC, n_dropped_rows=dropped, data=data,
                      kind="solar_irradiance", comments=hdr,
                      notes="Extraterrestrial (top-of-atmosphere) solar spectral irradiance, not actinic flux at the surface.")
    written.append(write_record(rec, os.path.join(clean, "flux")))

with open(os.path.join(clean, "_logs", "tuvx_skipped.json"), "w") as f:
    json.dump(skipped, f, indent=1)
print("written", len(written), "skipped", len(skipped))
for s in skipped:
    print("  SKIP", s)
