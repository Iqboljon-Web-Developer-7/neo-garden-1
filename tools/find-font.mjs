/**
 * Font identification pass.
 *
 * Downloads candidate Google Fonts woff2 binaries, injects them into headless
 * Chromium as FontFace objects (so a silent canvas fallback is impossible), and
 * ranks them against glyph metrics extracted from screen.png.
 *
 * Measured targets (word "Olmaliq" / line 1 of the H1, at 2x):
 *   cap height 48px, x-height 34px, O ink box 29x48,
 *   "Olmaliq" ink width 171px, full line-1 ink width 638px
 *
 * Ratios are scale-free so they hold at any font-size. Because a design may use
 * tracking, each candidate is also scored with a best-fit letter-spacing solved
 * from the two width targets; `lsErr` is the residual after that fit.
 */
import { launch } from './browser.mjs';
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const CACHE = '.work/fonts';
mkdirSync(CACHE, { recursive: true });

const UA_MODERN = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

const TARGET = {
  oAspect: 29 / 48,        // O ink width / O ink height
  xOverCap: 34 / 48,       // x-height / cap height
  wordOverCap: 171 / 48,   // "Olmaliq" ink width / cap height
  lineOverCap: 638 / 48,   // full line-1 ink width / cap height
};
const WORD_CHARS = 7, LINE_CHARS = 25;
const LINE1 = 'Olmaliq shahar markazidan';

const CANDIDATES = [
  ['Anton', 400], ['Antonio', 600], ['Antonio', 700],
  ['Oswald', 600], ['Oswald', 700],
  ['Barlow Condensed', 800], ['Barlow Condensed', 900],
  ['Barlow Semi Condensed', 800],
  ['Fira Sans Extra Condensed', 800], ['Fira Sans Extra Condensed', 900],
  ['Fira Sans Condensed', 800], ['Fira Sans Condensed', 900],
  ['Saira Condensed', 800], ['Saira Condensed', 900],
  ['Saira Extra Condensed', 800], ['Saira Extra Condensed', 900],
  ['Saira Semi Condensed', 900],
  ['Encode Sans Condensed', 800], ['Encode Sans Condensed', 900],
  ['Archivo Narrow', 700],
  ['Roboto Condensed', 700], ['Roboto Condensed', 800], ['Roboto Condensed', 900],
  ['PT Sans Narrow', 700],
  ['Big Shoulders Display', 800], ['Big Shoulders Display', 900],
  ['Alumni Sans', 800], ['Alumni Sans', 900],
  ['Teko', 600], ['Teko', 700], ['Khand', 700], ['Rajdhani', 700],
  ['Asap Condensed', 700], ['Cabin Condensed', 700],
  ['Ubuntu Condensed', 400], ['Yanone Kaffeesatz', 700],
  ['Pathway Gothic One', 400], ['Economica', 700],
  ['Archivo', 900], ['Inter Tight', 900], ['Montserrat', 900],
  ['Roboto', 900], ['Noto Sans Display', 900], ['Chivo', 900],
  ['Mulish', 900], ['Manrope', 800], ['Figtree', 900], ['Nunito Sans', 900],
  ['League Spartan', 900], ['Bebas Neue', 400],
];

