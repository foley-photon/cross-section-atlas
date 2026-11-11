# Data notice

The MIT license in LICENSE covers my code and text in this repository. It does not cover the cross-section data the
page shows. Those data are not in this repository (README.md says why); cdfoley.com serves its own copy at
https://cdfoley.com/beta/cross-sections/, with the terms of each source shown on the page.

## What is here

Only the test fixtures in `tests/fixtures/data/` hold measured values:

- Two excerpts of the MPI-Mainz UV/VIS Spectral Atlas of Gaseous Molecules of Atmospheric Interest, 2013-06-24
  snapshot, by H. Keller-Rudek, G. K. Moortgat, R. Sander and R. Sörensen, Zenodo, doi:10.5281/zenodo.6951, licensed
  under the Creative Commons Attribution 4.0 International license (CC BY 4.0,
  https://creativecommons.org/licenses/by/4.0/). The excerpts are the ozone cross sections of L. T. Molina and
  M. J. Molina, "Absolute absorption cross sections of ozone in the 185- to 350-nm wavelength range," J. Geophys. Res.
  91, 14501–14508 (1986), 0.5 nm averages at 298 K and at 226 K, from the files
  `O3_MolinaMolina(1986)_298K_185-350nm(0.5nm).txt` and `O3_MolinaMolina(1986)_226K_185-350nm(0.5nm).txt`. Changes:
  only the 35 points from 245 to 262 nm of each file are kept, written as JSON; the values are unchanged. Cite the
  atlas as H. Keller-Rudek, G. K. Moortgat, R. Sander and R. Sörensen, Earth Syst. Sci. Data 5, 365–373 (2013),
  doi:10.5194/essd-5-365-2013, and the measurement as Molina and Molina (1986).
- The synthetic spectra of the made-up molecule "Xx" in the same folder are mine and are covered by the MIT license.

The ozone reference value the self-test compares with, 1.1329(35) × 10⁻¹⁷ cm² at 253.65 nm, is from J. T. Hodges et
al., "Recommendation of a consensus value of the ozone absorption cross-section at 253.65 nm based on a literature
review," Metrologia 56, 034001 (2019), doi:10.1088/1681-7575/ab0bdd. Physical constants are CODATA 2022 (P. J. Mohr,
D. B. Newell, B. N. Taylor and E. Tiesinga, Rev. Mod. Phys. 97, 025002 (2025)).

## The sources the site's data come from

These are the terms as I found them when I made the archive on 2026-11-07. This is not legal advice.

| Source | Terms | Cite |
|---|---|---|
| MPI-Mainz UV/VIS Spectral Atlas, 2013 snapshot | CC BY 4.0 (Zenodo record 6951) | Keller-Rudek et al. (2013), doi:10.5194/essd-5-365-2013, and the original paper |
| NCAR TUV-x v0.17.0 data files | Apache License 2.0 (the repository's license) | the TUV-x software, doi:10.5281/zenodo.7126039, and the reference each file names |
| Leiden database of photodissociation and photoionization cross sections | no license stated; the site asks users to cite an overview paper and the original sources | A. N. Heays, A. D. Bosman and E. F. van Dishoeck, Astron. Astrophys. 602, A105 (2017), doi:10.1051/0004-6361/201628742, or H. R. Hrodmarsson and E. F. van Dishoeck, Astron. Astrophys. 675, A25 (2023), doi:10.1051/0004-6361/202346645 |
| IUP Bremen molecular spectroscopy data | no license stated; the files ask that the publication be cited | the paper named with each dataset |
| Harvard-Smithsonian Center for Astrophysics molecular database | no license stated; cite the publications | the paper named with each dataset |

The measurements are in every case the work of their original authors. The scripts in `scripts/archive/` and
`scripts/build_data.py` read these sources and the archive made from them; they contain no data.

## No endorsement

None of the sources above, their authors or their institutions endorses this repository or the page.
