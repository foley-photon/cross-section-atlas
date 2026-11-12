// scripts/selftest.mjs, the check the site runs on its copy of the page before it publishes a release: the engine cases
// with hand-worked values, the data checks on the small data folder in tests/fixtures/data (two CC BY 4.0 excerpts of
// the MPI-Mainz 2013 snapshot and synthetic spectra; see tests/fixtures/make_fixtures.mjs), broken copies of that folder
// that the data checks must catch (in index.json and the spectra, and in the split files species.json, sp/, who.json and
// coarse.json), the rule that picks one dataset per molecule for "Who absorbs here?", and the command line's exit codes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CASES, runEngineCases, checkData, ozoneCheck, runSelfTest, O3_HG, deriveSplit, pickBefore, binMeans, fileStems, gapAt, gapIn } from '../scripts/selftest.mjs';
import * as X from '../site/js/xsec.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SITE = path.join(ROOT, 'site');
const FIX = path.join(ROOT, 'tests', 'fixtures', 'data');
const read = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));

/** Write the split files of a data folder again from its index.json and spectra, as the build would. */
function resplit(dir) {
    const index = read(path.join(dir, 'index.json'));
    const s = deriveSplit(index, (f) => read(path.join(dir, 's', `${f}.json`)), X);
    fs.rmSync(path.join(dir, 'sp'), { recursive: true, force: true }); fs.mkdirSync(path.join(dir, 'sp'));
    fs.writeFileSync(path.join(dir, 'species.json'), JSON.stringify(s.slim));
    for (const [stem, sp] of s.files) fs.writeFileSync(path.join(dir, 'sp', `${stem}.json`), JSON.stringify(sp));
    fs.writeFileSync(path.join(dir, 'who.json'), JSON.stringify(s.who));
    fs.writeFileSync(path.join(dir, 'coarse.json'), JSON.stringify(s.coarse));
}
/**
 * checkData of a temporary copy of the fixture data, changed by edit(dir, index); the index is written back after edit.
 * With split 'again' the split files are then made again from the changed index (a consistent rebuild); with 'stale'
 * they stay as they were.
 */
function broken(edit, opt, split = 'stale') {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-data-'));
    try {
        fs.cpSync(FIX, dir, { recursive: true });
        const index = read(path.join(dir, 'index.json'));
        edit(dir, index);
        fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify(index));
        if (split === 'again') resplit(dir);
        return checkData(dir, opt);
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
}
const xx = (index, id) => index.species.find((s) => s.k === 'Xx').sets.find((x) => x.id === id);

test('every engine case passes on the shipped engine', async () => {
    const r = await runEngineCases(SITE);
    assert.equal(r.length, CASES.length);
    assert.deepEqual(r.filter((x) => !x.pass).map((x) => `${x.id}: ${x.detail}`), []);
});

