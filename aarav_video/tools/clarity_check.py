"""Check that every voiced character line is intelligible: transcribe it with local Whisper and compare
with the script. A high word error rate means a listener will struggle too (mumbled or mispronounced).

Usage: python tools/clarity_check.py [ep13 ...]   ->  table of lines, worst first
Needs: faster-whisper (downloads the base.en model from Hugging Face on first run, free).
"""
import io
import json
import re
import subprocess
import sys
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent.parent
NUM = {"82": "eighty two"}
FFMPEG = ROOT / "node_modules" / "@remotion" / "compositor-win32-x64-msvc" / "ffmpeg.exe"


def load(path: Path) -> np.ndarray:
    """16 kHz mono float samples (decoded with Remotion's ffmpeg; PyAV in this venv is incompatible)."""
    raw = subprocess.run([str(FFMPEG), "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "wav", "-"], capture_output=True, check=True).stdout
    with wave.open(io.BytesIO(raw)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def words(s: str) -> list[str]:
    s = s.lower().replace("%", " percent").replace("-", " ")
    for k, v in NUM.items():
        s = s.replace(k, v)
    return re.findall(r"[a-z']+", s)


def wer(ref: list[str], hyp: list[str]) -> float:
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    return 1 - matched / max(len(ref), 1)


def main() -> None:
    eps = sys.argv[1:] or sorted(p.stem for p in (ROOT / "src" / "timelines").glob("ep*.json"))
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    rows = []
    for ep in eps:
        tl = json.loads((ROOT / "src" / "timelines" / f"{ep}.json").read_text(encoding="utf-8"))
        script = [ln for s in json.loads((ROOT / "episodes" / f"{ep}.json").read_text(encoding="utf-8"))["shots"]
                  for ln in s.get("lines", [])]
        voiced = [ln for s in tl["shots"] for ln in s["lines"]]
        for src, ln in zip(script, voiced):
            if ln.get("silent"):
                continue
            segs, _ = model.transcribe(load(ROOT / "public" / ln["audio"]), language="en", beam_size=5)
            heard = " ".join(s.text.strip() for s in segs)
            rows.append((wer(words(src.get("say", src["text"])), words(heard)), ep, ln["who"], src["text"], heard))
    rows.sort(reverse=True)
    for e, ep, who, text, heard in rows:
        flag = "  <-- unclear" if e > 0.15 else ""
        print(f"{e:4.0%} {ep} {who:7s} | {text[:60]}\n{'':18s}heard: {heard[:60]}{flag}")
    print(f"\n{len(rows)} lines, mean WER {sum(r[0] for r in rows) / max(len(rows), 1):.1%}")


if __name__ == "__main__":
    main()
