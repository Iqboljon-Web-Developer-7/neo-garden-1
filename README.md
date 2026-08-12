# Neo Garden — landing page

Pixel-matched build of `screen.png` as hand-written HTML/CSS/JS. No framework, no
runtime build step. The deliverable is **`index.html`** plus `assets/`.

```
open index.html                 # it just works, no server needed
python3 -m http.server 8000     # or serve it
```

## Performance

| | measured | budget |
|---|---|---|
| HTTP requests | **5** | — |
| index.html (gzipped) | 6.8 KB | 14 KB |
| Font subset (woff2) | 8.2 KB | 8.5 KB |
| building-card.avif | 7.5 KB | 45 KB |
| person.avif | 14.0 KB | 40 KB |
| logo.avif | 4.5 KB | 6 KB |
| **Total over the wire** | **41.1 KB** | 110 KB |
| Render-blocking requests | **0** | 0 |
| CLS | **0** | 0 |
| LCP | ~70–100 ms (local) | — |

How it gets there:

- **All CSS inline** in `<head>` (~8 KB). An external stylesheet would cost a round
  trip for no cache benefit on a one-page site. The doc gzips to 6.8 KB, well inside the
  initial congestion window, so first paint costs a single round trip.
- **Self-hosted, subsetted font.** The page's character set is fixed, so Oswald is cut
  to the 61 glyphs actually used and the `wght` axis clipped to 500–700 (the only
  weights the page uses) — 8.2 KB instead of ~180 KB. Preloaded, `font-display:swap`,
  with a metric-matched `@font-face` fallback (`size-adjust`/`ascent-override`) so the
  swap causes no shift. No Google Fonts request at runtime.
- **AVIF with WebP fallback** via `<picture>`, each image encoded at exactly 2× its
  display size. Explicit `width`/`height` on every `<img>` ⇒ CLS 0.
- **Clock glyph inlined as a data URI** (2.2 KB) — above the fold, so it trades a
  little HTML for a saved round trip. The logo needs an alpha channel and costs ~20 KB
  inlined as WebP, so it ships as a cacheable AVIF file (4.5 KB) instead.
- **Background texture is pure CSS** (layered gradients + a dot pattern). Zero bytes.
- **No third parties.** No analytics, no font CDN, no icon library ⇒ no extra DNS or TLS.
- JS is ~1 KB inline and non-blocking; nothing runs before first paint.

## How it matches the mockup

`screen.png` is a 2× capture of a 384 px-wide viewport (768×1376 = 2 × 384×688).
Every length in the CSS is written in **mockup CSS px** and multiplied by `--u`:

```css
--u: calc(min(100vw, 430px) / 384);   /* one design pixel */
```

At a 384 px viewport `--u` is exactly `1px` and the render is 1:1 with the mockup; on
wider screens the whole composition scales uniformly and caps at a 430 px column,
centred on the dark page background (mobile-only, per the brief).

*Tradeoff worth knowing:* a viewport-locked scale ignores the browser's font-size
preference. That's the standard cost of a pixel-locked marketing page — pinch-zoom
still works. Change `--u` to a fixed `1px` if you'd rather have that back.

### Typeface

The headline face is **Oswald**, identified by rendering candidate fonts and
pixel-overlapping them against the real glyph bitmap in `screen.png` — not by eye.
Oswald 700 scored **86.1 % IoU** on the H1 at 58 px (2×) with zero tracking; the
runner-up (Saira Condensed) managed 73 %. Rerun with `node tools/match-glyphs.mjs h1`.

## Current pixel diff

`node tools/verify.mjs` — renders at 384×688 @2× and diffs against `screen.png`.

| region | diff | meaningful? |
|---|---|---|
| header | 5.9 % | yes |
| h1 | 7.0 % | yes |
| cta | 9.3 % | yes |
| timer | 12.9 % | **no** — shows MM:SS, mockup shows HH:MM:SS |
| card | 32.1 % | **no** — different building *and* different person |
| **overall** | **17.8 %** | |

Only the header, h1 and CTA numbers still measure fidelity, and they're at the floor:
what's left there is text antialiasing, which never reaches zero on a thresholded diff.

The card and timer no longer match the mockup **by request** — the card carries your
real `building.jpeg` and the supplied person photo, and the countdown dropped its hours
column. Their diff percentages measure those decisions, not build quality.

## Known, deliberate deviations

1. **The person is a different photo.** `person.avif` (supplied) shows the man in a
   navy *polo shirt, arms down*. `screen.png` shows the same man in a *suit jacket and
   white dress shirt, hands clasped*. You chose to keep the supplied asset, so the card
   cannot pixel-match there. Dropping the correct suit-jacket cutout into
   `person.avif` and re-running `tools/make-assets.py` would close it.