test('negative control: a wrong constant in a copy of the engine fails its cases', async () => {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-engine-'));
    try {
        fs.cpSync(SITE, tmp, { recursive: true });
        const p = path.join(tmp, 'js', 'xsec.js');
        const t = fs.readFileSync(p, 'utf8');
        assert.ok(t.includes('(K_B * 273.15)'));
        fs.writeFileSync(p, t.replace('(K_B * 273.15)', '(K_B * 273)'));          // n0 at 273 K instead of 273.15 K
        const failed = (await runEngineCases(tmp)).filter((x) => !x.pass).map((x) => x.id);
        assert.deepEqual(failed, ['loschmidt', 'k273', 'k273-10']);
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
});

test('the fixture data pass the data checks', () => {
    const r = checkData(FIX);
    assert.equal(r.present, true);
    assert.deepEqual(r.problems, []);
    assert.equal(r.nSets, 6);
    assert.equal(r.split, true, 'the fixture folder has the split files');
    assert.equal(r.splitOk, true);
    assert.equal(r.ozone.pass, null, 'one room-temperature ozone set: fewer than the five the check asks for');
});

test('ozone at the mercury line in the Mainz excerpt', () => {
    // Molina and Molina (1986), 298 K: 1.155 + 0.3 × (1.159 − 1.155) = 1.1562e-17 cm², 2.06 % above Hodges et al. (2019)
    const index = read(path.join(FIX, 'index.json'));
    const spectra = (f) => read(path.join(FIX, 's', `${f}.json`));
    const one = { ...O3_HG, minSets: 1 };
    const r = ozoneCheck(index, spectra, one);
    assert.equal(r.n, 1);
    assert.ok(Math.abs(r.median / 1.1562e-17 - 1) < 1e-12);
    assert.equal(r.pass, false, 'outside 2 %');
    assert.equal(ozoneCheck(index, spectra, { ...one, tol: 0.03 }).pass, true);
    assert.equal(ozoneCheck(index, spectra, { ...one, Tmin: 220, Tmax: 230 }).values[0][0], 'mainz2013:O3_MolinaMolina(1986)_226K_185-350nm(0.5nm)');
});

test('an ozone value far from the reference fails the check', () => {
    const r = broken((dir) => {
        const p = path.join(dir, 's', '00001.json');
        fs.writeFileSync(p, JSON.stringify(read(p).map(([l, s]) => [l, s * 1.25])));
    }, { ...O3_HG, minSets: 1, tol: 0.03 });
    assert.equal(r.problems.length, 1);
    assert.match(r.problems[0], /^ozone at 253\.65 nm: median of 1 datasets 1\.4453e-17 cm², 27\.57 % from 1\.1329e-17$/);
});

test('broken data are caught', () => {
    const one = (edit) => broken(edit).problems;
    assert.deepEqual(one((dir) => fs.rmSync(path.join(dir, 's', '00003.json'))),
        ['Xx test:Xx_band_298K: data/s/00003.json is missing or does not parse']);
    assert.deepEqual(one((dir) => fs.writeFileSync(path.join(dir, 's', '00099.json'), '[]')),
        ['data/s has 1 file(s) no dataset names: 00099.json']);
    assert.deepEqual(one((dir) => fs.writeFileSync(path.join(dir, 's', '00006.json'), '[[150,1e-19],[170,4e-19],[160,2e-19],[180,2e-19]]')),
        ['Xx test:Xx_vuv_steps: data/s/00006.json has 1 point(s) out of order, not finite or with σ ≤ 0']);
    assert.deepEqual(one((dir) => fs.writeFileSync(path.join(dir, 's', '00006.json'), '[[150,1e-19],[160,0],[170,4e-19],[180,2e-19]]')),
        ['Xx test:Xx_vuv_steps: data/s/00006.json has 1 point(s) out of order, not finite or with σ ≤ 0']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').np = 5; xx(ix, 'test:Xx_vuv_steps').n0 = 5; }),
        ['Xx test:Xx_vuv_steps: data/s/00006.json has 4 points, the index says 5']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').l = [150, 190]; }),
        ['Xx test:Xx_vuv_steps: data/s/00006.json spans 150–180 nm, the index says 150–190']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').src = 'nowhere'; }),
        ['Xx test:Xx_vuv_steps: source "nowhere" is not in meta.sources']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').med = 'vac'; }),
        ['Xx test:Xx_vuv_steps: wavelength scale "vac" is not air, vacuum or unknown']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').T = [300, 200]; }),
        ['Xx test:Xx_vuv_steps: temperature [300,200] is not a number, a [low, high] range or null']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').id = 'test:Xx_band_298K'; }),
        ['Xx test:Xx_band_298K: dataset id missing or repeated']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_vuv_steps').np = 3000; xx(ix, 'test:Xx_vuv_steps').n0 = 3000; }), [
        'Xx test:Xx_vuv_steps: point counts np 3000, n0 3000 (max 2000) do not fit',
        'Xx test:Xx_vuv_steps: data/s/00006.json has 4 points, the index says 3000']);
    assert.deepEqual(broken((dir) => fs.writeFileSync(path.join(dir, 'index.json.tmp'), '')).problems, []);
});

test('a Mainz file whose data lie far outside the range in its name is caught', () => {
    // a "(T dependence)" file: temperatures 1059 to 1745 K read as wavelengths, in a file named for 219 nm
    const r = broken((dir, ix) => { const x = xx(ix, 'test:Xx_vuv_steps'); x.src = 'mainz2013'; x.id = 'mainz2013:O2_Hong(2011)_1059-1745K_219nm(T dependence)'; x.l = [150, 180]; }, undefined, 'again');
    assert.deepEqual(r.problems, []);
    const far = broken((dir, ix) => { const x = xx(ix, 'test:Xx_vuv_steps'); x.src = 'mainz2013'; x.id = 'mainz2013:Xx_A(2000)_298K_15-18nm'; }, undefined, 'again');
    assert.deepEqual(far.problems, ['Xx mainz2013:Xx_A(2000)_298K_15-18nm: wavelengths 150–180 nm, far outside the 15–18 nm of the file name']);
});

