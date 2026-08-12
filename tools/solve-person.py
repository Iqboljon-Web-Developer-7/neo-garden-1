#!/usr/bin/env python3
"""
Solve the person cutout's scale + position against screen.png.

The mockup contains the *same image data* as person.avif, just scaled and placed.
So the reliable signal is appearance, not silhouette: sample points well inside the
alpha mask (where the mockup must be showing the person and nothing else) and
maximise normalised cross-correlation against the mockup's luminance. NCC is
invariant to the brightness/contrast grading applied in the composite, and needs no
model of what is behind the figure.

Prints the winning transform in 2x mockup pixels and CSS px, and writes a visual check.
"""
import math
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = dict(x0=26, y0=487, x1=742, y1=979)


def main():
    screen = Image.open(os.path.join(ROOT, "screen.png")).convert("L")
    sp = screen.load()
    SW, SH = screen.size

    person = Image.open(os.path.join(ROOT, "person.avif")).convert("RGBA")
    person = person.crop(person.getchannel("A").getbbox())
    PW, PH = person.size

    cache = {}

    def sample_set(tw):
        """interior sample points (x, y, luminance) for the figure scaled to width tw"""
        if tw in cache:
            return cache[tw]
        th = max(1, round(tw * PH / PW))
        small = person.resize((tw, th), Image.LANCZOS)
        gray = small.convert("L").load()
        alpha = small.getchannel("A")
        # erode the mask so no sample sits on an antialiased edge
        from PIL import ImageFilter
        eroded = alpha.filter(ImageFilter.MinFilter(5)).load()
        step = max(1, int(math.sqrt(tw * th / 4000)))
        pts = []
        for y in range(0, th, step):
            for x in range(0, tw, step):
                if eroded[x, y] > 250:
                    pts.append((x, y, gray[x, y]))
        cache[tw] = (pts, th)
        return cache[tw]

    def ncc(tw, dx, dy):
        pts, th = sample_set(tw)
        a = []
        b = []
        for px_, py_, v in pts:
            X, Y = dx + px_, dy + py_
            if 0 <= X < SW and 0 <= Y < SH:
                a.append(v)
                b.append(sp[X, Y])
        n = len(a)
        if n < 0.5 * len(pts) or n < 200:
            return -1
        ma = sum(a) / n
        mb = sum(b) / n
        num = sa = sb = 0.0
        for i in range(n):
            da = a[i] - ma
            db = b[i] - mb
            num += da * db
            sa += da * da
            sb += db * db
        if sa <= 0 or sb <= 0:
            return -1
        return num / math.sqrt(sa * sb)

    best = None
    for tw in range(300, 781, 20):
        for dx in range(340, 601, 12):
            for dy in range(400, 521, 10):
                s = ncc(tw, dx, dy)
                if best is None or s > best[0]:
                    best = (s, tw, dx, dy)
    for rad, stepw, stepo in ((18, 6, 4), (6, 2, 2), (2, 1, 1)):
        _, tw0, dx0, dy0 = best
        for tw in range(tw0 - rad, tw0 + rad + 1, stepw):
            for dx in range(dx0 - rad, dx0 + rad + 1, stepo):
                for dy in range(dy0 - rad, dy0 + rad + 1, stepo):
                    s = ncc(tw, dx, dy)
                    if s > best[0]:
                        best = (s, tw, dx, dy)

    s, tw, dx, dy = best
    th = sample_set(tw)[1]
    print(f"NCC={s:.4f}   size={tw}x{th}@2x   screen offset=({dx},{dy})")
    print(f"  right edge {dx+tw} (card right border 742)")
    print(f"  bottom     {dy+th} (card bottom 979)")
    print(f"  head top   {dy} (card top 486)")
    print()
    print("CSS, relative to the card interior box (all /2):")
    print(f"  width {tw/2:.1f}  height {th/2:.1f}   left {(dx-CARD['x0'])/2:.1f}  top {(dy-CARD['y0'])/2:.1f}")

    rgb = Image.open(os.path.join(ROOT, "screen.png")).convert("RGB")
    sc = person.resize((tw, th), Image.LANCZOS)
    tint = Image.new("RGBA", sc.size, (255, 0, 128, 0))
    tint.putalpha(Image.eval(sc.getchannel("A"), lambda v: int(v * 0.45)))
    rgb.paste(tint, (dx, dy), tint)
    rgb.crop((360, 420, 768, 1000)).save(os.path.join(ROOT, ".work", "person-fit.png"))
    print("\nwrote .work/person-fit.png (magenta = solved placement)")

    with open(os.path.join(ROOT, ".work", "person-fit.txt"), "w") as f:
        f.write(f"{tw} {th} {dx} {dy}\n")


if __name__ == "__main__":
    main()
