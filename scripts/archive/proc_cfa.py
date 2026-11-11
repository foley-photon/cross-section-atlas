"""Process Harvard-Smithsonian CfA AMP molecular database files -> clean JSON.
usage: python -I proc_cfa.py <cfa_files_root> <clean_dir>
"""
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import make_record, write_record, parse_numeric_rows

root, clean = sys.argv[1:3]
SRC = "cfa"


def R(a, y, t, j, doi=None, **kw):
    d = {"authors": a, "year": y, "title": t, "journal": j, "doi": doi}
    d.update(kw)
    return d


# axis: 'wn' (cm-1, vacuum), 'nm', 'A' (angstrom), 'airA' (col index for air angstrom)
SERIES = [
    dict(id="O2_Yoshino2005_SRcontinuum_295K", sp="O2", name="oxygen", T=295.0, files=["16o2/srcntrt.xsc"], axis="nm", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, W.H. Parkinson, K. Ito, T. Matsui", 2005, "Absolute absorption cross-section measurements of Schumann-Runge continuum of O2 at 90 and 295 K", "J. Mol. Spectrosc. 229, 238-243", None)),
    dict(id="O2_Yoshino2005_SRcontinuum_90K", sp="O2", name="oxygen", T=90.0, files=["16o2/srcnt90.xsc"], axis="nm", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, W.H. Parkinson, K. Ito, T. Matsui", 2005, "Absolute absorption cross-section measurements of Schumann-Runge continuum of O2 at 90 and 295 K", "J. Mol. Spectrosc. 229, 238-243", None)),
    dict(id="O2_Yoshino1992_SRbands_300K", sp="O2", name="oxygen", T=300.0, files="o2pub92/o2wb*x0.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, A.S.-C. Cheung, D.E. Freeman, W.H. Parkinson", 1992, "High resolution absorption cross sections in the transmission window region of the Schumann-Runge bands and Herzberg continuum of O2", "Planet. Space Sci. 40, 185-192", None),
         notes="Schumann-Runge (v',0) band files concatenated; supersede the window-region values of Yoshino et al. 1983 (Planet. Space Sci. 31, 339)."),
    dict(id="O2_Yoshino1987_SRbands_79K", sp="O2", name="oxygen (16O2)", T=79.0, files="o1679k/o6lb*.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, D.E. Freeman, J.R. Esmond, W.H. Parkinson", 1987, "High resolution absorption cross sections and band oscillator strengths of the Schumann-Runge bands of oxygen at 79 K", "Planet. Space Sci. 35, 1067", None)),
    dict(id="18O2_Yoshino1988_SRbands_79K", sp="18O2", name="oxygen-18 (18O2)", T=79.0, files="o1879k/o18b*.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, D.E. Freeman, J.R. Esmond, R.S. Friedman, W.H. Parkinson", 1988, "High resolution absorption cross sections and band oscillator strengths of the Schumann-Runge bands of isotopic oxygen, 18O2, at 79 K", "Planet. Space Sci. 36, 1201-1210", None)),
    dict(id="16O18O_Yoshino1989_SRbands_79K", sp="16O18O", name="oxygen (16O18O)", T=79.0, files="o6879k/o68b*.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, D.E. Freeman, J.R. Esmond, R.S. Friedman, W.H. Parkinson", 1989, "High resolution absorption cross sections and band oscillator strengths of the Schumann-Runge bands of isotopic oxygen, 16O18O, at 79 K", "Planet. Space Sci. 37, 419-426", None)),
    dict(id="H2O_Yoshino_Parkinson_295K", sp="H2O", name="water", T=295.0, files=["h2o/h2o.xsc"], axis="nm", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, W.H. Parkinson, K. Ito, T. Matsui", 1996, "Absorption cross section measurements of water vapor in the wavelength region 120 to 188 nm", "Chem. Phys. 211, 387-391", None,
               also="K. Yoshino et al., Chem. Phys. 215, 429 (1997); W.H. Parkinson and K. Yoshino, Chem. Phys. 294, 31 (2003)"),
         notes="Combination of two measurements per the file header: Chem. Phys. 211, 387 (1996); 215, 429 (1997); and Chem. Phys. 294, 31 (2003)."),
    dict(id="O3_Freeman1984_195K", sp="O3", name="ozone", T=195.0, files="o3pub84/o3*kwna*.pub", axis="wn", li=0, si=1, scale=1.0,
         ref=R("D.E. Freeman, K. Yoshino, J.R. Esmond, W.H. Parkinson", 1984, "High resolution absorption cross section measurements of ozone at 195 K in the wavelength region 240-350 nm", "Planet. Space Sci. 32, 239-248", None)),
    dict(id="O3_Yoshino1993_VUV_195K", sp="O3", name="ozone", T=195.0, files=["o3xvuv93/o3xvuvd.xsc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, D.E. Freeman, W.H. Parkinson", 1993, "Measurements of absolute absorption cross sections of ozone in the 185- to 254-nm wavelength region and the temperature dependence", "J. Geophys. Res. 98(D3), 5205-5211", None)),
    dict(id="O3_Yoshino1993_VUV_228K", sp="O3", name="ozone", T=228.0, files=["o3xvuv93/o3xvuvm.xsc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, D.E. Freeman, W.H. Parkinson", 1993, "Measurements of absolute absorption cross sections of ozone in the 185- to 254-nm wavelength region and the temperature dependence", "J. Geophys. Res. 98(D3), 5205-5211", None),
         notes="Readme O3RDME93.INF: O3XVUVM = 228 K (the file title line says 195K)."),
    dict(id="O3_Yoshino1993_VUV_295K", sp="O3", name="ozone", T=295.0, files=["o3xvuv93/o3xvuvr.xsc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, D.E. Freeman, W.H. Parkinson", 1993, "Measurements of absolute absorption cross sections of ozone in the 185- to 254-nm wavelength region and the temperature dependence", "J. Geophys. Res. 98(D3), 5205-5211", None)),
    dict(id="C2H2_Smith1991_295K_PhotonFactory", sp="C2H2", name="acetylene", T=295.0, files=["c2h2/c2h2a295.xcc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("P.L. Smith, K. Yoshino, W.H. Parkinson, K. Ito, G. Stark", 1991, "High-resolution, VUV (147-201 nm) photoabsorption cross sections for C2H2 at 195 and 295 K", "J. Geophys. Res. 96(E2), 17529-17533", None),
         notes="CfA caveat (P.L. Smith, 2000): the 174-201 nm sample was later found to contain ~1400 ppm acetone; extraneous peaks near 190 and 195 nm, possibly also 149.5 nm."),
    dict(id="C2H2_Smith1991_295K_CfA", sp="C2H2", name="acetylene", T=295.0, files=["c2h2/c2h2b295.xcc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("P.L. Smith, K. Yoshino, W.H. Parkinson, K. Ito, G. Stark", 1991, "High-resolution, VUV (147-201 nm) photoabsorption cross sections for C2H2 at 195 and 295 K", "J. Geophys. Res. 96(E2), 17529-17533", None),
         notes="CfA caveat (P.L. Smith, 2000): the 174-201 nm sample was later found to contain ~1400 ppm acetone; extraneous peaks near 190 and 195 nm."),
    dict(id="C2H2_Smith1991_195K", sp="C2H2", name="acetylene", T=195.0, files=["c2h2/c2h2x195.xcc"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("P.L. Smith, K. Yoshino, W.H. Parkinson, K. Ito, G. Stark", 1991, "High-resolution, VUV (147-201 nm) photoabsorption cross sections for C2H2 at 195 and 295 K", "J. Geophys. Res. 96(E2), 17529-17533", None),
         notes="CfA caveat (P.L. Smith, 2000): acetone contamination of the 174-201 nm sample; extraneous peaks near 190 and 195 nm."),
    dict(id="CO2_Yoshino1996_295K", sp="CO2", name="carbon dioxide", T=295.0, files=["co296/CO2rw96.xsc"], axis="A", li=0, si=1, scale=1e-21,
         ref=R("K. Yoshino, J.R. Esmond, Y. Sun, W.H. Parkinson, K. Ito, T. Matsui", 1996, "Absorption cross section measurements of carbon dioxide in the wavelength region 118.7-175.5 nm and the temperature dependence", "J. Quant. Spectrosc. Radiat. Transfer 55, 53-60", None)),
    dict(id="CO2_Yoshino1996_195K", sp="CO2", name="carbon dioxide", T=195.0, files=["co296/CO2dw96.xsc"], axis="A", li=0, si=1, scale=1e-21,
         ref=R("K. Yoshino, J.R. Esmond, Y. Sun, W.H. Parkinson, K. Ito, T. Matsui", 1996, "Absorption cross section measurements of carbon dioxide in the wavelength region 118.7-175.5 nm and the temperature dependence", "J. Quant. Spectrosc. Radiat. Transfer 55, 53-60", None)),
    dict(id="CO2_Parkinson2003_295K", sp="CO2", name="carbon dioxide", T=295.0, files=["co296/CO2rw03.xsc"], axis="A", li=0, si=1, scale=1e-21,
         ref=R("W.H. Parkinson, J. Rufus, K. Yoshino", 2003, "Absolute absorption cross section measurements of CO2 in the wavelength region 163-200 nm and the temperature dependence", "Chem. Phys. 290, 251-256", None,
               basis="CfA page gives no citation for the 2003 files; attribution inferred from file range/date (verify)")),
    dict(id="CO2_Parkinson2003_195K", sp="CO2", name="carbon dioxide", T=195.0, files=["co296/CO2dw03.xsc"], axis="A", li=0, si=1, scale=1e-21,
         ref=R("W.H. Parkinson, J. Rufus, K. Yoshino", 2003, "Absolute absorption cross section measurements of CO2 in the wavelength region 163-200 nm and the temperature dependence", "Chem. Phys. 290, 251-256", None,
               basis="CfA page gives no citation for the 2003 files; attribution inferred from file range/date (verify)")),
    dict(id="CO2_Stark2007_295K", sp="CO2", name="carbon dioxide", T=295.0, files=["co2.106_119/CO2-295K.dat"], axis="A", li=0, si=1, scale=1.0,
         ref=R("G. Stark, K. Yoshino, P.L. Smith, K. Ito", 2007, "Photoabsorption cross section measurements of CO2 between 106.1 and 118.7 nm at 295 and 195 K", "J. Quant. Spectrosc. Radiat. Transfer 103, 67-73", None)),
    dict(id="CO2_Stark2007_195K", sp="CO2", name="carbon dioxide", T=195.0, files=["co2.106_119/CO2-195K.dat"], axis="A", li=0, si=1, scale=1.0,
         ref=R("G. Stark, K. Yoshino, P.L. Smith, K. Ito", 2007, "Photoabsorption cross section measurements of CO2 between 106.1 and 118.7 nm at 295 and 195 K", "J. Quant. Spectrosc. Radiat. Transfer 103, 67-73", None)),
    dict(id="CO_Stark1991_295K", sp="CO", name="carbon monoxide", T=295.0, files=["cosigma/cosigma.295"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("G. Stark, K. Yoshino, P.L. Smith, K. Ito, W.H. Parkinson", 1991, "High resolution absorption cross sections of carbon monoxide bands at 295 K between 91.7 and 100.4 nanometers", "Astrophys. J. 369, 574-580", None),
         notes="File WARNING: values are cross sections convolved with the instrument profile (~5.5 mA FWHM); peaks too small and valleys too large, by up to 15-40% for intermediate/sharp bands. The file text says units of 1e-16 cm2 but the numbers are already of order 1e-17..1e-16, so they are stored as given (cm2)."),
    dict(id="SO2_Freeman1984_213K", sp="SO2", name="sulfur dioxide", T=213.0, files="so2213/so2*k213.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("D.E. Freeman, K. Yoshino, J.R. Esmond, W.H. Parkinson", 1984, "High resolution absorption cross section measurements of SO2 at 213 K in the wavelength region 172-240 nm", "Planet. Space Sci. 32, 1125-1134", None)),
    dict(id="SO2_Rufus2009_160K", sp="SO2", name="sulfur dioxide", T=160.0, files=["so2_160/so2_160_data.txt"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("J. Rufus, G. Stark, A.P. Thorne, J.C. Pickering, R.J. Blackwell-Whitehead, D. Blackie, P.L. Smith", 2009, "High-resolution photoabsorption cross-section measurements of SO2 at 160 K between 199 and 220 nm", "J. Geophys. Res. 114, E06003", "10.1029/2008JE003319")),
    dict(id="SO2_Blackie2011_198K", sp="SO2", name="sulfur dioxide", T=198.0, files=["so2_198K/so2_198data.txt"], axis="wn", li=0, si=1, scale=1.0,
         ref=R("D. Blackie, R.J. Blackwell-Whitehead, G. Stark, J.C. Pickering, P.L. Smith, J. Rufus, A.P. Thorne", 2011, "High-resolution photoabsorption cross-section measurements of SO2 at 198 K between 213 and 325 nm", "J. Geophys. Res. 116, E03006", "10.1029/2010JE003707")),
    dict(id="SO2_Stark1999_295K", sp="SO2", name="sulfur dioxide", T=295.0, files="so2high/glenn*", axis="wn", li=0, si=1, scale=1e-17,
         ref=R("G. Stark, P.L. Smith, J. Rufus, A.P. Thorne, J.C. Pickering, G. Cox", 1999, "High-resolution photoabsorption cross-section measurements of SO2 at 295 K between 198 and 220 nm", "J. Geophys. Res. 104, 16585-16590", None)),
    dict(id="SO2_Rufus2003_295K", sp="SO2", name="sulfur dioxide", T=295.0, files=["so2rt/data.fmt"], axis="wn", li=0, si=1, scale=1e-19,
         ref=R("J. Rufus, G. Stark, P.L. Smith, J.C. Pickering, A.P. Thorne", 2003, "High-resolution photoabsorption cross section measurements of SO2, 2: 220 to 325 nm at 295 K", "J. Geophys. Res. 108", "10.1029/2002JE001931")),
    dict(id="NO2_Yoshino1997_298K", sp="NO2", name="nitrogen dioxide", T=298.5, files="no2rpub/no2r*s.pub", axis="airA", li=2, si=1, scale=1.0,
         ref=R("K. Yoshino, J.R. Esmond, W.H. Parkinson", 1997, "High resolution absorption cross section measurements of NO2 in the UV and visible region", "Chem. Phys. 221, 169-174", None),
         notes="Air wavelength column (angstrom) used, as given in the source; the file also gives vacuum wavenumbers."),
    dict(id="N2O_Yoshino1984_295K", sp="N2O", name="nitrous oxide", T=[295.0, 299.0], files="n2opub84/n2o*.xsc", axis="wn", li=0, si=1, scale=1.0,
         ref=R("K. Yoshino, D.E. Freeman, W.H. Parkinson", 1984, "High resolution absorption cross section measurements of N2O at 295-299 K in the wavelength region 170-222 nm", "Planet. Space Sci. 32, 1219-1222", None)),
]

written = []
for s in SERIES:
    files = s["files"] if isinstance(s["files"], list) else sorted(glob.glob(os.path.join(root, *s["files"].split("/"))))
    files = [os.path.join(root, *f.split("/")) if isinstance(s["files"], list) else f for f in files]
    data, dropped, hdrs = [], 0, []
    for f in files:
        lines = open(f, "rb").read().decode("latin-1").splitlines()
        # skip lines before the first numeric row (headers); for cosigma the 3rd column marks file starts
        rows, d = parse_numeric_rows(lines)
        dropped += d
        hdrs.append(os.path.basename(f) + ": " + " | ".join(l.strip() for l in lines[:3] if l.strip())[:300])
        for r in rows:
            if len(r) <= max(s["li"], s["si"]):
                dropped += 1
                continue
            x, y = r[s["li"]], r[s["si"]] * s["scale"]
            if s["axis"] == "wn":
                if x <= 0:
                    dropped += 1; continue
                lam = 1e7 / x
            elif s["axis"] in ("A", "airA"):
                lam = x / 10.0
            else:
                lam = x
            data.append([lam, y])
    medium = {"wn": "vacuum", "airA": "air", "A": "unknown", "nm": "unknown"}[s["axis"]]
    basis = {"wn": "source axis is vacuum wavenumber (cm-1); lambda_nm = 1e7/wavenumber",
             "airA": "source readme: 'air wavelength in angstroms'"}.get(s["axis"])
    axis = {"wn": "vacuum wavenumber (cm-1), converted to nm", "A": "wavelength in angstrom, divided by 10",
            "airA": "air wavelength in angstrom, divided by 10", "nm": "wavelength in nm (as given)"}[s["axis"]]
    rel = [os.path.relpath(f, root).replace("\\", "/") for f in files]
    rec = make_record(id=f"{SRC}:{s['id']}", species=s["sp"], name=s["name"], source=SRC,
                      file=rel[0] if len(rel) == 1 else rel, T_K=s["T"], lambda_medium=medium, lambda_medium_basis=basis,
                      reference=s["ref"], recommended=False, n_dropped_rows=dropped, data=data, kind="cross_section",
                      original_axis=axis + (f"; sigma scaled by {s['scale']:g}" if s["scale"] != 1 else ""),
                      notes=s.get("notes"), comments="\n".join(hdrs)[:5000])
    written.append(write_record(rec, os.path.join(clean, "xs", SRC)))
    print(s["id"], len(files), "files", len(data), "pts", "dropped", dropped, "range %.2f-%.2f" % (min(d[0] for d in data), max(d[0] for d in data)), "max %.2e" % max(d[1] for d in data))
print("written", len(written))
