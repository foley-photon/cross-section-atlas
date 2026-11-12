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
  The list can be filtered to the recommended datasets or to one source.
- **Spectrum.** σ against wavelength (nm), wavenumber (cm⁻¹) or photon energy (eV), on a log or linear axis, in any
  of eleven units: cm² molecule⁻¹, Mb, barn, Å², a₀², m², molar absorptivity ε in base 10 or base e, the absorption
  coefficient k in cm⁻¹ atm⁻¹ at 273.15 K in base e or base 10, and the oscillator-strength density df/dE. Wavelength
  ranges (VUV, UV-C, UV-B/A, visible), common laser lines marked on the plot, a CSV download of what is shown, and a
  link that restores the view. The plot limits are typed in the unit of the axis. Reset returns the page to how it opens.
- **At a laser line.** σ of each shown dataset at a wavelength, as a point value or averaged over a Gaussian line of
  a given FWHM, with a note when the line is outside the data, partly outside, narrower than the data spacing, when
  the dataset holds upper limits, or when the value comes from a spectrum thinned for the web. At the preset laser
  lines a thinned dataset gives the point value of its full spectrum, which the build stores. Where one series was
  measured at several temperatures, σ at the gas temperature is interpolated between them from the same values.
- **Who absorbs here?** The reverse question: at the wavelength of the laser-line field, every molecule with data
  there, strongest first, with the dataset the value comes from (reference, temperature, source). It opens on the
  gases of air (N₂, O₂, H₂O, CO₂, CH₄, H₂, N₂O, CO, O₃, NO₂, NO, SO₂, NH₃) and names the ones with no data at the
  wavelength; "All molecules" lists the rest. One dataset stands for each molecule, chosen by a fixed rule. At the
  thirteen preset lines the values are point values of the full spectra; at any other wavelength they are means over
  2 nm, marked as approximate. A press on a molecule loads it with that dataset first.
  The air view answers "what takes my beam in air": for each gas its mole fraction in air, the absorption coefficient
  α = σ × mole fraction × number density of air at 1 atm and 296 K, per meter, and the 1/e path length. It opens in the
  order of α, with the order by σ per molecule one press away, and a line above the table names the gas with the
  largest α and the 1/e length of the listed gases together. The line says "takes the most light" only when N₂, O₂ and
  H₂O are all in the sum and the leading value carries no flag; otherwise it says "has the largest listed value" and
  names the main gases without a table. A value in a structured spectrum (the dataset's points within 0.25 nm of the
  line differ by a factor of two or more) is flagged. O₂ above 245 nm, where its datasets disagree, is listed and left
  out of the sum. One field sets the relative humidity (50 % to start). A fold lists every mole fraction with its
  source.
- **Absorption and photolysis.** From σ, a pressure, a temperature and a path: number density, optical depth,
  absorbance and transmitted fraction. From a pulse fluence and a quantum yield: photons per cm², fraction excited,
  fraction photolyzed and the saturation fluence.
- **Convert units.** One value in every unit above.

Every field reads a number whole or not at all, by the same rules as the calculators on the site: 1,5 is 1.5, while
1,064 (1064 or 1.064?) and 12abc are refused with a message that names the field.

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
- "Who absorbs here?" compares one dataset per molecule. Among a molecule's datasets with a value at the wavelength
  the build takes, in this order: measured values before upper limits; optical absorption before electron energy
  loss spectra (files marked "(e,e)", whose resolution is far below an optical one); points no more than 5 nm apart
  around the wavelength; a spectrum (three points or more) before a list of separate points (a single point within
  1 nm, or a file of band maxima); the natural sample before a single isotopologue; room temperature (280 to 300 K,
  or a range that reaches it), then no stated temperature, then the temperature nearest 296 K; a dataset an
  evaluation recommended; the newest; the one with the most points in the source. Where a weak dataset is all there
  is, the row says so in a Note column: upper limit, measured at one wavelength only, electron energy loss,
  interpolated across a gap (with its width), the isotopologue, or a temperature below 250 K or above 350 K. Left
  out of the tables: line-intensity lists (integrated line strengths, not σ against wavelength) and values below
  10⁻⁴⁰ cm² (underflow in the source files). A file of band maxima is read point by point in the laser-line table
  too: the nearest listed point within 1 nm, never a line drawn between two bands. At a preset line the value is the one the laser-line table gives for that dataset. Between the lines it
  is the mean of σ over the 2 nm bin that holds the wavelength (trapezoid rule on the full spectrum), stored as
  round(100 log₁₀ σ), so to about 1 %. It is a ranking of single datasets of different age, resolution and temperature,
  not of consensus values, and a molecule that is not listed has no data there.
