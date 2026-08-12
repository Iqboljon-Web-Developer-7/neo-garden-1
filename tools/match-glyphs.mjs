/**
 * Definitive font check: render candidate faces and pixel-overlap them against the
 * actual glyph bitmap lifted out of screen.png.
 *
 * Scored by IoU (intersection over union) of the thresholded ink masks over a grid
 * of font-size / letter-spacing, aligned by ink bounding box. A ratio match can be
 * coincidental; an outline match cannot.
 *
 *   node tools/match-glyphs.mjs <blockName>
 *
 * Blocks are defined below with the region in screen.png (2x coords), the literal
 * string, and whether the ink is light-on-dark or dark-on-light.
 */
import { launch } from './browser.mjs';
import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { PNG } from 'pngjs';

const CACHE = '.work/fonts';
mkdirSync('.work', { recursive: true });

const BLOCKS = {
  h1:      { box: [55, 145, 715, 235],   text: 'Olmaliq shahar markazidan', invert: false, sizes: [50, 78] },
  cta:     { box: [118, 1048, 628, 1122], text: 'TAQDIMOTDA QATNASHISH',    invert: true,  sizes: [34, 60] },
  bullet:  { box: [92, 672, 372, 722],    text: 'Boshlang‘ich to‘lovsiz', invert: false, sizes: [24, 44] },
  price:   { box: [50, 833, 560, 888],    text: 'Oyiga 3 mln 400',          invert: false, sizes: [32, 56] },
  digits:  { box: [243, 1258, 322, 1314], text: '00',                       invert: false, sizes: [40, 72] },
  caption: { box: [88, 1203, 500, 1238],  text: 'Ro’yxatdan o’tish uchun', invert: false, sizes: [16, 34] },
  badge:   { box: [600, 44, 745, 76],     text: '29-IYUN',                  invert: false, sizes: [18, 40] },
};

const CANDIDATES = [
  ['Oswald', 400], ['Oswald', 500], ['Oswald', 600], ['Oswald', 700],
  ['Saira Condensed', 800], ['Khand', 700], ['Barlow Condensed', 800],
  ['Roboto Condensed', 700], ['Big Shoulders Display', 900], ['Teko', 600],
];

const name = process.argv[2] || 'h1';
const blk = BLOCKS[name];
if (!blk) { console.error('unknown block:', name, '\nknown:', Object.keys(BLOCKS).join(', ')); process.exit(1); }
const [rx0, ry0, rx1, ry1] = blk.box;

// ---- reference mask from screen.png -----------------------------------------
const src = PNG.sync.read(readFileSync('screen.png'));
const W = rx1 - rx0, H = ry1 - ry0;
const ref = new Uint8Array(W * H);
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const i = ((ry0 + y) * src.width + (rx0 + x)) << 2;
  const lum = (src.data[i] + src.data[i + 1] + src.data[i + 2]) / 3;
  ref[y * W + x] = (blk.invert ? lum < 110 : lum > 128) ? 1 : 0;
}

const bbox = (m) => {
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (m[y * W + x]) {
    if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  return { x0, y0, x1, y1 };
};
const rb = bbox(ref);
console.error(`[${name}] ref ink box ${rb.x1 - rb.x0 + 1}x${rb.y1 - rb.y0 + 1} in ${W}x${H} region`);

const faces = CANDIDATES.map(([family, weight]) => {
  const file = join(CACHE, `${family.replace(/\s+/g, '_')}-${weight}.woff2`);
  return existsSync(file) ? { family, weight, b64: readFileSync(file).toString('base64') } : null;
}).filter(Boolean);

const b = await launch();
const page = await b.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });

const scored = [];
for (const face of faces) {
  const alias = `T${face.family.replace(/\W/g, '')}${face.weight}`;
  await page.setContent(`<!doctype html><meta charset="utf-8"><style>
    html,body{margin:0;padding:0;background:#000;width:${W}px;height:${H}px;overflow:hidden}
    #t{position:absolute;left:0;top:0;color:#fff;white-space:pre;font-family:"${alias}";
       font-weight:${face.weight};line-height:1;-webkit-font-smoothing:antialiased}
  </style><div id="t">${blk.text}</div>`);
  await page.evaluate(async ({ alias, b64 }) => {
    const f = new FontFace(alias, Uint8Array.from(atob(b64), c => c.charCodeAt(0)));
    await f.load(); document.fonts.add(f); await document.fonts.ready;
  }, { alias, b64: face.b64 });

  const trial = async (size, ls) => {
    await page.evaluate(({ size, ls }) => {
      const t = document.getElementById('t');
      t.style.fontSize = size + 'px'; t.style.letterSpacing = ls.toFixed(2) + 'px';
    }, { size, ls });
    const img = PNG.sync.read(await page.screenshot({ type: 'png' }));
    const cand = new Uint8Array(W * H);
    for (let i = 0, p = 0; i < W * H; i++, p += 4) {
      cand[i] = (img.data[p] + img.data[p + 1] + img.data[p + 2]) / 3 > 128 ? 1 : 0;
    }
    if (!cand.some(Boolean)) return null;
    const cb = bbox(cand);
    const dx = rb.x0 - cb.x0, dy = rb.y0 - cb.y0;
    let inter = 0, union = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const r = ref[y * W + x];
      const sx = x - dx, sy = y - dy;
      const c = (sx >= 0 && sx < W && sy >= 0 && sy < H) ? cand[sy * W + sx] : 0;
      if (r || c) union++;
      if (r && c) inter++;
    }
    return { iou: inter / union, size, ls, inkW: cb.x1 - cb.x0 + 1, inkH: cb.y1 - cb.y0 + 1 };
  };

  // coarse sweep, then refine around the winner — ~7x fewer screenshots than a full grid
  let best = null;
  const keep = (r) => { if (r && (!best || r.iou > best.iou)) best = r; };
  for (let size = blk.sizes[0]; size <= blk.sizes[1]; size += 2)
    for (let ls = -2.0; ls <= 3.01; ls += 0.5) keep(await trial(size, ls));
  const c = best;
  for (let size = c.size - 1; size <= c.size + 1; size++)
    for (let ls = c.ls - 0.4; ls <= c.ls + 0.41; ls += 0.1) keep(await trial(size, +ls.toFixed(2)));
  scored.push({ ...face, ...best, b64: undefined });
}
await b.close();

scored.sort((a, b) => b.iou - a.iou);
console.log(`\n[${name}] "${blk.text}"`);
console.log('='.repeat(74));
console.log('family / weight'.padEnd(30), 'IoU'.padStart(7), 'size@2x'.padStart(8), 'CSSpx'.padStart(7), 'ls@2x'.padStart(7));
console.log('-'.repeat(74));
for (const s of scored) {
  console.log(`${s.family} ${s.weight}`.padEnd(30),
    (s.iou * 100).toFixed(1).padStart(6) + '%',
    String(s.size).padStart(8), (s.size / 2).toFixed(1).padStart(7), s.ls.toFixed(2).padStart(7));
}
writeFileSync(`.work/match-${name}.json`, JSON.stringify(scored, null, 2));
