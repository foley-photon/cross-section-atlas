// The engine (site/js/xsec.js): unit factors, photon conversions, interpolation, laser-line averages, temperature
// interpolation, thinning, Beer–Lambert and photolysis per pulse, reference labels and the rows of "Who absorbs here?".
// Expected values are worked out by hand in the comments,
// with CODATA 2022 constants (N_A, h, c, k and e are exact).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as X from '../site/js/xsec.js';

const near = (got, want, rel, msg) => assert.ok(Math.abs(got / want - 1) <= rel, `${msg || ''} got ${got}, want ${want} (±${rel})`);

test('constants are CODATA 2022', () => {
    assert.equal(X.N_A, 6.02214076e23);
    assert.equal(X.H, 6.62607015e-34);
    assert.equal(X.C, 299792458);
    assert.equal(X.K_B, 1.380649e-23);
    // n0 = 101 325 / (1.380 649e-23 × 273.15) m⁻³ = 2.686 780 111e25 m⁻³ = 2.686 780 111e19 cm⁻³
    near(X.LOSCHMIDT, 2.686780111e19, 1e-9);
    // a0 = 5.291 772 105 44e-11 m, so a0² = 2.800 285 20e-17 cm²
    near(X.A0_2, 2.80028520e-17, 1e-8);
    // 2π² r_e ħc = 19.7392 × 2.817 940 3205e-13 cm × 1.973 269 804e-5 eV cm = 1.097 61e-16 cm² eV
    near(X.SIGMA_PER_DFDE, 1.09761e-16, 1e-5);
});

test('cross-section units, from 1e-17 cm²', () => {
    const s = 1e-17; const U = X.SIGMA_UNITS;
    near(U.cm2.to(s), 1e-17, 1e-15);
    near(U.eps10.to(s), 2615.3825, 1e-7, 'ε10 = σ N_A / (1000 ln 10) = 6022.140 76 / 2.302 585');
    near(U.epse.to(s), 6022.14076, 1e-9, 'εe = σ N_A / 1000');
    near(U.k273.to(s), 268.678011, 1e-8, 'k = σ n0');
    near(U.k273_10.to(s), 116.685378, 1e-7, 'k10 = σ n0 / ln 10');
    near(U.Mb.to(s), 10, 1e-12);
    near(U.barn.to(s), 1e7, 1e-12);
    near(U.A2.to(s), 0.1, 1e-12);
    near(U.a02.to(s), 0.357106, 1e-5, '1e-17 / 2.800 285e-17');
    near(U.m2.to(s), 1e-21, 1e-12);
    near(U.dfdE.to(s), 0.0911071, 1e-5, '1e-17 / 1.097 61e-16 eV⁻¹');
    // Berkowitz's rule of thumb: σ in Mb ≈ 109.76 × df/dE in eV⁻¹
    near(U.Mb.to(U.dfdE.from(1)), 109.761, 1e-5);
});

test('every unit converts to σ and back, and labels are distinct', () => {
    for (const [k, u] of Object.entries(X.SIGMA_UNITS)) {
        for (const s of [1e-24, 3.7e-19, 2e-16]) near(u.from(u.to(s)), s, 1e-12, k);
        assert.ok(u.to(2e-18) > u.to(1e-18), `${k} increases with σ`);
    }
    const labels = Object.values(X.SIGMA_UNITS).map((u) => u.label);
    assert.equal(new Set(labels).size, labels.length);
});

test('photon energy, wavenumber and number density', () => {
    near(X.nmToEV(1239.8419843320026), 1, 1e-12, 'hc/e = 1239.841 984 nm eV');
    near(X.nmToEV(248.4), 4.991313, 1e-6);
    near(X.nmToEV(121.567), 10.198837, 1e-6, 'Lyman-α');
    assert.equal(X.nmToCm1(250), 40000);
    near(X.photonJ(248.4), 7.996964e-19, 1e-6, 'hc/λ = 1.986 446e-25 J m / 248.4e-9 m');
    // 1 Torr = 101 325/760 Pa = 133.322 368 Pa; n = p/kT = 133.322 368 / (1.380 649e-23 × 296) m⁻³ = 3.262 33e16 cm⁻³
    near(X.density(133.322368, 296), 3.262331e16, 1e-6);
    assert.equal(X.density(0, 296), 0);
    assert.equal(X.density(100, 0), 0);
    assert.equal(X.density(-1, 296), 0);
});

test('linear interpolation, and no value outside the data', () => {
    const d = [[253.5, 1.155e-17], [254, 1.159e-17], [255, 1.161e-17]];
    near(X.sigmaAt(d, 253.65), 1.1562e-17, 1e-12, '1.155 + 0.3 × 0.004');
    assert.equal(X.sigmaAt(d, 253.5), 1.155e-17);
    assert.equal(X.sigmaAt(d, 254), 1.159e-17);
    assert.equal(X.sigmaAt(d, 255), 1.161e-17);
    assert.equal(X.sigmaAt(d, 253.49), null);
    assert.equal(X.sigmaAt(d, 255.01), null);
    assert.equal(X.sigmaAt([], 250), null);
    assert.equal(X.sigmaAt([[121.567, 3e-18]], 121.567), 3e-18);
    assert.equal(X.sigmaAt([[121.567, 3e-18]], 121.6), null);
    // a repeated wavelength (a step in a binned table): the value after the step there, and no division by zero
    const step = [[100, 1e-18], [110, 2e-18], [110, 5e-18], [120, 5e-18]];
    assert.equal(X.sigmaAt(step, 110), 5e-18);
    near(X.sigmaAt(step, 105), 1.5e-18, 1e-12);
});

test('median step', () => {
    assert.equal(X.medianStep([[1, 1], [2, 1], [4, 1], [5, 1]]), 1);
    assert.equal(X.medianStep([[1, 1], [3, 1]]), 2);
    assert.equal(X.medianStep([[1, 1]]), null);
});

const gauss = (A, l0, w) => (l) => A * Math.exp(-(((l - l0) / w) ** 2));
const band = []; for (let l = 200; l <= 300; l += 0.5) band.push([l, gauss(1e-17, 255, 20)(l)]);

test('a Gaussian laser line on a Gaussian band', () => {
    // band σ0 exp(−((λ−255)/20)²) has standard deviation s1 = 20/√2 nm; a line of 10 nm FWHM has s2 = 10/2.3548 = 4.2466 nm.
    // The line-weighted average at the band center is σ0 s1/√(s1² + s2²) = σ0 × 14.142/√(200 + 18.034) = 0.957 75 σ0.
    const s1 = 20 / Math.SQRT2; const s2 = 10 / (2 * Math.sqrt(2 * Math.LN2));
    const r = X.sigmaLine(band, 255, 10);
    near(r.sigma, 1e-17 * s1 / Math.hypot(s1, s2), 1e-4);
    near(r.sigma, 0.95775e-17, 1e-4);
    near(r.covered, 1, 1e-6);
    assert.equal(r.coarse, false);
    assert.equal(r.points, 41, 'points within ±FWHM: 245 to 265 nm in 0.5 nm steps');
});