test('stored laser-line values must be positive, inside the data, and on a thinned dataset', () => {
    const one = (edit) => broken(edit).problems;
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_band_298K').at['222'] = -1; }),
        ['Xx test:Xx_band_298K: stored laser-line values 222 are not positive numbers inside the data']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_band_298K').at['121.567'] = 1e-18; }),
        ['Xx test:Xx_band_298K: stored laser-line values 121.567 are not positive numbers inside the data']);
    assert.deepEqual(one((dir, ix) => { xx(ix, 'test:Xx_band_298K').n0 = 201; }),
        ['Xx test:Xx_band_298K: stored laser-line values on a dataset that is not thinned']);
});

test('an index that does not parse is caught, and no index means no data', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-data-'));
    try {
        assert.deepEqual(checkData(dir), { present: false, problems: [], ozone: null });
        fs.writeFileSync(path.join(dir, 'index.json'), '{"meta":');
        const r = checkData(dir);
        assert.equal(r.present, true);
        assert.match(r.problems[0], /^data\/index\.json does not parse/);
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
});

test('runSelfTest: the repository copy passes without data, and fails when data are required', async () => {
    assert.deepEqual((await runSelfTest(SITE)).why, []);
    assert.deepEqual((await runSelfTest(SITE, { requireData: true })).why, [`no data files in ${path.join(SITE, 'data')}`]);
    const fx = await runSelfTest(SITE, { requireData: true, dataDir: FIX });
    assert.deepEqual(fx.why, ['the ozone check could not run: room-temperature ozone datasets covering 253.65 nm: 1, fewer than 5']);
});

test('the command line exits 0 when the check passes and 1 when it does not', () => {
    const run = (...a) => spawnSync(process.execPath, [path.join(ROOT, 'scripts', 'selftest.mjs'), ...a], { encoding: 'utf8' });
    const ok = run();
    assert.equal(ok.status, 0, ok.stdout + ok.stderr);
    assert.match(ok.stdout, new RegExp(`engine: ${CASES.length} of ${CASES.length} cases pass; page loads`));
    assert.match(ok.stdout, /data: not present/);
    const fx = run(SITE, '--data-dir', FIX);
    assert.equal(fx.status, 0, fx.stdout);
    assert.match(fx.stdout, /data: 2 species, 6 datasets, 0 problem\(s\)/);
    assert.match(fx.stdout, /split files: species\.json, sp\/, who\.json and coarse\.json agree with index\.json and the spectra/);
    assert.match(fx.stdout, /boot: pass/);
    const need = run(SITE, '--data');
    assert.equal(need.status, 1);
    assert.match(need.stdout, /not passed: no data files in /);
});

/* ── the split files and "Who absorbs here?" ──────────────────────────── */
const set = (id, extra = {}) => ({ id, T: 298, rec: false, y: 2000, np: 100, n0: 100, ...extra });

