"""Process IUP Bremen MolSpec downloads -> clean JSON.
usage: python -I proc_bremen.py <bremen_files_root> <clean_dir>
"""
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs_common import make_record, write_record, parse_numeric_rows, empty_ref

root, clean = sys.argv[1:3]
SRC = "bremen"


def R(authors, year, title, journal, doi=None, **kw):
    d = {"authors": authors, "year": year, "title": title, "journal": journal, "doi": doi}
    d.update(kw)
    return d


SERD = R("A. Serdyuchenko, V. Gorshelev, M. Weber, W. Chehade, J.P. Burrows", 2014,
         "High spectral resolution ozone absorption cross-sections - Part 2: Temperature dependence",
         "Atmos. Meas. Tech. 7, 625-636", "10.5194/amt-7-625-2014",
         companion="V. Gorshelev, A. Serdyuchenko, M. Weber, W. Chehade, J.P. Burrows, High spectral resolution ozone absorption cross-sections - Part 1: Measurements, data analysis and comparison with previous measurements around 293 K, Atmos. Meas. Tech. 7, 609-624 (2014), doi:10.5194/amt-7-609-2014")
VOIGT_O3 = R("S. Voigt, J. Orphal, K. Bogumil, J.P. Burrows", 2001,
             "The temperature dependence (203-293 K) of the absorption cross sections of O3 in the 230-850 nm region measured by Fourier-transform spectroscopy",
             "J. Photochem. Photobiol. A 143, 1-9", "10.1016/S1010-6030(01)00480-4")
VOIGT_NO2 = R("S. Voigt, J. Orphal, J.P. Burrows", 2002,
              "The temperature and pressure dependence of the absorption cross-sections of NO2 in the 250-800 nm region measured by Fourier-transform spectroscopy",
              "J. Photochem. Photobiol. A 149, 1-7", "10.1016/S1010-6030(01)00650-5")
BOGUMIL = R("K. Bogumil, J. Orphal, T. Homann, S. Voigt, P. Spietz, O.C. Fleischmann, A. Vogel, M. Hartmann, H. Kromminga, H. Bovensmann, J. Frerick, J.P. Burrows", 2003,
            "Measurements of molecular absorption spectra with the SCIAMACHY pre-flight model: instrument characterization and reference data for atmospheric remote-sensing in the 230-2380 nm region",
            "J. Photochem. Photobiol. A 157, 167-184", "10.1016/S1010-6030(03)00062-5")
BRO = R("O.C. Fleischmann, M. Hartmann, J.P. Burrows, J. Orphal", 2004,
        "New ultraviolet absorption cross-sections of BrO at atmospheric temperatures measured by time-windowing Fourier transform spectroscopy",
        "J. Photochem. Photobiol. A 168, 117-132", "10.1016/j.jphotochem.2004.03.026")
OCLO = R("H. Kromminga, J. Orphal, P. Spietz, S. Voigt, J.P. Burrows", 2003,
         "New measurements of OClO absorption cross-sections in the 325-435 nm region and their temperature dependence between 213 and 293 K",
         "J. Photochem. Photobiol. A 157, 149-160", "10.1016/S1010-6030(03)00071-6")
OBRO = R("O.C. Fleischmann, J.P. Burrows", 2002, "OBrO absorption cross section at 298 K (IUP Bremen data file)", "University of Bremen data release", None)
GOMEZ = R("J.C. Gómez Martín, P. Spietz, J.P. Burrows", 2005,
          "Spectroscopic studies of the I2/O3 photochemistry. Part 1: Determination of the absolute absorption cross sections of iodine oxides of atmospheric relevance",
          "J. Photochem. Photobiol. A 176, 15-38", "10.1016/j.jphotochem.2005.09.024")
SPIETZ_THESIS = R("P. Spietz", 2005,
                  "Absorption cross sections for iodine species of relevance to the photolysis of mixtures of I2 and O3 and for the atmosphere",
                  "Doctoral thesis, University of Bremen", None)
I2 = R("P. Spietz, J.C. Gómez Martín, J.P. Burrows", 2006,
       "Effects of column density on I2 spectroscopy and determination of I2 absorption cross section at 500 nm",
       "Atmos. Chem. Phys. 6, 2177-2191", "10.5194/acp-6-2177-2006")
