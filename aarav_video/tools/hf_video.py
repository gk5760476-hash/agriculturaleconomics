"""Generate image-to-video clips for clips/jobs.json on a free Hugging Face Space (no account, no key).

Uses the Wan 2.2 fast Space (ZeroGPU). Anonymous users get a small daily GPU quota, so when the quota
runs out the script waits and retries; it is resumable (finished clips in clips/in/ are skipped).
Each upload is centre-cropped to the Space's 832x480 aspect first, so clip pixels line up with
clips/frozen/<clip_id>.png (bubble overlay, see tools/freeze_masks.py).

Usage: python tools/hf_video.py [--only ID ...] [--limit N] [--seconds 5] [--wait-min 20] [--max-hours 24]
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "clips"
SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"
ASPECT = 832 / 480
NEGATIVE = ("changing art style, morphing faces, distorted hands, warped text, changing speech bubbles, "
            "camera movement, zoom, scene cut, flicker, blurry, low quality, static image")


def crop_for_model(src: Path, dst: Path) -> None:
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w / h > ASPECT:
            cw = round(h * ASPECT)
            im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
        else:
            ch = round(w / ASPECT)
            im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
        im.save(dst, quality=95)


def quota_wait(err: Exception, default_s: float) -> float | None:
    """Seconds to wait if this is a ZeroGPU quota error ("Try again in 23:56:16"), else None."""
    text = str(err)
    if not any(k in text.lower() for k in ("quota", "exceeded", "rate limit", "too many")):
        return None
    m = re.search(r"Try again in (\d+):(\d+):(\d+)", text)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + 30 if m else default_s


def hf_token() -> str | None:
    """Optional free Hugging Face token (HF_TOKEN in env or aarav_video/.env) for a larger quota."""
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("HF_TOKEN=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip().strip('"')
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--wait-min", type=float, default=20)
    ap.add_argument("--max-hours", type=float, default=24)
    args = ap.parse_args()

    jobs = json.loads((CLIPS / "jobs.json").read_text(encoding="utf-8"))
    todo = [j for j in jobs if not (CLIPS / "in" / f"{j['clip_id']}.mp4").exists()]
    if args.only:
        todo = [j for j in todo if j["clip_id"] in args.only]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} clips to generate on {SPACE}", flush=True)

    (CLIPS / "model_in").mkdir(exist_ok=True)
    deadline = time.time() + args.max_hours * 3600
    client = None
    for i, j in enumerate(todo, 1):
        cid = j["clip_id"]
        src = CLIPS / "model_in" / f"{cid}.jpg"
        crop_for_model(ROOT / j["image"], src)
        while True:
            try:
                client = client or Client(SPACE, token=hf_token(), verbose=False)
                t0 = time.time()
                video, _seed = client.predict(input_image=handle_file(str(src)), prompt=j["prompt"],
                                              negative_prompt=NEGATIVE, steps=6,
                                              duration_seconds=args.seconds, api_name="/generate_video")
                path = video["video"] if isinstance(video, dict) else video
                shutil.copy(path, CLIPS / "in" / f"{cid}.mp4")
                (CLIPS / "in" / f"{cid}.json").write_text(json.dumps(
                    {"source": SPACE, "created": int(time.time()), "duration": args.seconds}), encoding="utf-8")
                print(f"[{i}/{len(todo)}] done {cid} in {time.time() - t0:.0f}s", flush=True)
                break
            except Exception as e:  # quota, queue or network trouble: wait and retry the same clip
                client = None
                if time.time() > deadline:
                    print(f"stopping (max hours reached) at {cid}: {e}", flush=True)
                    return
                wait = quota_wait(e, args.wait_min * 60) or 60
                if time.time() + wait > deadline:
                    print(f"stopping: quota resets in {wait / 3600:.1f} h, past --max-hours ({cid})", flush=True)
                    return
                print(f"[{i}/{len(todo)}] {cid}: {type(e).__name__}: {str(e)[:200]} -> retry in {wait / 60:.0f} min",
                      flush=True)
                time.sleep(wait)
    print("all done", flush=True)


if __name__ == "__main__":
    main()
