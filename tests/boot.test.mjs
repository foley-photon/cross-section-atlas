// The page boots: app.js runs against a stand-in document built from index.html's ids, with the fixture data
// (scripts/selftest.mjs bootPage, which the site's check also runs on its own data). The checks read what a visitor
// would see in the panels: the laser-line table, the notes on thinned data and upper limits, the citation text where
// a source gives no authors, the absorption and photolysis results, and the "Who absorbs here?" table. The page is
// booted on the split data files, and on a copy of the folder without them (index.json only), and must show the same. The negative controls break a copy of the page in
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

/** bootPage on a copy of the fixture data changed by edit(dir). */
function bootData(edit, query = '') {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-bootdata-'));
    try {
        fs.cpSync(FIX, tmp, { recursive: true });
        edit(tmp);
        return bootPage(SITE, tmp, query);
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}
const noSplit = (d) => { for (const f of ['species.json', 'who.json', 'coarse.json', 'sp']) fs.rmSync(path.join(d, f), { recursive: true }); };

test('who absorbs here: the air view at the default line, with the gases that have no data named', () => {
    const r = bootPage(SITE, FIX);
    assert.equal(r.ok, true, r.problems.join('; '));
    const who = text(r.first['xs-who']);
    // the fixture has ozone only among the gases of air: Molina and Molina at 298 K, 1.0798e-17 at 248.4 nm. In air at
    // 1 atm, 296 K and 50 % relative humidity ozone is 40 ppb × (1 − 0.013 731) = 39.45 ppb, so
    // α = 1.0798e-17 cm² × 3.945 07e-8 × 2.479 372e19 cm⁻³ = 1.0562e-5 cm⁻¹ = 1.056e-3 m⁻¹ and 1/α = 946.8 m
    assert.match(who, /1 O 3 ozone 1\.080 × 10 E−17 39\.5 ppb 0\.00106 947 m Molina and Molina \(1986\) MPI-Mainz 2013 298 K/);
    assert.match(who, /O 3 is the only one of these gases with a value at 248\.4 nm\. In air it gives α = 0\.00106 m⁻¹, a 1\/e length of 947 m\. No table here for N 2 , O 2 and H 2 O , so this is not the whole answer for air: the sum covers only the gases with a value at this wavelength and counts absorption only, not scattering\./);
    assert.match(who, /Air at 1 atm and 296 K as an ideal gas, n = 2\.479 × 10 E19 cm⁻³, at 50 % relative humidity \(1\.37 % water vapor\)\./);
    // the fold names every share and its source, argon among them
    assert.match(who, /O 2 20\.95 % 20\.66 % U\.S\. Standard Atmosphere, 1976, Table 3: sea-level dry air Ar 0\.934 % 0\.921 % .* No cross sections in the five collections/);
    assert.match(who, /CO 2 426\.1 ppm 420\.2 ppm NOAA Global Monitoring Laboratory, Trends in CO₂: global monthly mean, July 2026/);
    assert.match(who, /O 3 40 ppb 39\.45 ppb U\.S\. Standard Atmosphere, 1976, Table 15: typical value near the surface/);
    assert.match(who, /Argon, 0\.934 % of dry air, is in none of the five collections\./);
    assert.match(r.first['xs-who'], /data-who-sort="" aria-pressed="true"/, 'the air view opens ordered by absorption in air');
    assert.match(who, /1 of these 13 gases has data at 248\.4 nm\. No data here for N 2 , O 2 , H 2 O , CO 2 , CH 4 , H 2 , N 2 O , CO , NO 2 , NO , SO 2 and NH 3 : no table in the five collections reaches this wavelength for them\. That is not the same as no absorption\./);
    assert.match(who, /Point values at this preset line/);
    assert.doesNotMatch(who, /synthetic test molecule/, 'Xx is not a gas of air');
    assert.equal((r.first['xs-who'].match(/<th role="columnheader"/g) || []).length, 8, 'the three air columns, and no Note column when no row has a note');
    assert.match(r.first['xs-who'], /data-who-view="air" aria-pressed="true"/);
});

test('who absorbs here, in air: the humidity, the order by σ, a wavelength between the lines, and a bad humidity', () => {
    // dry air: ozone is 40 ppb, α = 1.0798e-17 × 40e-9 × 2.479 372e19 × 100 = 1.0709e-3 m⁻¹, 1/α = 933.8 m
    const dry = text(bootPage(SITE, FIX, 'rh=0').first['xs-who']);
    assert.match(dry, /1 O 3 ozone 1\.080 × 10 E−17 40 ppb 0\.00107 934 m Molina and Molina/);
    assert.match(dry, /at 0 % relative humidity \(dry air\)/);
    assert.match(dry, /H 2 O — 0 Relative humidity 0 % at 296 K/);
    // saturated air: 2.746 % water, ozone 40 ppb × 0.972 537 = 38.90 ppb, α = 1.0709e-3 × 0.972 537 = 1.0415e-3 m⁻¹, 1/α = 960.1 m
    assert.match(text(bootPage(SITE, FIX, 'rh=100').first['xs-who']), /1 O 3 ozone 1\.080 × 10 E−17 38\.9 ppb 0\.00104 960 m .* \(2\.75 % water vapor\)/);
    // one click away: the same rows in the order of σ per molecule, and the link keeps it
    const sig = bootPage(SITE, FIX, 'ws=sig').first['xs-who'];
    assert.match(sig, /data-who-sort="sig" aria-pressed="true"/);
    assert.match(text(sig), /The list is in the order of σ per molecule\./);
    assert.match(text(sig), /1 O 3 ozone 1\.080 × 10 E−17 39\.5 ppb 0\.00106 947 m/);
    // between the lines the values are 2 nm means (ozone 10^−16.95 = 1.122e-17 cm² at 250 nm): every figure made from one
    // is marked ≈, given to two figures, and the line above the table says why it is rough.
    // α = 1.122e-17 × 3.945 07e-8 × 2.479 372e19 × 100 = 1.0975e-3 m⁻¹, 1/α = 911 m
    const mean = text(bootPage(SITE, FIX, 'lam=250').first['xs-who']);
    assert.match(mean, /1 O 3 ozone ≈ 1\.1 × 10 E−17 39\.5 ppb ≈ 0\.0011 ≈ 910 m Molina and Molina/);
    assert.match(mean, /In air it gives α ≈ 0\.0011 m⁻¹, a 1\/e length of ≈ 910 m\. Rough figures: these are means of σ over 2 nm, not values at the line\./);
    // a humidity that is not a number from 0 to 100 gives a message and the plain list, with no figure for air
    const bad = bootPage(SITE, FIX, 'rh=5x').first['xs-who'];
    assert.match(text(bad), /“5x” is not a number \(relative humidity\)\./);
    assert.doesNotMatch(bad, /xs-who-take|xs-w-a/);
    assert.match(text(bad), /1 O 3 ozone 1\.080 × 10 E−17 Molina and Molina \(1986\) MPI-Mainz 2013 298 K/);
    assert.match(text(bootPage(SITE, FIX, 'rh=120').first['xs-who']), /Enter a relative humidity from 0 to 100 %\./);
    // all molecules: ranked by σ, with no air columns and no line for air
    const all = bootPage(SITE, FIX, 'who=all&lam=248.4').first['xs-who'];
    assert.doesNotMatch(all, /xs-who-take|xs-w-a|data-who-sort/);
    // no gas of air at the wavelength: no line for air, and nothing that looks like a number
    const none = bootPage(SITE, FIX, 'lam=600').first['xs-who'];
    assert.doesNotMatch(none, /xs-who-take|NaN|undefined/);
    assert.match(text(none), /0 of these 13 gases have data at 600 nm\./);
});

/** bootPage on a copy of the fixture data with oxygen and water added to the species list and to the rows of who.json. */
function bootAir(at, query) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'xs-air-'));
    try {
        fs.cpSync(FIX, tmp, { recursive: true });
        const sp = JSON.parse(fs.readFileSync(path.join(tmp, 'species.json'), 'utf8'));
        sp.species.push(['O2', 'O2', 'oxygen', '7782-44-7', 1], ['H2O', 'H2O', 'water', '7732-18-5', 1]);
        fs.writeFileSync(path.join(tmp, 'species.json'), JSON.stringify(sp));
        const who = JSON.parse(fs.readFileSync(path.join(tmp, 'who.json'), 'utf8'));
        Object.assign(who.sets, { '00091': ['O2', 'Series (2003)', 293, 'test', 0], '00092': ['H2O', 'Water (2011)', 298, 'test', 0] });
        for (const [k, rows] of Object.entries(at)) who.at[k] = [...who.at[k], ...rows].sort((a, b) => b[1] - a[1]);
        fs.writeFileSync(path.join(tmp, 'who.json'), JSON.stringify(who));
        return text(bootPage(SITE, tmp, query).first['xs-who']);
    } finally {
        fs.rmSync(tmp, { recursive: true, force: true });
    }
}

