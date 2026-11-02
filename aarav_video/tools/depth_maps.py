"""Estimate depth for the photo plates (Depth Anything V2 small, local ONNX) for 2.5D parallax.

For each public/img/scenes/<id>.jpg (title plates skipped) writes public/img/depth/<id>.png: 8-bit grey,
1024 px wide, white = near. The renderer (DepthShot in src/Episode.tsx) shifts every pixel by its depth as
the camera moves, so near objects (Aarav, the table) slide against the room instead of the picture moving
as one flat card. Comic panels stay flat: their speech-bubble text would bend.

Usage: python tools/depth_maps.py [p01_17 ...] [--sheet out.png]
Needs: onnxruntime, opencv-python-headless, huggingface_hub (the model downloads once from Hugging Face, free).
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "img" / "scenes"
OUT = ROOT / "public" / "img" / "depth"
FLAT = {"p01_10", "p01_16", "p01_19"}  # title plates / graphics
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
WIDTH = 1024


def nearness(sess: ort.InferenceSession, rgb: np.ndarray) -> np.ndarray:
    """Relative nearness 0 (far) .. 1 (near), at WIDTH px wide."""
    h, w = rgb.shape[:2]
    ih = 518
    iw = max(14, round(ih * w / h / 14) * 14)
    x = cv2.resize(rgb, (iw, ih), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None]
    d = sess.run(None, {"pixel_values": x})[0][0]
    d = cv2.resize(d, (WIDTH, round(WIDTH * h / w)), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, [2, 98])
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    # a light blur keeps depth edges from tearing fine detail when pixels shift
    return cv2.GaussianBlur(d, (0, 0), 1.5)


def main() -> None:
    sheet_path = sys.argv[sys.argv.index("--sheet") + 1] if "--sheet" in sys.argv else None
    ids = [a for a in sys.argv[1:] if not a.startswith("--") and a != sheet_path]
    ids = ids or sorted(p.stem for p in SRC.glob("*.jpg") if p.stem not in FLAT)
    sess = ort.InferenceSession(hf_hub_download("onnx-community/depth-anything-v2-small", "onnx/model.onnx"),
                                providers=["CPUExecutionProvider"])
    OUT.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for img_id in ids:
        rgb = np.array(Image.open(SRC / f"{img_id}.jpg").convert("RGB"))
        d = nearness(sess, rgb)
        Image.fromarray((d * 255).astype(np.uint8), "L").save(OUT / f"{img_id}.png")
        print(f"depth/{img_id}.png")
        if sheet_path:
            th = round(400 * d.shape[0] / d.shape[1])
            dm = cv2.applyColorMap(cv2.resize((d * 255).astype(np.uint8), (400, th)), cv2.COLORMAP_INFERNO)[..., ::-1]
            thumbs.append(np.hstack([cv2.resize(rgb, (400, th)), dm]))
    if sheet_path and thumbs:
        Image.fromarray(np.vstack([cv2.resize(t, (800, t.shape[0])) for t in thumbs])).save(sheet_path)


if __name__ == "__main__":
    main()