GLY = R("R. Volkamer, P. Spietz, J. Burrows, U. Platt", 2005,
        "High-resolution absorption cross-section of glyoxal in the UV-vis and IR spectral ranges",
        "J. Photochem. Photobiol. A 172, 35-46", "10.1016/j.jphotochem.2004.11.011")
CLO = R("D. Maric, J.P. Burrows", 1999,
        "Analysis of the UV absorption spectrum of ClO: a comparative study of four methods for spectral computations",
        "J. Quant. Spectrosc. Radiat. Transfer 62, 345-369", "10.1016/S0022-4073(98)00108-1")

n_written = []


def emit(idn, species, name, rel, T, data, ref, medium, dropped, resolution=None, notes=None, comments=None, axis=None, extra=None):
    rec = make_record(id=f"{SRC}:{idn}", species=species, name=name, source=SRC, file=rel, T_K=T,
                      lambda_medium=medium, lambda_medium_basis="file header" if medium != "unknown" else None,
                      reference=ref, recommended=False, n_dropped_rows=dropped, data=data, kind="cross_section",
                      resolution=resolution, notes=notes, comments=comments, original_axis=axis, extra=extra)
    n_written.append(write_record(rec, os.path.join(clean, "xs", SRC)))


def read(rel, decimal_comma=False):
    p = os.path.join(root, *rel.split("/"))
    txt = open(p, "rb").read().decode("latin-1")
    lines = txt.splitlines()
    rows, dropped = parse_numeric_rows(lines, decimal_comma=decimal_comma)
    # header = lines before first data row
    hdr = []
    for l in lines:
        s = l.strip()
        if rows and s and re.match(r"^[-+]?\d", s):
            break
        hdr.append(l.rstrip())
    return rows, dropped, "\n".join(hdr)[:5000]


def nm_from_wn(rows, wi, si):
    return [[1e7 / r[wi], r[si]] for r in rows if r[wi] > 0]


# --- Serdyuchenko/Gorshelev 2012 full-range version (11 temperatures)
TS = [293, 283, 273, 263, 253, 243, 233, 223, 213, 203, 193]
rel = "downloads/serdyuchenkogorshelev5digits.dat"
rows, dropped, hdr = read(rel)
for i, T in enumerate(TS):
    data = [[r[0], r[1 + i]] for r in rows if len(r) > 1 + i]
    emit(f"O3_Serdyuchenko2014_{T}K", "O3", "ozone", rel, float(T), data, SERD, "vacuum", dropped,
         resolution="0.01 nm HWHM <290 nm and 350-450 nm; 1 cm-1 HWHM 290-350 and 450-1100 nm; 0.01 nm grid",
         notes="IUP Bremen version 25.07.2012 (file created 05.03.2012), 213-1100 nm.", comments=hdr)
# --- July 2013 version (FFT-filtered 213.33-317 nm), decimal comma, tab separated, ragged columns
rel = "downloads/serdyuchenkogorshelevversionjuly2013_unz/SerdyuchenkoGorshelevVersionJuly2013.dat"
p = os.path.join(root, *rel.split("/"))
lines = open(p, "rb").read().decode("latin-1").splitlines()
cols = {T: [] for T in TS}
dropped = 0
for l in lines:
    if not re.match(r"^\s*\d+,\d+\t", l):
        continue
    cells = l.rstrip("\r\n").split("\t")
    try:
        lam = float(cells[0].replace(",", "."))
    except ValueError:
        dropped += 1; continue
    for i, T in enumerate(TS):
        c = cells[1 + i].strip() if len(cells) > 1 + i else ""
        if c:
            try:
                cols[T].append([lam, float(c.replace(",", "."))])
            except ValueError:
                dropped += 1
hdr = "\n".join(lines[:60])
for T in TS:
    if cols[T]:
        emit(f"O3_Serdyuchenko2014_v2013FFT_{T}K", "O3", "ozone", rel, float(T), cols[T], SERD, "vacuum", dropped,
             resolution="as 2012 version; FFT filter applied 213.33-317 nm",
             notes="IUP Bremen version 22.07.2013: Fast Fourier Transform filter applied to the 213.33-317 nm region only (UV part).",
             comments=hdr[:5000])