test('who absorbs here, in air: the line above the table with an unconfirmed oxygen value, and with a value in a band', () => {
    // 248.4 nm: ozone 1.0798e-17 (α = 1.056e-3 m⁻¹, 947 m) and an O2 value of 1.984e-24 cm² above 245 nm, which is
    // listed last, flagged, and left out of the sum: 1.984e-24 × 0.2065996 × 2.479 372e19 × 100 = 1.016e-3 m⁻¹
    const kr = bootAir({ '248.4': [['00091', 1.984e-24]] }, 'lam=248.4');
    assert.match(kr, /O 3 is the only one of these gases with a firm value at 248\.4 nm\. In air it gives α = 0\.00106 m⁻¹, a 1\/e length of 947 m\./);
    assert.match(kr, /O 2 is listed and left out of the sum \(not a firm value: above 245 nm one series stands for O₂, far above the other O₂ data where they overlap\); its listed value would give α ≈ 0\.001 m⁻¹\./);
    assert.match(kr, /No table here for N 2 and H 2 O , so this is not the whole answer for air: the sum covers only/);
    assert.match(kr, /2 O 2 oxygen 1\.984 × 10 E−24 20\.7 % ≈ 0\.001 ≈ 980 m Series \(2003\) Test 293 K not a firm value: .*; not in the sum for air/);
    assert.doesNotMatch(kr, /take the most light|takes the most light/);
    // 193.3 nm: O2 6.7918e-22 on the flank of a band (σ spans a factor of 63 within 0.25 nm) gives 0.3479 m⁻¹, water
    // 1.95e-21 gives 0.066 39 m⁻¹: 0.4143 m⁻¹ together, 1/α = 2.41 m; without the flagged value 1/0.06639 = 15.06 m
    const arf = bootAir({ '193.3': [['00092', 1.95e-21], ['00091', 6.7918e-22, null, null, 63]] }, 'lam=193.3');
    assert.match(arf, /O 2 has the largest listed value in air at 193\.3 nm : α ≈ 0\.35 m⁻¹, 84 % of the listed total\. The 2 gases with a value add up to α ≈ 0\.41 m⁻¹, a 1\/e length of ≈ 2\.4 m\./);
    assert.match(arf, /Rough figures: the O 2 value is flagged \(structured here: σ spans a factor of 63 within ±0\.25 nm\)\. Without the flagged values the sum is α ≈ 0\.066 m⁻¹, a 1\/e length of ≈ 15 m\./);
    assert.match(arf, /No table here for N 2 , so this is not the whole answer for air/);
    assert.match(arf, /1 O 2 oxygen 6\.792 × 10 E−22 20\.7 % ≈ 0\.35 ≈ 2\.9 m Series \(2003\) Test 293 K structured here: σ spans a factor of 63 within ±0\.25 nm/);
});

