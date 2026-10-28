"""Extract every embedded image from the source PDFs into assets/, named by page and order.

Usage: python tools/extract_assets.py
"""
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "pictographic script.pdf": ROOT / "assets" / "panels",
    "Aaravs study room.pdf": ROOT / "assets" / "scenes",
    "plannee.pdf": ROOT / "assets" / "characters",
}


def extract(pdf_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(pdf_path)
    for page_no, page in enumerate(reader.pages, start=1):
        for idx, image in enumerate(page.images, start=1):
            img = image.image
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            name = f"p{page_no:02d}_{idx:02d}_{img.width}x{img.height}.png"
            img.save(out_dir / name)
            print(f"{pdf_path.name}: {name}")


if __name__ == "__main__":
    for pdf_name, out_dir in SOURCES.items():
        extract(ROOT / "source" / pdf_name, out_dir)
