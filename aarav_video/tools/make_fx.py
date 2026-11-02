"""Generate the film-grain tiles the renderer overlays on every frame (public/fx/grain_N.png).

Soft, mid-grey Gaussian grain; the renderer cycles the tiles and shifts them each frame so the grain
never repeats visibly. Usage: python tools/make_fx.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
TILES = 6
W, H = 1408, 848  # a little larger than the 1280x720 frame so each frame can shift it

if __name__ == "__main__":
    out = ROOT / "public" / "fx"
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    for i in range(TILES):
        g = np.clip(128 + rng.normal(0, 38, (H, W)), 0, 255).astype(np.uint8)
        # a slight blur makes the grain organic rather than digital pixel noise
        Image.fromarray(g, "L").filter(ImageFilter.GaussianBlur(0.6)).save(out / f"grain_{i}.png")
    print(f"{TILES} grain tiles -> public/fx/")
