// The page boots: app.js runs against a stand-in document built from index.html's ids, with the fixture data
// (scripts/selftest.mjs bootPage, which the site's check also runs on its own data). The checks read what a visitor
// would see in the panels: the laser-line table, the notes on thinned data and upper limits, the citation text where
// a source gives no authors, the absorption and photolysis results. The negative controls break a copy of the page in
// ways the static checks cannot see (a call to a function that does not exist, an element id that index.html lost).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bootPage, checkPage } from '../scripts/selftest.mjs';

const SITE = fileURLToPath(new URL('../site/', import.meta.url));
const FIX = fileURLToPath(new URL('./fixtures/data/', import.meta.url));
const text = (html) => String(html || '').replace(/<sup>/g, ' E').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

/** bootPage of a copy of site/ changed by edit(dir). */
function bootCopy(edit, query = '') {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-boot-'));
    try {
        fs.cpSync(SITE, tmp, { recursive: true });
        edit(tmp);
        return { boot: bootPage(tmp, FIX, query), page: checkPage(tmp) };
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}
const change = (dir, f, from, to) => {
    const p = path.join(dir, f); const t = fs.readFileSync(p, 'utf8');
    assert.ok(t.includes(from), `${f}: ${from}`);
    fs.writeFileSync(p, t.replace(from, to));
};

test('the shipped page boots on the fixture data and fills every panel', () => {
    const r = bootPage(SITE, FIX);
    assert.deepEqual(r.problems, []);
    assert.equal(r.ok, true);
    assert.match(r.summary, /^O3: 1 dataset\(s\) shown/);
    // ozone at the default 248.4 nm: Molina and Molina 298 K, 1.071e-17 at 248 nm and 1.082e-17 at 248.5 nm,
    // so 1.071 + 0.8 × 0.011 = 1.0798 (× 1e-17 cm²)
    assert.match(text(r.first['xs-at']), /Molina and Molina \(1986\) 298 K 1\.080 × 10 E−17/);
    // after "use ›" (σ = 1e-17 cm², 1 Torr, 296 K, 10 cm): n = 3.262e16 cm⁻³, τ = 3.262, transmitted e^−3.262 = 3.83 % (shown to 4 figures, trailing zero dropped)
    assert.match(text(r.last['xs-bl']), /3\.262 × 10 E16 .*3\.262 .*Transmitted 3\.83 % absorbed 96\.17 %/);
    // 10 mJ cm⁻² at 121.567 nm (the clicked line): hc/λ = 1.634 03e-18 J, so 6.1199e15 photons cm⁻²; hν/σ = 163.4 mJ cm⁻²
    assert.match(text(r.last['xs-pp']), /6\.120 × 10 E15 .*163\.4 mJ/);
});

test('a thinned dataset gives its stored full-resolution value at a preset line, and is flagged elsewhere', () => {
    const r = bootPage(SITE, FIX, 'k=Xx&on=test:Xx_band_298K,test:Xx_vuv_steps&lam=248.4');
    assert.equal(r.ok, true, r.problems.join('; '));
    // the stored value: 1e-17 exp(−(6.6/20)²) = 8.9682e-18
    assert.match(text(r.first['xs-at']), /Foley \(2026\) 298 K 8\.968 × 10 E−18 from the full 6001-point spectrum; the plot is thinned/);
    const off = bootPage(SITE, FIX, 'k=Xx&on=test:Xx_band_298K&lam=250');
    assert.match(text(off.first['xs-at']), /thinned to 201 of 6001 points for the web; check the source/);
    const wide = bootPage(SITE, FIX, 'k=Xx&on=test:Xx_band_298K&lam=248.4&fw=2');
    assert.match(text(wide.first['xs-at']), /thinned to 201 of 6001 points/);
    assert.doesNotMatch(text(wide.first['xs-at']), /from the full/);
});

test('a dataset with a citation text and upper limits is listed as such', () => {
    const r = bootPage(SITE, FIX, 'k=Xx&on=test:Xx_vuv_steps&lam=160');
    assert.equal(r.ok, true, r.problems.join('; '));
    const sets = text(r.first['xs-sets']);
    assert.match(sets, /Xx steps \(2026\) recommended upper limits Synthetic test spectrum, not a measurement \(2026\)\./);
    assert.match(text(r.first['xs-at']), /Xx steps \(2026\) rec\. 295 K 2\.000 × 10 E−19 upper limit/);
});

test('a decimal comma in a field is read as a decimal, not cut at the comma', () => {
    // 1,5 mJ cm⁻² at 121.567 nm (the clicked line): 1.5e-3 J / 1.634 03e-18 J = 9.180e14 photons cm⁻²; cut at the comma it would be 6.120e14
    const comma = bootPage(SITE, FIX, 'F=1,5');
    const point = bootPage(SITE, FIX, 'F=1.5');
    assert.equal(comma.ok, true, comma.problems.join('; '));
    assert.match(text(comma.last['xs-pp']), /Photon fluence 9\.180 × 10 E14 /);
    assert.equal(comma.last['xs-pp'], point.last['xs-pp']);
    assert.doesNotMatch(text(comma.last['xs-pp']), /6\.120 × 10 E14/);
});

test('text that is not a number gives a message that names the field, and no result', () => {
    const amb = bootPage(SITE, FIX, 'F=1,064');
    assert.match(text(amb.last['xs-pp']), /“1,064” is ambiguous \(pulse fluence\): enter 1064 or 1\.064 \(decimal comma: 1,0640\)\./);
    assert.doesNotMatch(amb.last['xs-pp'], /tc-results/);
    const junk = bootPage(SITE, FIX, 'p=12abc');
    assert.match(text(junk.last['xs-bl']), /“12abc” is not a number \(pressure\)\./);
    assert.doesNotMatch(junk.last['xs-bl'], /tc-results/, 'parseFloat would have computed with 12');
    const lam = bootPage(SITE, FIX, 'lam=24x');
    assert.match(text(lam.first['xs-at']), /“24x” is not a number \(wavelength\)\./);
});

test('the laser-line table: units spelled out, and a second value column only for another unit', () => {
    const r = bootPage(SITE, FIX);
    // 248.4 nm: 10⁷/248.4 = 40257.6 cm⁻¹, 1239.841 984/248.4 = 4.9913 eV
    assert.match(text(r.first['xs-at']), /248\.4 nm = 40257\.6 cm⁻¹ = 4\.9913 eV\./);
    assert.equal((r.first['xs-at'].match(/<th[ >]/g) || []).length, 5, 'Dataset, T, σ, Note and the use column');
    const eps = bootPage(SITE, FIX, 'y=eps10');
    assert.equal((eps.first['xs-at'].match(/<th[ >]/g) || []).length, 6);
    // ε (base 10) of 1.0798e-17 cm²: × 6.022 140 76e23 / (1000 ln 10) = 2824
    assert.match(text(eps.first['xs-at']), /1\.080 × 10 E−17 2824 /);
});

test('negative control: an unchanged copy boots', () => {
    assert.equal(bootCopy(() => {}).boot.ok, true);
});

test('a page that throws on its first render is caught by the boot check only', () => {
    const r = bootCopy((d) => change(d, 'js/app.js', 'function renderAll() { markFields(); renderPlot();', 'function renderAll() { markFields(); renderPlotX();'));
    assert.deepEqual(r.page.problems, [], 'the static page check cannot see this');
    assert.equal(r.boot.ok, false);
    assert.ok(r.boot.problems.some((p) => /renderPlotX is not defined/.test(p)), r.boot.problems.join('; '));
});

test('an element id app.js needs that index.html lost is caught by both checks', () => {
    const r = bootCopy((d) => change(d, 'index.html', 'id="xs-conv"', 'id="xs-convX"'));
    assert.deepEqual(r.page.problems, ['js/app.js looks up #xs-conv, which index.html does not have']);
    assert.equal(r.boot.ok, false);
});

test('a unit slip in the form steps shows in the panels', () => {
    // the pressure unit dropped: 1 Torr read as 1 Pa gives n = 2.447e14 cm⁻³, not 3.262e16
    const r = bootCopy((d) => change(d, 'js/xsec.js', 'density(p * unitPa, T)', 'density(p, T)'));
    assert.doesNotMatch(text(r.boot.last['xs-bl']), /3\.262 × 10 E16/);
});