test('laser-line average: point value, flat spectrum, edge of the data, outside, coarse data', () => {
    const p = X.sigmaLine(band, 253.65, 0);
    assert.equal(p.sigma, X.sigmaAt(band, 253.65));
    assert.equal(p.covered, 1);
    assert.equal(X.sigmaLine(band, 199, 0).covered, 0);
    near(X.sigmaLine([[200, 2e-19], [210, 2e-19], [220, 2e-19]], 210, 3).sigma, 2e-19, 1e-12);
    // centered on the last point, half of the line's weight lies inside the data
    near(X.sigmaLine(band, 300, 2).covered, 0.5, 2e-3);
    const out = X.sigmaLine(band, 400, 1);
    assert.equal(out.sigma, null);
    assert.equal(out.covered, 0);
    // data every 5 nm against a 1 nm line: flagged as coarse (the average is then only an interpolation)
    const coarse = X.sigmaLine([[240, 1e-18], [245, 2e-18], [250, 3e-18], [255, 2e-18]], 247, 1);
    assert.equal(coarse.coarse, true);
    near(coarse.sigma, 2.4e-18, 1e-3, 'linear between 245 and 250 nm at 247 nm');
});

test('temperature interpolation is linear in T and never extrapolates', () => {
    const at = (s) => [[253.5, s[0]], [254, s[1]]];
    const sets = [{ T: 226, data: at([1.167e-17, 1.169e-17]) }, { T: 298, data: at([1.155e-17, 1.159e-17]) }];
    // 1.1676 at 226 K, 1.1562 at 298 K: at 262 K, 1.1676 − 0.0114 × 36/72 = 1.1619
    const r = X.sigmaAtT(sets, 253.65, 262);
    near(r.sigma, 1.1619e-17, 1e-9);
    assert.deepEqual([r.T0, r.T1], [226, 298]);
    const ex = X.sigmaAtT(sets, 253.65, 298);
    near(ex.sigma, 1.1562e-17, 1e-12);
    assert.deepEqual([ex.T0, ex.T1], [298, 298]);
    assert.equal(X.sigmaAtT(sets, 253.65, 310), null);
    assert.equal(X.sigmaAtT(sets, 253.65, 200), null);
    assert.equal(X.sigmaAtT(sets, 300, 262), null, 'no set covers 300 nm');
    // a set that does not cover the wavelength is passed over: 226 and 298 K are used around 250 K
    const gap = [...sets, { T: 250, data: [[260, 1e-17], [270, 1e-17]] }, { T: NaN, data: at([1, 1]) }];
    near(X.sigmaAtT(gap, 253.65, 250).sigma, 1.1676e-17 - 0.0114e-17 * 24 / 72, 1e-9);
});

test('thinning keeps the ends, the length limit and narrow peaks', () => {
    const short = band.slice(0, 50);
    const s = X.resample(short, 100);
    assert.deepEqual(s, short);
    assert.notEqual(s, short, 'a copy, not the same array');
    const big = Array.from({ length: 10000 }, (_, i) => [200 + i * 0.01, 1e-18 * (1.5 + Math.sin(i / 50))]);
    big[6543][1] = 4e-17;                                   // one narrow spike, one sample wide
    const r = X.resample(big, 2000);
    assert.equal(r.length, 2000);
    assert.equal(r[0], big[0]);
    assert.equal(r[r.length - 1], big[big.length - 1]);
    assert.ok(r.includes(big[6543]), 'the spike survives');
    for (let i = 1; i < r.length; i++) assert.ok(r[i][0] > r[i - 1][0], 'wavelengths stay in order');
    // away from the spike, linear interpolation of the kept points stays within 1 % (gaps of at most 10 samples:
    // 10²/8 × 1/50² = 0.005 × 1e-18 where σ ≥ 0.5e-18)
    let worst = 0;
    for (let i = 0; i < big.length; i++) if (Math.abs(i - 6543) > 12) worst = Math.max(worst, Math.abs(X.sigmaAt(r, big[i][0]) / big[i][1] - 1));
    assert.ok(worst < 0.01, `worst ${worst}`);
});

test('Beer–Lambert', () => {
    // 1.1329e-17 cm² × 3.262 33e16 cm⁻³ × 10 cm = 3.695 89; e^−3.695 89 = 0.024 825; A = τ/ln 10 = 1.605 11
    const r = X.beerLambert(1.1329e-17, X.density(133.322368, 296), 10);
    near(r.tau, 3.695895, 1e-6);
    near(r.T, 0.02482523, 1e-6);
    near(r.A, 1.605107, 1e-6);
    near(r.absorbed, 1 - 0.02482523, 1e-7);
    assert.deepEqual(X.beerLambert(1e-17, 0, 10), { tau: 0, A: 0, T: 1, absorbed: 0 });
    near(X.beerLambert(1e-24, 1e12, 1).absorbed, 1e-12, 1e-6, 'a very thin sample: absorbed = τ, without rounding to 0');
});

test('photolysis per pulse', () => {
    // 10 mJ cm⁻² at 248.4 nm: 0.01 J / 7.996 96e-19 J = 1.250 47e16 photons cm⁻²; σΦ = 0.125 047
    const r = X.pulsePhotolysis(1e-17, 0.01, 248.4, 0.5);
    near(r.photons, 1.2504746e16, 1e-6);
    near(r.excited, 0.1175450, 1e-5, '1 − e^−0.125 047');
    near(r.photolyzed, 0.0606092, 1e-5, '1 − e^−0.062 524');
    near(r.saturation, 0.07996964, 1e-6, 'hν/σ in J cm⁻²');
    assert.equal(X.pulsePhotolysis(1e-17, 0.01, 248.4).photolyzed, X.pulsePhotolysis(1e-17, 0.01, 248.4).excited, 'φ = 1 by default');
    assert.equal(X.pulsePhotolysis(1e-17, 0.01, 248.4, 0).photolyzed, 0);
    assert.equal(X.pulsePhotolysis(0, 0.01, 248.4).saturation, null);
    // optically thin, weak pulse: fraction photolyzed → σΦφ
    const w = X.pulsePhotolysis(1e-20, 1e-6, 308, 0.3);
    near(w.photolyzed, 1e-20 * w.photons * 0.3, 1e-6);
    // at the saturation fluence a fraction 1 − 1/e has absorbed
    near(X.pulsePhotolysis(1e-17, r.saturation, 248.4).excited, 1 - Math.exp(-1), 1e-12);
});

