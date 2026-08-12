/**
 * Pixel-diff harness — the primary gate on "pixel-perfect".
 *
 * Serves the project, renders index.html at 384x688 with deviceScaleFactor 2 (so the
 * screenshot is 768x1376, directly comparable to screen.png), diffs per pixel, and
 * reports a per-region breakdown so it's obvious *which* component is off.
 *
 * The countdown is pinned via ?freeze= so the diff is deterministic.
 *
 *   node tools/verify.mjs            # diff + byte budgets
 *   node tools/verify.mjs --open     # also write side-by-side crops per region
 */
import { launch } from './browser.mjs';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { gzipSync } from 'node:zlib';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';

const ROOT = process.cwd();
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.woff2': 'font/woff2', '.avif': 'image/avif', '.webp': 'image/webp',
  '.png': 'image/png', '.jpeg': 'image/jpeg', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
};

const REGIONS = [
  ['header', 0, 0, 768, 128],
  ['h1', 0, 128, 768, 440],
  ['card', 0, 440, 768, 1000],
  ['cta', 0, 1000, 768, 1160],
  ['timer', 0, 1160, 768, 1376],
];

const BUDGET = {
  'index.html (gzip)': 14_000,
  'assets/fonts/oswald-subset.woff2': 8_500,
  'assets/img/building-card.avif': 45_000,
  'assets/img/person.avif': 40_000,
  'assets/img/logo.avif': 6_000,
  'TOTAL (over the wire)': 110_000,
};

// ---------------------------------------------------------------- static server
const server = createServer(async (req, res) => {
  try {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p === '/') p = '/index.html';
    const file = join(ROOT, normalize(p).replace(/^(\.\.[/\\])+/, ''));
    const body = await readFile(file);
    res.writeHead(200, {
      'Content-Type': MIME[extname(file)] || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-store',
    });
    res.end(body);
  } catch {
    res.writeHead(404).end('nope');
  }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

// ---------------------------------------------------------------------- render
const browser = await launch();
const page = await browser.newPage({
  viewport: { width: 384, height: 688 },
  deviceScaleFactor: 2,
});
const requests = [];
page.on('request', r => requests.push(r.url()));

await page.goto(`${base}/index.html?freeze=00:54:22`, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(120);

const shot = PNG.sync.read(await page.screenshot({ clip: { x: 0, y: 0, width: 384, height: 688 } }));
writeFileSync('.work/render.png', PNG.sync.write(shot));

// LCP + layout shift, measured in the same run
const vitals = await page.evaluate(() => new Promise(res => {
  let lcp = null, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e; }).observe({ type: 'largest-contentful-paint', buffered: true });
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
  setTimeout(() => res({
    lcpElement: lcp ? (lcp.element ? lcp.element.tagName + (lcp.element.className ? '.' + lcp.element.className : '') : lcp.url) : 'n/a',
    lcpTime: lcp ? Math.round(lcp.startTime) : null,
    cls: +cls.toFixed(4),
  }), 400);
}));

await browser.close();
server.close();

// ------------------------------------------------------------------------ diff
const ref = PNG.sync.read(readFileSync('screen.png'));
if (ref.width !== shot.width || ref.height !== shot.height) {
  console.error(`size mismatch: render ${shot.width}x${shot.height} vs ref ${ref.width}x${ref.height}`);
  process.exit(1);
}
const diff = new PNG({ width: ref.width, height: ref.height });
const THRESH = 0.12;
const total = pixelmatch(ref.data, shot.data, diff.data, ref.width, ref.height, {
  threshold: THRESH, includeAA: false, alpha: 0.15, diffColor: [255, 0, 128],
});
writeFileSync('.work/diff.png', PNG.sync.write(diff));

const regionPct = (x0, y0, x1, y1) => {
  let bad = 0, n = 0;
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    const i = (y * ref.width + x) << 2;
    n++;
    if (diff.data[i] === 255 && diff.data[i + 1] === 0 && diff.data[i + 2] === 128) bad++;
  }
  return { pct: 100 * bad / n, bad, n };
};

const pct = 100 * total / (ref.width * ref.height);
console.log(`\nPIXEL DIFF vs screen.png  (768x1376, threshold ${THRESH})`);
console.log('='.repeat(58));
console.log(`  OVERALL   ${pct.toFixed(2)}%  (${total.toLocaleString()} px)`);
console.log('-'.repeat(58));
for (const [name, ...box] of REGIONS) {
  const r = regionPct(...box);
  const bar = '█'.repeat(Math.min(28, Math.round(r.pct * 1.4)));
  console.log(`  ${name.padEnd(8)} ${r.pct.toFixed(2).padStart(6)}%  ${bar}`);
}
console.log('-'.repeat(58));
console.log('  wrote .work/render.png and .work/diff.png');

// --------------------------------------------------------------------- budgets
console.log(`\nBYTE BUDGET`);
console.log('='.repeat(58));
let over = 0, wire = 0;
const rows = [];
for (const key of Object.keys(BUDGET)) {
  if (key.startsWith('TOTAL')) continue;
  const path = key.replace(' (gzip)', '');
  if (!existsSync(path)) { rows.push([key, 0, BUDGET[key], 'MISSING']); continue; }
  const raw = readFileSync(path);
  const n = key.includes('gzip') ? gzipSync(raw, { level: 9 }).length : raw.length;
  wire += n;
  const ok = n <= BUDGET[key];
  if (!ok) over++;
  rows.push([key, n, BUDGET[key], ok ? 'ok' : 'OVER']);
}
rows.push(['TOTAL (over the wire)', wire, BUDGET['TOTAL (over the wire)'],
  wire <= BUDGET['TOTAL (over the wire)'] ? 'ok' : 'OVER']);
for (const [k, n, b, s] of rows) {
  console.log(`  ${k.padEnd(36)} ${n.toLocaleString().padStart(8)} / ${b.toLocaleString().padStart(8)}  ${s}`);
}

console.log(`\nRUNTIME`);
console.log('='.repeat(58));
console.log(`  requests        ${requests.length}  (${requests.map(u => u.split('/').pop().split('?')[0]).join(', ')})`);
console.log(`  LCP element     ${vitals.lcpElement}`);
console.log(`  LCP time        ${vitals.lcpTime} ms`);
console.log(`  CLS             ${vitals.cls}`);

process.exitCode = 0;
