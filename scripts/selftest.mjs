// Check a copy of the page the way the site checks it before it publishes one: the page can load, the engine
// (site/js/xsec.js) gives the hand-worked values below, and, where the data files are present, they are complete and
// consistent, ozone at the 253.65 nm mercury line agrees with the reference value, and the page boots on them.
//
//   node scripts/selftest.mjs [site folder] [--data] [--data-dir DIR]
//
//   site folder    default: site/ of this repository
//   --data         the data files are required (the site's copy has them; this repository does not)
//   --data-dir     read the data from DIR instead of <site folder>/data
//
// The page check: every module in js/ parses, every name a module imports is exported by the module it names,
// index.html loads ./js/app.js as a module, links ./xsec.css and names only files that exist, and every element id
// app.js looks up ($('…')) is in index.html. The page also links the Thermochemistry Lab's stylesheet
// (../thermochem/thermochem.css); that file is checked when the folder beside this one has it, as on the site, and
// reported as not checked otherwise.
//
// The boot check (with data): app.js runs in a child Node process against a stand-in for the browser's document,
// with fetch served from the data folder; it must load the index, draw the default molecule and fill every panel,
// and stay free of errors through a few clicks (a laser line, the eV axis, a line width). bootPage() runs it.
//
// Exit code 1 when an engine case or a data check fails, when the page would not load, or when --data is given and
// the data are missing. The site's own repository has no package.json, so Node would not know that js/*.js are ES
// modules there; the modules are copied to a temporary folder that says so, and imported from it.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SELF = fileURLToPath(import.meta.url);
const SITE = path.join(HERE, '..', 'site');

/** Copy js/*.js to a temporary folder marked as ES modules; returns [folder, file names]. */
function moduleCopy(siteDir) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-selftest-'));
    const files = fs.readdirSync(path.join(siteDir, 'js')).filter((f) => f.endsWith('.js'));
    for (const f of files) fs.copyFileSync(path.join(siteDir, 'js', f), path.join(tmp, f));
    fs.writeFileSync(path.join(tmp, 'package.json'), '{"type":"module"}\n');
    return [tmp, files];
}

/** Names exported by a module's source: export const/let/function/class NAME and export { a, b as c }. */
function exportsOf(src) {
    const out = new Set();
    for (const m of src.matchAll(/^export\s+(?:async\s+)?(?:const|let|var|function\*?|class)\s+([A-Za-z_$][\w$]*)/gm)) out.add(m[1]);
    for (const m of src.matchAll(/^export\s*\{([^}]*)\}/gm)) {
        for (const part of m[1].split(',')) {
            const p = part.trim().split(/\s+as\s+/);
            if (p[0]) out.add((p[1] || p[0]).trim());
        }
    }
    return out;
}

/**
 * Problems that would stop the page from loading: { problems: [...], notes: [...] }. Files under ./data/ are checked by
 * checkData, not here, so that the page can be checked without them.
 */
export function checkPage(siteDir = SITE) {
    const problems = []; const notes = [];
    const [tmp, files] = moduleCopy(siteDir);
    try {
        for (const f of files) {
            const r = spawnSync(process.execPath, ['--check', path.join(tmp, f)], { encoding: 'utf8' });
            const why = (r.stderr || '').split(/\r?\n/).find((l) => /Error/.test(l)) || (r.stderr || '').trim();
            if (r.status !== 0) problems.push(`js/${f} does not parse: ${why}`);
        }
        const src = Object.fromEntries(files.map((f) => [f, fs.readFileSync(path.join(siteDir, 'js', f), 'utf8')]));
        for (const f of files) {
            for (const m of src[f].matchAll(/^import\s*\{([^}]*)\}\s*from\s*'\.\/([\w.-]+\.js)'/gm)) {
                const target = m[2];
                if (!(target in src)) { problems.push(`js/${f} imports ./${target}, which is missing`); continue; }
                const have = exportsOf(src[target]);
                for (const part of m[1].split(',')) {
                    const name = part.trim().split(/\s+as\s+/)[0].trim();
                    if (name && !have.has(name)) problems.push(`js/${f} imports ${name} from ./${target}, which does not export it`);
                }
            }
        }
        if ('app.js' in src) {
            // the data layout the page reads, which checkData and scripts/build_data.py write
            if (!src['app.js'].includes("fetch('./data/index.json')")) problems.push('js/app.js does not fetch ./data/index.json');
            if (!src['app.js'].includes('fetch(`./data/s/${x.f}.json`)')) problems.push('js/app.js does not fetch spectra from ./data/s/<f>.json');
            const html = fs.existsSync(path.join(siteDir, 'index.html')) ? fs.readFileSync(path.join(siteDir, 'index.html'), 'utf8') : '';
            const have = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
            const want = new Set([...src['app.js'].matchAll(/\$\('([\w-]+)'\)/g)].map((m) => m[1]));
            for (const id of want) if (html && !have.has(id)) problems.push(`js/app.js looks up #${id}, which index.html does not have`);
        }
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
    const htmlPath = path.join(siteDir, 'index.html');
    if (!fs.existsSync(htmlPath)) return { problems: [...problems, 'index.html is missing'], notes };
    const html = fs.readFileSync(htmlPath, 'utf8');
    if (!/<script type="module" src="\.\/js\/app\.js"><\/script>/.test(html)) problems.push('index.html does not load ./js/app.js as a module');
    if (!/<link rel="stylesheet" href="\.\/xsec\.css">/.test(html)) problems.push('index.html does not link ./xsec.css');
    for (const m of html.matchAll(/(?:href|src)="\.\/([^"]+)"/g)) {
        if (m[1].startsWith('data/')) continue;
        if (!fs.existsSync(path.join(siteDir, m[1]))) problems.push(`index.html names ./${m[1]}, which is missing`);
    }
    for (const m of html.matchAll(/(?:href|src)="\.\.\/([^"]+)"/g)) {
        const p = path.join(siteDir, '..', m[1]);
        if (fs.existsSync(path.dirname(p))) { if (!fs.existsSync(p)) problems.push(`index.html names ../${m[1]}, which is missing`); }
        else notes.push(`../${m[1]} is outside this folder and was not checked (on the site it is the Thermochemistry Lab's)`);
    }
    return { problems, notes };
}