test('laser lines are in order and labeled with their wavelength', () => {
    const L = X.LASER_LINES;
    for (let i = 1; i < L.length; i++) assert.ok(L[i].nm > L[i - 1].nm);
    for (const x of L) {
        assert.ok(x.nm > 100 && x.nm < 600);
        assert.ok(x.label.startsWith(String(Math.floor(x.nm))), x.label);
    }
    near(L.find((x) => /Lyman/.test(x.label)).nm, 121.567, 1e-9);
    assert.ok(Object.isFrozen(L));
});

test('median step and the coarse flag', () => {
    // steps 0.5, 1.5 and 2 nm: the median is 1.5 nm (the smallest would be 0.5)
    assert.equal(X.medianStep([[1, 1], [1.5, 1], [3, 1], [5, 1]]), 1.5);
    // data every 1.5 nm: coarse for a 1 nm line (step > FWHM), not for a 2 nm line
    const d = Array.from({ length: 21 }, (_, i) => [240 + 1.5 * i, 1e-18]);
    assert.equal(X.sigmaLine(d, 250, 1).coarse, true);
    assert.equal(X.sigmaLine(d, 250, 2).coarse, false);
});

test('temperature interpolation uses the nearest temperature on each side, and the value it is given', () => {
    // 200 K: 5, 250 K: 1, 300 K: 2, 350 K: 7 (× 1e-18); at 260 K, between 250 and 300 K: 1 + (2 − 1) × 10/50 = 1.2
    const f = (v) => [[250, v], [260, v]];
    const r = X.sigmaAtT([{ T: 300, data: f(2e-18) }, { T: 350, data: f(7e-18) }, { T: 200, data: f(5e-18) }, { T: 250, data: f(1e-18) }], 255, 260);
    near(r.sigma, 1.2e-18, 1e-12);
    assert.deepEqual([r.T0, r.T1], [250, 300]);
    // a value function (the page's table value) replaces the point value: 2 at 200 K and 4 at 300 K give 3 at 250 K
    assert.equal(X.sigmaAtT([{ T: 200, v: 2 }, { T: 300, v: 4 }], 0, 250, (s) => s.v).sigma, 3);
    // a set whose value is null does not count
    assert.equal(X.sigmaAtT([{ T: 200, v: 2 }, { T: 300, v: null }], 0, 250, (s) => s.v), null);
});

test('the preset laser lines, and the same list in the build script', () => {
    // Nd:YAG harmonics of 1064.2 nm: /2 532.1, /3 354.7, /4 266.05, /5 212.84
    const nm = X.LASER_LINES.map((L) => L.nm);
    assert.deepEqual(nm, [118.2, 121.567, 157.6, 193.3, 212.8, 222, 248.4, 266, 308, 351.1, 354.7, 405, 532.1]);
    const py = fs.readFileSync(new URL('../scripts/build_data.py', import.meta.url), 'utf8').match(/^LASER_NM = \[([^\]]*)\]$/m)[1].split(',').map(Number);
    assert.deepEqual(py, nm);
});

test('form steps: x axes, number density, one pulse', () => {
    assert.equal(X.X_AXES.nm.of(250), 250);
    assert.equal(X.X_AXES.cm1.of(250), 40000);
    near(X.X_AXES.eV.of(250), 4.959368, 1e-6, '1239.841 984 / 250');
    assert.match(X.X_AXES.cm1.label, /cm⁻¹/);
    assert.match(X.X_AXES.eV.label, /eV/);
    // 1 Torr (133.322 368 Pa) at 296 K: 3.262 33e16 cm⁻³; 1 mbar (100 Pa): 100 / (1.380 649e-23 × 296) m⁻³ = 2.446 95e16 cm⁻³
    near(X.densityFromForm(1, 133.322368, 296), 3.262331e16, 1e-6);
    near(X.densityFromForm(1, 100, 296), 2.446950e16, 1e-6);
    near(X.densityFromForm(1, 101325, 273.15), X.LOSCHMIDT, 1e-12, '1 atm at 273.15 K is Loschmidt\'s constant');
    // 10 mJ cm⁻² at 248.4 nm, σ = 1e-17 cm²: 1.250 47e16 photons cm⁻²; saturation hν/σ = 0.079 97 J cm⁻² = 79.97 mJ cm⁻²
    const r = X.pulseFromForm(1e-17, 10, 248.4, 0.5);
    near(r.photons, 1.2504746e16, 1e-6);
    near(r.saturationmJ, 79.96964, 1e-6);
    near(r.photolyzed, 0.0606092, 1e-5);
    assert.equal(X.pulseFromForm(0, 10, 248.4).saturationmJ, null);
});

test('thinned datasets and the stored full-resolution values', () => {
    assert.equal(X.isThinned({ n0: 5000, np: 2000 }), true);
    assert.equal(X.isThinned({ n0: 5, np: 5 }), false);
    assert.equal(X.isThinned(null), false);
    const meta = { n0: 104735, np: 3, at: { '121.567': 1.147e-20, 266: 2e-21 } };
    assert.equal(X.storedAt(meta, 121.567), 1.147e-20);
    assert.equal(X.storedAt(meta, 266), 2e-21, 'the key is the number as JavaScript prints it');
    assert.equal(X.storedAt(meta, 121.6), null);
    assert.equal(X.storedAt({ n0: 3, np: 3 }, 121.567), null);
    const d = [[120, 1e-18], [121.567, 5.62e-18], [123, 1e-18]];
    // a point value at a preset line: the stored value of the full spectrum
    const a = X.tableValue(meta, d, 121.567);
    assert.deepEqual([a.sigma, a.full, a.thinned, a.covered], [1.147e-20, true, false, 1]);
    // with a line width, the thinned curve, flagged
    const b = X.tableValue(meta, d, 121.567, 0.05);
    assert.deepEqual([b.full, b.thinned], [false, true]);
    // away from a preset line, the thinned curve, flagged; outside the data, nothing to flag
    assert.equal(X.tableValue(meta, d, 122).thinned, true);
    assert.equal(X.tableValue(meta, d, 130).thinned, false);
    // a dataset that was not thinned is never flagged
    assert.equal(X.tableValue({ n0: 3, np: 3 }, d, 122).thinned, false);
    // one or two points: the nearest within 1 nm, not an interpolation
    const one = X.tableValue({ n0: 1, np: 1 }, [[121.6, 3e-18]], 121.567);
    assert.deepEqual([one.sigma, one.at], [3e-18, 121.6]);
    assert.equal(X.tableValue({ n0: 1, np: 1 }, [[121.6, 3e-18]], 130).sigma, null);
});

