"""Copy extracted panels/scenes into public/img as sharpened JPEGs at least 2048 px wide.

Ids drop the size suffix: assets/panels/p02_02_1024x572.png -> public/img/panels/p02_02.jpg
Usage: python tools/prepare_assets.py
"""
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
TARGET_W = 2048


def prepare(kind: str) -> None:
    out_dir = ROOT / "public" / "img" / kind
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted((ROOT / "assets" / kind).glob("*.png")):
        img_id = "_".join(src.stem.split("_")[:2])
        im = Image.open(src).convert("RGB")
        if im.width < TARGET_W:
            scale = TARGET_W / im.width
            im = im.resize((TARGET_W, round(im.height * scale)), Image.LANCZOS)
            # Stronger sharpening for the tiny opening panels.
            radius = 2.5 if scale > 3 else 1.6
            im = im.filter(ImageFilter.UnsharpMask(radius=radius, percent=90, threshold=2))
        im.save(out_dir / f"{img_id}.jpg", quality=92)
        print(f"{kind}/{img_id}.jpg  {im.width}x{im.height}")


if __name__ == "__main__":
    for kind in ("panels", "scenes"):
        prepare(kind)
