# Changelog

Versions follow semantic versioning. Releases are made by hand (`scripts/release.py bump`, then
`scripts/finish-release.sh`, README.md "Making a release"); cdfoley.com copies the latest release once a day. A new build of the data files is not a release of this repository: the data live only on
the site (README.md).

## 1.0.1 - 2026-11-11

- The site's daily copy now passes on Linux: the self-test's boot check waits for its result line to be written before the check process exits. On Linux, output to a pipe is written asynchronously, so exiting early cut the line short and the check reported that the boot did not finish. The page and the data are unchanged.

## 1.0.0 - 2026-11-11

First release as its own repository. The page is the one served at https://cdfoley.com/beta/cross-sections/, with
these changes made at the move:

- "At a laser line" gives, at the preset lines, the point value of a thinned dataset's full spectrum, which the data
  build now stores, and elsewhere says when a value comes from a spectrum thinned for the web (more than 2000 points
  in the source). Between the kept points σ can be far from the source's: at the laser lines, 12 % of the pairs of a
  thinned dataset and a line in its range are more than 10 % off, and a few are off by orders of magnitude (O2 at
  Lyman-α in the Leiden spectrum, 490 times). The temperature interpolation below the table uses the same values,
  keeps one paper's versions (resolution, pressure, revision) apart, and carries the same note. The "How it works"
  section and the plot note explain the thinning.
- Laser presets at the wavelengths of the lines they name: Nd:YAG 5th 212.8 nm (was 213), 3rd 354.7 nm (was 355),
  2nd 532.1 nm (was 532), XeF 351.1 nm (was 351). In the well-resolved SO2 spectra near 213 nm and CH2O spectra near
  355 nm, the 0.2 to 0.3 nm offsets changed σ by 25 to 33 % at the median.
- Numbers from 10⁴ to 10⁵ (ε above about 3.8 × 10⁻¹⁷ cm², σ in barn, and others) showed as "1.308e+4"; they now use
  the page's "× 10ⁿ" form, and so does the transmitted percentage.
- On a log axis, points more than 12 decades below the largest value shown (the band wings of some modeled Leiden
  spectra, down to 10⁻³²⁰ cm²) are left out of the plot, and the plot note says how many.
- Datasets that are upper limits are labeled as such in the list, the table and the CSV download. Where a source gives
  no authors or title, the list shows its citation text, and the CSV download does too.
- The "Data sources and terms" text no longer says every dataset's original paper is listed with it; it says what is
  listed. "Fraction photolysed" is spelled "photolyzed".
- The introduction says "five public collections" instead of "five open datasets", since three of the five state no
  license.
- The photolysis note states its assumption (a molecule that absorbs without dissociating is back in the ground state
  within the pulse) and gives φ(1 − e^−σΦ) for the other case.
- The air and vacuum note adds that the wavenumber and photon-energy axes use the wavelength as given, so an air
  wavelength lands about 3 parts in 10⁴ high (12 cm⁻¹ at 250 nm).
- The introduction no longer says every dataset is credited to the paper that measured it: Leiden and TUV-x datasets
  carry the compilation's or the evaluation's reference.
- Problems are reported through this repository's issues; the "Data sources and terms" section links the source code.
- The unit converter shows Loschmidt's constant as 2.68678011 × 10¹⁹ cm⁻³. It showed 2.686780112, which looked like a
  disagreement with the 2.686 780 111 in the text; both are the CODATA value, one rounded and one cut off.
- Corrected comments: the air and vacuum difference at 250 nm in xsec.js (0.075 nm, not 0.06 nm) and the data path in
  app.js.

Data on the site (not part of this repository; rebuilt with this release's scripts/build_data.py):

- 32 more datasets left out: 17 MPI-Mainz O2-O2 collision-induced absorption files (cm5 molecule-2, labeled
  cm2 molecule-1), 14 MPI-Mainz files that are not σ against wavelength (σ against temperature at one wavelength,
  fit parameters, a temperature gradient), which the page plotted against "wavelength", and one file whose only point
  lies far outside its named range. One point at 21.0 nm in a 210 to 227.5 nm file is dropped. 1004 molecules and
  5860 datasets remain.
- Bremen and CfA terms now read "No license stated", as the sources say, instead of "Distributed for research use".
- References given only as free text are shown; run-together journal fields are separated.

Also in this release:

- scripts/build_data.py, the script that builds the page's data files from the cleaned archive (taken from the site's
  repository, now with the paths as arguments, a fixed build date option and the changes above). Its output from the
  2026-11-07 archive with `--built 2026-11-11` is the site's data byte for byte.
- scripts/archive/, the scripts that made the cleaned archive from the five sources' downloads (2026-11-07), as run.
- scripts/thinning_check.py, which measures the thinning error at the laser lines against the full spectra.
- Tests: engine unit tests with hand-worked values; the page check (modules parse, imports resolve, index.html names
  files that exist, app.js reads the data layout the build writes) with negative controls; the data checks on a small
  fixture folder (two CC BY 4.0 excerpts of the MPI-Mainz 2013 snapshot and synthetic spectra) with broken copies; the
  build script on a synthetic archive, including a point-for-point comparison of its thinning with the page's.
- scripts/selftest.mjs, the check the site runs on its copy before it publishes a release: engine cases and the page
  check (including every element id app.js uses), and with `--data` every data file, ozone at 253.65 nm against
  Hodges et al. (2019), and a boot of the page on the data in a stand-in document.
- scripts/finish-release.sh, which tags the version on main and makes its GitHub release.
- Local preview: scripts/serve.mjs, with the data from cdfoley.com, a local folder or a local checkout of the site.
