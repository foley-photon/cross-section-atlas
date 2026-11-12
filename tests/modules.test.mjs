// The page can load: every module in site/js parses, every imported name is exported by the module it comes from,
// index.html loads app.js, the stylesheet and files that exist, and app.js reads the data layout that
// scripts/build_data.py writes (scripts/selftest.mjs checkPage, the same check the site runs before it copies a
// release). The negative controls break a copy of site/ in each of those ways and expect the check to say so; they
// keep the gate itself honest.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkPage } from '../scripts/selftest.mjs';

const SITE = fileURLToPath(new URL('../site/', import.meta.url));

/** checkPage of a temporary copy of site/ placed at <tmp>/cross-sections, changed by edit(dir, tmp). */
function copy(edit = () => {}) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-page-'));
    const dir = path.join(tmp, 'cross-sections');
    try {
        fs.cpSync(SITE, dir, { recursive: true });
        edit(dir, tmp);
        return checkPage(dir);
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}
const change = (dir, f, from, to) => {
    const p = path.join(dir, f); const t = fs.readFileSync(p, 'utf8');
    assert.ok(t.includes(from), `${f}: ${from}`);
    fs.writeFileSync(p, t.replace(from, to));
};

test('the shipped page loads', () => {
    const r = checkPage(SITE);
    assert.deepEqual(r.problems, []);
    assert.deepEqual(r.notes, ['../thermochem/thermochem.css is outside this folder and was not checked (on the site it is the Thermochemistry Lab\'s)']);
});

test('negative control: an unchanged copy loads too', () => {
    assert.deepEqual(copy().problems, []);
});

test('beside a Thermochemistry Lab folder, its stylesheet is checked', () => {
    const withCss = copy((dir, tmp) => { fs.mkdirSync(path.join(tmp, 'thermochem')); fs.writeFileSync(path.join(tmp, 'thermochem', 'thermochem.css'), ''); });
    assert.deepEqual(withCss, { problems: [], notes: [] });
    const without = copy((dir, tmp) => fs.mkdirSync(path.join(tmp, 'thermochem')));
    assert.deepEqual(without.problems, ['index.html names ../thermochem/thermochem.css, which is missing']);
});

test('a module that does not parse is caught', () => {
    const r = copy((d) => change(d, 'js/app.js', 'function renderAll()', 'function renderAll('));
    assert.equal(r.problems.length, 1);
    assert.match(r.problems[0], /^js\/app\.js does not parse/);
});

test('an import of a name the engine does not export is caught', () => {
    const r = copy((d) => change(d, 'js/xsec.js', 'export function sigmaAtT(', 'function sigmaAtT('));
    assert.deepEqual(r.problems, ['js/app.js imports sigmaAtT from ./xsec.js, which does not export it']);
});

test('a missing engine module is caught', () => {
    const r = copy((d) => fs.rmSync(path.join(d, 'js', 'xsec.js')));
    assert.ok(r.problems.includes('js/app.js imports ./xsec.js, which is missing'));
    assert.ok(r.problems.includes('index.html names ./js/xsec.js, which is missing'));
});

test('index.html that does not load app.js or the stylesheet is caught', () => {
    assert.deepEqual(copy((d) => change(d, 'index.html', '<script type="module" src="./js/app.js"></script>', '')).problems,
        ['index.html does not load ./js/app.js as a module']);
    const css = copy((d) => fs.rmSync(path.join(d, 'xsec.css')));
    assert.deepEqual(css.problems, ['index.html names ./xsec.css, which is missing']);
});

test('app.js that reads another data layout is caught', () => {
    const r = copy((d) => change(d, 'js/app.js', 'fetch(`./data/s/${x.f}.json`)', 'fetch(`./data/spectra/${x.f}.json`)'));
    assert.deepEqual(r.problems, ['js/app.js does not fetch spectra from ./data/s/<f>.json']);
    assert.deepEqual(copy((d) => change(d, 'js/app.js', "getJSON('./data/species.json')", "getJSON('./data/list.json')")).problems, ['js/app.js does not fetch ./data/species.json']);
    assert.deepEqual(copy((d) => change(d, 'js/app.js', '`./data/sp/${encodeURIComponent(s.file)}.json`', '`./data/sp/${s.k}.json`')).problems, ['js/app.js does not fetch a species from ./data/sp/<file>.json']);
    assert.deepEqual(copy((d) => change(d, 'js/app.js', "full ||= getJSON('./data/index.json');", "full ||= getJSON('./data/all.json');")).problems.length, 0, 'the fallback at boot still names index.json');
    assert.deepEqual(copy((d) => { change(d, 'js/app.js', "full ||= getJSON('./data/index.json');", "full ||= getJSON('./data/all.json');"); change(d, 'js/app.js', "full = getJSON('./data/index.json');", "full = getJSON('./data/all.json');"); }).problems,
        ['js/app.js does not fall back on ./data/index.json']);
    assert.deepEqual(copy((d) => change(d, 'js/app.js', 'getJSON(`./data/${name}.json`)', 'getJSON(`./data/who/${name}.json`)')).problems, ['js/app.js does not fetch ./data/who.json and ./data/coarse.json']);
});