test('numbers on the page', () => {
    // toPrecision(4) of 13 077.2 is '1.308e+4': it must come out in the page's own exponent form
    assert.equal(X.formatSci(13077.2), '1.308 × 10<sup>4</sup>');
    assert.equal(X.formatSci(1e4), '1.000 × 10<sup>4</sup>');
    assert.equal(X.formatSci(99999), '1.000 × 10<sup>5</sup>');
    assert.equal(X.formatSci(9999.6), '1.000 × 10<sup>4</sup>');
    assert.equal(X.formatSci(2615.38), '2615');
    assert.equal(X.formatSci(1000), '1000');
    assert.equal(X.formatSci(0.0606092), '0.06061');
    assert.equal(X.formatSci(0.5), '0.5');
    assert.equal(X.formatSci(-3.2e5), '−3.200 × 10<sup>5</sup>');
    assert.equal(X.formatSci(1.805e-31), '1.805 × 10<sup>−31</sup>');
    assert.equal(X.formatSci(2.686780111e19, 8), '2.68678011 × 10<sup>19</sup>');
    assert.equal(X.formatSci(123456.789, 8), '123456.789', 'with 9 figures, plain up to 1e9');
    assert.equal(X.formatSci(0), '0');
    assert.equal(X.formatSci(null), '—');
    assert.equal(X.formatSci(NaN), '—');
});

test('temperature series and the log-axis floor', () => {
    assert.equal(X.seriesKey('mainz2013:O3_Bass(1984)_203K_245-340nm'), 'mainz2013:O3_Bass(1984)');
    assert.equal(X.seriesKey('mainz2013:O3_MolinaMolina(1986)_298K_185-350nm(0.5nm)'), 'mainz2013:O3_MolinaMolina(1986)(0.5nm)');
    assert.equal(X.seriesKey('mainz2013:CH2O_X(2011)_223.15-293.15K_300-385nm'), 'mainz2013:CH2O_X(2011)');
    assert.equal(X.seriesKey('bremen:O3_Serdyuchenko2014_293K'), 'bremen:O3_Serdyuchenko2014');
    assert.notEqual(X.seriesKey('bremen:O3_Serdyuchenko2014_v2013FFT_293K'), X.seriesKey('bremen:O3_Serdyuchenko2014_293K'));
    assert.equal(X.seriesKey('tuvx:O3_2_218K'), 'tuvx:O3_2');
    // 12 decades below the largest σ shown: 1e-17 → 1e-29
    near(X.logFloor([[[1, 1e-17], [2, 1e-320]], [[1, 3e-19]]]), 1e-29, 1e-12);
    assert.equal(X.logFloor([]), 0);
});

test('numbers typed into the form are read whole or not at all', () => {
    // the bug this replaces: parseFloat("1,5") is 1, and a fluence of 1,5 mJ/cm² was computed as 1
    assert.equal(X.parseNum('1,5'), 1.5, 'a decimal comma');
    assert.notEqual(X.parseNum('1,5'), 1);
    assert.equal(X.parseNum('0,532'), 0.532);
    assert.equal(X.parseNum('1,5e-17'), 1.5e-17);
    assert.equal(X.parseNum('1,234,567'), 1234567, 'thousands separators');
    assert.equal(X.parseNum('1,064'), null, 'one comma and three digits: 1064 or 1.064, so neither');
    assert.equal(X.parseNum('12abc'), null, 'parseFloat would give 12');
    assert.equal(X.parseNum('1e'), null);
    assert.equal(X.parseNum('abc'), null);
    assert.equal(X.parseNum(''), null);
    assert.equal(X.parseNum(null), null);
    assert.equal(X.parseNum('1e400'), null, 'not finite');
    assert.equal(X.parseNum(' 248.4 '), 248.4);
    assert.equal(X.parseNum('−2'), -2, 'a typographic minus');
    assert.equal(X.parseNum('.5'), 0.5);
    assert.equal(X.parseNum('1E-17'), 1e-17);
    assert.equal(X.parseNum('133.322368'), 133.322368, 'the pressure-unit factors of the form');
    // a value copied from the page: "1.079 × 10⁻¹⁷", or "1.079 × 10−17" when the superscript is lost
    assert.equal(X.parseNum('1.079 × 10⁻¹⁷'), 1.079e-17);
    assert.equal(X.parseNum('1.079 × 10−17'), 1.079e-17);
    assert.equal(X.parseNum('2x10^-3'), 0.002);
});

test('the message for a field that is not a number names the field', () => {
    assert.equal(X.numError('248.4', 'wavelength'), '');
    assert.equal(X.numError('1,5', 'pulse fluence'), '');
    assert.equal(X.numError('', 'wavelength'), '', 'an empty field is not an error');
    assert.equal(X.numError('abc', 'wavelength'), '“abc” is not a number (wavelength).');
    assert.equal(X.numError('1,064', 'wavelength'), '“1,064” is ambiguous (wavelength): enter 1064 or 1.064 (decimal comma: 1,0640).');
    assert.equal(X.numError('1e', 'cross section'), '', 'an exponent still being typed');
    assert.equal(X.numError('1e-', 'cross section'), '');
    assert.equal(X.numError('1e400', 'cross section'), 'That value is out of range (cross section).');
});

test('plot limits in the unit of the x axis', () => {
    // 200 to 280 nm: 1239.841 984 / 280 = 4.428 eV to 1239.841 984 / 200 = 6.199 eV; 10⁷/280 = 35 714 to 10⁷/200 = 50 000 cm⁻¹
    assert.deepEqual(X.limitsFromNm('nm', '200', '280'), { from: '200', to: '280' });
    assert.deepEqual(X.limitsFromNm('eV', '200', '280'), { from: '4.428', to: '6.199' }, 'the ends swap: a longer wavelength is a lower energy');
    assert.deepEqual(X.limitsFromNm('cm1', '200', '280'), { from: '35714', to: '50000' });
    assert.deepEqual(X.limitsFromNm('eV', '', '400'), { from: '3.1', to: '' }, 'an open end stays open');
    assert.deepEqual(X.limitsToNm('nm', '200', '280'), { min: '200', max: '280' });
    // 4 eV is 309.9605 nm and 6.2 eV is 199.9745 nm
    assert.deepEqual(X.limitsToNm('eV', '4', '6.2'), { min: '199.9745', max: '309.9605' });
    assert.deepEqual(X.limitsToNm('cm1', '40000', '50000'), { min: '200', max: '250' });
    assert.deepEqual(X.limitsToNm('nm', 'abc', '2,5e2'), { min: '', max: '250' }, 'text that is not a number leaves the end open');
    assert.deepEqual(X.limitsToNm('eV', '0', '-3'), { min: '', max: '' }, 'no wavelength for zero or a negative value');
    near(X.axisToNm('eV', X.X_AXES.eV.of(248.4)), 248.4, 1e-12, 'hc/λ is its own inverse');
    near(X.axisToNm('cm1', 40000), 250, 1e-12);
    assert.equal(X.axisText('eV', 248.4), '4.991');
    assert.equal(X.axisText('cm1', 248.4), '40258');
    assert.equal(X.axisText('nm', 121.567), '121.567');
    assert.deepEqual(['nm', 'cm1', 'eV'].map((k) => X.X_AXES[k].unit), ['nm', 'cm⁻¹', 'eV']);
});

