"""Make dry TTS lines sound recorded in a small room (numpy/scipy; Remotion's ffmpeg has no audio filters).

Chain: 80 Hz low cut, 11.5 kHz high cut, -2.5 dB at 280 Hz (mud), +1.5 dB at 3.2 kHz (presence),
gentle 2.2:1 compression, then faint early reflections at 23/41/67 ms. Length is unchanged.

Usage: python tools/voice_fx.py in.wav out.wav
"""
import sys
import wave

import numpy as np
from scipy import signal


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        rate, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32768
    return x.reshape(-1, ch).mean(axis=1), rate


def write_wav(path: str, x: np.ndarray, rate: int) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def peaking(f0: float, gain_db: float, q: float, rate: int) -> np.ndarray:
    """RBJ cookbook peaking EQ as a second-order section."""
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / rate
    alpha = np.sin(w0) / (2 * q)
    b = [1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a]
    den = [1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a]
    return np.array([[*(np.array(b) / den[0]), 1, den[1] / den[0], den[2] / den[0]]])


def compress(x: np.ndarray, rate: int, thresh_db=-22.0, ratio=2.2, attack=0.010, release=0.150,
             makeup_db=1.5) -> np.ndarray:
    level = np.abs(x)
    env = np.empty_like(x)
    a_att, a_rel = np.exp(-1 / (attack * rate)), np.exp(-1 / (release * rate))
    e = 0.0
    for i, v in enumerate(level):
        e = (a_att if v > e else a_rel) * e + (1 - (a_att if v > e else a_rel)) * v
        env[i] = e
    db = 20 * np.log10(np.maximum(env, 1e-6))
    over = np.maximum(db - thresh_db, 0)
    gain_db = -over * (1 - 1 / ratio) + makeup_db
    return x * 10 ** (gain_db / 20)


def room(x: np.ndarray, rate: int) -> np.ndarray:
    sos = np.vstack([
        signal.butter(2, 80, "highpass", fs=rate, output="sos"),
        signal.butter(2, 11500, "lowpass", fs=rate, output="sos"),
        peaking(280, -2.5, 1.0, rate),
        peaking(3200, 1.5, 1.2, rate),
    ])
    y = compress(signal.sosfilt(sos, x), rate)
    # early reflections, slightly darkened, like a plastered room
    refl = np.zeros_like(y)
    dark = signal.sosfilt(signal.butter(1, 4000, "lowpass", fs=rate, output="sos"), y)
    for ms, g in ((23, 0.12), (41, 0.07), (67, 0.045)):
        d = int(rate * ms / 1000)
        refl[d:] += dark[:-d] * g
    y = y + refl
    fade = min(len(y), int(0.015 * rate))
    y[:fade] *= np.linspace(0, 1, fade)
    # keep the line as loud as the dry take (mood volumes stay intact), then cap the peak
    rms_in, rms_out = np.sqrt(np.mean(x ** 2)), np.sqrt(np.mean(y ** 2))
    if rms_out > 0:
        y *= rms_in / rms_out
    peak = np.max(np.abs(y))
    return y * (0.95 / peak) if peak > 0.95 else y


if __name__ == "__main__":
    x, rate = read_wav(sys.argv[1])
    write_wav(sys.argv[2], room(x, rate), rate)
