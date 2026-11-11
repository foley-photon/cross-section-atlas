# Absorption Cross-Section Atlas

Gas-phase UV, visible and VUV absorption cross sections of about 1000 molecules, from five public collections,
overlaid on one plot, with the value at a laser line and what one pulse does to the sample. It runs in the browser at
**https://cdfoley.com/beta/cross-sections/**, and this repository is its source: the page, the scripts that build its
data files, and the tests. The data themselves are not here; see [Why the data are not here](#why-the-data-are-not-here).

I built it for the questions that come up whenever a laser meets a gas cell or a molecular beam. How strongly does this
molecule absorb at 193 or 248 nm, and how much do the measurements disagree? Is the line I am using on a band or
between bands? What fraction of the molecules does a 10 mJ/cm² pulse excite, and is that already near saturation?
How much light is left after 10 cm of 1 Torr? The cross sections are scattered over several databases in different
formats and units. The atlas puts them side by side, credits each dataset, and does the arithmetic.

## What it does

- **Molecule and datasets.** 1004 molecules and 5860 datasets, found by formula, name or CAS number. For each
  molecule the page shows the newest recommended dataset near room temperature and the best-resolved measurements
  from different papers; any of them can be added, up to eight at once. Each dataset is listed with its reference,
  temperature, wavelength range, number of points, source and wavelength scale (air, vacuum or not stated). Where a
  source gives no authors or title, the page shows its citation text (or, for TUV-x, the file header) instead.
- **Spectrum.** σ against wavelength (nm), wavenumber (cm⁻¹) or photon energy (eV), on a log or linear axis, in any
  of eleven units: cm² molecule⁻¹, Mb, barn, Å², a₀², m², molar absorptivity ε in base 10 or base e, the absorption
  coefficient k in cm⁻¹ atm⁻¹ at 273.15 K in base e or base 10, and the oscillator-strength density df/dE. Wavelength
  ranges (VUV, UV-C, UV-B/A, visible), common laser lines marked on the plot, a CSV download of what is shown, and a
  link that restores the view.
- **At a laser line.** σ of each shown dataset at a wavelength, as a point value or averaged over a Gaussian line of
  a given FWHM, with a note when the line is outside the data, partly outside, narrower than the data spacing, when
  the dataset holds upper limits, or when the value comes from a spectrum thinned for the web. At the preset laser
  lines a thinned dataset gives the point value of its full spectrum, which the build stores. Where one series was
  measured at several temperatures, σ at the gas temperature is interpolated between them from the same values.
- **Absorption and photolysis.** From σ, a pressure, a temperature and a path: number density, optical depth,
  absorbance and transmitted fraction. From a pulse fluence and a quantum yield: photons per cm², fraction excited,
  fraction photolyzed and the saturation fluence.
- **Convert units.** One value in every unit above.

## The physics in brief

- Values between tabulated points are linear interpolations; nothing is extrapolated past the data. A line of FWHM w
  averages σ over a Gaussian of standard deviation w/(2√(2 ln 2)), integrated over ±4 standard deviations on a grid
  that includes every data point, and the page reports which fraction of the line's weight falls inside the data.
- ε (base 10) = σN_A/(1000 ln 10) and ε (base e) = σN_A/1000 in L mol⁻¹ cm⁻¹; k = σn₀ with Loschmidt's constant
  n₀ = 101 325 Pa/(k_B × 273.15 K) = 2.686 780 111 × 10¹⁹ cm⁻³; 1 Mb = 10⁻¹⁸ cm²; a₀² = 2.800 285 × 10⁻¹⁷ cm²;
  σ = 2π²r_eħc × df/dE, so σ in Mb ≈ 109.76 × df/dE in eV⁻¹.
- Beer–Lambert: n = p/(k_B T), τ = σnL, transmitted fraction e^−τ, absorbance τ/ln 10.
- One pulse of fluence F at λ carries Φ = F/(hc/λ) photons per cm². On an optically thin sample a fraction 1 − e^−σΦ
  absorbs and 1 − e^−σΦφ is photolyzed; the second assumes that a molecule which absorbs and does not dissociate is
  back in the ground state within the pulse (otherwise the fraction is φ(1 − e^−σΦ)). The saturation fluence hν/σ is
  where 1 − 1/e has absorbed. Stimulated emission and multiphoton steps are not included.
- σ at a temperature between two measured ones is linear in T between the nearest two that cover the wavelength.
  A series is one paper's files of the same version (resolution, pressure, air or vacuum, revision): the dataset id
  without its temperature and file-name wavelength range.
- Wavelengths are as each source gives them, air or vacuum where the source says. The wavenumber and photon-energy
  axes are 10⁷/λ and hc/λ of that wavelength, so an air wavelength lands about 3 parts in 10⁴ high (12 cm⁻¹ at
  250 nm). Above 200 nm the air and vacuum wavelengths differ by about 0.075 nm at 250 nm and 0.11 nm at 400 nm.
- The preset laser lines are the wavelengths as usually quoted; the Nd:YAG harmonics are those of 1064.2 nm (532.1,
  354.7, 266.0 and 212.8 nm).
- On a log axis, points more than 12 decades below the largest value shown are left out of the plot (some modeled
  Leiden spectra run down to 10⁻³²⁰ cm² in their band wings), and the plot note says how many.
- Constants are CODATA 2022.

## Where the data come from

I downloaded each source on 2026-11-07 and keep the downloads, untouched, with checksums, in my own data archive.
The scripts in `scripts/archive/` turned them into one JSON file per dataset in a common form (wavelength in nm,
σ in cm² molecule⁻¹, temperature, wavelength scale, reference), and `scripts/build_data.py` turns that into the
page's data files.

| Source | Version | Datasets on the page | Terms |
|---|---|---|---|
| MPI-Mainz UV/VIS Spectral Atlas | 2013-06-24 snapshot, Zenodo record 6951 | 5440 | CC BY 4.0 |
| NCAR TUV-x | v0.17.0 data files | 173 | Apache License 2.0 |
| Leiden photodissociation and photoionization database | text files of 2025-03-10 | 115 | no license stated |
| IUP Bremen molecular spectroscopy data | files as downloaded | 104 | no license stated; the files ask that the paper be cited |
| Harvard-Smithsonian CfA molecular database | files dated 1984 to 2011 | 28 | no license stated; cite the publications |

From Leiden only the total photoabsorption column is used; its photodissociation and photoionization columns are not
shown. 35 datasets are left out (`meta.skipped` and `meta.skipped_why` in `index.json`):

- 17 Mainz files of the O₂–O₂ collision-induced absorption (O4). Their values, 10⁻⁴⁸ to 10⁻⁴⁵, are in cm⁵ molecule⁻²
  (absorption goes as the square of the O₂ density), although the files and my archive label them cm² molecule⁻¹.
  The one O4 file with values near 10⁻²⁰ (Shardanand and Prasad Rao 1977) is in units I could not confirm.
- 14 Mainz files that are not σ against wavelength: 11 marked "(T dependence)", whose first column is the temperature
  (σ of O₂ at 1059 to 2760 K, and of SiCl₂, SiCl₃ and SiCl₄ at Lyman-α), one "(parameters)" file in wavenumbers with
  fit coefficients (CH₂O, Chance and Orphal 2011), and one "(T-gradient)" file of dσ/dT (CH₂O, Meller and Moortgat
  2000). The page plotted these against "wavelength" before.
- Two whose units are not cm² (relative or not stated), one that my archive's checks flagged as about 25 times too
  large (NO₂, Bass 1976, in the Mainz snapshot), and one Mainz file named for 6.5 to 10 nm whose only point is at
  225 nm (CFCl₃, Cole and Dexter 1978).

Points of a Mainz file more than a factor of two outside the wavelength range in its file name are dropped and named
in the dataset's note; this removes one point, at 21.0 nm in the 210 to 227.5 nm HO₂ file of Lightfoot (1988). Files
marked as upper limits (H₂SO₄, CF₃OH, CHF₂OCF₃) are shown and labeled. Where two references are run together in a
journal field, the build separates them. NOTICE.md gives the citation each source asks for.

## Why the data are not here

Two of the five sources state a license that allows redistribution (Mainz, CC BY 4.0, and TUV-x, Apache 2.0). The
other three state none: Leiden asks users to cite its overview papers and the original sources, and the Bremen files
and the CfA pages ask that the papers be cited. The site shows each dataset with its reference, which is what they ask for.
Putting all of them in a public repository as a bulk download is redistribution that their terms do not clearly
allow, and I would rather not guess. So this repository carries the code and the build scripts and no
data, except two short CC BY 4.0 excerpts of the Mainz snapshot used by the tests (NOTICE.md). Anyone with the same
downloads can rebuild the files with the scripts here.

## How the site's copy works

The site keeps its data files in `beta/cross-sections/data/`: `index.json` (2.8 MB, the species and dataset metadata)
and `s/00001.json` to `s/05860.json` (39 MB, one spectrum each, loaded when it is shown). I rebuild them from my archive
with

```sh
python scripts/build_data.py <archive>/clean <site>/beta/cross-sections/data
```

and commit them to the site's repository. Each spectrum with more than 2000 points is thinned to 2000 that keep its
shape on a log σ scale: in each bucket of points the one that spans the largest triangle with its neighbors, so peaks
and band heads survive (`resample()` in `site/js/xsec.js` and in the build script; a test checks that they agree
point for point). Narrow windows between bands can still fall between the kept points, so for each thinned spectrum
the index also stores σ of the full spectrum at every preset laser line (`at`), and the table uses it there. The full
spectra stay in the archive. The spectrum files are numbered in build order, so a rebuild that leaves a dataset out
renumbers the files after it; the page finds each file through `index.json`.

The page code comes from this repository. Once a day the site's `sync-tool-repos` workflow reads the latest release,
runs its Node tests, copies its `site/` folder over `beta/cross-sections/` while keeping the site's `data/` folder as it
is, and then runs `node scripts/selftest.mjs <copied folder> --data`, which checks the code against the site's data
and boots the page on it. It publishes only if both pass; otherwise the folder is put back as it was. A data rebuild
committed to the site is not checked by that job; I run the same command on the site's folder before I commit one.

## The data build

The archive scripts are the ones I ran on 2026-11-07, kept as run except for the name of the date field in
`clean/index.json` (now `date`; `build_data.py` reads both). They take every path as an argument and are run with
`python -I`. They need Python 3 with numpy, and netCDF4 for the TUV-x files; `build_data.py` and the other scripts
in `scripts/` use only the standard library.

1. `safe_unzip.py ZIP OUT` unpacks each download without trusting its paths (it strips `..` and absolute parts and
   renames names Windows cannot hold), with a map of the renames.
2. `proc_mainz.py`, `proc_tuvx.py`, `proc_leiden.py`, `proc_bremen.py` and `proc_cfa.py` (`RAW CLEAN`, plus the
   commit and tag for TUV-x and the bundle date for Leiden) write one JSON file per dataset; `xs_common.py` holds
   their shared parsing, the species aliases and the license texts.
3. `recanon.py CLEAN` and `mainz_medium_tags.py CLEAN` reapply the species names and the Mainz air or vacuum tags;
   `doi_check.py CLEAN` checks and fills the Bremen and CfA DOIs against Crossref (the one script that uses the
   network).
4. `build_index.py CLEAN STATS` writes `clean/index.json`; `spotcheck.py CLEAN OUT` compares the datasets at
   reference wavelengths; `sha256sums.py DIR OUT` writes the checksums.
5. `scripts/build_data.py CLEAN OUT [--built YYYY-MM-DD]` writes the page's data files, and
   `scripts/thinning_check.py CLEAN OUT` reports how far the thinned spectra are from the full ones at the laser lines.

Each step reads what the one before it wrote. `survey_mainz.py` and `tuvx_inventory.py` were used once to look at the
file layouts before the conversion.

## Running the tests

Node 22 or later, no packages to install:

```sh
node --test "tests/*.test.mjs"
```

- `tests/engine.test.mjs`: unit factors, photon conversions, interpolation, laser-line averages (a Gaussian line on
  a Gaussian band against the closed form), temperature interpolation, thinning, Beer–Lambert and photolysis per
  pulse, the steps from the form to the numbers on the page (pressure units, mJ, the x axes, thinned and stored
  values, number formatting) and the preset laser lines, with the expected values worked out by hand in the comments.
- `tests/modules.test.mjs`: the page loads. Every module parses, every imported name is exported, `index.html` loads
  `app.js`, the stylesheet and files that exist, every element id `app.js` looks up is in `index.html`, and `app.js`
  reads the data layout the build writes; broken copies of the page check that this check catches them.
- `tests/boot.test.mjs`: the page boots. `app.js` runs in Node against a stand-in document made from the ids in
  `index.html`, with the fixture data; the test reads the panels (the value at a line, the notes on thinned data,
  upper limits and citation texts, the absorption and photolysis results) and breaks copies of the page in ways the
  static check cannot see.
- `tests/selftest.test.mjs`: the engine cases of `scripts/selftest.mjs`, the data checks on `tests/fixtures/data`
  (two Mainz excerpts and synthetic spectra, made by `tests/fixtures/make_fixtures.mjs`), broken copies of that folder
  that the data checks must catch, and the exit codes of the command line.
- `tests/repo.test.mjs`: one version in package.json, CITATION.cff and the CHANGELOG, no `site/data` folder, and no
  local paths or email addresses in the files.

Python 3 (CI uses 3.14), standard library only:

```sh
python -m unittest discover -s tests -v
```

`tests/test_build_data.py` runs the build script on two small synthetic archives: which datasets are kept and which
skipped and why, the dropping of non-finite and non-positive σ and of points far outside a file's named range,
sorting, rounding, thinning to 2000 points with a narrow spike kept, the stored full-resolution values at the laser
lines, upper limits, references given only as free text, species merged across spellings, a rebuild that gives the
same bytes, the output passing the site's data checks, and the thinning compared with the page's point for point
(the last ones need Node). `tests/test_release.py` checks the
version bookkeeping.

The check the site runs can also be run alone: `node scripts/selftest.mjs` on this repository's `site/`, or
`node scripts/selftest.mjs <folder> --data` on a copy with its data.

## Preview locally

```sh
node scripts/serve.mjs
```

and open http://127.0.0.1:8000/beta/cross-sections/. The page takes its header, footer, chart code (`/assets/js/plot.js`),
font and the Thermochemistry Lab's stylesheet from the main site, and its data from `./data/`; the preview fetches
those from https://cdfoley.com on first use and keeps them in memory. `--data DIR` serves the data from a local folder
instead (a build of `scripts/build_data.py`, or `tests/fixtures/data` for a small offline set), `--site DIR` serves the
shared files and the data from a local checkout of the site, and `--offline` serves nothing from the network. Links to
other pages of the site are sent on to https://cdfoley.com. `--port` picks another port.

## Repository layout

```
site/                what cdfoley.com serves at /beta/cross-sections/, without its data/ folder
  index.html, xsec.css
  js/                xsec.js (the engine: units, interpolation, line averages, absorption, photolysis), app.js (the page)
scripts/
  selftest.mjs       the check the site runs on its copy: engine cases, page check, data checks
  build_data.py      the page's data files from the cleaned archive
  thinning_check.py  how far the thinned spectra are from the full ones at the laser lines
  archive/           the scripts that made the cleaned archive from the downloads
  release.py         version bookkeeping for a release
  finish-release.sh  tags the version on origin/main and makes its GitHub release
  serve.mjs          local preview
tests/               Node and Python tests, and their fixtures
.github/workflows/   test.yml (every push and pull request)
```

## Validation

- The site's data files are the output of `scripts/build_data.py --built 2026-11-11` on the 2026-11-07 archive,
  byte for byte (the 2026-11-07 build, before the exclusions above, was reproduced byte for byte by the earlier
  version of the script).
- Ozone at the 253.65 nm mercury line: the median of the 41 room-temperature (290 to 300 K) ozone datasets on the
  site is 1.1410 × 10⁻¹⁷ cm², 0.71 % above the consensus value 1.1329(35) × 10⁻¹⁷ cm² of Hodges et al. (2019). The
  site's check requires the median to be within 2 %. Individual datasets range from 6 % below (Vigroux, listed on the
  page as 1953) to 18 % above (Davenport 1982), which is why the check uses the median.