test('line labels that would pile up are left out', () => {
    // labels 40 px wide at 0, 10, 20 and 100 px: the first is kept, the two within its width are not, the far one is
    assert.deepEqual(X.keepLabels([{ px: 0, w: 40 }, { px: 10, w: 40 }, { px: 20, w: 40 }, { px: 100, w: 40 }]), [true, false, false, true]);
    // the reader's own line always keeps its label, and is placed first
    assert.deepEqual(X.keepLabels([{ px: 0, w: 40 }, { px: 10, w: 40, keep: true }, { px: 100, w: 40 }]), [false, true, true]);
    // a lower rank is kept first
    assert.deepEqual(X.keepLabels([{ px: 0, w: 40, rank: 3 }, { px: 10, w: 40, rank: 0 }, { px: 45, w: 40, rank: 1 }, { px: 60, w: 40, rank: 2 }]), [false, true, false, true]);
    assert.deepEqual(X.keepLabels([]), []);
    // every preset line has a rank, and no other wavelength does
    assert.deepEqual([...X.LINE_RANK].sort((a, b) => a - b), X.LASER_LINES.map((L) => L.nm));
});

test('reference labels: first surname, "et al." past two authors, the file label or the title without authors', () => {
    assert.equal(X.authorsShort('A. Serdyuchenko, V. Gorshelev, M. Weber, W. Chehade, and J. P. Burrows'), 'Serdyuchenko et al.');
    assert.equal(X.authorsShort('L.T Molina and M.J. Molina'), 'Molina and Molina');
    assert.equal(X.authorsShort('A.M. Bass'), 'Bass');
    assert.equal(X.authorsShort('S.P. Sander et al.'), 'Sander et al.');
    assert.equal(X.authorsShort('G. von Helden'), 'Helden', 'the last word of the name');
    assert.equal(X.authorsShort(''), '');
    assert.equal(X.refLabel({ a: 'S.P. Sander, J. Abbatt, J. R. Barker', y: 2011, t: 'Chemical Kinetics' }), 'Sander et al. (2011)');
    assert.equal(X.refLabel({ a: '', y: 2026, lab: 'Xx steps', c: 'a citation' }), 'Xx steps (2026)');
    assert.equal(X.refLabel({ a: '', y: '', t: 'A title that runs on for rather more than fifty characters in all' }), 'A title that runs on for rather more than fifty ch…', 'the first 50 characters');
    assert.equal(X.refLabel({ a: '', y: '' }), 'unknown');
    assert.equal(X.refLabel(null), 'unknown');
});

// A small who.json and coarse.json in the layout scripts/build_data.py writes: sets are [species key, label, T, source, flags]
// (1 recommended, 2 upper limits, 4 electron energy loss, 8 a list of band maxima) and, for a file of one isotopologue,
// its name; a row at a line is [file number, σ], [file number, σ, λ of the single point] or [file number, σ, null, the gap
// in nm between the points it is interpolated between]; a coarse run is [file number, first bin, [round(100 log10 σ) …]]
// with bins 2 nm wide, and a 1 after the values where the points lie more than 5 nm apart.
const WHO = {
    lines: ['193.3', '248.4'],
    sets: { '00001': ['O3', 'Sander et al. (2011)', [293, 298], 'mainz2013', 1], '00002': ['O2', 'Yoshino et al. (1992)', 300, 'cfa', 0],
        '00003': ['CF3OH', 'Molina (1996)', 298, 'mainz2013', 2], '00004': ['HO2', 'Paukert (1972)', null, 'mainz2013', 0] },
    at: { '193.3': [['00004', 3.9e-18, 193], ['00001', 4.2763e-19], ['00003', 1e-21], ['00002', 6.7918e-22]], '248.4': [['00001', 1.0785e-17]] },
};
const COARSE = { bin: 2, sets: WHO.sets, runs: [['00002', 96, [-2100, -2130]], ['00001', 96, [-1837, -1840, -1850]], ['00003', 90, [-2000]]] };

test('who absorbs here: the rows at a preset line, strongest first as the build stored them', () => {
    assert.equal(X.lineKey(193.3), '193.3');
    assert.equal(X.lineKey(266), '266');
    assert.equal(X.lineKey(193), null, '193 nm is not the 193.3 nm preset');
    const rows = X.whoAtLine(WHO, '193.3');
    assert.deepEqual(rows.map((r) => r.k), ['HO2', 'O3', 'CF3OH', 'O2']);
    assert.deepEqual(rows[0], { k: 'HO2', f: '00004', sigma: 3.9e-18, label: 'Paukert (1972)', T: null, src: 'mainz2013', rec: false, ul: false, ee: false, peaks: false, iso: '', nm: 193.3, at: 193, gap: null, wide: false, band: null, approx: false });
    assert.deepEqual([rows[1].rec, rows[1].ul, rows[1].at, rows[1].T], [true, false, null, [293, 298]]);
    assert.deepEqual([rows[2].rec, rows[2].ul], [false, true], 'flag 2 is an upper limit');
    assert.deepEqual(X.whoAtLine(WHO, '266'), [], 'a line the file does not have');
    assert.deepEqual(X.whoAtLine(null, '193.3'), []);
    assert.deepEqual(X.whoAtLine({ sets: {}, at: { '193.3': [['00009', 1e-20]] } }, '193.3'), [], 'a row whose dataset is not named is left out');
    // what makes a row a weak one: electron energy loss (4) across a 29.5 nm gap, band maxima (8), one isotopologue
    const weak = X.whoAtLine({ sets: { '00001': ['H2O', 'Tan et al. (1978)', 298, 'mainz2013', 4], '00002': ['RbI', 'Davidovits and Brodhead (1967)', 1007, 'mainz2013', 8], '00003': ['NH3', 'Liang et al. (2007)', 300, 'mainz2013', 0, '15NH3'] },
        at: { '266': [['00002', 6e-17, 265], ['00003', 9.3e-18], ['00001', 2.1e-18, null, 29.5]] } }, '266');
    assert.deepEqual(weak.map((r) => [r.k, r.ee, r.peaks, r.iso, r.at, r.gap, r.wide]), [['RbI', false, true, '', 265, null, false], ['NH3', false, false, '15NH3', null, null, false], ['H2O', true, false, '', null, 29.5, true]]);
});