async function fetchFace(family, weight) {
  const slug = `${family.replace(/\s+/g, '_')}-${weight}.woff2`;
  const file = join(CACHE, slug);
  if (existsSync(file)) return readFileSync(file);

  const url = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family).replace(/%20/g, '+')}:wght@${weight}&display=block`;
  const css = await (await fetch(url, { headers: { 'User-Agent': UA_MODERN } })).text();
  // prefer the latin-ext / latin block; take the last woff2 (latin is last in GF output)
  const urls = [...css.matchAll(/url\((https:[^)]+\.woff2)\)/g)].map(m => m[1]);
  if (!urls.length) throw new Error('no woff2 in CSS');
  const buf = Buffer.from(await (await fetch(urls.at(-1))).arrayBuffer());
  writeFileSync(file, buf);
  return buf;
}

// download (cached) in parallel
const faces = [];
await Promise.all(CANDIDATES.map(async ([family, weight]) => {
  try {
    const buf = await fetchFace(family, weight);
    faces.push({ family, weight, b64: buf.toString('base64') });
  } catch (e) {
    console.error(`  ! ${family} ${weight}: ${e.message}`);
  }
}));
console.error(`loaded ${faces.length}/${CANDIDATES.length} faces\n`);

const b = await launch();
const page = await b.newPage();
await page.goto('about:blank');

const results = await page.evaluate(async ({ faces, LINE1 }) => {
  const ctx = document.createElement('canvas').getContext('2d');
  const SIZE = 400;
  const out = [];

  for (const { family, weight, b64 } of faces) {
    const alias = `T_${family.replace(/\W/g, '')}_${weight}`;
    const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    let face;
    try {
      face = new FontFace(alias, bin);
      await face.load();
      document.fonts.add(face);
    } catch (e) { out.push({ family, weight, error: 'load:' + e.message }); continue; }

    const spec = `${SIZE}px "${alias}"`;
    const ink = (t) => {
      ctx.font = spec;
      const m = ctx.measureText(t);
      return {
        w: m.actualBoundingBoxLeft + m.actualBoundingBoxRight,
        h: m.actualBoundingBoxAscent + m.actualBoundingBoxDescent,
        asc: m.actualBoundingBoxAscent,
      };
    };
    const cap = ink('H').asc, xh = ink('x').asc, O = ink('O');
    const word = ink('Olmaliq').w, line = ink(LINE1).w;
    if (!cap || !O.h) { out.push({ family, weight, error: 'no-metrics' }); continue; }
    out.push({
      family, weight,
      oAspect: O.w / O.h, xOverCap: xh / cap,
      wordOverCap: word / cap, lineOverCap: line / cap,
    });
  }
  return out;
}, { faces, LINE1 });

await b.close();

const W = { oAspect: 1.0, xOverCap: 1.0, wordOverCap: 1.4, lineOverCap: 1.4 };
const ok = results.filter(r => !r.error).map(r => {
  let err = 0, tot = 0;
  for (const k of Object.keys(TARGET)) {
    err += W[k] * Math.abs(r[k] - TARGET[k]) / TARGET[k];
    tot += W[k];
  }
  // best-fit letter-spacing (in units of cap height) from the two width targets:
  //   word: r.word + (WORD_CHARS-1)*L = target.word
  //   line: r.line + (LINE_CHARS-1)*L = target.line
  const dW = TARGET.wordOverCap - r.wordOverCap, dL = TARGET.lineOverCap - r.lineOverCap;
  const nW = WORD_CHARS - 1, nL = LINE_CHARS - 1;
  const L = (dW * nW + dL * nL) / (nW * nW + nL * nL);   // least squares
  const resid = (Math.abs(dW - nW * L) / TARGET.wordOverCap + Math.abs(dL - nL * L) / TARGET.lineOverCap) / 2;
  return { ...r, score: err / tot, ls: L, lsErr: resid };
}).sort((a, b) => (a.lsErr + Math.abs(a.oAspect - TARGET.oAspect) / TARGET.oAspect) - (b.lsErr + Math.abs(b.oAspect - TARGET.oAspect) / TARGET.oAspect));

const f = (n, d = 3) => n.toFixed(d).padStart(7);
console.log('TARGET'.padEnd(31), f(TARGET.oAspect), f(TARGET.xOverCap), f(TARGET.wordOverCap), f(TARGET.lineOverCap));
console.log('='.repeat(96));
console.log('family / weight'.padEnd(31), 'O-asp'.padStart(7), 'x/cap'.padStart(7), 'word'.padStart(7), 'line'.padStart(7), '  raw%', ' fit-ls', ' resid%');
console.log('-'.repeat(96));
for (const r of ok.slice(0, 20)) {
  console.log(
    `${r.family} ${r.weight}`.padEnd(31),
    f(r.oAspect), f(r.xOverCap), f(r.wordOverCap), f(r.lineOverCap),
    (r.score * 100).toFixed(1).padStart(6) + '%',
    r.ls.toFixed(4).padStart(7),
    (r.lsErr * 100).toFixed(2).padStart(6) + '%',
  );
}
const bad = results.filter(r => r.error);
if (bad.length) console.log('\nskipped:', bad.map(b => `${b.family} ${b.weight} (${b.error})`).join(', '));