- Thinning: 637 of the 5860 datasets have more than 2000 points in the source. Over the 2237 pairs of a thinned
  dataset and a laser line (or the 253.65 nm mercury line) in its range, σ from the thinned spectrum differs from the
  full spectrum by 0.19 % at the median, but by more than 10 % in 12 % of the pairs, and by orders of magnitude in a
  few banded spectra (Leiden S₂ at 405 nm, 5.6 × 10⁴ times; Leiden CO at 118.2 nm, 1.4 × 10⁴ times; Leiden O₂ at
  Lyman-α, 490 times). That is the error of the plotted curve (`scripts/thinning_check.py`). At the preset lines the
  table gives the stored full-resolution value instead (Leiden O₂ at Lyman-α: 1.147 × 10⁻²⁰ cm²); anywhere else it
  says when a value comes from a thinned spectrum.
- The 40 engine cases pass in Node on this repository's copy and on the site's, the site's copy passes the data
  checks and the boot check, and the page loads in a browser with no console errors. 49 Node tests and 27 Python
  tests pass.

## Known limitations

- 223 datasets (170 from the Mainz snapshot and 53 from TUV-x) have their reference in the archive only as free
  text, with no author or title fields. The page shows that text (for TUV-x, the start of the file header, which
  usually names the paper), with the authors taken from it where they can be read (153 of the 170 Mainz files);
  the other 70 are labeled by the author part of the Mainz file name or the TUV-x file name.