test('a list of band maxima is read point by point at a laser line, never interpolated', () => {
    const d = [[241, 5e-17], [265, 6e-17], [330, 2e-17]];
    const peaks = { id: 'mainz2013:RbI_DavidovitsBrodhead(1967)_1007K_241,265,330nm(max)', np: 3, n0: 3 };
    for (const tag of ['max', 'max,min', 'min,max', 'sh,max', 'max,sol', 'peaks-1cm-1', 'band peaks,rec', 'band heads']) assert.equal(X.isPeakList({ id: `mainz2013:Xx_A(2000)_298K_241,265nm(${tag})` }), true, tag);
    for (const tag of ['rec', 'sol', 'smoo', '2nm', 'e,e', 'maximal']) assert.equal(X.isPeakList({ id: `mainz2013:Xx_A(2000)_298K_240-270nm(${tag})` }), false, tag);
    assert.equal(X.isPeakList(null), false);
    // 248.4 nm lies between two maxima: no value, and the nearest listed point is named
    assert.deepEqual(X.tableValue(peaks, d, 248.4), { sigma: null, covered: 0, coarse: false, at: 241, full: false, thinned: false });
    assert.deepEqual(X.tableValue(peaks, d, 266), { sigma: 6e-17, covered: 1, coarse: false, at: 265, full: false, thinned: false });
    // the same three points without the tag are a spectrum
    near(X.tableValue({ id: 'mainz2013:RbI_A(1967)_1007K_241-330nm', np: 3, n0: 3 }, d, 248.4).sigma, 5e-17 + (1e-17 * 7.4) / 24, 1e-12);
});

test('who absorbs here: any wavelength from the coarse bins', () => {
    // 193.3 nm is in bin floor(193.3 / 2) = 96, 192 to 194 nm: O3 10^-18.37 = 4.266e-19 and O2 10^-21 = 1e-21
    const rows = X.whoCoarse(COARSE, 193.3);
    assert.deepEqual(rows.map((r) => r.k), ['O3', 'O2']);
    near(rows[0].sigma, 4.2658e-19, 1e-4);
    near(rows[1].sigma, 1e-21, 1e-12);
    assert.deepEqual([rows[0].approx, rows[0].lo, rows[0].hi], [true, 192, 194]);
    // 195 nm is in bin 97: the second value of each run
    near(X.whoCoarse(COARSE, 195)[0].sigma, 10 ** -18.4, 1e-12);
    // bin 98 (196 to 198 nm): the O2 run has ended
    assert.deepEqual(X.whoCoarse(COARSE, 197).map((r) => r.k), ['O3']);
    assert.deepEqual(X.whoCoarse(COARSE, 181).map((r) => [r.k, r.ul]), [['CF3OH', true]]);
    assert.deepEqual(X.whoCoarse(COARSE, 500), []);
    assert.deepEqual(X.whoCoarse(null, 193.3), []);
    assert.deepEqual(X.whoCoarse(COARSE, NaN), []);
    // a run whose points lie more than 5 nm apart says so, and a null (below the floor in the full spectrum) is no row
    const gaps = { bin: 2, sets: WHO.sets, runs: [['00002', 96, [-2100, null], 1], ['00001', 96, [-1837, -1840]]] };
    assert.deepEqual(X.whoCoarse(gaps, 193).map((r) => [r.k, r.wide]), [['O3', false], ['O2', true]]);
    assert.deepEqual(X.whoCoarse(gaps, 195).map((r) => r.k), ['O3']);
});

test('who absorbs here: the air view keeps the gases of air and names the ones without data', () => {
    assert.deepEqual([...X.AIR_GASES], ['N2', 'O2', 'H2O', 'CO2', 'CH4', 'H2', 'N2O', 'CO', 'O3', 'NO2', 'NO', 'SO2', 'NH3']);
    const rows = X.whoAtLine(WHO, '193.3');
    const air = X.whoView(rows, true);
    assert.deepEqual(air.rows.map((r) => r.k), ['O3', 'O2'], 'in the order of the full list');
    assert.deepEqual(air.missing, ['N2', 'H2O', 'CO2', 'CH4', 'H2', 'N2O', 'CO', 'NO2', 'NO', 'SO2', 'NH3']);
    const all = X.whoView(rows, false);
    assert.equal(all.rows, rows);
    assert.deepEqual(all.missing, []);
});

/* ── Who absorbs here, in air ─────────────────────────────────────────── */
test('the air of the air view: 1 atm, 296 K, and water vapor from the relative humidity', () => {
    assert.deepEqual({ ...X.AIR }, { p: 101325, T: 296, rh: 50 });
    // n = 101 325 Pa / (1.380 649e-23 J/K × 296 K) = 2.479 372e25 m⁻³ = 2.479 372e19 cm⁻³
    near(X.density(X.AIR.p, X.AIR.T), 2.4793716e19, 1e-7);
    // Antoine, NIST WebBook, 273 to 303 K: log10(p/bar) = 5.40221 − 1838.675/(296 − 31.737) = 5.40221 − 6.957746 = −1.555536,
    // so p = 0.0278268 bar = 2782.68 Pa
    near(X.waterSaturation(296), 2782.68, 1e-6);
    assert.equal(X.waterSaturation(310), null, 'outside the 273 to 303 K of the fit');
    assert.equal(X.waterSaturation(270), null);
    // 50 %: 0.5 × 2782.6806 / 101 325 = 0.013 731 46; saturated: 0.027 462 92; dry: 0
    near(X.waterFraction(50), 0.01373146, 1e-6);
    near(X.waterFraction(100), 0.02746292, 1e-6);
    assert.equal(X.waterFraction(0), 0);
    near(X.waterFraction(), 0.01373146, 1e-6, 'the default humidity is 50 %');
    assert.equal(X.waterFraction(101), null);
    assert.equal(X.waterFraction(-1), null);
});

