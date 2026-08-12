#!/usr/bin/env python3
"""Side-by-side region crops: reference (top) vs render (bottom), with a red rule
between them. Much faster to act on than fragile automated probes once the layout
is close.

    python3 tools/sbs.py header|h1|card|cta|timer|all
"""
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = {
    "header": (0, 0, 768, 130),
    "h1":     (0, 130, 768, 440),
    "card":   (0, 430, 768, 1000),
    "cta":    (0, 995, 768, 1165),
    "timer":  (0, 1160, 768, 1376),
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    ref = Image.open(os.path.join(ROOT, "screen.png")).convert("RGB")
    got = Image.open(os.path.join(ROOT, ".work", "render.png")).convert("RGB")
    names = list(R) if which == "all" else [which]
    for n in names:
        box = R[n]
        a, b = ref.crop(box), got.crop(box)
        w, h = a.size
        out = Image.new("RGB", (w, h * 2 + 4), (255, 0, 0))
        out.paste(a, (0, 0))
        out.paste(b, (0, h + 4))
        p = os.path.join(ROOT, ".work", f"sbs-{n}.png")
        out.save(p)
        print("wrote", os.path.relpath(p, ROOT), f"({w}x{h} each; ref top, render bottom)")


if __name__ == "__main__":
    main()