# --- Voigt FTS O3 (h/l = 1000/100 mbar) and NO2
for f in sorted(glob.glob(os.path.join(root, "fts-o3", "o3_*.dat"))):
    rel = "fts-o3/" + os.path.basename(f)
    m = re.match(r"o3_(\d+)([hl])\.dat", os.path.basename(f))
    T, hl = float(m.group(1)), m.group(2)
    rows, dropped, hdr = read(rel)
    data = [[r[0], r[2]] for r in rows]
    emit(f"O3_Voigt2001_{int(T)}K_{'1000' if hl == 'h' else '100'}mbar", "O3", "ozone", rel, T, data, VOIGT_O3, "vacuum", dropped,
         comments=hdr,
         notes=f"Total pressure {'1000' if hl == 'h' else '100'} mbar.", extra={"sigma_error": [r[3] for r in rows]})
for f in sorted(glob.glob(os.path.join(root, "fts-no2", "no2_*_unz", "*.dat"))):
    rel = os.path.relpath(f, root).replace("\\", "/")
    m = re.match(r"no2_(\d+)([hl])\.dat", os.path.basename(f), re.I)
    T, hl = float(m.group(1)), m.group(2).lower()
    rows, dropped, hdr = read(rel)
    data = [[r[0], r[2]] for r in rows]
    emit(f"NO2_Voigt2002_{int(T)}K_{'1000' if hl == 'h' else '100'}mbar", "NO2", "nitrogen dioxide", rel, T, data, VOIGT_NO2, "vacuum", dropped,
         comments=hdr, notes=f"Total pressure {'1000' if hl == 'h' else '100'} mbar.", extra={"sigma_error": [r[3] for r in rows]})

# --- SCIAMACHY PFM (Bogumil 2003)
for f in sorted(glob.glob(os.path.join(root, "net", "O3_*_V3_0.dat")) + glob.glob(os.path.join(root, "net", "scia", "*.dat"))):
    rel = os.path.relpath(f, root).replace("\\", "/")
    b = os.path.basename(f)
    m = re.match(r"([A-Za-z0-9]+)_(\d+)K(?:_(UV|Vis|V3_0))?\.dat", b)
    sp, T, part = m.group(1), float(m.group(2)), m.group(3)
    rows, dropped, hdr = read(rel)
    data = [[r[0], r[1]] for r in rows]
    nm = {"O3": "ozone", "NO2": "nitrogen dioxide", "SO2": "sulfur dioxide", "O2": "oxygen", "H2CO": "formaldehyde", "OClO": "chlorine dioxide"}[sp]
    mres = re.search(r"Spectral Resolution:\s*(.+?)\n(?:Number|\S)", hdr, re.S)
    emit(f"{sp}_Bogumil2003_SCIA_{int(T)}K" + (f"_{part}" if part and part != "V3_0" else "") + ("_v3.0" if part == "V3_0" else ""),
         sp, nm, rel, T, data, BOGUMIL, "vacuum", dropped, resolution=re.sub(r"\s+", " ", mres.group(1)).strip() if mres else None,
         comments=hdr)

# --- BrO TRFTS (wavenumber, vacuum)
for f in sorted(glob.glob(os.path.join(root, "net", "BrO", "*.dat"))):
    rel = os.path.relpath(f, root).replace("\\", "/")
    T = float(re.search(r"_(\d+)K_", f).group(1))
    rows, dropped, hdr = read(rel)
    emit(f"BrO_Fleischmann2004_{int(T)}K", "BrO", "bromine monoxide", rel, T, nm_from_wn(rows, 0, 1), BRO, "vacuum", dropped,
         resolution="4 cm-1 FWHM", comments=hdr, axis="vacuum wavenumber (cm-1); converted lambda_nm = 1e7/wavenumber")

# --- OClO FTS (decimal comma, wavenumber)
for f in sorted(glob.glob(os.path.join(root, "net", "OClO*cm1_*K.DAT"))):
    rel = os.path.relpath(f, root).replace("\\", "/")
    res, T = re.search(r"OClO(\d+)cm1_(\d+)K", f).groups()
    rows, dropped, hdr = read(rel, decimal_comma=True)
    emit(f"OClO_Kromminga2003_{T}K_{res}cm-1", "OClO", "chlorine dioxide", rel, float(T), nm_from_wn(rows, 0, 1), OCLO, "vacuum", dropped,
         resolution=f"{res} cm-1", comments=hdr, axis="vacuum wavenumber (cm-1); converted lambda_nm = 1e7/wavenumber")

