#!/usr/bin/env python3
"""
Asset pipeline for the Neo Garden landing page.

1. Builds the card image from building.jpeg — a daylight render, graded to night so
   it sits in the dark composition and keeps white text legible over it.
2. Places the person cutout from measured landmarks and exports it at 2x its
   display size.
3. Encodes AVIF + WebP for both and reports byte sizes against budget.

Run from the project root:  python3 tools/make-assets.py
"""
import json
import os
from PIL import Image, ImageChops, ImageFilter

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

# Crop taken from building.jpeg (3456x4608). A wide band across the building's upper
# mass: the card is short and wide, and the CSS mask fades its lower half out, so the
# roofline belongs in the upper third or it disappears under the fade. Matches the
# plate's 716x330 aspect exactly so nothing is squashed.
SOURCE_CROP = (0, 300, 3456, 1893)   # only used to derive the blurred backdrop

# The tower itself, cropped tight in building.jpeg pixels, plus where it lands on the
# plate. TOWER_X biases left of centre: the person cutout covers the plate from x~444,
# so anything past that is hidden behind him.
TOWER_BOX = (740, 330, 3210, 2930)
TOWER_H = 318
TOWER_X = 150

# Grade constants. Per-channel gain + gamma turns the daylight render to night; the
# warm pass puts light back into windows.
NIGHT_GAIN = ((0.30, 1.42), (0.35, 1.38), (0.50, 1.24))   # (gain, gamma) per channel
GLOW_COLOR = (255, 196, 116)
GLOW_FLOOR = 150      # luminance below which nothing glows
SKY_SCALE = 55        # blue-minus-red above this reads as sky
FADE_START = 92       # plate row (0-255 scale) where the floor fade begins


def night_grade(img):
    """Daylight render -> night. Darkens and cools everything, then puts a warm glow
    back into the bright NON-SKY pixels so windows and lit facade read as lit.

    The sky has to be excluded from the glow explicitly. It's the brightest thing in
    the frame, so a plain luminance threshold turns it into a sunset instead of a
    night sky. It's separable because it is the only large area where blue dominates
    red that strongly."""
    r, g, b = img.split()
    lum = img.convert("L")

    sky = ImageChops.subtract(b, r).point(lambda v: min(255, int(v * 255 / SKY_SCALE)))
    hi = lum.point(lambda v: 0 if v < GLOW_FLOOR
                   else min(255, int((v - GLOW_FLOOR) * 255 / (255 - GLOW_FLOOR))))
    glow = ImageChops.multiply(hi, ImageChops.invert(sky))
    glow = glow.point(lambda v: int(255 * (v / 255) ** 1.5))

    def ch(band, gain, gamma):
        return band.point(
            lambda v: max(0, min(255, int(255 * (v / 255) ** gamma * gain))))

    base = Image.merge("RGB", tuple(
        ch(band, gain, gamma) for band, (gain, gamma) in zip((r, g, b), NIGHT_GAIN)))
    warm = Image.new("RGB", img.size, GLOW_COLOR)
    glow3 = Image.merge("RGB", (glow, glow, glow))
    return ImageChops.add(base, ImageChops.multiply(warm, glow3))


def floor_fade(img):
    """Darken the lower part of the plate. The bullets and price sit over it in white
    and gold, and an evenly-lit facade behind them costs too much contrast. Baked in
    rather than left to the CSS mask alone so the text is legible even if the mask
    is ever changed."""
    w, h = img.size
    ramp = Image.linear_gradient("L").resize((w, h))          # 0 at top -> 255 at bottom
    ramp = ramp.point(lambda v: 255 if v < FADE_START else
                      max(0, int(255 - (v - FADE_START) * 255 / (255 - FADE_START))))
    return Image.composite(img, Image.new("RGB", (w, h), (5, 12, 24)), ramp)


def build_plate():
    """Build the card image from building.jpeg.

    The source is a 3:4 portrait of a tall tower; the card is a 2.17:1 strip. Cropping
    a band out of it shows four floors and reads as a low-rise, so instead the whole
    building is scaled to the plate height and composited onto a backdrop derived from
    the source itself — a heavily blurred, stretched copy, which matches the sky and
    ground colours exactly and hides the seam a synthetic gradient would show.

    Nothing has to be painted out here: unlike the crop from screen.png this source is
    clean, with no bullet text or figure baked into it."""
    src = Image.open(os.path.join(ROOT, "building.jpeg")).convert("RGB")

    tower = src.crop(TOWER_BOX)
    tw = round(TOWER_H * tower.width / tower.height)
    tower = tower.resize((tw, TOWER_H), Image.LANCZOS)

    bg = src.crop(SOURCE_CROP).resize((PLATE_W, PLATE_H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(38))

    plate = bg.copy()
    plate.paste(tower, (TOWER_X, PLATE_H - TOWER_H))
    # soften the two vertical seams so the pasted rectangle doesn't read as an edge
    for sx in (TOWER_X, TOWER_X + tw):
        band = 10
        box = (max(0, sx - band), 0, min(PLATE_W, sx + band), PLATE_H)
        if box[2] <= box[0]:
            continue
        patch = plate.crop(box).filter(ImageFilter.GaussianBlur(3))
        plate.paste(patch, box[:2])

    return floor_fade(night_grade(plate))


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