- In air: α = σxn with n = 101 325 Pa/(k_B × 296 K) = 2.479 × 10¹⁹ cm⁻³ (ideal gas) and x the mole fraction; the
  1/e length is 1/α. The mole fractions are constants of the engine (`AIR_DRY` in `site/js/xsec.js`), not data files:
  N₂ 0.78084, O₂ 0.209476, Ar 0.00934 and H₂ 0.5 ppm from Table 3 of the U.S. Standard Atmosphere, 1976; CO 190,
  O₃ 40, NO₂ 1, NO 0.5, SO₂ 1 and NH₃ 4 ppb from its Table 15 (typical values near the surface); CO₂ 426.10 ppm
  (July 2026), CH₄ 1934.57 ppb and N₂O 339.86 ppb (June 2026) from NOAA's global monthly means. Water vapor is
  x = RH × p_sat/p with p_sat = 2783 Pa at 296 K, from the Antoine equation of the NIST Chemistry WebBook (273 to
  303 K), and each dry-air share is multiplied by 1 − x. Argon is in none of the five collections and has no row.
  The sum of α runs over the gases with a value at the wavelength. Upper limits are listed (≤ α, ≥ length) and left
  out of it; a 2 nm mean, and a row with any other note, shows α and the length as ≈, to two figures. The sum is marked rough (≈, two figures, with the reason) when the values are 2 nm means, when the
  largest α or one within a factor of two of it comes from a flagged row, or when flagged rows carry a tenth of it or
  more; the line then also gives the sum without the flagged rows. It is absorption by the listed gases only: no
  scattering, no collision-induced absorption, no gas without a table.
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

The site keeps its data files in `beta/cross-sections/data/`:

| File | Size | What | Read |
|---|---|---|---|
| `species.json` | 57 kB | the species list: key, formula, name, CAS number, number of datasets | first; search works once it is in |
| `sp/<key>.json` | 1004 files, 2.8 MB | one species' datasets (reference, temperature, range, points) | when the species is chosen |
| `s/00001.json` to `s/05860.json` | 39 MB | one spectrum each | when it is shown |
| `who.json` | 186 kB | "Who absorbs here?" at the 13 preset lines: one dataset per species, its σ, and the spread of σ within 0.25 nm where the spectrum is structured | after the first render |
| `coarse.json` | 547 kB | the same in 2 nm bins, for any other wavelength | when such a wavelength is typed |
| `index.json` | 2.8 MB | `species.json` and all of `sp/` in one file | only where those are missing |

Up to version 1.0.4 the page read `index.json` before it showed anything. It now starts from `species.json` (57 kB)
and the chosen species' own file (143 kB for ozone, the largest; under 1 kB for half of them). `index.json` is still
written, byte for byte as before, for two reasons: a copy of the page from before the split reads nothing else, and the
page falls back on it when a species file is missing or holds another species. A species key that differs from an
earlier one only by case (CO and Co) gets a file name with a suffix, which the species list names, so that the folder
also works on a disk that ignores case.

I rebuild the files from my archive with

```sh
python scripts/build_data.py <archive>/clean <site>/beta/cross-sections/data
```

and commit them to the site's repository. Each spectrum with more than 2000 points is thinned to 2000 that keep its
shape on a log σ scale: in each bucket of points the one that spans the largest triangle with its neighbors, so peaks
and band heads survive (`resample()` in `site/js/xsec.js` and in the build script; a test checks that they agree
point for point). Narrow windows between bands can still fall between the kept points, so for each thinned spectrum
the index also stores σ of the full spectrum at every preset laser line (`at`), and the table uses it there. The full
spectra stay in the archive. The spectrum files are numbered in build order, so a rebuild that leaves a dataset out
renumbers the files after it; the page finds each file through the species' entry.

