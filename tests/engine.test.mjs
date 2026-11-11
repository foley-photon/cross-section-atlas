// The engine (site/js/xsec.js): unit factors, photon conversions, interpolation, laser-line averages, temperature
// interpolation, thinning, Beer–Lambert and photolysis per pulse. Expected values are worked out by hand in the comments,
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