test('one dataset per molecule: the order of the rule', () => {
    const base = set('a');
    // each line: the first is chosen before the second
    const pairs = [
        [set('z', { T: 200, y: 1950 }), set('a', { ul: true }), 'a measured value before an upper limit, whatever else'],
        [set('z', { T: 200 }), set('a(e,e)', { rec: true, y: 2020, n0: 9000 }), 'optical absorption before electron energy loss'],
        [set('z', { T: 200 }), set('a', { np: 1, n0: 1 }), 'a spectrum before a single point'],
        [set('z', { T: 200 }), set('a_241,265,330nm(max)', { rec: true, y: 2020 }), 'a spectrum before a list of band maxima'],
        [set('z_240-270nm(34SO2)', { T: 200 }), set('a_241,265,330nm(max)', { rec: true }), 'an isotopologue spectrum before a list of points'],
        [set('z', { T: 273 }), set('a_240-270nm(15NH3)', { rec: true, y: 2020, n0: 9000 }), 'the natural sample before one isotopologue'],
        [set('z_240-270nm(150Torr)', { T: 301 }), set('a', { T: 273 }), 'a pressure is not an isotopologue: the temperature decides'],
        [set('z', { T: 280 }), set('a', { T: null, rec: true }), 'room temperature before no temperature given'],
        [set('z', { T: [250, 285] }), set('a', { T: 301 }), 'a range that reaches into 280 to 300 K is room temperature'],
        [set('z', { T: null }), set('a', { T: 301, rec: true }), 'no temperature given before another temperature'],
        [set('z', { T: 305 }), set('a', { T: 273, rec: true, y: 2020 }), 'away from room temperature, the nearest to 296 K: 9 K before 23 K'],
        [set('z', { rec: true, y: 1990 }), set('a', { y: 2020 }), 'recommended before newer'],
        [set('z', { y: 2011 }), set('a', { y: 2006, n0: 9000 }), 'the newer before the one with more points'],
        [set('z', { y: null, n0: 500 }), set('a', { y: null }), 'the same year (none): more points in the source'],
        [set('a'), set('b'), 'everything equal: the id decides'],
    ];
    for (const [first, second, why] of pairs) {
        assert.equal(pickBefore(first, second), true, why);
        assert.equal(pickBefore(second, first), false, why);
    }
    assert.equal(pickBefore(base, base), false);
    // points more than 5 nm apart around the wavelength: after the ones that are closer, before a single point, and an
    // optical spectrum with a gap still before an electron energy loss spectrum without one
    assert.equal(pickBefore(set('z', { T: 200, y: 1950 }), set('a', { rec: true }), false, true), true, 'the dense spectrum before the sparse one');
    assert.equal(pickBefore(set('a', { rec: true }), set('z', { T: 200, y: 1950 }), true, false), false);
    assert.equal(pickBefore(set('z', { np: 1, n0: 1 }), set('a'), false, true), true, 'a point measured at the line before a value interpolated across a gap');
    assert.equal(pickBefore(set('z'), set('a(e,e)'), true, false), true, 'optical with a gap before electron energy loss without');
});

test('the gap between the points around a wavelength, and the widest step that reaches into a bin', () => {
    const d = [[177.12, 3e-18], [206.64, 1.3e-18], [207, 1e-18], [212, 1e-18], [217.01, 1e-18]];
    assert.ok(Math.abs(gapAt(d, 193.3) - 29.52) < 1e-9);
    assert.equal(gapAt(d, 207), 0, 'at a point');
    assert.equal(gapAt(d, 217.01), 0, 'the last point');
    assert.equal(gapAt(d, 170), null); assert.equal(gapAt(d, 220), null);
    assert.ok(Math.abs(gapIn(d, 206, 208) - 29.52) < 1e-9);
    assert.ok(Math.abs(gapIn(d, 208, 210) - 5) < 1e-9);
    assert.ok(Math.abs(gapIn(d, 206.8, 207) - 0.36) < 1e-9);
});

test('bin means: the average of the interpolated spectrum over each 2 nm bin whose center the data cover', () => {
    // flat at 1e-20 from 199 to 205 nm: bins 100 (200 to 202) and 101 (202 to 204) have their centers 201 and 203 inside;
    // bin 99 (center 199) is covered from 199 to 200 only, bin 102 (center 205) from 204 to 205. round(100 log10 1e-20) = -2000
    assert.deepEqual([...binMeans([[199, 1e-20], [202, 1e-20], [205, 1e-20]])], [[99, -2000], [100, -2000], [101, -2000], [102, -2000]]);
    // a ramp from 1e-20 at 200 nm to 3e-20 at 202 nm has the mean 2e-20: round(100 × -19.69897) = -1970
    assert.deepEqual([...binMeans([[200, 1e-20], [201, 2e-20], [202, 3e-20]])], [[100, -1970]]);
    // a step table: 1e-20 up to 202 nm, 4e-20 after it. The step at the bin edge belongs to the next bin
    assert.deepEqual([...binMeans([[200, 1e-20], [202, 1e-20], [202, 4e-20], [204, 4e-20]])], [[100, -2000], [101, -1940]]);
    // data that end inside a bin: 200 to 201.5 nm covers the center 201, and the mean is taken over the part covered
    assert.deepEqual([...binMeans([[200, 1e-20], [200.5, 1e-20], [201.5, 1e-20]])], [[100, -2000]]);
    // 200 to 200.8 nm does not reach the center: no bin
    assert.deepEqual([...binMeans([[200, 1e-20], [200.4, 1e-20], [200.8, 1e-20]])], []);
});