The page code comes from this repository. Once a day the site's `sync-tool-repos` workflow reads the latest release,
runs its Node tests, copies its `site/` folder over `beta/cross-sections/` while keeping the site's `data/` folder as it
is, and then runs `node scripts/selftest.mjs <copied folder> --data`, which checks the code against the site's data
and boots the page on it. It publishes only if both pass; otherwise the folder is put back as it was. A data rebuild
committed to the site is not checked by that job; I run the same command on the site's folder before I commit one.

The data come first: a release that reads new data files is made after those files are on the site. The check works
the split files out again from `index.json` and the spectra, in JavaScript, and fails where the build's files differ:
the species list and the species files entry for entry, `who.json` dataset for dataset and value for value, and
`coarse.json` run for run (the values of thinned datasets excepted, since their full spectra are not on the site). A
data folder without the split files passes, with a line that says so; the page then reads `index.json` and shows no
reverse lookup.

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
5. `scripts/build_data.py CLEAN OUT [--built YYYY-MM-DD]` writes the page's data files (all six kinds above), and
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
  values, number formatting), the preset laser lines, the reference labels and the rows of "Who absorbs here?" (at a
  line, from the coarse bins, the air view), the air of the air view (number density, water vapor from the humidity,
  the mole fractions against their sources), α and the 1/e length, what makes a sum rough (upper limits, flagged
  rows, 2 nm means, a value in a structured spectrum) and what stays out of it (O₂ above 245 nm), with the expected
  values worked out by hand in the comments.
- `tests/modules.test.mjs`: the page loads. Every module parses, every imported name is exported, `index.html` loads
  `app.js`, the stylesheet and files that exist, every element id `app.js` looks up is in `index.html`, and `app.js`
  reads the data layout the build writes; broken copies of the page check that this check catches them.
- `tests/boot.test.mjs`: the page boots. `app.js` runs in Node against a stand-in document made from the ids in
  `index.html`, with the fixture data; the test reads the panels (the value at a line, the notes on thinned data,
  upper limits and citation texts, the absorption and photolysis results, the "Who absorbs here?" table in its air
  and all-molecules views, between the lines, and a molecule loaded from it; the air view's line, columns and fold at
  three humidities, in the order of σ, between the lines and with a humidity that is not a number; the line with an
  unconfirmed oxygen value and with a value in a band, on a copy of the fixture with O₂ and H₂O added) and breaks copies of the page in ways the
  static check cannot see. It also boots the page on a copy of the data without the split files, with a species file
  missing and with one that holds another molecule: the page must read `index.json` and show the same.
- `tests/selftest.test.mjs`: the engine cases of `scripts/selftest.mjs`, the data checks on `tests/fixtures/data`
  (two Mainz excerpts and synthetic spectra, made by `tests/fixtures/make_fixtures.mjs`), broken copies of that folder
  that the data checks must catch (in the index, the spectra and each of the split files), the rule that picks one
  dataset per molecule step by step, the bin means, and the exit codes of the command line.
- `tests/repo.test.mjs`: one version in package.json, CITATION.cff and the CHANGELOG, no `site/data` folder, and no
  local paths or email addresses in the files.

Python 3 (CI uses 3.14), standard library only:

```sh
python -m unittest discover -s tests -v
```

`tests/test_build_data.py` runs the build script on two small synthetic archives: which datasets are kept and which
skipped and why, the dropping of non-finite and non-positive σ and of points far outside a file's named range,
sorting, rounding, thinning to 2000 points with a narrow spike kept, the stored full-resolution values at the laser
lines, upper limits, references given only as free text, species merged across spellings, the species list and the
species files (two keys that differ only by case among them), the "Who absorbs here?" tables on an archive with one
pair of datasets for each step of the rule, `index.json` with the fields and field order it had before the split, a
rebuild that gives the same bytes, the output passing the site's data checks (which make the split files again in
JavaScript), and the thinning and the reference labels compared with the page's (the last ones need Node).
`tests/test_release.py` checks the version bookkeeping.

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
shared files and the data from a local checkout of the site, and `--offline` serves nothing from the network. A data
folder from before the split (only `index.json` and `s/`) works too, without the reverse lookup. Links to
other pages of the site are sent on to https://cdfoley.com. `--port` picks another port.

## Repository layout

