"""Synthesize the small sound effects used by episodes into public/sfx/ (no external assets).

Usage: python tools/make_sfx.py
"""
import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATE = 44100


def tone(freq: float, dur: float, vol: float) -> list[float]:
    n = int(RATE * dur)
    return [vol * math.sin(2 * math.pi * freq * i / RATE) * math.exp(-6 * i / n) for i in range(n)]


def write(name: str, samples: list[float]) -> None:
    out = ROOT / "public" / "sfx"
    out.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


if __name__ == "__main__":
    # Phone notification: two short rising chimes.
    write("notify", tone(880, 0.18, 0.5) + [0.0] * int(RATE * 0.05) + tone(1320, 0.35, 0.5))