test('species file names: the key, with a suffix where two differ only by case or Windows keeps the name', () => {
    assert.deepEqual(fileStems(['CO', 'O3', 'Co', 'co', 'Co_2', 'NUL', 'C2H5O2+']), ['CO', 'O3', 'Co_2', 'co_3', 'Co_2_2', 'NUL_2', 'C2H5O2+']);
});

test('the split files of the fixture data', () => {
    const index = read(path.join(FIX, 'index.json'));
    const s = deriveSplit(index, (f) => read(path.join(FIX, 's', `${f}.json`)), X);
    assert.deepEqual(s.slim.species, [['O3', 'O3', 'ozone', '10028-15-6', 2], ['Xx', 'Xx', 'synthetic test molecule', '', 4]]);
    assert.deepEqual(Object.keys(s.slim.meta).sort(), ['archive', 'built', 'max_points', 'sets', 'sources']);
    assert.equal(s.slim.meta.sets, 6);
    // 248.4 nm: ozone from Molina and Molina at 298 K, 1.071 + 0.8 × 0.011 = 1.0798e-17; Xx from the thinned band's stored
    // value 8.9682e-18 (it has 6001 points in its source, the 200 to 300 K band 201)
    assert.deepEqual(s.who.at['248.4'], [['00001', 1.0798e-17], ['00003', 8.9682e-18]]);
    // Lyman-α: the single point, with its wavelength; 157.6 nm: only the upper limits cover it, 1e-19 + 0.76 × 1e-19,
    // interpolated between points 10 nm apart, which the row says
    assert.deepEqual(s.who.at['121.567'], [['00005', 3e-18, 121.567]]);
    assert.deepEqual(s.who.at['157.6'], [['00006', 1.76e-19, null, 10]]);
    assert.deepEqual(s.who.sets['00006'], ['Xx', 'Xx steps (2026)', 295, 'test', 3], 'recommended (1) and upper limits (2)');
    assert.deepEqual(s.who.sets['00001'], ['O3', 'Molina and Molina (1986)', 298, 'mainz2013', 0]);
    assert.equal(s.who.at['193.3'].length, 0);
    // coarse: ozone 245 to 262 nm has the bin centers 245 to 261 (bins 122 to 130); Xx the upper limits over 150 to 180
    // (centers 151 to 179, bins 75 to 89), then the band over 200 to 300 (bins 100 to 149)
    assert.deepEqual(s.coarse.runs.map((r) => [r[0], r[1], r[2].length, ...r.slice(3)]), [['00001', 122, 9], ['00006', 75, 15, 1], ['00003', 100, 50]]);
    // the band's bin 127 (254 to 256 nm) holds its peak, 1e-17 at 255: the mean is a little under it, round(100 × -17.00036)
    assert.equal(s.coarse.runs[2][2][27], -1700);
    assert.deepEqual([...s.thinned], ['00003']);
    // what the folder holds is what the function gives
    assert.deepEqual(read(path.join(FIX, 'species.json')), s.slim);
    assert.deepEqual(read(path.join(FIX, 'who.json')), s.who);
    assert.deepEqual(read(path.join(FIX, 'coarse.json')), s.coarse);
});

