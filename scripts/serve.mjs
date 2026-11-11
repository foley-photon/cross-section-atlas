// Local preview of the page the way cdfoley.com serves it: site/ at /beta/cross-sections/, with the files the page takes
// from the rest of the site (/assets/css/site.css, /assets/js/site.js for the header and footer, /assets/js/plot.js for
// the chart, the Inter font, the favicon and the Thermochemistry Lab's stylesheet) and the data files, which are not in
// this repository (see README.md). No dependencies.
//
//   node scripts/serve.mjs                    http://127.0.0.1:8000/beta/cross-sections/; shared files and data from
//                                             https://cdfoley.com, fetched on first use and kept in memory
//   node scripts/serve.mjs --data DIR         the data from a local folder (index.json and s/), for example a build of
//                                             scripts/build_data.py or tests/fixtures/data
//   node scripts/serve.mjs --site DIR         shared files and data from a local checkout of the site instead
//   node scripts/serve.mjs --offline          nothing from the network: no site header, footer, font or chart, and
//                                             no data unless --data or --site gives them
//   node scripts/serve.mjs --port 8123
//
// Links to other pages of the site are sent on to https://cdfoley.com; with --offline they give a 404.
// Edits under site/ show on reload (nothing is cached for them).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'site');
const MOUNT = '/beta/cross-sections/';
const UPSTREAM = 'https://cdfoley.com';
const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : null; };
const port = +(opt('--port') || 0) || 8000;
const offline = args.includes('--offline');
const localSite = opt('--site') ? path.resolve(opt('--site')) : null;
const dataDir = opt('--data') ? path.resolve(opt('--data')) : localSite ? path.join(localSite, 'beta', 'cross-sections', 'data') : null;
const TYPES = {
    '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png',
    '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8',
};
const shared = new Map();      // path on the site -> { status, type, body }

function send(res, status, type, body, extra = {}) {
    res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store', ...extra });
    res.end(body);
}

/** A file under root (never outside it); a folder serves its index.html. */
function fromFolder(res, root, rel) {
    const file = path.resolve(root, rel || 'index.html');
    if (file !== root && !file.startsWith(root + path.sep)) return send(res, 403, 'text/plain', 'forbidden');
    let st;
    try { st = fs.statSync(file); } catch { return send(res, 404, 'text/plain', `not found: ${rel}`); }
    if (st.isDirectory()) return fromFolder(res, root, path.join(rel, 'index.html'));
    send(res, 200, TYPES[path.extname(file)] || 'application/octet-stream', fs.readFileSync(file));
}

async function fromMainSite(res, p) {
    if (localSite) return fromFolder(res, localSite, p.slice(1));
    if (offline) return send(res, 404, 'text/plain', 'offline preview: files of the main site are not served');
    if (!shared.has(p)) {
        try {
            const r = await fetch(UPSTREAM + p);
            shared.set(p, { status: r.status, type: r.headers.get('content-type') || 'application/octet-stream', body: Buffer.from(await r.arrayBuffer()) });
        } catch (err) {
            return send(res, 502, 'text/plain', `could not fetch ${UPSTREAM}${p}: ${err.message}`);
        }
    }
    const x = shared.get(p);
    send(res, x.status, x.type, x.body);
}

const server = http.createServer(async (req, res) => {
    let p;
    try { p = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); } catch { return send(res, 400, 'text/plain', 'bad request'); }
    if (p === '/' || p === MOUNT.slice(0, -1)) return send(res, 302, 'text/plain', '', { Location: MOUNT });
    if (p.startsWith(MOUNT + 'data/')) return dataDir ? fromFolder(res, dataDir, p.slice(MOUNT.length + 5)) : fromMainSite(res, p);
    if (p.startsWith(MOUNT)) return fromFolder(res, SITE, p.slice(MOUNT.length));
    if (p.startsWith('/assets/') || p === '/beta/thermochem/thermochem.css') return fromMainSite(res, p);
    if (!offline) return send(res, 302, 'text/plain', '', { Location: UPSTREAM + new URL(req.url, 'http://localhost').pathname });
    send(res, 404, 'text/plain', `not part of this offline preview: ${p}`);
});
server.listen(port, '127.0.0.1', () => {
    const from = dataDir ? `data from ${dataDir}` : offline ? 'no data (offline)' : `data from ${UPSTREAM}`;
    console.log(`Absorption Cross-Section Atlas preview: http://127.0.0.1:${port}${MOUNT} (${from}${localSite ? `; shared files from ${localSite}` : offline ? '; no site header, footer, font or chart' : ''})`);
});
