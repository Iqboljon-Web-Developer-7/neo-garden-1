#!/usr/bin/env python3
"""
Download the Oswald variable font and subset it to exactly the glyphs index.html uses.

Oswald was identified by rendering candidate faces and pixel-overlapping them against
the real glyph bitmap in screen.png (see tools/match-glyphs.mjs): 86.1% IoU on the H1
against 73% for the runner-up.

The page's character set is fixed and known, so the subset is tiny (~4KB) and no
Google Fonts request happens at runtime. The wght axis is retained so one file
covers the 500/600/700 weights the page uses.

    python3 tools/subset-font.py
"""
import html
import os
import re
import subprocess
import urllib.request

from fontTools import subset
from fontTools.varLib import instancer
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "fonts", "oswald-subset.woff2")
CACHE = os.path.join(ROOT, ".work", "oswald-var.ttf")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CSS_URL = "https://fonts.googleapis.com/css2?family=Oswald:wght@200..700&display=swap"


def _get(url):
    """Fetch a URL. Falls back to curl because this machine's Python has no CA
    bundle configured (urllib raises CERTIFICATE_VERIFY_FAILED) while curl works."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=20).read()
    except Exception:
        return subprocess.run(
            ["curl", "-sSL", "--max-time", "30", "-A", UA, url],
            check=True, capture_output=True).stdout


def fetch_source():
    if os.path.exists(CACHE):
        return CACHE
    css = _get(CSS_URL).decode()
    urls = re.findall(r"url\((https://[^)]+\.(?:woff2|ttf))\)", css)
    if not urls:
        raise SystemExit("no font URL found in the Google Fonts CSS")
    # last block is latin; it carries the full wght axis
    with open(CACHE, "wb") as f:
        f.write(_get(urls[-1]))
    return CACHE


def page_charset():
    """Every character that ends up as rendered text in index.html."""
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        doc = f.read()
    body = doc[doc.index("<body"):]
    body = re.sub(r"<script\b.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style\b.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<svg\b.*?</svg>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))

    chars = set(text)
    chars |= set("0123456789:")                 # every digit the countdown can show
    chars |= set("‘’ʻʼ'")   # Uzbek apostrophes, both curly and modifier
    chars -= set("\n\r\t")
    chars.add(" ")
    return "".join(sorted(chars))


def main():
    src = fetch_source()
    chars = page_charset()
    print(f"→ subsetting to {len(chars)} chars: {chars!r}")

    font = TTFont(src)
    opts = subset.Options()
    opts.layout_features = ["kern", "liga", "calt", "locl", "ccmp"]
    opts.name_IDs = ["*"]
    opts.name_legacy = False
    opts.notdef_outline = False
    opts.recalc_bounds = True
    opts.drop_tables += ["DSIG"]
    opts.desubroutinize = False

    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text=chars)
    subsetter.subset(font)

    # The page only uses 500/600/700, so clip the wght axis to that range. Deltas
    # outside it are dead weight — this is worth ~30% of the file.
    if "fvar" in font:
        font = instancer.instantiateVariableFont(font, {"wght": (500, 700)}, updateFontNames=False)

    font.flavor = "woff2"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    font.save(OUT)

    n = os.path.getsize(OUT)
    axes = ""
    if "fvar" in font:
        axes = ", ".join(f"{a.axisTag} {a.minValue:g}..{a.maxValue:g}" for a in font["fvar"].axes)
    print(f"→ {os.path.relpath(OUT, ROOT)}  {n:,} B   axes: {axes or 'static'}")
    if n > 8500:
        print(f"   ! over the 8,500 B budget")


if __name__ == "__main__":
    main()
