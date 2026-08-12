#!/usr/bin/env python3
"""
Extract the two pieces of bespoke artwork that exist only inside screen.png — the
NEO GARDEN logo lockup and the badge's clock glyph — and wire them into index.html.

A logo is an asset, not text, so an image is the correct representation; hand-drawing
it as SVG never converges on the original.

Both are keyed to transparency rather than shipped opaque: an opaque crop leaves a
visible rectangle, because the mockup's background carries a faint building silhouette
the CSS gradient doesn't reproduce. The clock is a disc, so it gets a circular mask;
the logo's alpha is recovered from luminance and its colour unmixed.

The clock is small enough to inline as a data URI (2.2KB). The logo is not once it
carries alpha, so it ships as a cacheable file.

    python3 tools/make-icons.py
"""
import base64
import io
import os
import re

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# measured ink boxes in screen.png (2x), padded by 1px
LOGO = (24, 35, 244, 106)      # mark + "NEO GARDEN" wordmark
CLOCK = (529, 41, 593, 105)    # the white clock disc


def to_datauri(img, fmt="webp", **kw):
    buf = io.BytesIO()
    img.save(buf, fmt.upper(), **kw)
    b = buf.getvalue()
    return f"data:image/{fmt};base64," + base64.b64encode(b).decode(), len(b)


def main():
    screen = Image.open(os.path.join(ROOT, "screen.png")).convert("RGB")

    # Key the logo's dark backdrop out to transparency. Shipping it opaque leaves a
    # visible rectangle, because the mockup's background there carries a faint
    # building silhouette the CSS gradient doesn't reproduce. The mark is gold on
    # near-black, so alpha can be recovered from luminance and the colour unmixed.
    src = screen.crop(LOGO).convert("RGB")
    bg = (10, 21, 38)
    lum_bg = sum(bg) / 3
    lum_fg = 210.0                       # luminance of a solid gold stroke
    out = Image.new("RGBA", src.size)
    sp, op = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = sp[x, y]
            a = (sum((r, g, b)) / 3 - lum_bg) / (lum_fg - lum_bg)
            a = 0.0 if a < 0 else (1.0 if a > 1 else a)
            if a <= 0.004:
                op[x, y] = (0, 0, 0, 0)
                continue
            # unmix: observed = fg*a + bg*(1-a)
            fg = tuple(
                min(255, max(0, int(round((c - bgc * (1 - a)) / a))))
                for c, bgc in zip((r, g, b), bg)
            )
            op[x, y] = (*fg, int(round(a * 255)))
    logo = out
    # The logo is too big to inline once it carries an alpha channel (~20KB as WebP),
    # so it ships as a real cacheable file instead. AVIF q40 holds it at ~4.5KB; the
    # WebP is the fallback for browsers without AVIF.
    imgdir = os.path.join(ROOT, "assets", "img")
    os.makedirs(imgdir, exist_ok=True)
    logo.save(os.path.join(imgdir, "logo.avif"), quality=40, speed=1)
    logo.save(os.path.join(imgdir, "logo.webp"), quality=72, method=6)
    n1 = os.path.getsize(os.path.join(imgdir, "logo.avif"))

    clock = screen.crop(CLOCK).convert("RGBA")
    mask = Image.new("L", clock.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, clock.width - 1, clock.height - 1), fill=255)
    clock.putalpha(mask)
    clock_uri, n2 = to_datauri(clock, "webp", quality=92, method=6, exact=True)

    print(f"logo  {logo.size[0]}x{logo.size[1]}  {n1:,} B (assets/img/logo.avif)")
    print(f"clock {clock.size[0]}x{clock.size[1]}  {n2:,} B raw -> {len(clock_uri):,} B base64")

    p = os.path.join(ROOT, "index.html")
    s = open(p, encoding="utf-8").read()

    # replace the hand-drawn logo <svg>…</svg> + <b>…</b> with one <img>
    logo_img = ('<picture>'
                f'<source srcset="assets/img/logo.avif" type="image/avif">'
                f'<img class="logo__img" src="assets/img/logo.webp" '
                f'width="{logo.size[0]}" height="{logo.size[1]}" alt="Neo Garden" '
                f'fetchpriority="high" decoding="async">'
                '</picture>')
    s, n = re.subn(r'(?:<picture>)?(?:<svg viewBox="0 0 33 34\.5".*?</svg>\s*<b>NEO<br>GARDEN</b>'
                   r'|<source srcset="assets/img/logo\.avif".*?</picture>)',
                   logo_img, s, count=1, flags=re.S)
    print("logo swapped:", bool(n))

    clock_img = (f'<img class="badge__clock" src="{clock_uri}" '
                 f'width="{clock.size[0]}" height="{clock.size[1]}" alt="" decoding="async">')
    s, n = re.subn(r'<svg viewBox="0 0 31 31".*?</svg>', clock_img, s, count=1, flags=re.S)
    print("clock swapped:", bool(n))

    open(p, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main()
