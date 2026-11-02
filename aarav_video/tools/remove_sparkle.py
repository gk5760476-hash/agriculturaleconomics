"""Paint out the small four-point "sparkle" watermark the image generator left in the bottom-right corner of
the photo plates (assets/scenes/*.png, in place). It is bright, grey and star-shaped on a busy background,
so it is found as a bright outlier against the local median, then inpainted from its surroundings.

Usage: python tools/remove_sparkle.py [p01_02 ...] [--sheet before_after.png]   then rerun prepare_assets.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SCENES = ROOT / "assets" / "scenes"
SKIP = {"p01_17", "p01_18", "p01_19"}  # user-supplied plates, already cleaned


def find_mask(img: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    mask = np.zeros(img.shape[:2], np.uint8)
    boxes = []
    # the generator stamps up to two sparkles at fixed spots: a main one and a fainter one up-left of it
    for u, v in ((0.959, 0.927), (0.912, 0.845)):
        r = int(0.045 * w)
        cx, cy = int(u * w), int(v * h)
        x0, y0 = max(0, cx - r), max(0, cy - r)
        roi = img[y0:cy + r, x0:cx + r]
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.int16)
        bg = cv2.medianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 2 * (r // 2) + 1).astype(np.int16)
        sat = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[..., 1]
        cand = ((grey - bg) > 8) & (sat < 80)
        n, _, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8))

        def star_like(i: int) -> bool:
            x, y, bw, bh, area = stats[i]
            return area >= 8 and 0.7 < bw / max(bh, 1) < 1.4 and 0.2 < area / max(bw * bh, 1) < 0.7 and max(bw, bh) < r

        best = max(filter(star_like, range(1, n)), key=lambda i: stats[i][4], default=None)
        if best is None:
            continue
        x, y, bw, bh, area = stats[best]
        pad = max(3, int(0.35 * max(bw, bh)))
        box = (x0 + x - pad, y0 + y - pad, bw + 2 * pad, bh + 2 * pad)
        cv2.rectangle(mask, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), 255, -1)
        boxes.append(box)
    if not boxes:
        return mask, (0, 0, 0, 0)
    # report the union so the before/after crop shows every sparkle
    xs = [b[0] for b in boxes] + [b[0] + b[2] for b in boxes]
    ys = [b[1] for b in boxes] + [b[1] + b[3] for b in boxes]
    return mask, (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def main() -> None:
    sheet = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else None
    ids = [a for a in sys.argv[1:] if not a.startswith("--") and a != sheet]
    files = [f for f in sorted(SCENES.glob("*.png")) if "_".join(f.stem.split("_")[:2]) not in SKIP
             and (not ids or "_".join(f.stem.split("_")[:2]) in ids)]
    tiles = []
    for f in files:
        img = cv2.imread(str(f))
        mask, box = find_mask(img)
        if not mask.any():
            print(f"{f.name}: no sparkle found")
            continue
        fixed = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)
        if sheet:
            x, y, bw, bh = box
            m = 3 * max(bw, bh)
            cx, cy = x + bw // 2, y + bh // 2
            crop = lambda im: cv2.resize(im[max(0, cy - m):cy + m, max(0, cx - m):cx + m], (160, 160), interpolation=cv2.INTER_NEAREST)
            tiles.append(np.hstack([crop(img), crop(fixed)]))
        if "--dry" not in sys.argv:
            cv2.imwrite(str(f), fixed)
        print(f"{f.name}: sparkle at {box[:2]} size {box[2]}x{box[3]}")
    if sheet and tiles:
        cols = 4
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
        cv2.imwrite(sheet, np.vstack(rows))


if __name__ == "__main__":
    main()
