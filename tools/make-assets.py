#!/usr/bin/env python3
"""
Asset pipeline for the Neo Garden landing page.

1. Builds the card image from building.jpeg, used as shot — cropped to the card's
   aspect and resized, nothing else.
2. Places the person cutout from measured landmarks and exports it at 2x its
   display size.
3. Encodes AVIF + WebP for both and reports byte sizes against budget.

Run from the project root:  python3 tools/make-assets.py
"""
import json
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "img")
WORK = os.path.join(ROOT, ".work")
os.makedirs(OUT, exist_ok=True)
os.makedirs(WORK, exist_ok=True)

# ---- geometry measured from screen.png (all coords are 2x / mockup pixels) ----
CARD = dict(x0=26, y0=487, x1=742, y1=979)     # card interior
PLATE_H = 330                                   # card image is 358x165 CSS

BUDGET = {"building-card.avif": 45_000, "person.avif": 40_000}


PLATE_W = 716

# Crop taken from building.jpeg (3456x4608), matching the plate's 2.17:1 aspect
# exactly so nothing is squashed. Starts just above the penthouse so the roofline
# reads, and runs down through the upper floors; the card's lower half sits under the
# text scrim anyway.
SOURCE_CROP = (0, 430, 3456, 2022)


def build_plate():
    """Build the card image from building.jpeg: crop to the card's aspect, resize, done.

    The photo is used as shot — no colour grade, no recomposition. Earlier passes tried
    grading it to night to match the mockup, and compositing the whole tower onto a
    blurred backdrop so all ten floors fit; both were rejected. Legibility for the text
    over it is handled by a CSS scrim in index.html, which leaves the image untouched."""
    src = Image.open(os.path.join(ROOT, "building.jpeg")).convert("RGB")
    return src.crop(SOURCE_CROP).resize((PLATE_W, PLATE_H), Image.LANCZOS)


# Figure placement, in 2x mockup pixels. Derived from three independent landmarks
# measured in screen.png, all of which agree:
#   * head spans x 505..650 (face skin x 512..640 plus hair), head top y~460
#   * silhouette spans x 448..742 at y=740 (clipped by the card's right border)
#   * figure bottom coincides with the card's bottom edge, y=979
# Scale = head width 145 / source head width 2091 = 0.0693 of the 4842x7730 source.
# Automated fits were tried and rejected: an RGB composite fit needs a model of the
# backdrop (which above the card is page background, not the plate), and an edge
# fit locks onto the building facade's strong vertical lines.
PERSON = dict(w=336, h=536, x=444, y=444)


def place_person():
    person = Image.open(os.path.join(ROOT, "person.avif")).convert("RGBA")
    person = person.crop(person.getchannel("A").getbbox())        # tight to the figure
    fit = dict(PERSON)
    fit["span"] = fit["w"] / (CARD["x1"] - CARD["x0"])
    fit["dx"] = fit["x"] - CARD["x0"]
    fit["dy"] = fit["y"] - CARD["y0"]
    return person, fit


def encode(img, stem, avif_q, webp_q, alpha=False):
    paths = {}
    a = os.path.join(OUT, stem + ".avif")
    w = os.path.join(OUT, stem + ".webp")
    img.save(a, quality=avif_q, speed=2)
    img.save(w, quality=webp_q, method=6, lossless=False, exact=alpha)
    paths["avif"], paths["webp"] = a, w
    return paths


def main():
    print("→ building plate (from building.jpeg)")
    plate = build_plate()
    plate.save(os.path.join(WORK, "plate.png"))

    print("→ person placement (measured landmarks)")
    person, fit = place_person()
    cw = CARD["x1"] - CARD["x0"]
    print(f"   size={fit['w']}x{fit['h']}@2x  offset=({fit['dx']},{fit['dy']}) "
          f"relative to card interior; right {fit['x']+fit['w']} vs card right "
          f"{CARD['x1']}, bottom {fit['y']+fit['h']} vs card bottom {CARD['y1']}")

    # export the cutout at exactly its 2x display size
    p_out = person.resize((fit["w"], fit["h"]), Image.LANCZOS)

    print("→ encoding")
    encode(plate, "building-card", avif_q=62, webp_q=76)
    encode(p_out, "person", avif_q=64, webp_q=80, alpha=True)

    # CSS-ready numbers (divide by 2 to get CSS px at the 384px design width)
    css = {
        "plate": {"w2x": plate.width, "h2x": plate.height,
                  "cssW": plate.width / 2, "cssH": plate.height / 2},
        "person": {"w2x": fit["w"], "h2x": fit["h"],
                   "cssW": fit["w"] / 2, "cssH": fit["h"] / 2,
                   "cssLeft": fit["dx"] / 2, "cssTop": fit["dy"] / 2},
        "card": {"cssW": cw / 2, "cssH": (CARD["y1"] - CARD["y0"]) / 2},
    }
    with open(os.path.join(WORK, "placement.json"), "w") as f:
        json.dump(css, f, indent=2)
    print("\n" + json.dumps(css, indent=2))

    print("\n→ sizes")
    total = 0
    for name in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, name)
        n = os.path.getsize(p)
        total += n if name.endswith(".avif") else 0
        flag = ""
        if name in BUDGET:
            flag = "  OK" if n <= BUDGET[name] else f"  OVER BUDGET ({BUDGET[name]:,})"
        print(f"   {name:24s} {n:8,d} B{flag}")
    print(f"   {'AVIF total':24s} {total:8,d} B")


if __name__ == "__main__":
    main()