test('negative control: an air view without its answer for air fails the boot check', () => {
    const r = bootCopy((d) => change(d, 'js/app.js', "const take = A ? airTakeaway(A, lam, view.missing) : rhErr ? bad(rhErr) : '';", "const take = '';"));
    assert.equal(r.boot.ok, false);
    assert.deepEqual(r.boot.problems, ['the air view of the reverse lookup has rows and no answer for air (the line above the table, the α column)']);
});

test('who absorbs here: all molecules, and a molecule loaded with the dataset it is ranked by', () => {
    const r = bootPage(SITE, FIX);
    // after the clicks of the boot check the line is Lyman-α, where the fixture has one point of Xx
    const all = text(r.who.all);
    assert.match(all, /1 Xx synthetic test molecule 3\.000 × 10 E−18 Foley \(2026\) Test T not given measured at 121\.567 nm only/);
    assert.match(all, /1 of the 2 molecules has data at 121\.567 nm\./);
    assert.match(all, /The line width is not applied in this table\./, 'the boot check set a line width of 0.05 nm');
    assert.equal(r.who.picked, 'Xx');
    assert.match(text(r.who.after), /Xx is loaded with that dataset/);
    assert.match(r.who.after, /<tr role="row" class="xs-w-cur">/);
    // the rows are laid out as cards on a phone, so the table states its roles
    assert.match(r.who.after, /<table class="tc-table xs-who" role="table" aria-labelledby="xs-who-h"><thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col" class="num">#<\/th>/);
    assert.equal((r.who.after.match(/<td role="cell"/g) || []).length, 6);
    // the laser-line table now starts with that dataset
    assert.match(text(r.who.at), /^Dataset T σ, cm² Note Foley \(2026\) T not given 3\.000 × 10 E−18 measured at 121\.567 nm only/);
    const link = bootPage(SITE, FIX, 'who=all&lam=248.4');
    assert.match(link.first['xs-who'], /data-who-view="all" aria-pressed="true"/);
    assert.match(text(link.first['xs-who']), /1 O 3 ozone 1\.080 × 10 E−17 .* 2 Xx synthetic test molecule 8\.968 × 10 E−18 Foley \(2026\) Test 298 K/);
});

test('who absorbs here: between the preset lines the coarse table answers, and says what it is', () => {
    // 250 nm is in the bin 250 to 252 nm. Ozone (Molina and Molina, 0.5 nm points 1.124, 1.113, 1.114, 1.146, 1.155): trapezoid
    // mean 1.128e-17, stored as round(100 × -16.9476) = -1695 and shown as 10^-16.95 = 1.1e-17. The band: 1e-17 exp(-0.04) =
    // 9.61e-18 at the bin's center, stored as -1702 and shown as 10^-17.02 = 9.5e-18 (one stored step is 2.3 %)
    const r = bootPage(SITE, FIX, 'who=all&lam=250');
    assert.equal(r.ok, true, r.problems.join('; '));
    const who = text(r.first['xs-who']);
    assert.match(who, /1 O 3 ozone ≈ 1\.1 × 10 E−17 Molina and Molina \(1986\) MPI-Mainz 2013 298 K 2 Xx synthetic test molecule ≈ 9\.5 × 10 E−18 Foley \(2026\) Test 298 K/);
    assert.match(who, /250 nm is not a preset line, so these are coarse values: the mean of σ from 250 to 252 nm in each dataset, to two figures\./);
    // upper limits are marked: 160 nm, where Xx has only those (bin 160 to 162 nm, 2e-19 rising to 2.4e-19: mean 2.2e-19)
    const ul = text(bootPage(SITE, FIX, 'who=all&lam=160').first['xs-who']);
    assert.match(ul, /1 Xx synthetic test molecule ≤ ≈ 2\.2 × 10 E−19 Xx steps \(2026\) rec\. Test 295 K upper limit; points more than 5 nm apart here/);
    // at a preset line the gap is given: 157.6 nm lies between the points at 150 and 160 nm
    const f2 = text(bootPage(SITE, FIX, 'who=all&lam=157.6').first['xs-who']);
    assert.match(f2, /1 Xx synthetic test molecule ≤ 1\.760 × 10 E−19 Xx steps \(2026\) rec\. Test 295 K upper limit; interpolated across 10 nm/);
    const none = text(bootPage(SITE, FIX, 'who=all&lam=600').first['xs-who']);
    assert.match(none, /0 of the 2 molecules have data at 600 nm\./);
    assert.doesNotMatch(none, /Press a molecule/);
    assert.match(text(bootPage(SITE, FIX, 'lam=24x').first['xs-who']), /Enter a wavelength under “At a laser line”\./);
});

test('on data without the split files the page reads index.json and shows the same panels', () => {
    const split = bootPage(SITE, FIX, 'k=Xx&on=test:Xx_band_298K,test:Xx_vuv_steps&lam=248.4');
    const old = bootData(noSplit, 'k=Xx&on=test:Xx_band_298K,test:Xx_vuv_steps&lam=248.4');
    assert.equal(old.ok, true, old.problems.join('; '));
    for (const id of ['xs-sets', 'xs-at', 'xs-plot-note']) assert.equal(old.first[id], split.first[id], id);
    assert.equal(old.last['xs-bl'], split.last['xs-bl']);
    assert.match(text(old.first['xs-who']), /This copy of the data has no table for the reverse lookup\./);
    assert.equal(bootData(noSplit).summary, bootPage(SITE, FIX).summary);
});

test('a species file that is missing or is another molecule sends the page to index.json', () => {
    const want = bootPage(SITE, FIX);
    const gone = bootData((d) => fs.rmSync(path.join(d, 'sp', 'O3.json')));
    assert.equal(gone.ok, true, gone.problems.join('; '));
    assert.equal(gone.first['xs-sets'], want.first['xs-sets']);
    // a stale or misnamed file (what a case-blind server gives for Co when it holds CO): not shown as this molecule
    const wrong = bootData((d) => fs.copyFileSync(path.join(d, 'sp', 'Xx.json'), path.join(d, 'sp', 'O3.json')));
    assert.equal(wrong.ok, true, wrong.problems.join('; '));
    assert.equal(wrong.first['xs-sets'], want.first['xs-sets']);
    assert.match(wrong.summary, /^O3: 1 dataset/);
});

test('with neither the species list nor index.json the page says so', () => {
    const r = bootData((d) => { noSplit(d); fs.rmSync(path.join(d, 'index.json')); });
    assert.equal(r.ok, false);
    assert.match(text(r.last['xs-sets']), /Could not load the dataset index \(HTTP 404\)\./);
});