test('mole fractions in air: dry air from the 1976 Standard Atmosphere and NOAA, scaled by 1 − x of water', () => {
    // every gas of the air view but water has a dry-air share, from a source the page names
    assert.deepEqual(Object.keys(X.AIR_DRY).sort(), X.AIR_GASES.filter((k) => k !== 'H2O').sort());
    for (const [k, [x, s]] of Object.entries(X.AIR_DRY)) { assert.ok(x > 0 && x < 1, k); assert.ok(X.AIR_SOURCES[s], `${k}: ${s}`); }
    // U.S. Standard Atmosphere 1976, Table 3: N2 0.78084, O2 0.209476, Ar 0.00934, H2 0.0000005
    assert.deepEqual([X.AIR_DRY.N2[0], X.AIR_DRY.O2[0], X.AIR_ARGON, X.AIR_DRY.H2[0]], [0.78084, 0.209476, 0.00934, 0.5e-6]);
    // NOAA global monthly means: CO2 426.10 ppm (July 2026), CH4 1934.57 ppb and N2O 339.86 ppb (June 2026)
    near(X.AIR_DRY.CO2[0], 426.10e-6, 1e-12); near(X.AIR_DRY.CH4[0], 1934.57e-9, 1e-12); near(X.AIR_DRY.N2O[0], 339.86e-9, 1e-12);
    // U.S. Standard Atmosphere 1976, Table 15, ppb: CO 190, O3 40, NO2 1, NO 0.5, SO2 1, NH3 4
    assert.deepEqual(['CO', 'O3', 'NO2', 'NO', 'SO2', 'NH3'].map((k) => +(X.AIR_DRY[k][0] * 1e9).toPrecision(6)), [190, 40, 1, 0.5, 1, 4]);
    // with argon the dry-air shares add up to 1.000085 (the 1976 table had 314 ppm of CO2; they are not renormalized)
    near(X.AIR_ARGON + Object.values(X.AIR_DRY).reduce((a, v) => a + v[0], 0), 1.000085, 1e-6);
    assert.equal(X.airFraction('N2', 0), 0.78084, 'dry air');
    // at 50 %: O2 0.209476 × (1 − 0.013 731 46) = 0.206 599 6; O3 40e-9 × 0.986 268 54 = 3.945 074e-8
    near(X.airFraction('O2', 50), 0.2065996, 1e-6);
    near(X.airFraction('O3'), 3.945074e-8, 1e-6);
    near(X.airFraction('H2O', 50), 0.01373146, 1e-6);
    assert.equal(X.airFraction('Ar', 50), null, 'argon has no cross sections in the collections and no row');
    assert.equal(X.airFraction('CF3OH', 50), null);
    assert.equal(X.airFraction('O2', 120), null);
});

const airRow = (k, sigma, more = {}) => ({ k, f: '00001', sigma, label: 'a', T: 298, src: 'x', rec: false, ul: false, ee: false, peaks: false, iso: '', at: null, gap: null, wide: false, approx: false, ...more });

test('who absorbs here, in air: α = σ × mole fraction × n, largest first, with the 1/e length', () => {
    // dry air, n = 2.479 372e19 cm⁻³. O2: 2e-24 × 0.209476 × n = 1.038 74e-5 cm⁻¹ = 1.038 74e-3 m⁻¹, 1/α = 962.71 m.
    // O3: 1e-17 × 40e-9 × n = 9.917 49e-6 cm⁻¹ = 9.917 49e-4 m⁻¹, 1/α = 1008.3 m. The larger σ is the smaller α.
    const A = X.airAbsorption([airRow('O3', 1e-17), airRow('O2', 2e-24)], 0);
    assert.deepEqual(A.rows.map((r) => r.k), ['O2', 'O3']);
    near(A.n, 2.4793716e19, 1e-7); assert.equal(A.water, 0);
    near(A.rows[0].alpha, 1.038738e-3, 1e-6); near(A.rows[0].L, 962.707, 1e-6); assert.equal(A.rows[0].x, 0.209476);
    near(A.rows[1].alpha, 9.917486e-4, 1e-6); near(A.rows[1].L, 1008.320, 1e-6);
    // total 2.030 486e-3 m⁻¹, 1/e length 492.493 m; O3 is within a factor of two of O2, so the two are a tie
    near(A.total, 2.030486e-3, 1e-6); near(A.L, 492.493, 1e-6);
    assert.deepEqual([A.top.k, A.tie.k, A.rough, A.weakShare, A.limits.length], ['O2', 'O3', false, 0, 0]);
    near(A.firmTotal, A.total, 1e-12);
    // at 50 % humidity every dry-air share is 1.373 % smaller, and water has a share of its own
    const B = X.airAbsorption([airRow('O2', 2e-24), airRow('H2O', 1e-21)], 50);
    near(B.rows.find((r) => r.k === 'O2').alpha, 1.038738e-3 * 0.98626854, 1e-6);
    // H2O: 1e-21 × 0.013 731 46 × n × 100 = 3.404 54e-2 m⁻¹, the first row; O2 is far below half of it, so no tie
    near(B.rows[0].alpha, 3.404539e-2, 1e-6); assert.equal(B.rows[0].k, 'H2O'); assert.equal(B.tie, null);
    // in dry air water stays in the list with α = 0 and no length
    const dry = X.airAbsorption([airRow('H2O', 1e-21), airRow('O2', 2e-24)], 0);
    assert.deepEqual(dry.rows.map((r) => [r.k, r.alpha > 0, r.L === null]), [['O2', true, false], ['H2O', false, true]]);
    // a gas that is not a gas of air has no share and no row; a humidity outside 0 to 100 % gives no rows at all
    assert.deepEqual(X.airAbsorption([airRow('CF3OH', 1e-18), airRow('O2', 2e-24)], 0).rows.map((r) => r.k), ['O2']);
    assert.deepEqual(X.airAbsorption([airRow('O2', 2e-24)], 150).rows, []);
    const none = X.airAbsorption([], 50);
    assert.deepEqual([none.total, none.L, none.top, none.tie, none.rough], [0, null, null, null, false]);
});

test('who absorbs here, in air: a flagged value is never part of a firm total', () => {
    // an upper limit is listed and left out of the sum: SO2 ≤ 1e-16 would give 1e-16 × 1e-9 × n × 100 = 2.479e-4 m⁻¹
    const ul = X.airAbsorption([airRow('SO2', 1e-16, { ul: true }), airRow('O2', 2e-24)], 0);
    assert.deepEqual([ul.rows.map((r) => r.k), ul.sum.map((r) => r.k), ul.limits.map((r) => r.k)], [['O2', 'SO2'], ['O2'], ['SO2']]);
    near(ul.total, 1.038738e-3, 1e-6); near(ul.limits[0].alpha, 2.479372e-4, 1e-6);
    assert.equal(ul.rough, false);
    // a small flagged row (CO2 across a gap: 4e-25 × 426.10e-6 × n × 100 = 4.2258e-7 m⁻¹, 0.04 % of the sum) leaves the total firm
    const small = X.airAbsorption([airRow('O2', 2e-24), airRow('CO2', 4e-25, { gap: 36.3, wide: true })], 0);
    assert.equal(small.rows[1].weak, true); assert.equal(small.rough, false);
    near(small.weakShare, 4.2258e-7 / (1.038738e-3 + 4.2258e-7), 1e-4);
    // a flagged row at the top makes it rough, and firmTotal is what is left without it: CO2 at one wavelength and 2073 K,
    // 1.5e-21 × 426.10e-6 × n × 100 = 1.584 69e-3 m⁻¹, over O2 at 1.6e-25 × 0.209476 × n × 100 = 8.3099e-5 m⁻¹
    const weak = X.airAbsorption([airRow('CO2', 1.5e-21, { at: 355, T: 2073 }), airRow('O2', 1.6e-25)], 0);
    assert.deepEqual([weak.top.k, weak.top.weak, weak.rough, weak.tie], ['CO2', true, true, null]);
    near(weak.total, 1.58469e-3 + 8.3099e-5, 1e-5); near(weak.firmTotal, 8.3099e-5, 1e-5); near(weak.weakShare, 0.950175, 1e-4);
    // a flagged row that carries a tenth of the sum or more, below a firm top: rough
    const tenth = X.airAbsorption([airRow('O2', 2e-24), airRow('O3', 2e-18, { T: 220 })], 0);   // O3: 1.9835e-4 m⁻¹, 16 % of 1.2371e-3
    assert.deepEqual([tenth.top.k, tenth.tie, tenth.rough], ['O2', null, true]);
    // 2 nm means are never firm
    assert.equal(X.airAbsorption([airRow('O2', 2e-24, { approx: true })], 0).rough, true);
    // the notes that make a row weak, in the words of the Note column
    assert.deepEqual(X.whoNotes(airRow('O2', 1)), []);
    assert.deepEqual(X.whoNotes(airRow('CO2', 1, { ul: true, gap: 10, wide: true })), ['upper limit', 'interpolated across 10 nm']);
    assert.deepEqual(X.whoNotes(airRow('CO2', 1, { at: 355, T: 2073 })), ['measured at 355 nm only', 'at 2073 K, not room temperature']);
    assert.deepEqual(X.whoNotes(airRow('RbI', 1, { at: 265, peaks: true, T: [200, 240] })), ['a band maximum listed at 265 nm, not a spectrum', 'at 200–240 K, not room temperature']);
    assert.deepEqual(X.whoNotes(airRow('H2', 1, { ee: true, wide: true, T: null })), ['electron energy loss, low resolution', 'points more than 5 nm apart here']);
    assert.deepEqual([X.tempText(null), X.tempText(298), X.tempText([293, 298])], ['T not given', '298 K', '293–298 K']);
});

