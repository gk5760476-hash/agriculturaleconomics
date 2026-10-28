"""Make per-clip overlays that keep speech bubbles and baked titles crisp over generated motion.

For each job image: find speech bubbles (near-white blobs containing dark text) automatically, add the
hand-marked title boxes from clips/prompts.json "_freeze", and save clips/frozen/<clip_id>.png — the
original pixels in those regions, transparent elsewhere — cropped to the same 832x480 aspect the
video model received. Also writes clips/frozen/_preview.png (regions tinted red) for checking.

Usage: python tools/freeze_masks.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hf_video import crop_for_model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "clips"
OUT = CLIPS / "frozen"


def bubble_mask(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    labels, n = ndimage.label(gray > 228, structure=np.ones((3, 3)))
    mask = np.zeros_like(gray, dtype=bool)
    for idx, sl in enumerate(ndimage.find_objects(labels), 1):
        comp = labels[sl] == idx
        area = comp.sum()
        if not (0.002 * w * h < area < 0.2 * w * h):
            continue
        filled = ndimage.binary_fill_holes(comp)
        box_fill = filled.sum() / comp.size
        dark = (gray[sl] < 100) & filled & ~comp
        text_ratio = dark.sum() / filled.sum()
        bright = gray[sl][comp].mean()
        if box_fill > 0.55 and 0.015 < text_ratio < 0.5 and bright > 236:
            mask[sl] |= filled
    # Grow well past the outline: the model sometimes redraws a bubble a few pixels off, leaving a ghost edge.
    return ndimage.binary_dilation(mask, iterations=22)


def main() -> None:
    prompts = json.loads((CLIPS / "prompts.json").read_text(encoding="utf-8"))
    boxes = prompts["_freeze"]
    jobs = json.loads((CLIPS / "jobs.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    previews = []
    for j in jobs:
        cid = j["clip_id"]
        img_id = cid.replace("_", "/", 1)
        cropped = OUT / f"_{cid}_src.jpg"
        crop_for_model(ROOT / j["image"], cropped)
        im = Image.open(cropped).convert("RGB")
        cropped.unlink()
        gray = np.asarray(im.convert("L"), dtype=np.float32)
        mask = bubble_mask(gray) if img_id.startswith("panels/") else np.zeros(gray.shape, bool)
        h, w = gray.shape
        for x0, y0, x1, y1 in boxes.get(img_id, []):
            mask[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = True
        out = OUT / f"{cid}.png"
        if not mask.any():
            out.unlink(missing_ok=True)
            continue
        alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
        rgba = im.copy()
        rgba.putalpha(alpha)
        rgba.save(out)
        tint = Image.blend(im, Image.new("RGB", im.size, (255, 0, 0)), 0.45)
        previews.append((cid, Image.composite(tint, im, alpha).resize((416, 240))))
        print(f"{cid}: {mask.mean() * 100:.1f}% frozen")

    cols = 4
    sheet = Image.new("RGB", (cols * 416, -(-len(previews) // cols) * 240), "white")
    for k, (_, p) in enumerate(previews):
        sheet.paste(p, ((k % cols) * 416, (k // cols) * 240))
    sheet.save(OUT / "_preview.png")


if __name__ == "__main__":
    main()
