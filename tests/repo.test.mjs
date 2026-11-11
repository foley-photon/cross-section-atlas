// The repository itself: one version in package.json, CITATION.cff and the CHANGELOG; no data folder under site/
// (the data are not published here; README.md says why); and nothing in the tracked text files that belongs on one
// computer only, such as a drive-letter path, or that should not be public, such as an email address.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8');

/** Text files of the repository, without .git and Python's caches. */
function files(dir = ROOT, out = []) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        if (['.git', 'node_modules', '__pycache__'].includes(e.name)) continue;
        const p = path.join(dir, e.name);
        if (e.isDirectory()) files(p, out);
        else if (/\.(mjs|js|py|sh|json|md|cff|yml|yaml|html|css|txt)$|^(LICENSE|\.gitignore|\.gitattributes)$/.test(e.name)) out.push(p);
    }
    return out;
}

test('one version everywhere', () => {
    const pkg = JSON.parse(read('package.json')).version;
    const cff = read('CITATION.cff').match(/^version: "([^"]+)"$/m)[1];
    const pref = read('CITATION.cff').match(/^ {2}version: "([^"]+)"$/m)[1];
    const log = read('CHANGELOG.md').match(/^## (\d+\.\d+\.\d+) - \d{4}-\d{2}-\d{2}$/m)[1];
    assert.deepEqual([cff, pref, log], [pkg, pkg, pkg]);
});

test('site/ holds the page and no data', () => {
    assert.ok(fs.existsSync(path.join(ROOT, 'site', 'index.html')));
    assert.equal(fs.existsSync(path.join(ROOT, 'site', 'data')), false, 'site/data must not be in this repository');
    assert.match(read('.gitignore'), /^\/site\/data\/$/m);
});

test('no drive-letter paths or email addresses in the text files', () => {
    const drive = new RegExp('(^|[^A-Za-z])[A-Za-z]:[\\\\/](?!/)', 'm');         // a drive letter, a colon and a slash (not the colon of https://)
    const email = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]/;
    const bad = [];
    for (const f of files()) {
        const t = fs.readFileSync(f, 'utf8');
        const rel = path.relative(ROOT, f).replace(/\\/g, '/');
        if (drive.test(t)) bad.push(`${rel}: ${t.match(drive)[0]}...`);
        if (email.test(t)) bad.push(`${rel}: ${t.match(email)[0]}`);
    }
    assert.deepEqual(bad, []);
});
