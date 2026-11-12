# Changelog

Versions follow semantic versioning. Releases are made by hand (`scripts/release.py bump`, then
`scripts/finish-release.sh`, README.md "Making a release"); cdfoley.com copies the latest release once a day. A new build of the data files is not a release of this repository: the data live only on
the site (README.md).

## 1.1.0 - 2026-11-12

- New panel, Who absorbs here?: at the wavelength of the laser-line field, every molecule with data there, strongest first, with the dataset each value comes from. It opens on the gases of air (N2, O2, H2O, CO2, CH4, H2, N2O, CO, O3, NO2, NO, SO2, NH3) and names the ones with no data at the wavelength; All molecules lists the rest. A press on a molecule loads it with that dataset first.
- The air view answers what takes the light in air. σ is per molecule, so ranking by it misleads there: ozone has a large cross section and is a trace gas, oxygen a small one and is a fifth of the air. Each gas now shows its mole fraction in air, its absorption coefficient α = σ × mole fraction × number density of air (1 atm, 296 K, ideal gas, 2.479 × 10¹⁹ cm⁻³) per meter, and the 1/e path length. The view opens in the order of α; “By σ per molecule” gives the old order, and All molecules still ranks by σ. A line above the table names the gas with the largest α (two gases, where they are within a factor of two) and the 1/e length of the listed gases together. At 248.4 nm that is O₃ and 947 m, with O₂ listed and left out of the sum.
- Mole fractions: N₂, O₂ and H₂ from Table 3 of the U.S. Standard Atmosphere, 1976; CO, O₃, NO₂, NO, SO₂ and NH₃ from its Table 15 (typical values near the surface); CO₂, CH₄ and N₂O from NOAA’s global monthly means of mid 2026. Water vapor follows a relative humidity field (50 % to start, at 296 K; saturation pressure from the Antoine equation of the NIST Chemistry WebBook), and the dry-air shares shrink with it. A fold lists every share with its source. Argon has no cross sections in the five collections, and the panel says so. The shares are constants of the page code; the data files are unchanged.
- Flags carry through. An upper limit shows as ≤ α and ≥ length and is left out of the sum. A 2 nm mean, and any row with another note, shows α and the length as ≈, to two figures. Where a flagged value leads, or flagged values carry a tenth of the sum or more, the line marks its figures ≈, says which flag, and gives the sum without the flagged values. The line always says that it sums only the gases with a value at the wavelength and leaves out scattering.
- A value in a structured spectrum is flagged. The build stores, with each value at a preset line, how far σ ranges among that dataset's points within 0.25 nm of the line (largest over smallest, from a factor of two up). At 193.3 nm the O₂ value sits on the flank of a Schumann-Runge line and its points span a factor of 63, so the row says so and the figures for air are marked ≈.
- O₂ above 245 nm is listed and left out of the sum for air. The recommended table ends at 245 nm, and the one series that runs on lies 7 times above the two older tables at 248.4 nm and about 100 times above the high-resolution spectrum at 266 nm. The line above the table says what the listed value would have given.
- The line says a gas takes the most light only when N₂, O₂ and H₂O are all in the sum and the leading value carries no flag. Otherwise it says the gas has the largest listed value and names the main gases with no table at the wavelength.
- The humidity field sits above the table, and the laser-line panel links to the new one.
- One dataset stands for each molecule, by a rule the panel states: measured values before upper limits, optical absorption before electron energy loss spectra, points no more than 5 nm apart around the wavelength, a spectrum before a single point or a list of band maxima, the natural sample before a single isotopologue, room temperature, a recommended dataset, the newest, the most points. A Note column says when the dataset that is left is a weak one: an upper limit, one measured wavelength, electron energy loss, a value interpolated across a gap, an isotopologue, or a temperature far from room temperature. Line-intensity lists and underflow values (below 1e-40 cm2) are not listed.
- A file of band maxima (marked max, peaks or band heads in the MPI-Mainz file names) is now read point by point in the laser-line table: the nearest listed point within 1 nm, with its wavelength, and no value between two bands. Before, the table interpolated between the maxima of separate bands. At the 13 preset lines the values are point values of the full spectra, the numbers the laser-line table gives. At any other wavelength they are means over 2 nm, marked as approximate. A molecule that is not listed has no data there, which the panel says is not the same as no absorption.
- The page starts faster. It used to read index.json (2.8 MB) before it showed anything. It now reads a species list of 57 kB, which is all the search needs, and then only the chosen molecule's own file.
- The data build writes the new files beside index.json: species.json, sp/<key>.json (one per species), who.json and coarse.json. index.json and the spectrum files are written with the same bytes as before, and the page falls back on index.json where the new files are missing, so the data can be updated before the page is.
- The site's check makes the new files again from index.json and the spectra, in JavaScript, and fails where the build's files differ. It boots the page on the split files, loads a molecule from the reverse lookup, and passes a data folder from before the split with a line that says so. Seven engine cases added (49 in all), four of them for the air view; the boot check fails a page whose air view has rows and no answer for air. On a phone the table is one card per molecule and keeps its table roles for screen readers.
- Worked example, How it works, Assumptions and limits and References cover the new panel and its air view; Key terms gains the absorption coefficient α.

## 1.0.4 - 2026-11-12

- A number typed into any field is now read whole or not at all. Before, 1,5 was read as 1 and 12abc as 12, and the page computed with that. Now a decimal comma is a decimal (1,5 is 1.5), and text that is not one number (1,064, which could be 1064 or 1.064, or 12abc) gives a message that names the field instead of a result.
- On a phone, the table of values at a laser line is now one card per dataset, so the cross section is no longer cut off at the edge of the screen.
- Shorter introduction. The list of the five collections moved to the Data sources and terms panel.
- New Typical values table and a Worked example that follows the page as it opens, number for number. A line under the laser-line table gives a sense of scale.
- Reset and Copy link sit in the head of the Spectrum panel. Reset returns the page to how it opens.
- The dataset list can be filtered to the recommended datasets or to one source. The count badge names the molecule (O3: 264 datasets). Two shown datasets with the same reference and temperature are told apart by their wavelength range.
- The From and To limits of the plot are in the unit of the horizontal axis (nm, cm-1 or eV) and convert when the axis changes. Laser-line labels on the plot are in that unit too, and where the lines crowd only the labels that fit are drawn.
- The line under the laser-line table writes its units out (248.4 nm = 40257.6 cm-1 = 4.9913 eV). The second value column appears only when the plot unit is not cm2.
- A search with no match says so instead of closing. The optical depth heading shows a lower-case tau. The value field of the unit converter keeps its width on a phone.
- The BETA badge beside the title is gone; the line above the title, the breadcrumb and the notice already say beta.

## 1.0.3 - 2026-11-11

- Page description, social-card text and structured data say "five public collections" instead of "five open datasets", matching the introduction: three of the five collections state no license.

## 1.0.2 - 2026-11-11

- Release test checks the current version's notes without assuming it is the first release. The v1.0.1 tag was never released; this release carries its boot-check fix too.

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