```
site/                what cdfoley.com serves at /beta/cross-sections/, without its data/ folder
  index.html, xsec.css
  js/                xsec.js (the engine: units, interpolation, line averages, absorption, photolysis, the rows of
                     "Who absorbs here?"), app.js (the page)
scripts/
  selftest.mjs       the check the site runs on its copy: engine cases, page check, data checks (the split files
                     are made again from index.json and compared), boot check
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
  version of the script). Version 1.1.0 of the script writes `index.json` and the 5860 spectrum files with the same
  bytes as before, and adds `species.json`, the 1004 species files, `who.json` and `coarse.json`.
- "Who absorbs here?": the build makes its tables in Python from the archive, and the site's check makes them again in
  JavaScript from `index.json` and the spectra on the site. On the site's data the two agree on every one of the 4514
  rows at the 13 preset lines (dataset, value to 1 part in 10⁹, point or gap, label) and on every one of the 2362 runs
  of the coarse table. Of the 4514 rows, 661 are marked as interpolated across a gap of more than 5 nm, 55 as a
  single listed point, 52 as electron energy loss and 12 as upper limits; no row needs an isotopologue file. At 248.4 nm the row for ozone is the first row of the laser-line table, 1.079 × 10⁻¹⁷ cm² (Sander et al.
  2011).
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
- The air view at 248.4 nm and 50 % relative humidity, on the site's data: O₃ 39.5 ppb, α = 0.00105 m⁻¹, 948 m;
  five gases together 0.00106 m⁻¹, a 1/e length of 947 m (the page's worked example, by hand). O₂ is listed and left
  out of that sum: the series the rule picks above 245 nm gives 1.98 × 10⁻²⁴ cm² at 248.4 nm (α ≈ 0.001 m⁻¹, as much
  as ozone), two older tables 2.96 and 2.80 × 10⁻²⁵, and a high-resolution spectrum 2.9 × 10⁻²⁸ between its bands.
  At 193.3 nm the O₂ value sits on the flank of a line (its dataset's points within 0.25 nm span a factor of 63), so
  the figures are marked ≈: α ≈ 0.35 of ≈ 0.41 m⁻¹, a 1/e length of ≈ 2.4 m. At 354.7 nm the largest α comes from a
  CO₂ value measured at one wavelength and 2073 K; the line says so, marks the figures ≈ and gives the sum without
  it.
- The 49 engine cases pass in Node on this repository's copy and on the site's, the site's copy passes the data
  checks and the boot check, and the page loads in a browser with no console errors. 83 Node tests and 42 Python
  tests pass.

## Known limitations

- 223 datasets (170 from the Mainz snapshot and 53 from TUV-x) have their reference in the archive only as free
  text, with no author or title fields. The page shows that text (for TUV-x, the start of the file header, which
  usually names the paper), with the authors taken from it where they can be read (153 of the 170 Mainz files);
  the other 70 are labeled by the author part of the Mainz file name or the TUV-x file name.
- "Who absorbs here?" ranks one dataset per molecule. Two molecules a factor of two apart may be measured at
  different resolutions, temperatures and decades, so the order of near neighbors means little, and for banded
  spectra (O₂, NO, SO₂) the value at one wavelength depends on the resolution and on where exactly the line sits.
  The rule that picks the dataset reads file names and point spacing, not the physics: an optical table can still
  be the weaker one (the Leiden NO₂ file between its VUV bands sits at a floor of 5 × 10⁻²⁰ cm², far below the
  electron energy loss spectrum it is preferred to), so a row is a pointer to the data, not a reviewed value.
  Between the preset lines the values are 2 nm means. Outside the air view the table ranks σ per molecule and knows
  nothing about abundance, and the gases of air that none of the five collections tabulates (argon, for one) are not
  in it.
- The air view uses one typical set of mole fractions at 1 atm and 296 K. The 1976 values for CO, O₃, NO₂, NO, SO₂
  and NH₃ stand for clean air near the surface; real air can hold many times more, and α scales with the share. Its
  sum is not the extinction of air (no scattering, no collision-induced absorption, only the gases with a table, and
  no O₂ above 245 nm), and in banded regions one σ at one wavelength does not give the transmission of a real laser
  line. The structure flag sees only what the chosen dataset resolves, and only at the preset lines. The O₂ case was
  found by comparing datasets by hand; the rule cannot find such cases, and there may be others.
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