- Most Mainz and all TUV-x and Leiden datasets do not say whether their wavelengths are in air or vacuum.
- TUV-x O₂ files are tables of wavelength bins, and the page interpolates them as if they were points.
- The page reads the shared site files (`/assets/...`) and the Thermochemistry Lab's stylesheet from the site, so it
  is not usable as a stand-alone file.

## Citation

Cite this tool for the arithmetic only: interpolation, line averages, unit conversion, absorption and photolysis. The
cross sections are the work of the authors of each measurement: cite the original paper named with each dataset and
the collection it came through (NOTICE.md). `CITATION.cff` has the entry for the tool and the main references; GitHub
shows it under "Cite this repository".

## License

The code is MIT-licensed (LICENSE). The data the page shows are not in this repository and are not relicensed here;
the test fixtures taken from the MPI-Mainz snapshot keep its CC BY 4.0 license (NOTICE.md). Nothing here is endorsed
by any of the sources.

## Making a release

The site copies only GitHub releases, so a change reaches the page when it is released:

```sh
python scripts/release.py bump --note "What changed, one line per item" [--part minor]
git commit -am "vX.Y.Z" && git push origin main
bash scripts/finish-release.sh        # tags the version on origin/main and makes its GitHub release from the CHANGELOG
```

`finish-release.sh` needs the GitHub CLI (`gh`) with a token. It does nothing when the version on main is already
released, so it is safe to run again. The next daily run of the site's `sync-tool-repos` workflow, or a manual run of
it, copies the release.

Found a wrong number? Please open an issue.
