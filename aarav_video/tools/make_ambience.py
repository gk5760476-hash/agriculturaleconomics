"""Synthesize seamless 30 s ambience loops into public/sfx/amb_<name>.wav (no external assets).

Noise is shaped in the frequency domain, so each loop is exactly periodic and repeats without a seam.
  room   - indoor room tone with a slow ceiling-fan swish (home, shop, office, hospital, classroom)
  street - distant traffic rumble with slow swells and the odd faraway horn
  night  - dark, quiet outdoor air with sparse crickets (rooftop, shuttered lane)
Levels are set low on purpose: the bed sits under dialogue and under the presenter's live narration.

Usage: python tools/make_ambience.py
"""
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RATE = 48000
SECONDS = 30
N = RATE * SECONDS
rng = np.random.default_rng(7)
t = np.arange(N) / RATE


def shaped_noise(lo: float, hi: float, tilt: float) -> np.ndarray:
    """Periodic noise with energy between lo and hi Hz, falling off as f**-tilt (1 = pink, 2 = brown)."""
    spec = np.fft.rfft(rng.standard_normal(N))
    f = np.fft.rfftfreq(N, 1 / RATE)
    gain = np.where(f > 0, np.maximum(f, 1.0) ** (-tilt / 2), 0.0)
    gain *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)  # soft high-pass
    gain *= 1 / (1 + (f / hi) ** 4)                    # soft low-pass
    x = np.fft.irfft(spec * gain, n=N)
    return x / np.sqrt(np.mean(x ** 2))


def slow_lfo(cycles: list[int], depth: float) -> np.ndarray:
    """Amplitude wobble built from whole cycles per loop, so it stays seamless."""
    m = sum(np.sin(2 * np.pi * c * t / SECONDS + rng.uniform(0, 6.28)) for c in cycles) / len(cycles)
    return 1 + depth * m


def events(make, every: tuple[float, float], length: float) -> np.ndarray:
    """Scatter short sounds through the loop, wrapping around the end."""
    out = np.zeros(N)
    pos = rng.uniform(0, every[0])
    while pos < SECONDS:
        s = make()
        i = int(pos * RATE)
        idx = (np.arange(len(s)) + i) % N
        out[idx] += s
        pos += rng.uniform(*every) + length
    return out


def horn() -> np.ndarray:
    d = rng.uniform(0.25, 0.6)
    tt = np.arange(int(d * RATE)) / RATE
    f0 = rng.uniform(330, 470)
    tone = np.sign(np.sin(2 * np.pi * f0 * tt)) * 0.5 + np.sin(2 * np.pi * f0 * 1.26 * tt) * 0.5
    env = np.minimum(1, tt / 0.03) * np.minimum(1, (d - tt) / 0.08)
    # far away: keep only the band that carries over distance
    spec = np.fft.rfft(tone * env)
    f = np.fft.rfftfreq(len(tt), 1 / RATE)
    return np.fft.irfft(spec / (1 + (f / 1200) ** 4), n=len(tt)) * rng.uniform(0.15, 0.35)


def cricket() -> np.ndarray:
    chirps = rng.integers(3, 7)
    f0 = rng.uniform(4300, 4900)
    out = []
    for _ in range(chirps):
        tt = np.arange(int(0.045 * RATE)) / RATE
        out.append(np.sin(2 * np.pi * f0 * tt) * np.sin(np.pi * tt / tt[-1]) ** 2)
        out.append(np.zeros(int(0.03 * RATE)))
    return np.concatenate(out) * rng.uniform(0.2, 0.5)


def room() -> np.ndarray:
    tone = shaped_noise(40, 900, 1.6)
    fan_rate = 5  # blade swishes per second, a whole number per loop
    swish = shaped_noise(300, 3000, 1.0) * (0.6 + 0.4 * np.sin(2 * np.pi * fan_rate * t) ** 2) * 0.35
    return (tone + swish) * slow_lfo([1, 3], 0.12)


def street() -> np.ndarray:
    rumble = shaped_noise(35, 1800, 1.5) * slow_lfo([1, 2, 5], 0.35)
    hiss = shaped_noise(800, 6000, 1.0) * 0.15 * slow_lfo([2, 7], 0.5)
    return rumble + hiss + events(horn, (6, 14), 0.5)


def night() -> np.ndarray:
    air = shaped_noise(30, 600, 1.8) * slow_lfo([1, 2], 0.25)
    return air + events(cricket, (1.5, 5), 0.3) * 0.6


def write(name: str, x: np.ndarray, dbfs: float) -> None:
    x = x / np.sqrt(np.mean(x ** 2)) * 10 ** (dbfs / 20)  # RMS level
    x = np.clip(x, -0.99, 0.99)
    out = ROOT / "public" / "sfx"
    out.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out / f"amb_{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"amb_{name}.wav  {dbfs} dBFS RMS")


if __name__ == "__main__":
    write("room", room(), -44)
    write("street", street(), -40)
    write("night", night(), -44)
