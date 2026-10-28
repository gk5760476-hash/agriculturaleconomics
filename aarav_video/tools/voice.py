"""Voice every line of an episode with Edge TTS and write a frame-exact Remotion timeline.

Usage: python tools/voice.py ep02|all [--force]
Outputs: public/audio/<ep>/<NNN>.mp3, src/timelines/<ep>.json, src/timelines/index.ts
"""
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
LEAD_IN = 0.5      # silence before the first line of a shot
LINE_GAP = 0.35    # silence between lines in one shot
TAIL = 0.7         # silence after the last line of a shot
CARD_MIN = 2.5
PAGE_WORDS = 9

CAST = json.loads((ROOT / "tools" / "cast.json").read_text(encoding="utf-8"))

# Edge TTS has no emotion styles, so a line's `mood` shifts the speaker's rate (%), pitch (Hz) and volume (%).
MOODS = {
    "warm":      (-6, -1, -5),
    "tender":    (-10, -3, -12),
    "sad":       (-14, -6, -15),
    "weary":     (-12, -4, -10),
    "reflective": (-10, -2, -5),
    "firm":      (-4, -3, +10),
    "curt":      (+6, -2, +5),
    "defensive": (+8, +3, +10),
    "heated":    (+12, +6, +20),
    "pleading":  (+4, +5, +5),
    "worried":   (+5, +3, -5),
    "curious":   (+2, +4, 0),
    "hopeful":   (+4, +5, +5),
    "sceptical": (-4, -3, 0),
    "bitter":    (-2, -4, +5),
    "proud":     (+2, +2, +10),
    "insistent": (+8, +4, +15),
}


def delivery(who: str, mood: str | None) -> dict:
    """Edge TTS voice settings for one line: the speaker's cast entry shifted by the line's mood."""
    c = CAST[who]
    if mood and mood not in MOODS:
        raise ValueError(f"unknown mood {mood!r} for {who}; known: {', '.join(MOODS)}")
    dr, dp, dv = MOODS.get(mood, (0, 0, 0))
    return {"voice": c["voice"],
            "rate": f"{int(c['rate'].rstrip('%')) + dr:+d}%",
            "pitch": f"{int(c['pitch'].rstrip('Hz')) + dp:+d}Hz",
            "volume": f"{int(c.get('volume', '+0%').rstrip('%')) + dv:+d}%"}


async def synth(text: str, who: str, mood: str | None, mp3: Path, force: bool) -> list[dict]:
    """Return word timings [{text, start, end}] in seconds; reuse cached clip when unchanged."""
    c = delivery(who, mood)
    sig = f"{text}|{c['voice']}|{c['rate']}|{c['pitch']}"
    if c["volume"] != "+0%":
        sig += f"|{c['volume']}"
    key = hashlib.sha1(sig.encode()).hexdigest()[:12]
    meta = mp3.with_suffix(".json")
    if not force and mp3.exists() and meta.exists():
        cached = json.loads(meta.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return cached["words"]
    words, audio = [], bytearray()
    for attempt in range(4):
        try:
            words, audio = [], bytearray()
            comm = edge_tts.Communicate(text, c["voice"], rate=c["rate"], pitch=c["pitch"],
                                        volume=c["volume"], boundary="WordBoundary")
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    words.append({"text": chunk["text"], "start": start,
                                  "end": start + chunk["duration"] / 1e7})
            break
        except Exception as exc:  # network hiccups from the TTS service
            if attempt == 3:
                raise
            print(f"  retry {who}: {exc}")
            await asyncio.sleep(2 * (attempt + 1))
    mp3.write_bytes(bytes(audio))
    meta.write_text(json.dumps({"key": key, "words": words}), encoding="utf-8")
    return words


# Dry TTS sounds pasted on; tools/voice_fx.py puts it in a small room (EQ, gentle compression,
# faint early reflections). Bump FX_VERSION when that chain changes.
FX_VERSION = 2


def room_fx(mp3: Path) -> Path:
    """Processed copy of a voiced line, rebuilt when the raw clip or the chain changes."""
    out = mp3.with_name(f"{mp3.stem}.fx{FX_VERSION}.mp3")
    if not out.exists() or out.stat().st_mtime < mp3.stat().st_mtime:
        for old in mp3.parent.glob(f"{mp3.stem}.fx*.mp3"):
            old.unlink()
        dry, wet = mp3.with_suffix(".dry.wav"), mp3.with_suffix(".wet.wav")
        ff = [npx(), "remotion", "ffmpeg", "-y", "-loglevel", "error"]
        subprocess.run([*ff, "-i", str(mp3), "-ac", "1", "-ar", "48000", str(dry)], check=True, cwd=ROOT)
        subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "voice_fx.py"), str(dry), str(wet)], check=True)
        subprocess.run([*ff, "-i", str(wet), "-c:a", "libmp3lame", "-b:a", "192k", str(out)], check=True, cwd=ROOT)
        dry.unlink()
        wet.unlink()
    return out


# Ambience bed per shot (tools/make_ambience.py). Default is indoor room tone; title plates stay silent.
AMB_STREET = {"panels/p10_01", "panels/p18_01", "panels/p18_02", "panels/p12_01", "panels/p19_02",
              "scenes/p01_06"}
