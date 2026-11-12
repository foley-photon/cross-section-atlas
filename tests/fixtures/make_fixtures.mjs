// Writes tests/fixtures/data/: a data folder in the layout the page reads (index.json and s/<n>.json, and the split
// files species.json, sp/<key>.json, who.json and coarse.json), small enough to live in the repository. It holds
//   - two excerpts of the MPI-Mainz UV/VIS Spectral Atlas 2013 snapshot (CC BY 4.0, doi:10.5281/zenodo.6951; see
//     NOTICE.md): ozone from L. T. Molina and M. J. Molina, J. Geophys. Res. 91, 14501 (1986), 0.5 nm averages at 298 K
//     and 226 K, 245–262 nm only (35 of the 331 points of each file), values unchanged;
//   - synthetic spectra of a made-up molecule "Xx" (a Gaussian band, a single point, a temperature range, no stated
//     temperature), which are mine and MIT-licensed like the code. The 298 K band is marked as if the build had thinned
//     it from 6001 points and stored the band's values at four laser lines (the Gaussian itself, to 5 figures); the
//     VUV steps carry a citation text instead of authors and title, and are marked as upper limits.
// The split files are made from the index and the spectra by deriveSplit() of scripts/selftest.mjs, the JavaScript twin
// of what scripts/build_data.py writes (tests/test_build_data.py checks that the two agree). In "Who absorbs here?" the
// thinned band stands for Xx at 212.8 to 266 nm (it has more points in its source than the 200 to 300 K band), the single
// point at Lyman-α, and the upper limits at 157.6 nm, where Xx has nothing else.
// Run from the repository root to rewrite the folder: node tests/fixtures/make_fixtures.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { deriveSplit } from '../../scripts/selftest.mjs';
import * as X from '../../site/js/xsec.js';

const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'data');
const nm = Array.from({ length: 35 }, (_, i) => 245 + 0.5 * i);
const MOLINA_298 = [9.932e-18, 1.025e-17, 1.033e-17, 1.034e-17, 1.047e-17, 1.068e-17, 1.071e-17, 1.082e-17, 1.112e-17, 1.112e-17,
    1.124e-17, 1.113e-17, 1.114e-17, 1.146e-17, 1.155e-17, 1.139e-17, 1.14e-17, 1.155e-17, 1.159e-17, 1.14e-17, 1.161e-17, 1.173e-17,
    1.154e-17, 1.13e-17, 1.139e-17, 1.129e-17, 1.124e-17, 1.157e-17, 1.145e-17, 1.09e-17, 1.08e-17, 1.114e-17, 1.094e-17, 1.057e-17, 1.057e-17];
const MOLINA_226 = [1.007e-17, 1.04e-17, 1.042e-17, 1.039e-17, 1.058e-17, 1.08e-17, 1.079e-17, 1.094e-17, 1.124e-17, 1.121e-17,
    1.134e-17, 1.118e-17, 1.123e-17, 1.164e-17, 1.165e-17, 1.143e-17, 1.149e-17, 1.167e-17, 1.169e-17, 1.145e-17, 1.174e-17, 1.184e-17,
    1.158e-17, 1.132e-17, 1.147e-17, 1.134e-17, 1.13e-17, 1.172e-17, 1.151e-17, 1.084e-17, 1.086e-17, 1.128e-17, 1.095e-17, 1.056e-17, 1.064e-17];

const molina = { a: 'L.T Molina and M.J. Molina', y: 1986, t: 'Absolute absorption cross sections of ozone in the 185- to 350-nm wavelength range', j: 'J. Geophys. Res. 91, 14501-14508 (1986)', doi: '' };
const synth = { a: 'C. D. Foley', y: 2026, t: 'Synthetic test spectrum (not a measurement)', j: '', doi: '' };
const band = []; for (let l = 200; l <= 300 + 1e-9; l += 0.5) band.push([+l.toFixed(1), +(1e-17 * Math.exp(-(((l - 255) / 20) ** 2))).toPrecision(5)]);

