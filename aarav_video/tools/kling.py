"""Generate the image-to-video clips in clips/jobs.json with the Kling API.

Keys come from the environment or aarav_video/.env (never commit it):
  KLING_ACCESS_KEY=...   KLING_SECRET_KEY=...   [KLING_API_BASE=https://api-singapore.klingai.com]

Usage:
  python tools/kling.py --only panels_p02_02        # pilot one clip
  python tools/kling.py --limit 5                   # next 5 not-yet-done clips
  python tools/kling.py                             # everything not done
  python tools/kling.py --dry-run                   # show what would be sent
Options: --mode std|pro (default std), --model kling-v2-1, --parallel 3, --duration-cap 10
State is kept in clips/kling_tasks.json so an interrupted run resumes without re-paying.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "clips"
STATE = CLIPS / "kling_tasks.json"
NEGATIVE = ("changing art style, morphing faces, extra limbs, distorted hands, warped text, moving speech bubbles, "
            "camera movement, zoom, scene cut, flicker, blur, new characters")


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token() -> str:
    """HS256 JWT as Kling requires: iss = access key, valid 30 min."""
    ak, sk = os.environ["KLING_ACCESS_KEY"], os.environ["KLING_SECRET_KEY"]
    now = int(time.time())
    head = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64url(json.dumps({"iss": ak, "exp": now + 1800, "nbf": now - 5}).encode())
    sig = b64url(hmac.new(sk.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def call(method: str, path: str, payload: dict | None = None) -> dict:
    base = os.environ.get("KLING_API_BASE", "https://api-singapore.klingai.com").rstrip("/")
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(payload).encode() if payload else None,
                                 headers={"Authorization": f"Bearer {token()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {path}: {e.read().decode(errors='replace')[:400]}") from None
    if out.get("code") not in (0, None):
        raise RuntimeError(f"Kling error {out.get('code')}: {out.get('message')}")
    return out["data"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--mode", default="std", choices=["std", "pro"])
    ap.add_argument("--model", default="kling-v2-1")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--duration-cap", type=int, default=10, choices=[5, 10])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    load_env()

    jobs = json.loads((CLIPS / "jobs.json").read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    todo = [j for j in jobs if not (CLIPS / "in" / f"{j['clip_id']}.mp4").exists()]
    if args.only:
        todo = [j for j in todo if j["clip_id"] in args.only]
    if args.limit:
        todo = todo[:args.limit]
    secs = sum(min(j["length_s"], args.duration_cap) for j in todo)
    print(f"{len(todo)} clips, {secs} s of video, model {args.model} mode {args.mode}")
    if args.dry_run:
        for j in todo:
            print(f"  {j['clip_id']:18s} {min(j['length_s'], args.duration_cap)}s  {j['prompt'][:90]}")
        return
    if not todo:
        return
    if not (os.environ.get("KLING_ACCESS_KEY") and os.environ.get("KLING_SECRET_KEY")):
        raise SystemExit("Set KLING_ACCESS_KEY and KLING_SECRET_KEY (environment or aarav_video/.env)")

    pending = list(todo)
    active: dict[str, str] = {j["clip_id"]: state[j["clip_id"]] for j in todo if j["clip_id"] in state}
    pending = [j for j in pending if j["clip_id"] not in active]
    failed = []
    while pending or active:
        while pending and len(active) < args.parallel:
            j = pending.pop(0)
            img = base64.b64encode((ROOT / j["image"]).read_bytes()).decode()
            data = call("POST", "/v1/videos/image2video", {
                "model_name": args.model, "mode": args.mode, "image": img,
                "prompt": j["prompt"][:2500], "negative_prompt": NEGATIVE, "cfg_scale": 0.6,
                "duration": str(min(j["length_s"], args.duration_cap)),
            })
            active[j["clip_id"]] = data["task_id"]
            state[j["clip_id"]] = data["task_id"]
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
            print(f"submitted {j['clip_id']} -> {data['task_id']}")
        time.sleep(15)
        for cid, tid in list(active.items()):
            data = call("GET", f"/v1/videos/image2video/{tid}")
            status = data.get("task_status")
            if status == "succeed":
                video = data["task_result"]["videos"][0]
                urllib.request.urlretrieve(video["url"], CLIPS / "in" / f"{cid}.mp4")
                # lipsync.py needs Kling's own video id (valid for 30 days) to lip-sync this clip.
                (CLIPS / "in" / f"{cid}.json").write_text(json.dumps({
                    "task_id": tid, "video_id": video.get("id"), "duration": video.get("duration"),
                    "created": int(time.time())}), encoding="utf-8")
                print(f"done {cid}")
            elif status == "failed":
                print(f"FAILED {cid}: {data.get('task_status_msg')}")
                failed.append(cid)
            else:
                continue
            del active[cid]
            state.pop(cid, None)
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(f"finished; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