2. **The card shows `building.jpeg`, graded to night.** You asked for your real render
   instead of the mockup's. It's a daylight photo of a *different* building, so the card
   cannot match `screen.png` there. Two things were needed to make it work in a dark
   composition — see *Note on the card image* below.
   To go back to the mockup's building, restore `build_plate()` to crop from
   `screen.png` (it's in git-less history, but the crop was `CARD` x `PLATE_H`).
3. **The page ends at the countdown.** `screen.png` is cut off mid-box at y=1376; you
   chose to close the dashed box cleanly and stop there. Conveniently the design is
   exactly 688 CSS px tall, so the box closes right at the fold.
4. **The countdown shows minutes and seconds only.** You asked to drop the hours
   column, so the mockup's `SOAT` group is gone. Minutes accumulate rather than rolling
   into a hidden hours field, so a 90-minute deadline reads `90:00`, not `30:00`.
5. **Logo and clock are images, not SVG.** They're bespoke artwork that exists only
   inside `screen.png`; a hand-drawn SVG never converged (the header diff was 10.5 %
   with my traced version, 5.9 % with the real artwork). A logo is an asset, not text,
   so this is also the more conventional representation. It carries `alt="Neo Garden"`,
   and both are keyed to transparency so no background rectangle shows.

## Things you'll probably want to change

| what | where |
|---|---|
| **CTA destination** | `index.html`, `<a class="cta" href="#">` — point it at a Telegram bot, `tel:`, or a form. It's a placeholder; the mockup gave no target. |
| **Countdown length** | `index.html`, `DURATION_SECONDS = 120` (one line). Currently a plain 2-minute timer that starts on load. |
| Make the timer survive reloads | store `endsAt` in `localStorage` instead of recomputing it — two lines, in the same IIFE. |

The countdown renders from an absolute deadline rather than decrementing a counter, so
it can't drift when the tab is backgrounded, and it only touches the DOM when a digit
actually changes.

The dashed frame around it is an SVG rounded rect, not a CSS border. `border:1px dashed`
can't hit the measured 2.5/2 dash pitch, and drawing it as four gradient strips (the
first approach) leaves all four corners blank — `border-radius` clips the strips flat
where the arcs are. A stroked `<rect rx>` draws the dashes continuously around them.

## Tools

All regenerable; none of it ships.

| command | what it does |
|---|---|
| `python3 tools/make-assets.py` | Builds the card image from `building.jpeg` (night grade + composite) and the person cutout, and encodes AVIF+WebP. |
| `python3 tools/make-icons.py` | Extracts the logo lockup + clock glyph from `screen.png`, keys them to transparency, writes `assets/img/logo.*` and inlines the clock. **Re-run after editing the header markup.** |
| `python3 tools/subset-font.py` | Downloads Oswald and subsets it to the glyphs `index.html` actually uses. |
| `node tools/verify.mjs` | Pixel diff + byte budgets + LCP/CLS. The gate. Writes `.work/render.png` and `.work/diff.png`. |
| `python3 tools/compare.py` | Landmark table: ref vs render vs delta, in 2× px. |
| `python3 tools/sbs.py <region>` | Side-by-side crop, reference above render. |
| `node tools/match-glyphs.mjs <block>` | Font identification by glyph-outline IoU. |

Requires Python with Pillow + fontTools, and Node with the three dev deps in
`package.json`. Playwright uses the Chromium already cached on this machine.

### Note on the card image

`building.jpeg` is a 3:4 portrait of a tall tower; the card is a 2.17:1 strip. Two
problems had to be solved, both in `tools/make-assets.py`:

**Framing.** Cropping a band out of the portrait shows four floors and reads as a
low-rise — it loses the building. Instead the whole tower is scaled to the plate height
and composited onto a backdrop made from a heavily blurred, stretched copy of the
source. Deriving the backdrop from the source rather than inventing a gradient means
the sky and ground colours match exactly, so the seam doesn't show. `TOWER_X` biases it
left of centre because the person covers the plate from x≈444.

**Grade.** `night_grade()` drops a per-channel gain and gamma over the image to darken
and cool it, then adds a warm pass back into bright pixels. The sky has to be excluded
from that warm pass explicitly (it's masked by blue-minus-red): it's the brightest
thing in the frame, so a plain luminance threshold turns it into a sunset instead of a
night sky. `floor_fade()` then darkens the lower plate so the white bullets and gold
price keep their contrast.

Honest limitation: a daylight render has *unlit* windows, and no global grade can turn
them on. The result reads as blue hour rather than the mockup's lit-at-night tower.
Getting actual lit windows needs either a night render of the building or per-window
compositing. All the constants (`TOWER_BOX`, `TOWER_X`, `TOWER_H`, `NIGHT_GAIN`,
`GLOW_COLOR`, `FADE_START`) are at the top of the file if you want to retune it.

### Note on the person

The person's placement (`336×536` at `(444,444)` in 2× coords) is set from three
measured landmarks that agree: the head box, the silhouette width at y=740, and the
figure's bottom meeting the card's bottom edge. Automated fits were tried and rejected
— an RGB-composite fit needs a model of the backdrop (which above the card is page
background, not the plate), and a silhouette-edge fit locks onto the building facade's
strong vertical lines.
# neo-garden-1