# --- OBrO
rel = "OBrO_298K_at_10cm^-1.txt"
rows, dropped, hdr = read(rel)
emit("OBrO_Fleischmann2002_298K", "OBrO", "bromine dioxide", rel, 298.0, nm_from_wn(rows, 0, 1), OBRO, "vacuum", dropped,
     resolution="10 cm-1", comments=hdr, axis="vacuum wavenumber (cm-1); converted lambda_nm = 1e7/wavenumber")

# --- iodine species (use vacuum-wavelength column; air column also given in source)
spec = [
    ("OIO/RefSpec_0.35nmFWHM_OIO_IUPBremen.txt", "OIO", "iodine dioxide", 1, 5, GOMEZ, "0.35 nm FWHM", "OIO_GomezMartin2005_0.35nm"),
    ("OIO/RefSpec_1.3nmFWHM_OIO_IUPBremen.TXT", "OIO", "iodine dioxide", 1, 3, SPIETZ_THESIS, "1.3 nm FWHM (apparent cross section)", "OIO_Spietz2005_1.3nm"),
    ("IO/RefSpec_0.07nmFWHM_IO_IUPBremen.txt", "IO", "iodine monoxide", 1, 3, GOMEZ, "0.07 nm FWHM", "IO_GomezMartin2005_0.07nm"),
    ("IO/RefSpec_1.3nmFWHM_IOgroundstate_IUPBremen.TXT", "IO", "iodine monoxide", 1, 3, SPIETZ_THESIS, "1.3 nm FWHM (apparent; ground state)", "IO_Spietz2005_1.3nm_groundstate"),
    ("IO/RefSpec_1.3nmFWHM_IOexcitedstate_IUPBremen.TXT", "IO", "iodine monoxide (vibrationally excited)", 1, 3, SPIETZ_THESIS, "1.3 nm FWHM (apparent; excited state)", "IO_Spietz2005_1.3nm_excitedstate"),
    ("I2/RefSpec_0.25nmFWHM_I2_IUPBremen.TXT", "I2", "iodine", 0, 1, I2, "0.25 nm FWHM", "I2_Spietz2006_0.25nm"),
    ("I2/RefSpec_0.59nmFWHM_I2_IUPBremen.TXT", "I2", "iodine", 0, 1, I2, "0.59 nm FWHM", "I2_Spietz2006_0.59nm"),
]
for rel, sp, nm, li, si, ref, res, idn in spec:
    rows, dropped, hdr = read(rel)
    data = [[r[li], r[si]] for r in rows if len(r) > si]
    T = None  # only set when the file header states it
    mT = re.search(r"T\s*=\s*(\d{3})\s*K", hdr, re.I) or re.search(r"(\d{3})\s*K\b", hdr)
    if mT:
        T = float(mT.group(1))
    emit(idn, sp, nm, rel, T, data, ref, "vacuum", dropped + sum(1 for r in rows if len(r) <= si), resolution=res, comments=hdr,
         notes="Vacuum-wavelength column used; the source also lists air wavelengths." if li == 1 else None)

# --- glyoxal (decimal comma; lambdaAir lambdaVac wavenumber sigma)
for f in sorted(glob.glob(os.path.join(root, "Glyoxal", "glyoxal_*_unz", "*.TXT"))):
    rel = os.path.relpath(f, root).replace("\\", "/")
    res = re.search(r"glyoxal_([0-9.]+nm)FWHM", f).group(1)
    rows, dropped, hdr = read(rel, decimal_comma=True)
    data = [[r[1], r[3]] for r in rows if len(r) >= 4]
    emit(f"CHOCHO_Volkamer2005_296K_{res}", "CHOCHO", "glyoxal", rel, 296.0, data, GLY, "vacuum", dropped, resolution=f"{res} FWHM",
         comments=hdr, notes="Vacuum-wavelength column used; the source also lists air wavelengths.")

# --- ClO calculated spectra (Maric & Burrows 1999), 12 temperatures
rel = "downloads/clospectrum.prn"
rows, dropped, hdr = read(rel)
TC = [180, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300]
for i, T in enumerate(TC):
    data = [[r[1], r[3 + i]] for r in rows if len(r) > 3 + i]
    emit(f"ClO_MaricBurrows1999_calc_{T}K", "ClO", "chlorine monoxide", rel, float(T), data, CLO, "vacuum", dropped,
         comments=hdr, notes="Calculated (not measured) spectrum. Vacuum-wavelength column used; the source also lists air wavelengths.")

print("written", len(n_written))