/* ── engine cases, with the values worked out by hand ───────────────────── */
// Each case: [id, what, got(X), want, relative tolerance]. Constants are CODATA 2022 (N_A, h, c, k, e exact).
const gauss = (A, l0, w) => (l) => A * Math.exp(-(((l - l0) / w) ** 2));
const grid = (a, b, h, f) => { const d = []; for (let l = a; l <= b + 1e-9; l += h) d.push([+l.toFixed(6), f(l)]); return d; };
const band = grid(200, 300, 0.5, gauss(1e-17, 255, 20));
export const CASES = [
    ['loschmidt', 'Loschmidt constant n₀ = 101 325 Pa / (k 273.15 K) = 2.686 780 111 × 10¹⁹ cm⁻³ (CODATA 2022)', (X) => X.LOSCHMIDT, 2.686780111e19, 1e-9],
    ['eps10', 'ε (base 10) of 10⁻¹⁷ cm²: 10⁻¹⁷ × 6.022 140 76 × 10²³ / (1000 ln 10) = 2615.38 L mol⁻¹ cm⁻¹', (X) => X.SIGMA_UNITS.eps10.to(1e-17), 2615.3825, 1e-7],
    ['epse', 'ε (base e) of 10⁻¹⁷ cm²: 10⁻¹⁷ N_A / 1000 = 6022.14 L mol⁻¹ cm⁻¹', (X) => X.SIGMA_UNITS.epse.to(1e-17), 6022.14076, 1e-9],
    ['k273', 'k (base e) of 10⁻¹⁷ cm²: 10⁻¹⁷ n₀ = 268.678 cm⁻¹ atm⁻¹', (X) => X.SIGMA_UNITS.k273.to(1e-17), 268.678011, 1e-8],
    ['k273-10', 'k (base 10) of 10⁻¹⁷ cm²: 268.678 / ln 10 = 116.685 cm⁻¹ atm⁻¹', (X) => X.SIGMA_UNITS.k273_10.to(1e-17), 116.685378, 1e-7],
    ['Mb', '10⁻¹⁷ cm² = 10 Mb', (X) => X.SIGMA_UNITS.Mb.to(1e-17), 10, 1e-12],
    ['barn', '10⁻¹⁷ cm² = 10⁷ barn', (X) => X.SIGMA_UNITS.barn.to(1e-17), 1e7, 1e-12],
    ['A2', '10⁻¹⁷ cm² = 0.1 Å²', (X) => X.SIGMA_UNITS.A2.to(1e-17), 0.1, 1e-12],
    ['a02', 'a₀² = (5.291 772 105 44 × 10⁻⁹ cm)² = 2.800 285 × 10⁻¹⁷ cm²', (X) => X.SIGMA_UNITS.a02.from(1), 2.8002852e-17, 1e-7],
    ['m2', '10⁻¹⁷ cm² = 10⁻²¹ m²', (X) => X.SIGMA_UNITS.m2.to(1e-17), 1e-21, 1e-12],
    ['dfdE', 'df/dE of 1 eV⁻¹ is σ = 2π² r_e ħc = 109.76 Mb', (X) => X.SIGMA_UNITS.Mb.to(X.SIGMA_UNITS.dfdE.from(1)), 109.761, 1e-5],
    ['round-trip', 'every unit converts to σ and back unchanged', (X) => Math.max(...Object.values(X.SIGMA_UNITS).map((u) => Math.abs(u.from(u.to(3.7e-19)) / 3.7e-19 - 1))), 0, 1e-12],
    ['eV', '248.4 nm is 1239.841 98 nm eV / 248.4 nm = 4.991 31 eV', (X) => X.nmToEV(248.4), 4.991313, 1e-6],
    ['cm1', '250 nm is 40 000 cm⁻¹', (X) => X.nmToCm1(250), 40000, 1e-12],
    ['density', '1 Torr at 296 K: 133.322 368 Pa / (k 296 K) = 3.262 33 × 10¹⁶ cm⁻³', (X) => X.density(133.322368, 296), 3.262331e16, 1e-6],
    ['beer-lambert', 'τ of 1.1329 × 10⁻¹⁷ cm² at 1 Torr, 296 K over 10 cm: 3.6959, so 2.4825 % transmitted', (X) => {
        const r = X.beerLambert(1.1329e-17, X.density(133.322368, 296), 10); return [r.tau, r.T, r.A * Math.LN10, r.absorbed + r.T];
    }, [3.695895, 0.02482523, 3.695895, 1], 1e-6],
    ['photons', '10 mJ cm⁻² at 248.4 nm: hc/λ = 7.996 96 × 10⁻¹⁹ J, so 1.250 47 × 10¹⁶ photons cm⁻²', (X) => X.pulsePhotolysis(1e-17, 0.01, 248.4).photons, 1.2504746e16, 1e-6],
    ['excited', 'with σ = 10⁻¹⁷ cm²: σΦ = 0.125 047, fraction excited 1 − e^−0.125 047 = 0.117 545', (X) => X.pulsePhotolysis(1e-17, 0.01, 248.4).excited, 0.1175450, 1e-5],
    ['photolyzed', 'φ = 0.5: 1 − e^−0.062 524 = 0.060 609', (X) => X.pulsePhotolysis(1e-17, 0.01, 248.4, 0.5).photolyzed, 0.0606092, 1e-5],
    ['saturation', 'saturation fluence hν/σ = 7.996 96 × 10⁻¹⁹ J / 10⁻¹⁷ cm² = 79.97 mJ cm⁻²', (X) => X.pulsePhotolysis(1e-17, 0.01, 248.4).saturation * 1000, 79.96964, 1e-6],
    ['interp', 'linear interpolation between tabulated points: 1.155 + 0.3 × 0.004 = 1.1562 (× 10⁻¹⁷ cm²)', (X) => X.sigmaAt([[253.5, 1.155e-17], [254, 1.159e-17]], 253.65), 1.1562e-17, 1e-9],
    ['outside', 'no value outside the data (null, not an extrapolation)', (X) => [X.sigmaAt(band, 199.9), X.sigmaAt(band, 300.1)].every((v) => v === null) ? 0 : 1, 0, 0],
    ['line-avg', 'a Gaussian line of 10 nm FWHM on a Gaussian band of 1/e half width 20 nm: σ₀ s₁/√(s₁² + s₂²) = 0.9578 σ₀', (X) => {
        const s1 = 20 / Math.SQRT2; const s2 = 10 / (2 * Math.sqrt(2 * Math.LN2)); return X.sigmaLine(band, 255, 10).sigma / (1e-17 * s1 / Math.hypot(s1, s2));
    }, 1, 1e-4],
    ['line-edge', 'a line centered on the last data point is half inside the data', (X) => X.sigmaLine(band, 300, 2).covered, 0.5, 2e-3],
    ['line-flat', 'on a flat spectrum the line average is the flat value', (X) => X.sigmaLine([[200, 2e-19], [210, 2e-19], [220, 2e-19]], 210, 3).sigma, 2e-19, 1e-12],
    ['temperature', 'σ at 262 K between 226 K (1.1676) and 298 K (1.1562): 1.1676 − 0.0114 × 36/72 = 1.1619 (× 10⁻¹⁷ cm²)', (X) => X.sigmaAtT([
        { T: 226, data: [[253.5, 1.167e-17], [254, 1.169e-17]] }, { T: 298, data: [[253.5, 1.155e-17], [254, 1.159e-17]] }], 253.65, 262).sigma, 1.1619e-17, 1e-9],
    ['temperature-nearest', 'with sets at 200, 250 and 300 K, 260 K lies between 250 and 300 K: 1 + 0.2 × 1 = 1.2 (× 10⁻¹⁸ cm²)', (X) => {
        const f = (v) => [[250, v], [260, v]]; const r = X.sigmaAtT([{ T: 300, data: f(2e-18) }, { T: 200, data: f(5e-18) }, { T: 250, data: f(1e-18) }], 255, 260);
        return [r.sigma, r.T0, r.T1];
    }, [1.2e-18, 250, 300], 1e-12],
    ['temperature-value', 'the table value passed in is the one interpolated: 2 and 4 at 200 and 300 K give 3 at 250 K', (X) => X.sigmaAtT([{ T: 200, v: 2 }, { T: 300, v: 4 }], 0, 250, (s) => s.v).sigma, 3, 1e-12],
    ['no-extrapolation-T', 'no temperature extrapolation: 310 K beyond the 298 K set gives null', (X) => X.sigmaAtT([
        { T: 226, data: band }, { T: 298, data: band }], 255, 310) === null ? 0 : 1, 0, 0],
    ['median-step', 'the median step of steps 0.5, 1.5 and 2 nm is 1.5 nm', (X) => X.medianStep([[1, 1], [1.5, 1], [3, 1], [5, 1]]), 1.5, 1e-12],
    ['coarse', 'data every 1.5 nm are coarse for a 1 nm line, not for a 2 nm line', (X) => {
        const d = Array.from({ length: 21 }, (_, i) => [240 + 1.5 * i, 1e-18]);
        return [X.sigmaLine(d, 250, 1).coarse, X.sigmaLine(d, 250, 2).coarse].join();
    }, 'true,false', 0],
    ['laser-lines', 'the preset laser lines (nm): 118.2, Lyman-α 121.567, F₂ 157.6, ArF 193.3, Nd:YAG/5 212.8, KrCl 222, KrF 248.4, Nd:YAG/4 266, XeCl 308, XeF 351.1, Nd:YAG/3 354.7, 405, Nd:YAG/2 532.1',
        (X) => X.LASER_LINES.map((L) => L.nm).join(), '118.2,121.567,157.6,193.3,212.8,222,248.4,266,308,351.1,354.7,405,532.1', 0],
    ['x-axes', 'the x axes: 250 nm is 250 nm, 40 000 cm⁻¹ and 4.959 37 eV', (X) => ['nm', 'cm1', 'eV'].map((k) => X.X_AXES[k].of(250)), [250, 40000, 4.959368], 1e-6],
    ['density-form', '1 in a pressure unit of 133.322 368 Pa (1 Torr) at 296 K: 3.262 33 × 10¹⁶ cm⁻³', (X) => X.densityFromForm(1, 133.322368, 296), 3.262331e16, 1e-6],
    ['pulse-form', '10 mJ cm⁻² at 248.4 nm and σ = 10⁻¹⁷ cm²: 1.250 47 × 10¹⁶ photons cm⁻², saturation 79.97 mJ cm⁻²', (X) => {
        const r = X.pulseFromForm(1e-17, 10, 248.4, 0.5); return [r.photons, r.saturationmJ, r.photolyzed];
    }, [1.2504746e16, 79.96964, 0.0606092], 1e-5],
    ['thinned', 'a dataset of 5000 points shown as 2000 is thinned; one of 5 shown as 5 is not', (X) => [X.isThinned({ n0: 5000, np: 2000 }), X.isThinned({ n0: 5, np: 5 })].join(), 'true,false', 0],
    ['full-value', 'at a preset line a thinned dataset gives its stored full-resolution value; with a line width, the thinned curve', (X) => {
        const meta = { n0: 9000, np: 3, at: { '121.567': 1.147e-20 } }; const d = [[120, 1e-18], [121.567, 5.62e-18], [123, 1e-18]];
        const a = X.tableValue(meta, d, 121.567); const b = X.tableValue(meta, d, 121.567, 0.05);
        return [a.sigma, a.full, a.thinned, b.full, b.thinned].join();
    }, '1.147e-20,true,false,false,true', 0],
    ['typed-number', 'a typed number is read whole or not at all: 1,5 is 1.5 (not 1), 1,064 and 12abc are refused', (X) => [X.parseNum('1,5'), X.parseNum('1.5e-17'), X.parseNum('1,064'), X.parseNum('12abc'), X.parseNum('')].join('|'), '1.5|1.5e-17|||', 0],
    ['axis-limits', 'plot limits of 200 to 280 nm are 4.428 to 6.199 eV, and 4 to 6.2 eV are 199.9745 to 309.9605 nm', (X) => { const a = X.limitsFromNm('eV', '200', '280'); const b = X.limitsToNm('eV', '4', '6.2'); return [a.from, a.to, b.min, b.max].join('|'); }, '4.428|6.199|199.9745|309.9605', 0],
    ['format', 'numbers on the page: 13 077.2 is 1.308 × 10⁴ (not 1.308e+4), 2615.38 is 2615, 0.0606092 is 0.06061', (X) => [X.formatSci(13077.2), X.formatSci(2615.38), X.formatSci(0.0606092), X.formatSci(1.805e-31)].join('|'),
        '1.308 × 10<sup>4</sup>|2615|0.06061|1.805 × 10<sup>−31</sup>', 0],
    ['series', 'one paper\'s versions are separate temperature series', (X) => [X.seriesKey('mainz2013:O3_Bass(1984)_203K_245-340nm'), X.seriesKey('bremen:O3_Serdyuchenko2014_v2013FFT_293K')].join('|'),
        'mainz2013:O3_Bass(1984)|bremen:O3_Serdyuchenko2014_v2013FFT', 0],
    // a kept point every 5 samples, gaps of at most 10: linear interpolation is off by at most 10²/8 × (1/50²) = 0.005 × 10⁻¹⁸ cm²
    // where σ ≥ 0.5 × 10⁻¹⁸ cm², so by at most 1 %
    ['resample', 'thinning a smooth 10 000-point spectrum to 2000 points keeps both ends and stays within 1 % of it', (X) => {
        const big = Array.from({ length: 10000 }, (_, i) => [200 + i * 0.01, 1e-18 * (1.5 + Math.sin(i / 50))]);
        const r = X.resample(big, 2000);
        if (r.length !== 2000 || r[0] !== big[0] || r[r.length - 1] !== big[big.length - 1]) return 1;
        let worst = 0; for (const [l, s] of big) worst = Math.max(worst, Math.abs(X.sigmaAt(r, l) / s - 1));
        return worst < 1e-2 ? 0 : worst;
    }, 0, 0],
];