test('split files that do not agree with index.json are caught', () => {
    const one = (edit) => broken(edit).problems;
    const edit = (dir, f, fn) => { const p = path.join(dir, f); const d = read(p); fn(d); fs.writeFileSync(p, JSON.stringify(d)); };
    assert.deepEqual(one((dir) => edit(dir, 'species.json', (d) => { d.species[1][4] = 5; })),
        ['data/species.json does not match index.json: species 2 is ["Xx","Xx","synthetic test molecule","",5], index.json has ["Xx","Xx","synthetic test molecule","",4]']);
    assert.deepEqual(one((dir) => edit(dir, 'species.json', (d) => { d.meta.built = '2026-01-01'; })), ['data/species.json does not match index.json: the meta block differs']);
    assert.deepEqual(one((dir) => fs.rmSync(path.join(dir, 'sp', 'Xx.json'))), ['data/sp/Xx.json is missing or is not the entry of Xx in index.json']);
    assert.deepEqual(one((dir) => edit(dir, 'sp/O3.json', (d) => { d.sets.pop(); })), ['data/sp/O3.json is missing or is not the entry of O3 in index.json']);
    assert.deepEqual(one((dir) => fs.writeFileSync(path.join(dir, 'sp', 'Zz.json'), '{}')), ['data/sp has 1 file(s) no species names: Zz.json']);
    assert.deepEqual(one((dir) => fs.rmSync(path.join(dir, 'who.json'))), ['data/who.json is missing or does not parse']);
    assert.deepEqual(one((dir) => fs.rmSync(path.join(dir, 'coarse.json'))), ['data/coarse.json is missing or does not parse']);
    // a value changed, a row for the wrong dataset, a row too many, a label changed
    assert.deepEqual(one((dir) => edit(dir, 'who.json', (d) => { d.at['248.4'][0][1] = 1.08e-17; })),
        ['data/who.json at 248.4 nm: row 1 is ["00001",1.08e-17], the index and spectra give ["00001",1.0798e-17]']);
    assert.deepEqual(one((dir) => edit(dir, 'who.json', (d) => { d.at['248.4'][1][0] = '00004'; })),
        ['data/who.json at 248.4 nm: row 2 is ["00004",8.9682e-18], the index and spectra give ["00003",8.9682e-18]']);
    assert.deepEqual(one((dir) => edit(dir, 'who.json', (d) => { d.at['193.3'].push(['00003', 1e-19]); })), ['data/who.json at 193.3 nm: 1 rows, the index and spectra give 0']);
    assert.deepEqual(one((dir) => edit(dir, 'who.json', (d) => { d.sets['00001'][1] = 'Molina (1986)'; })),
        ['data/who.json: dataset 00001 is labeled ["O3","Molina (1986)",298,"mainz2013",0], index.json gives ["O3","Molina and Molina (1986)",298,"mainz2013",0]']);
    assert.deepEqual(one((dir) => edit(dir, 'coarse.json', (d) => { d.runs[0][2][0] += 5; })),
        ['data/coarse.json run 1 is dataset 00001 from bin 122, 9 values; the index and spectra give 00001 from bin 122, 9 values, and a value differs']);
    assert.deepEqual(one((dir) => edit(dir, 'coarse.json', (d) => { d.runs[0][2][0] += 1; })), [], 'one step of the rounding is allowed');
    assert.deepEqual(one((dir) => edit(dir, 'coarse.json', (d) => { d.runs[2][2][3] += 40; })), [], 'a thinned dataset: its coarse values come from the full spectrum, which the site does not have');
    assert.deepEqual(one((dir) => edit(dir, 'coarse.json', (d) => { d.runs[2][2][3] += 0.5; })).length, 1, 'but they are whole numbers');
    assert.deepEqual(one((dir) => edit(dir, 'coarse.json', (d) => { d.runs[1][1] = 76; })).length, 1);
    // an index changed after the split files were written: they are stale
    const stale = one((dir, ix) => { xx(ix, 'test:Xx_band_200-300K').rec = true; });
    assert.ok(stale.includes('data/sp/Xx.json is missing or is not the entry of Xx in index.json'), stale.join('; '));
    // the recommended band now stands for Xx wherever it reaches; the first line where that shows is 212.8 nm
    assert.ok(stale.some((p) => p.startsWith('data/who.json at 212.8 nm: row 1 is ["00003",1.1654e-19], the index and spectra give ["00004",')), stale.join('; '));
    assert.deepEqual(broken((dir, ix) => { xx(ix, 'test:Xx_band_200-300K').rec = true; }, undefined, 'again').problems, [], 'made again from the changed index, they agree');
});

test('a data folder without the split files passes, and says so', async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-old-'));
    try {
        fs.cpSync(FIX, dir, { recursive: true });
        for (const f of ['species.json', 'who.json', 'coarse.json', 'sp']) fs.rmSync(path.join(dir, f), { recursive: true });
        const r = checkData(dir);
        assert.deepEqual(r.problems, []);
        assert.equal(r.split, false);
        const st = await runSelfTest(SITE, { dataDir: dir });
        assert.deepEqual(st.why, []);
        assert.equal(st.boot.ok, true, st.boot.problems.join('; '));
        const out = spawnSync(process.execPath, [path.join(ROOT, 'scripts', 'selftest.mjs'), SITE, '--data-dir', dir], { encoding: 'utf8' });
        assert.equal(out.status, 0, out.stdout);
        assert.match(out.stdout, /split files: not present; the page reads index\.json and has no reverse lookup/);
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
});