const spectra = {
    '00001': nm.map((l, i) => [l, MOLINA_298[i]]),
    '00002': nm.map((l, i) => [l, MOLINA_226[i]]),
    '00003': band,
    '00004': band.map(([l, s]) => [l, +(2 * s).toPrecision(5)]),
    '00005': [[121.567, 3.0e-18]],
    '00006': [[150, 1e-19], [160, 2e-19], [170, 4e-19], [180, 2e-19]],
};
const gaussAt = (l) => +(1e-17 * Math.exp(-(((l - 255) / 20) ** 2))).toPrecision(5);
const set = (id, f, src, T, ref, extra = {}) => {
    const d = spectra[f];
    return { id, f, src, T, l: [d[0][0], d[d.length - 1][0]], np: d.length, n0: d.length, rec: false, med: 'unknown', res: '', ref, y: ref.y, note: '', ...extra };
};
const index = {
    meta: {
        built: '2026-11-11', archive: 'fixture', max_points: 2000, skipped: [],
        sources: {
            mainz2013: {
                short: 'MPI-Mainz 2013', name: 'The MPI-Mainz UV/VIS Spectral Atlas of Gaseous Molecules of Atmospheric Interest, 2013 snapshot',
                url: 'https://doi.org/10.5281/zenodo.6951', license: 'CC BY 4.0 (Zenodo record).',
                cite: 'H. Keller-Rudek, G. K. Moortgat, R. Sander and R. Sörensen, Earth Syst. Sci. Data 5, 365–373 (2013), doi:10.5194/essd-5-365-2013, and the original papers.',
            },
            test: { short: 'Test', name: 'Synthetic spectra made for the tests of this repository', url: '', license: 'MIT (part of this repository).', cite: 'nothing: these are not measurements.' },
        },
    },
    species: [
        { k: 'O3', f: 'O3', n: 'ozone', cas: '10028-15-6', sets: [
            set('mainz2013:O3_MolinaMolina(1986)_298K_185-350nm(0.5nm)', '00001', 'mainz2013', 298, molina, { note: 'Excerpt for tests: 245-262 nm of the 331-point file.' }),
            set('mainz2013:O3_MolinaMolina(1986)_226K_185-350nm(0.5nm)', '00002', 'mainz2013', 226, molina, { note: 'Excerpt for tests: 245-262 nm of the 331-point file.' }),
        ] },
        { k: 'Xx', f: 'Xx', n: 'synthetic test molecule', cas: '', sets: [
            set('test:Xx_band_298K', '00003', 'test', 298, synth, { med: 'vacuum', n0: 6001, at: Object.fromEntries([212.8, 222, 248.4, 266].map((l) => [String(l), gaussAt(l)])) }),
            set('test:Xx_band_200-300K', '00004', 'test', [200, 300], synth, { med: 'air' }),
            set('test:Xx_lyman_alpha_point', '00005', 'test', null, synth),
            set('test:Xx_vuv_steps', '00006', 'test', 295, { a: '', y: 2026, t: '', j: '', doi: '', c: 'Synthetic test spectrum, not a measurement (2026).', lab: 'Xx steps' }, { rec: true, ul: true, note: 'Upper limits, not measured cross sections.' }),
        ] },
    ],
};
fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(path.join(OUT, 's'), { recursive: true });
fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index));
for (const [f, d] of Object.entries(spectra)) fs.writeFileSync(path.join(OUT, 's', `${f}.json`), JSON.stringify(d));
const split = deriveSplit(index, (f) => spectra[f], X);
fs.mkdirSync(path.join(OUT, 'sp'));
fs.writeFileSync(path.join(OUT, 'species.json'), JSON.stringify(split.slim));
for (const [stem, s] of split.files) fs.writeFileSync(path.join(OUT, 'sp', `${stem}.json`), JSON.stringify(s));
fs.writeFileSync(path.join(OUT, 'who.json'), JSON.stringify(split.who));
fs.writeFileSync(path.join(OUT, 'coarse.json'), JSON.stringify(split.coarse));
console.log(`wrote ${OUT}: ${index.species.length} species, ${Object.keys(spectra).length} spectra, and the split files`);