test('who absorbs here, in air: a value in a structured spectrum is flagged, and an unconfirmed one stays out of the sum', () => {
    // who.json carries the spread of σ within 0.25 nm of the line as a fifth number; the row says so in its note
    const who = { sets: { '00001': ['O2', 'a', 300, 'x', 0], '00002': ['H2O', 'b', 298, 'x', 0], '00003': ['O3', 'c', 298, 'x', 0] },
        at: { '193.3': [['00002', 1.95e-21], ['00001', 6.7918e-22, null, null, 63]], '248.4': [['00003', 1.079e-17], ['00001', 1.984e-24]] } };
    const rows = X.whoAtLine(who, '193.3');
    assert.deepEqual(rows.map((r) => [r.k, r.nm, r.band]), [['H2O', 193.3, null], ['O2', 193.3, 63]]);
    assert.deepEqual(X.whoNotes(rows[1]), ['structured here: σ spans a factor of 63 within ±0.25 nm']);
    assert.deepEqual(X.whoNotes({ ...rows[1], band: 10000 }), ['structured here: σ spans a factor of over 10 000 within ±0.25 nm']);
    // 193.3 nm at 50 % humidity: O2 6.7918e-22 × 0.2065996 × n × 100 = 0.347 90 m⁻¹, H2O 1.95e-21 × 0.01373146 × n × 100
    // = 0.066 389 m⁻¹. O2 leads, it is flagged, so the total is rough and firmTotal is water alone
    const A = X.airAbsorption(rows, 50);
    assert.deepEqual([A.top.k, A.top.weak, A.rough, A.tie, A.left.length], ['O2', true, true, null, 0]);
    near(A.top.alpha, 0.347900, 1e-5); near(A.firmTotal, 0.0663885, 1e-5); near(A.weakShare, 0.83975, 1e-4);
    // O2 above 245 nm: listed, flagged, last in the order of α, and left out of the sum, so ozone alone is the total
    const kr = X.whoAtLine(who, '248.4');
    assert.equal(X.whoDoubt(kr[1]).k, 'O2'); assert.equal(X.whoDoubt(kr[0]), null); assert.equal(X.whoDoubt(rows[1]), null);
    assert.match(X.whoNotes(kr[1])[0], /^not a firm value: above 245 nm/);
    const B = X.airAbsorption(kr, 50);
    assert.deepEqual([B.rows.map((r) => r.k), B.sum.map((r) => r.k), B.left.map((r) => r.k), B.top.k, B.tie, B.rough], [['O3', 'O2'], ['O3'], ['O2'], 'O3', null, false]);
    // O3: 1.079e-17 × 3.945074e-8 × n × 100 = 1.055 40e-3 m⁻¹; the O2 value would have given 1.984e-24 × 0.2065996 × n × 100 = 1.016 28e-3
    near(B.total, 1.055403e-3, 1e-6); near(B.left[0].alpha, 1.016279e-3, 1e-6); near(B.firmTotal, B.total, 1e-12);
    // an unconfirmed value with a larger α than every firm row still comes last and is not the top
    const C = X.airAbsorption([{ ...kr[1], sigma: 1e-22 }, kr[0]], 50);
    assert.deepEqual([C.rows.map((r) => r.k), C.top.k], [['O3', 'O2'], 'O3']);
    // between the lines the rule goes by the lower edge of the 2 nm bin: 244 to 246 nm is in, 246 to 248 nm is out
    const coarse = { bin: 2, sets: who.sets, runs: [['00001', 122, [-2400, -2380]]] };
    assert.deepEqual([X.whoDoubt(X.whoCoarse(coarse, 245.5)[0]), X.whoDoubt(X.whoCoarse(coarse, 246.5)[0]).above], [null, 245]);
    assert.equal(X.airAbsorption(X.whoCoarse(coarse, 246.5), 50).sum.length, 0);
    // an upper limit of such a gas is an upper limit: listed with ≤, in limits, not in left
    const ul = X.airAbsorption([{ ...kr[1], ul: true }], 50);
    assert.deepEqual([ul.limits.length, ul.left.length], [1, 0]);
});

test('mole fractions and path lengths as the page writes them', () => {
    assert.deepEqual([0.2065996, 0.0137315, 420.2e-6, 1.908e-6, 3.94507e-8, 4.931e-10, 2e-13].map((x) => X.fractionText(x)),
        ['20.7 %', '1.37 %', '420 ppm', '1.91 ppm', '39.5 ppb', '493 ppt', '0.2 ppt']);
    assert.equal(X.fractionText(0.78084, 3), '78.08 %');
    assert.equal(X.fractionText(null), '—');
    assert.equal(X.fractionText(0), '0', 'water in dry air');
    assert.deepEqual([482.67, 1900, 0.25, 0.0031, 3e-5, 2.66e6, 3.88e9].map((m) => X.pathText(m)), ['483 m', '1.9 km', '25 cm', '3.1 mm', '30 µm', '2660 km', '3.88 × 10<sup>6</sup> km']);
    assert.equal(X.pathText(482.67, 1), '480 m', 'two figures for a rough value');
    assert.equal(X.pathText(999.6), '1000 m');
    assert.equal(X.pathText(null), '—');
});
