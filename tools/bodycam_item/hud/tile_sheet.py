"""Tiles rendered frames into one contact sheet (run by per_shell.py with the system Python + Pillow).
Argument: JSON {"title", "tiles": [[label, png], ...], "out", "cols"?}; a numeric label prints as "f<n>".
The tile PNGs are deleted afterwards."""
import json
import os
import sys

from PIL import Image, ImageDraw

spec = json.loads(sys.argv[1])
tiles = spec["tiles"]
w, h = Image.open(tiles[0][1]).size
cols = int(spec.get("cols", 4))
rows = (len(tiles) + cols - 1) // cols
img = Image.new("RGB", (cols * w, rows * h + 40), (20, 20, 20))
d = ImageDraw.Draw(img)
d.text((10, 10), spec["title"], fill=(255, 255, 255))
for i, (f, p) in enumerate(tiles):
    x, y = (i % cols) * w, (i // cols) * h + 40
    img.paste(Image.open(p).convert("RGB"), (x, y))
    d.text((x + 8, y + 8), "f%d" % f if isinstance(f, int) else str(f), fill=(255, 255, 0))
img.save(spec["out"])
for _, p in tiles:
    os.remove(p)
