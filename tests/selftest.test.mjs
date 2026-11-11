// scripts/selftest.mjs, the check the site runs on its copy of the page before it publishes a release: the engine cases
// with hand-worked values, the data checks on the small data folder in tests/fixtures/data (two CC BY 4.0 excerpts of
// the MPI-Mainz 2013 snapshot and synthetic spectra; see tests/fixtures/make_fixtures.mjs), broken copies of that folder
// that the data checks must catch, and the command line's exit codes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CASES, runEngineCases, checkData, ozoneCheck, runSelfTest, O3_HG } from '../scripts/selftest.mjs';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const SITE = path.join(ROOT, 'site');
const FIX = path.join(ROOT, 'tests', 'fixtures', 'data');
const read = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));

/** checkData of a temporary copy of the fixture data, changed by edit(dir, index); the index is written back after edit. */
function broken(edit, opt) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-data-'));
    try {
        fs.cpSync(FIX, dir, { recursive: true });
        const index = read(path.join(dir, 'index.json'));
        edit(dir, index);
        fs.writeFileSync(path.join(dir, 'index.json'), JSON.stringify(index));
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
    const r = broken((dir, ix) => { const x = xx(ix, 'test:Xx_vuv_steps'); x.src = 'mainz2013'; x.id = 'mainz2013:O2_Hong(2011)_1059-1745K_219nm(T dependence)'; x.l = [150, 180]; });
    assert.deepEqual(r.problems, []);
    const far = broken((dir, ix) => { const x = xx(ix, 'test:Xx_vuv_steps'); x.src = 'mainz2013'; x.id = 'mainz2013:Xx_A(2000)_298K_15-18nm'; });
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
    const need = run(SITE, '--data');
    assert.equal(need.status, 1);
    assert.match(need.stdout, /not passed: no data files in /);
});
