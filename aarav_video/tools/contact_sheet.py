"""Tile every PNG in a folder into one labelled contact sheet for quick review.

Usage: python tools/contact_sheet.py <folder> <out.png> [columns]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

THUMB_W = 320


def main(folder: Path, out: Path, cols: int) -> None:
    files = sorted(folder.glob("*.png"))
    thumbs = []
    for f in files:
        im = Image.open(f).convert("RGB")
        h = round(im.height * THUMB_W / im.width)
        thumbs.append((f.stem, im.resize((THUMB_W, h))))
    cell_h = max(t.height for _, t in thumbs) + 22
    rows = -(-len(thumbs) // cols)
    sheet = Image.new("RGB", (cols * THUMB_W, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (name, t) in enumerate(thumbs):
        x, y = (i % cols) * THUMB_W, (i // cols) * cell_h
        sheet.paste(t, (x, y + 22))
        draw.text((x + 4, y + 4), name, fill="black")
    sheet.save(out)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 4)