function close(got, want, tol) {
    if (Array.isArray(want)) return Array.isArray(got) && got.length === want.length && want.every((w, i) => close(got[i], w, tol));
    if (typeof want === 'string') return got === want;
    if (!Number.isFinite(got)) return false;
    return want === 0 ? Math.abs(got) <= tol : Math.abs(got / want - 1) <= tol;
}

/** Run the engine cases against the engine of a site folder: [{ id, title, pass, detail }]. */
export async function runEngineCases(siteDir = SITE) {
    const [tmp] = moduleCopy(siteDir);
    try {
        const X = await import(pathToFileURL(path.join(tmp, 'xsec.js')).href);
        return CASES.map(([id, title, f, want, tol]) => {
            let got; try { got = f(X); } catch (err) { return { id, title, pass: false, detail: `threw ${err.message}` }; }
            const pass = close(got, want, tol);
            return { id, title, pass, detail: pass ? '' : `got ${JSON.stringify(got)}, want ${JSON.stringify(want)} within ${tol}` };
        });
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}

/* ── data ─────────────────────────────────────────────────────────────── */
// Ozone at the 253.65 nm mercury line: 1.1329(35) × 10⁻¹⁷ cm², Hodges et al., Metrologia 56, 034001 (2019).
export const O3_HG = { nm: 253.65, sigma: 1.1329e-17, tol: 0.02, minSets: 5, Tmin: 290, Tmax: 300 };

const interp = (d, x) => {
    for (let i = 1; i < d.length; i++) {
        if (d[i - 1][0] <= x && x <= d[i][0]) { const [x0, y0] = d[i - 1]; const [x1, y1] = d[i]; return x1 === x0 ? y0 : y0 + ((y1 - y0) * (x - x0)) / (x1 - x0); }
    }
    return null;
};

/**
 * Ozone at the mercury line in every room-temperature ozone dataset (T within [Tmin, Tmax], three points or more,
 * covering the line). The check passes when the median is within tol of the reference, and is not applicable with
 * fewer than minSets datasets. Returns { pass, median, n, values: [[id, σ]], detail }.
 */
export function ozoneCheck(index, spectra, opt = O3_HG) {
    const o3 = index.species.find((s) => s.f === 'O3');
    const values = [];
    for (const x of (o3 ? o3.sets : [])) {
        if (!(typeof x.T === 'number' && x.T >= opt.Tmin && x.T <= opt.Tmax) || x.np < 3 || x.l[0] > opt.nm || x.l[1] < opt.nm) continue;
        const d = spectra(x.f); const v = d && interp(d, opt.nm);
        if (v != null) values.push([x.id, v]);
    }
    if (values.length < opt.minSets) return { pass: null, median: null, n: values.length, values, detail: `room-temperature ozone datasets covering ${opt.nm} nm: ${values.length}, fewer than ${opt.minSets}` };
    const v = values.map((x) => x[1]).sort((a, b) => a - b);
    const median = v.length % 2 ? v[v.length >> 1] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
    const dev = median / opt.sigma - 1;
    return { pass: Math.abs(dev) <= opt.tol, median, n: values.length, values,
        detail: `median of ${values.length} datasets ${median.toExponential(4)} cm², ${(100 * dev).toFixed(2)} % from ${opt.sigma.toExponential(4)}` };
}

const MEDIA = new Set(['air', 'vacuum', 'unknown']);
/** The wavelength range in an MPI-Mainz file name (_245-340nm, _210nm, _477.3,532.2,577.2nm), or null. */
export function nameRange(id) {
    const m = /_(\d+(?:\.\d*)?(?:\s*[-,]\s*\d+(?:\.\d*)?)*)\s?nm/.exec(String(id));
    if (!m) return null;
    const v = m[1].split(/\s*[-,]\s*/).filter(Boolean).map(Number);
    return v.length ? [Math.min(...v), Math.max(...v)] : null;
}
const validT = (T) => T === null || Number.isFinite(T) || (Array.isArray(T) && T.length === 2 && T.every(Number.isFinite) && T[0] <= T[1]);

/**
 * The data files of a page copy: index.json parses and is consistent with itself, every dataset's spectrum file exists
 * and matches its row (point count, wavelength range, sorted wavelengths, σ > 0 and finite), there are no spectrum files
 * that no row names, and ozone agrees with the reference at the mercury line. Returns { present, problems, ozone }.
 */
export function checkData(dataDir, opt = O3_HG) {
    const ixPath = path.join(dataDir, 'index.json');
    if (!fs.existsSync(ixPath)) return { present: false, problems: [], ozone: null };
    const problems = [];
    let index;
    try { index = JSON.parse(fs.readFileSync(ixPath, 'utf8')); } catch (err) { return { present: true, problems: [`data/index.json does not parse: ${err.message}`], ozone: null }; }
    const meta = index.meta || {}; const max = meta.max_points;
    if (!Number.isInteger(max) || max < 3) problems.push('data/index.json: meta.max_points is not a whole number of at least 3');
    if (!meta.sources || typeof meta.sources !== 'object') problems.push('data/index.json: meta.sources is missing');
    if (!Array.isArray(index.species) || !index.species.length) return { present: true, problems: [...problems, 'data/index.json lists no species'], ozone: null };
    const ids = new Set(); const files = new Set(); const keys = new Set(); const cache = new Map();
    const spectrum = (f) => {
        if (cache.has(f)) return cache.get(f);
        let d = null; try { d = JSON.parse(fs.readFileSync(path.join(dataDir, 's', `${f}.json`), 'utf8')); } catch { d = null; }
        cache.set(f, d); return d;
    };
    for (const s of index.species) {
        if (!s.k || keys.has(s.k)) problems.push(`species key ${JSON.stringify(s.k)} is missing or repeated`);
        keys.add(s.k);
        if (!s.f || !Array.isArray(s.sets) || !s.sets.length) { problems.push(`species ${s.k}: no formula or no datasets`); continue; }
        for (const x of s.sets) {
            const at = `${s.k} ${x.id}`;
            if (!x.id || ids.has(x.id)) problems.push(`${at}: dataset id missing or repeated`);
            ids.add(x.id);
            if (!/^\d{5}$/.test(String(x.f)) || files.has(x.f)) { problems.push(`${at}: spectrum file name ${JSON.stringify(x.f)} is not five digits or is repeated`); continue; }
            files.add(x.f);
            if (!meta.sources || !meta.sources[x.src]) problems.push(`${at}: source ${JSON.stringify(x.src)} is not in meta.sources`);
            if (!MEDIA.has(x.med)) problems.push(`${at}: wavelength scale ${JSON.stringify(x.med)} is not air, vacuum or unknown`);
            if (!validT(x.T)) problems.push(`${at}: temperature ${JSON.stringify(x.T)} is not a number, a [low, high] range or null`);
            if (!x.ref || typeof x.ref !== 'object') problems.push(`${at}: no reference`);
            if (!(Number.isInteger(x.np) && Number.isInteger(x.n0) && x.np >= 1 && x.np <= x.n0 && (!max || x.np <= max))) problems.push(`${at}: point counts np ${x.np}, n0 ${x.n0} (max ${max}) do not fit`);
            if (!Array.isArray(x.l) || !(x.l[0] <= x.l[1]) || !(x.l[0] > 0)) problems.push(`${at}: wavelength range ${JSON.stringify(x.l)} is not a positive [low, high]`);
            // a Mainz file whose data lie far outside the range in its own name holds something else (temperatures, wavenumbers)
            const nr = x.src === 'mainz2013' ? nameRange(x.id) : null;
            if (nr && Array.isArray(x.l) && (x.l[0] < nr[0] / 2 || x.l[1] > nr[1] * 2)) problems.push(`${at}: wavelengths ${x.l[0]}–${x.l[1]} nm, far outside the ${nr[0]}–${nr[1]} nm of the file name`);
            if (x.at !== undefined) {
                const bad = !x.at || typeof x.at !== 'object' ? ['not an object'] : Object.entries(x.at).filter(([k, v]) => !(Number.isFinite(+k) && Number.isFinite(v) && v > 0 && +k >= x.l[0] && +k <= x.l[1])).map(([k]) => k);
                if (bad.length) problems.push(`${at}: stored laser-line values ${bad.join(', ')} are not positive numbers inside the data`);
                if (!(x.n0 > x.np)) problems.push(`${at}: stored laser-line values on a dataset that is not thinned`);
            }
            const d = spectrum(x.f);
            if (!Array.isArray(d)) { problems.push(`${at}: data/s/${x.f}.json is missing or does not parse`); continue; }
            if (d.length !== x.np) problems.push(`${at}: data/s/${x.f}.json has ${d.length} points, the index says ${x.np}`);
            let bad = 0;
            for (let i = 0; i < d.length; i++) {
                const p = d[i];
                if (!Array.isArray(p) || !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || p[1] <= 0 || p[0] <= 0 || (i && p[0] < d[i - 1][0])) bad++;
            }
            if (bad) problems.push(`${at}: data/s/${x.f}.json has ${bad} point(s) out of order, not finite or with σ ≤ 0`);
            else if (d.length && Array.isArray(x.l) && (Math.abs(d[0][0] - x.l[0]) > 0.006 || Math.abs(d[d.length - 1][0] - x.l[1]) > 0.006)) problems.push(`${at}: data/s/${x.f}.json spans ${d[0][0]}–${d[d.length - 1][0]} nm, the index says ${x.l[0]}–${x.l[1]}`);
        }
    }
    const sdir = path.join(dataDir, 's');
    const extra = fs.existsSync(sdir) ? fs.readdirSync(sdir).filter((f) => !files.has(f.replace(/\.json$/, ''))) : [];
    if (extra.length) problems.push(`data/s has ${extra.length} file(s) no dataset names: ${extra.slice(0, 5).join(', ')}`);
    const ozone = ozoneCheck(index, spectrum, opt);
    if (ozone.pass === false) problems.push(`ozone at ${opt.nm} nm: ${ozone.detail}`);
    return { present: true, problems, ozone, nSpecies: index.species.length, nSets: ids.size };
}

/* ── boot ─────────────────────────────────────────────────────────────── */
/**
 * Run app.js in a child Node process against a stand-in document whose elements are the ids of index.html, with
 * fetch served from dataDir, then click a laser line, switch to the eV axis and give the line a width. `query` is the
 * page's URL query (k=…&on=…&lam=…). Returns { ok, problems, summary, first, last }, with the HTML of the main panels
 * after the boot (first) and after the clicks (last).
 */
export function bootPage(siteDir = SITE, dataDir = path.join(siteDir, 'data'), query = '') {
    const [tmp] = moduleCopy(siteDir);
    try {
        const r = spawnSync(process.execPath, [SELF, '--boot-child', tmp, path.resolve(dataDir), path.join(siteDir, 'index.html'), query], { encoding: 'utf8', timeout: 120000 });
        let out = null; try { out = JSON.parse((r.stdout || '').trim().split(/\r?\n/).pop()); } catch { out = null; }
        if (!out) return { ok: false, problems: [`the boot check did not finish: ${(r.stderr || r.stdout || `exit ${r.status}`).trim().slice(0, 300)}`], summary: '' };
        return out;
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}

async function bootChild(modDir, dataDir, htmlPath, query) {
    let line = '';
    const problems = []; const fail = (what, err) => problems.push(`${what}: ${err && err.stack ? err.stack.split('\n').slice(0, 3).join(' | ') : err}`);
    process.on('unhandledRejection', (err) => fail('unhandled rejection', err));
    process.on('uncaughtException', (err) => fail('uncaught exception', err));
    const html = fs.readFileSync(htmlPath, 'utf8');
    const types = new Map([...html.matchAll(/<(\w+)\b([^>]*)>/g)].map((m) => [/\bid="([^"]+)"/.exec(m[2]), m]).filter(([id]) => id)
        .map(([id, m]) => [id[1], (/\btype="([^"]+)"/.exec(m[2]) || [])[1] || (m[1] === 'select' ? 'select-one' : '')]));
    const listeners = new Map(); const on = (key) => (type, fn) => { const k = `${key}|${type}`; if (!listeners.has(k)) listeners.set(k, []); listeners.get(k).push(fn); };
    const fire = async (key, type, ev) => { for (const fn of listeners.get(`${key}|${type}`) || []) await fn(ev); };
    class El {
        constructor(id, type = '') { this.id = id; this.type = type; this.innerHTML = ''; this.textContent = ''; this.value = ''; this.checked = false; this.hidden = false; this.dataset = {}; this.children = []; this.attrs = {}; }
        addEventListener(type, fn) { on(this.id)(type, fn); }
        setAttribute(k, v) { this.attrs[k] = String(v); }
        querySelector() { return null; }
        querySelectorAll() { return []; }
        closest() { return new El(''); }
        contains() { return false; }
        focus() {}
        getBoundingClientRect() { return { height: 300, width: 600, top: 0, left: 0 }; }
        get scrollHeight() { return 0; } get offsetHeight() { return 0; } get clientHeight() { return 0; }
    }
    const els = new Map([...types].map(([id, type]) => [id, new El(id, type)]));
    const draws = [];
    const g = globalThis;
    g.window = g;
    g.document = { getElementById: (id) => els.get(id) || null, addEventListener: on('document'), activeElement: null, body: new El('body'), createElement: () => new El('') };
    g.location = { search: query ? `?${query}` : '', pathname: '/beta/cross-sections/', hash: '', href: `https://cdfoley.com/beta/cross-sections/${query ? `?${query}` : ''}` };
    g.history = { replaceState: () => {} };
    g.matchMedia = () => ({ matches: true, addEventListener: () => {} });
    g.addEventListener = on('window');
    g.getComputedStyle = () => ({ top: 'auto' });
    g.innerHeight = 900;
    g.CSS = { escape: (s) => String(s).replace(/["\\]/g, '\\$&') };
    g.Plot = { draw: (el, o) => draws.push(o), clear: () => {} };
    g.fetch = async (url) => {
        const m = /^\.\/data\/(.+)$/.exec(String(url));
        const f = m && path.join(dataDir, ...m[1].split('/'));
        if (!f || !fs.existsSync(f)) return { ok: false, status: 404, json: async () => { throw new Error('404'); } };
        const text = fs.readFileSync(f, 'utf8');
        return { ok: true, status: 200, json: async () => JSON.parse(text) };
    };
    const settle = async (ms = 50) => { for (let i = 0; i < 4; i++) await new Promise((r) => setTimeout(r, ms)); };
    const $ = (id) => els.get(id);
    try {
        await import(pathToFileURL(path.join(modDir, 'app.js')).href);
        for (let i = 0; i < 400 && !g.__xsec && !problems.length; i++) await new Promise((r) => setTimeout(r, 25));
        await settle();
        if (!g.__xsec && !problems.length) problems.push('the page did not finish booting within 10 s');
        const panels = (calc) => {
            for (const [id, want] of [['xs-sets', '<table'], ['xs-at', '<table'], ['xs-conv', 'Loschmidt'], ['xs-src', 'datasets'], ...(calc ? [['xs-bl', 'tc-results'], ['xs-pp', 'tc-results']] : [['xs-bl', 'Enter σ']])]) {
                if (!$(id) || !$(id).innerHTML.includes(want)) problems.push(`#${id} does not show ${JSON.stringify(want)}`);
            }
            const last = draws[draws.length - 1];
            if (!last || !last.series || !last.series.length) problems.push('no curve was drawn');
            if (/NaN|undefined/.test($('xs-at') ? $('xs-at').innerHTML : '')) problems.push('the laser-line table shows NaN or undefined');
        };
        const snap = () => Object.fromEntries(['xs-sets', 'xs-at', 'xs-plot-note', 'xs-bl', 'xs-pp'].map((id) => [id, $(id) ? $(id).innerHTML || $(id).textContent : null]));
        let first = {};
        if (g.__xsec) {
            first = snap();
            panels(false);
            // the steps a reader takes: use a σ, a laser line, the eV axis, a line width
            await fire('document', 'click', { target: { closest: (s) => (s === 'button[data-use]' ? { dataset: { use: '1e-17' } } : null) } });
            await fire('xs-laser', 'click', { target: { closest: () => ({ dataset: { nm: '121.567' } }) } });
            $('xs-x').value = 'eV'; await fire('xs-x', 'change', {});
            $('xs-fw').value = '0.05'; await fire('xs-fw', 'input', {});
            await settle();
            panels(true);
            const last = draws[draws.length - 1];
            if (last && last.x && !/eV/.test(last.x.label)) problems.push(`the x axis is ${JSON.stringify(last.x.label)} after picking eV`);
            const xs = last && last.series ? last.series.flatMap((s) => s.x) : [];
            if (xs.some((x) => !(x > 0 && x < 50))) problems.push('after picking eV the curves are not drawn against photon energies (0 to 50 eV)');
        }
        const st = g.__xsec ? g.__xsec.state : {};
        const summary = g.__xsec ? `${st.k}: ${st.on.length} dataset(s) shown, ${draws.length} draw(s)` : '';
        line = (`${JSON.stringify({ ok: !problems.length, problems: [...new Set(problems)], summary, first, last: snap() })}\n`);
    } catch (err) {
        fail('boot', err);
        line = (`${JSON.stringify({ ok: false, problems, summary: '' })}\n`);
    }
    // On Linux, stdout to a pipe is written asynchronously, so exiting before the write finishes cuts the line short
    // and the parent cannot read it. Exit only once the whole line is written.
    process.stdout.write(line, () => process.exit(0));
}

/** Everything the site checks, for one site folder: { page, engine, data, boot, why } with why empty when it passes. */
export async function runSelfTest(siteDir = SITE, { requireData = false, dataDir = path.join(siteDir, 'data') } = {}) {
    const page = checkPage(siteDir);
    const engine = await runEngineCases(siteDir);
    const data = checkData(dataDir);
    const boot = data.present && !page.problems.length ? bootPage(siteDir, dataDir) : null;
    const why = [...page.problems];
    if (boot && !boot.ok) why.push(`the page does not boot on the data: ${boot.problems.join('; ')}`);
    const failed = engine.filter((x) => !x.pass);
    if (failed.length) why.push(`${failed.length} engine case(s) failed`);
    if (requireData && !data.present) why.push(`no data files in ${dataDir}`);
    if (data.present && data.problems.length) why.push(`${data.problems.length} data problem(s)`);
    if (requireData && data.present && data.ozone && data.ozone.pass === null) why.push(`the ozone check could not run: ${data.ozone.detail}`);
    return { page, engine, data, boot, why };
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain && process.argv[2] === '--boot-child') {
    await bootChild(process.argv[3], process.argv[4], process.argv[5], process.argv[6] || '');
} else if (isMain) {
    const args = process.argv.slice(2);
    const requireData = args.includes('--data');
    const k = args.indexOf('--data-dir');
    const dataArg = k >= 0 ? args[k + 1] : null;
    const pos = args.filter((a, i) => !a.startsWith('--') && !(k >= 0 && i === k + 1));
    const dir = pos[0] ? path.resolve(pos[0]) : SITE;
    const r = await runSelfTest(dir, { requireData, dataDir: dataArg ? path.resolve(dataArg) : path.join(dir, 'data') });
    for (const p of r.page.problems) console.log('PAGE', p);
    for (const n of r.page.notes) console.log('NOTE', n);
    const failed = r.engine.filter((x) => !x.pass);
    console.log(`engine: ${r.engine.length - failed.length} of ${r.engine.length} cases pass; page ${r.page.problems.length ? `${r.page.problems.length} problem(s)` : 'loads'}`);
    for (const x of failed) console.log('FAIL', x.id, x.detail);
    if (!r.data.present) console.log('data: not present (this repository carries no data; the site\'s copy does)');
    else {
        console.log(`data: ${r.data.nSpecies ?? '?'} species, ${r.data.nSets ?? '?'} datasets, ${r.data.problems.length} problem(s)`);
        for (const p of r.data.problems.slice(0, 20)) console.log('DATA', p);
        if (r.data.ozone) console.log(`ozone at ${O3_HG.nm} nm: ${r.data.ozone.pass === null ? 'not applicable' : r.data.ozone.pass ? 'pass' : 'FAIL'}; ${r.data.ozone.detail}`);
    }
    if (r.boot) console.log(`boot: ${r.boot.ok ? `pass (${r.boot.summary})` : 'FAIL'}`);
    for (const p of r.boot ? r.boot.problems : []) console.log('BOOT', p);
    if (r.why.length) console.log(`not passed: ${r.why.join('; ')}`);
    process.exit(r.why.length ? 1 : 0);
}
