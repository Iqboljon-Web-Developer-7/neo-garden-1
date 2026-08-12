#!/usr/bin/env python3
"""
Landmark comparator: measures the same features in screen.png and .work/render.png
and prints ref / render / delta so the diff loop converges numerically instead of
by eye.

    python3 tools/compare.py
"""
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    im = Image.open(p).convert("RGB")
    return im, im.load(), im.size


def bands(px, W, x0, x1, y0, y1, thr, gap=3):
    """vertical runs of rows containing ink brighter than thr"""
    out, run = [], None
    for y in range(y0, y1):
        hit = any(sum(px[x, y]) / 3 > thr for x in range(x0, x1, 2))
        if hit and run is None:
            run = y
        elif not hit and run is not None:
            if y - run > gap:
                out.append((run, y - 1))
            run = None
    if run is not None:
        out.append((run, y1 - 1))
    return out


def xext(px, x0, x1, y0, y1, thr):
    xs = [x for x in range(x0, x1) if any(sum(px[x, y]) / 3 > thr for y in range(y0, y1))]
    return (min(xs), max(xs)) if xs else None


def hedge(px, y, x0, x1, thr):
    """first/last column on row y brighter than thr"""
    xs = [x for x in range(x0, x1) if sum(px[x, y]) / 3 > thr]
    return (min(xs), max(xs)) if xs else None


def vedge(px, x, y0, y1, thr):
    ys = [y for y in range(y0, y1) if sum(px[x, y]) / 3 > thr]
    return (min(ys), max(ys)) if ys else None


def measure(px, W, H):
    m = {}
    # H1: four text lines
    b = bands(px, W, 40, 730, 120, 470, 165)
    for i, (a, z) in enumerate(b[:4]):
        m[f"h1 L{i+1} top"] = a
        m[f"h1 L{i+1} bot"] = z
    e = xext(px, 40, 730, 150, 230, 165)
    if e:
        m["h1 L1 x0"], m["h1 L1 x1"] = e
    e = xext(px, 40, 730, 355, 425, 165)
    if e:
        m["h1 L4 x0"], m["h1 L4 x1"] = e

    # header: logo mark and badge
    e = xext(px, 10, 110, 25, 115, 55)
    if e:
        m["logo x0"], m["logo x1"] = e
    v = vedge(px, 40, 20, 120, 55)
    if v:
        m["logo y0"], m["logo y1"] = v
    e = xext(px, 480, 760, 28, 118, 55)
    if e:
        m["badge x0"], m["badge x1"] = e
    v = vedge(px, 730, 20, 130, 55)
    if v:
        m["badge y0"], m["badge y1"] = v

    # card border box, probed in the left gutter well below the media plate
    v = vedge(px, 40, 430, 1010, 52)
    if v:
        m["card y0"], m["card y1"] = v
    e = hedge(px, 700, 10, 760, 52)
    if e:
        m["card x0"], m["card x1"] = e

    # bullets: gold dots
    for i, y in enumerate(range(660, 830, 1)):
        pass
    dots = bands(px, W, 55, 80, 650, 840, 90)
    for i, (a, z) in enumerate(dots[:3]):
        m[f"dot{i+1} top"] = a
    e = xext(px, 50, 90, 660, 720, 90)
    if e:
        m["dot x0"], m["dot x1"] = e
    e = xext(px, 90, 400, 670, 720, 150)
    if e:
        m["bullet1 x0"], m["bullet1 x1"] = e

    # price
    pb = bands(px, W, 50, 420, 820, 980, 120)
    for i, (a, z) in enumerate(pb[:2]):
        m[f"price L{i+1} top"] = a
        m[f"price L{i+1} bot"] = z
    e = xext(px, 40, 620, 830, 900, 120)
    if e:
        m["price L1 x0"], m["price L1 x1"] = e

    # CTA
    v = vedge(px, 384, 985, 1170, 120)
    if v:
        m["cta y0"], m["cta y1"] = v
    e = hedge(px, 1080, 5, 763, 120)
    if e:
        m["cta x0"], m["cta x1"] = e
    e = xext(px, 100, 660, 1050, 1120, -1)  # dark text on gold: use inverse below
    dark = [x for x in range(100, 680) if any(sum(px[x, y]) / 3 < 95 for y in range(1050, 1120))]
    if dark:
        m["cta text x0"], m["cta text x1"] = min(dark), max(dark)
    darky = [y for y in range(1030, 1140) if any(sum(px[x, y]) / 3 < 95 for x in range(120, 640))]
    if darky:
        m["cta text y0"], m["cta text y1"] = min(darky), max(darky)

    # timer
    v = vedge(px, 26, 1150, H, 70)
    if v:
        m["timer y0"] = v[0]
    cap = bands(px, W, 90, 690, 1185, 1250, 150)
    if cap:
        m["cap top"], m["cap bot"] = cap[0]
    e = xext(px, 60, 720, 1195, 1245, 150)
    if e:
        m["cap x0"], m["cap x1"] = e
    dg = bands(px, W, 200, 570, 1240, 1330, 150)
    if dg:
        m["digit top"], m["digit bot"] = dg[0]
    e = xext(px, 200, 580, 1255, 1320, 150)
    if e:
        m["digits x0"], m["digits x1"] = e
    # tile fill extents (dim, not the bright digits)
    tl = [x for x in range(200, 580) if sum(px[x, 1262]) / 3 > 26]
    if tl:
        m["tiles x0"], m["tiles x1"] = min(tl), max(tl)
    tv = [y for y in range(1230, 1340) if sum(px[248, y]) / 3 > 26]
    if tv:
        m["tile y0"], m["tile y1"] = min(tv), max(tv)
    lb = bands(px, W, 240, 540, 1322, 1360, 90)
    if lb:
        m["unit top"], m["unit bot"] = lb[0]
    return m


def main():
    ref_p = os.path.join(ROOT, "screen.png")
    got_p = os.path.join(ROOT, ".work", "render.png")
    if not os.path.exists(got_p):
        sys.exit("run `node tools/verify.mjs` first")

    ri, rp, (RW, RH) = load(ref_p)
    gi, gp, (GW, GH) = load(got_p)
    a = measure(rp, RW, RH)
    b = measure(gp, GW, GH)

    keys = list(a.keys())
    for k in b:
        if k not in keys:
            keys.append(k)

    print(f"{'landmark':22s} {'ref':>7s} {'render':>7s} {'Δ':>6s}   (2x px)")
    print("=" * 52)
    worst = []
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None or vb is None:
            print(f"{k:22s} {str(va):>7s} {str(vb):>7s}    --")
            continue
        d = vb - va
        flag = "" if abs(d) <= 1 else ("  <<<" if abs(d) >= 6 else "  <")
        print(f"{k:22s} {va:7d} {vb:7d} {d:+6d}{flag}")
        if abs(d) >= 3:
            worst.append((abs(d), k, d))
    worst.sort(reverse=True)
    if worst:
        print("\nbiggest offsets:")
        for d, k, sd in worst[:14]:
            print(f"   {k:22s} {sd:+d}")


if __name__ == "__main__":
    main()