AMB_NIGHT = {"panels/p08_01", "panels/p08_02", "scenes/p01_03", "scenes/p01_15"}
AMB_NONE = {"panels/p03_02", "panels/p17_02", "panels/p19_01", "scenes/p01_10", "scenes/p01_16", "scenes/p01_19"}


def ambience(shot: dict) -> str | None:
    if "amb" in shot:
        return shot["amb"]
    img = shot.get("img")
    if not img or img in AMB_NONE:
        return None
    return "street" if img in AMB_STREET else "night" if img in AMB_NIGHT else "room"


def attach_punctuation(text: str, words: list[dict]) -> list[dict]:
    """Edge word boundaries drop punctuation; map them back onto the script's own tokens."""
    tokens = text.split()
    norm = [re.sub(r"\W", "", tok).lower() for tok in tokens]
    out, ti = [], -1
    for w in words:
        bare = re.sub(r"\W", "", w["text"]).lower()
        nxt = ti + 1
        if nxt < len(tokens) and (not bare or norm[nxt].startswith(bare) or bare in norm[nxt]):
            ti = nxt
        elif ti >= 0 and bare and bare in norm[ti]:
            out[-1]["end"] = w["end"]  # e.g. "I've" voiced as two boundaries
            continue
        else:
            j = next((k for k in range(nxt, len(tokens)) if bare and bare in norm[k]), None)
            ti = j if j is not None else min(nxt, len(tokens) - 1)
        # Keep any skipped script tokens (lone dashes, numbers voiced differently) visible.
        shown = " ".join(tokens[nxt:ti + 1]) if 0 <= nxt <= ti else w["text"]
        if out and out[-1]["token"] == ti:
            out[-1]["end"] = w["end"]
            continue
        out.append({**w, "text": shown, "token": ti})
    # Any trailing script tokens never voiced (rare) get appended to the last word.
    if out and ti + 1 < len(tokens):
        out[-1]["text"] += " " + " ".join(tokens[ti + 1:])
    return [{k: v for k, v in w.items() if k != "token"} for w in out]


def paginate(words: list[dict]) -> list[list[dict]]:
    """Break at sentence ends first, then commas/dashes, and only hard-split very long runs."""
    pages, cur = [], []
    for w in words:
        cur.append(w)
        n = len(cur)
        if (n >= 3 and re.search(r"[.?!:]$", w["text"])) \
                or (n >= PAGE_WORDS - 2 and re.search(r"[,;—]$", w["text"])) \
                or n >= PAGE_WORDS + 3:
            pages.append(cur)
            cur = []
    if cur:
        if pages and len(cur) <= 2:
            pages[-1].extend(cur)
        else:
            pages.append(cur)
    return pages


async def build(ep_id: str, force: bool) -> None:
    ep = json.loads((ROOT / "episodes" / f"{ep_id}.json").read_text(encoding="utf-8"))
    audio_dir = ROOT / "public" / "audio" / ep_id
    audio_dir.mkdir(parents=True, exist_ok=True)

    shots_out, t, n = [], 0.0, 0
    for shot in ep["shots"]:
        lines_out = []
        cursor = LEAD_IN if shot.get("lines") else 0.0
        for line in shot.get("lines", []):
            n += 1
            mp3 = audio_dir / f"{n:03d}.mp3"
            words = await synth(line["text"], line["who"], line.get("mood"), mp3, force)
            words = attach_punctuation(line["text"], words)
            dur = (words[-1]["end"] + 0.25) if words else 1.0
            start = t + cursor
            lip = attach_lip(f"{ep_id}_{n:03d}", mp3)
            # A silent speaker (the live presenter) keeps its voiced timing but plays no audio or caption.
            silent = {"silent": True} if CAST[line["who"]].get("silent") else {}
            played = mp3 if silent else room_fx(mp3)
            lines_out.append({
                **lip,
                **silent,
                "who": line["who"],
                "name": CAST[line["who"]]["name"],
                "color": CAST[line["who"]]["color"],
                "audio": f"audio/{ep_id}/{played.name}",
                "from": round(start * FPS),
                "duration": round(dur * FPS) + 1,
                "pages": [[{"text": w["text"], "start": round((start + w["start"]) * FPS),
                            "end": round((start + w["end"]) * FPS)} for w in page]
                          for page in paginate(words)],
            })
            cursor += dur + LINE_GAP + line.get("pause", 0.0)
            print(f"  {ep_id} {n:03d} {line['who']:8s} {dur:5.1f}s  {line['text'][:60]}")
        length = cursor - LINE_GAP + TAIL if lines_out else 0.0
        length = max(length, shot.get("minSec", CARD_MIN if "card" in shot else 2.0))
        extra = {}
        if "img" in shot:
            with Image.open(ROOT / "public" / "img" / f"{shot['img']}.jpg") as im:
                extra["aspect"] = round(im.width / im.height, 4)
            extra.update(attach_clip(shot["img"]))
        amb = ambience(shot)
        if amb:
            extra["amb"] = amb
        shots_out.append({**{k: v for k, v in shot.items() if k != "lines"}, **extra,
                          "from": round(t * FPS), "duration": round(length * FPS),
                          "lines": lines_out})
        t += length

    # Consecutive shots on the same clip play it as one continuous take, slowed (not below 0.5x)
    # to cover the run; once the clip runs out the renderer holds its last frame.
    i = 0
    while i < len(shots_out):
        j = i
        while j + 1 < len(shots_out) and shots_out[j + 1].get("clip") and \
                shots_out[j + 1].get("img") == shots_out[i].get("img"):
            j += 1
        if shots_out[i].get("clip"):
            run = shots_out[i:j + 1]
            total = sum(s["duration"] for s in run) / FPS
            rate = min(1.0, max(0.5, run[0]["clipDuration"] / total))
            elapsed = 0.0
            for s in run:
                s["clipRate"], s["clipStart"] = round(rate, 4), round(elapsed * rate, 3)
                elapsed += s["duration"] / FPS
        i = j + 1

    timeline = {"id": ep_id, "title": ep["title"], "subtitle": ep.get("subtitle", ""),
                "fps": FPS, "durationInFrames": round(t * FPS), "shots": shots_out}
    out_dir = ROOT / "src" / "timelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{ep_id}.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
    print(f"{ep_id}: {len(shots_out)} shots, {n} lines, {t:.1f}s")


def npx() -> str:
    found = shutil.which("npx")
    return found or str(Path.home() / "tools" / "node-v24.22.1-win-x64" / "npx.cmd")


def attach_clip(img: str) -> dict:
    """If an image-to-video clip exists for this image, publish it and return its shot fields."""
    cid = img.replace("/", "_")
    src = ROOT / "clips" / "in" / f"{cid}.mp4"
    if not src.exists():
        return {}
    pub = ROOT / "public" / "clips"
    pub.mkdir(parents=True, exist_ok=True)
    dst, last = pub / f"{cid}.mp4", pub / f"{cid}_last.jpg"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        shutil.copy2(src, dst)
        subprocess.run([npx(), "remotion", "ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.1",
                        "-i", str(dst), "-frames:v", "1", "-q:v", "2", str(last)], check=True, cwd=ROOT)
    probe = subprocess.run([npx(), "remotion", "ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height:format=duration", "-of", "json", str(dst)],
                           capture_output=True, text=True, check=True, cwd=ROOT)
    info = json.loads(probe.stdout)
    stream = info["streams"][0]
    extra = {}
    frozen = ROOT / "clips" / "frozen" / f"{cid}.png"
    if frozen.exists():  # original bubbles/titles pasted over the motion so text never warps
        shutil.copy2(frozen, pub / f"{cid}_frozen.png")
        extra["clipFreeze"] = f"clips/{cid}_frozen.png"
    return {**extra, "clip": f"clips/{cid}.mp4", "clipLast": f"clips/{last.name}",
            "clipDuration": float(info["format"]["duration"]),
            "clipAspect": round(stream["width"] / stream["height"], 4)}


def attach_lip(lip_id: str, mp3: Path) -> dict:
    """If lipsync.py produced every synced part for this line, publish them and return the line's `lips`."""
    lips_dir = ROOT / "clips" / "lips"
    manifest = lips_dir / f"{lip_id}.json"
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    parts = data["parts"]
    if not all((lips_dir / p["file"]).exists() for p in parts):
        return {}
    audio_key = json.loads(mp3.with_suffix(".json").read_text(encoding="utf-8"))["key"]
    if data.get("audio_key") != audio_key:
        print(f"  {lip_id}: lip-sync made from older audio; dropped until lipsync.py re-syncs it")
        return {}
    pub = ROOT / "public" / "lips"
    pub.mkdir(parents=True, exist_ok=True)
    out = []
    for p in parts:
        src, dst = lips_dir / p["file"], pub / p["file"]
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dst)
        probe = subprocess.run([npx(), "remotion", "ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "json", str(dst)],
                               capture_output=True, text=True, check=True, cwd=ROOT)
        stream = json.loads(probe.stdout)["streams"][0]
        out.append({"src": f"lips/{p['file']}", "from": round(p["start_s"] * FPS),
                    "duration": round((p["end_s"] - p["start_s"]) * FPS) + 1,
                    "aspect": round(stream["width"] / stream["height"], 4)})
    return {"lips": out}


def write_index() -> None:
    out_dir = ROOT / "src" / "timelines"
    ids = sorted(p.stem for p in out_dir.glob("ep*.json"))
    body = "".join(f"import {i} from './{i}.json';\n" for i in ids)
    body += "import type {Timeline} from '../types';\n\n"
    body += f"export const timelines = [{', '.join(ids)}] as Timeline[];\n"
    (out_dir / "index.ts").write_text(body, encoding="utf-8")


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    force = "--force" in sys.argv
    ids = sorted(p.stem for p in (ROOT / "episodes").glob("ep*.json")) if target == "all" else [target]
    for ep_id in ids:
        asyncio.run(build(ep_id, force))
    write_index()


if __name__ == "__main__":
    main()
