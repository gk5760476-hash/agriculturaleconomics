"""Lip-sync each on-screen dialogue line onto its panel's Kling clip, using that line's own voice audio.

A line qualifies when its speaker is visible in the shot's image (clips/prompts.json "_faces") and the
image already has a Kling clip (clips/in/<clip_id>.json from kling.py). Lines longer than the clip are
split at the word nearest the middle and synced in two parts.
Results: clips/lips/<ep>_<NNN>[_a|_b].mp4 plus clips/lips/<ep>_<NNN>.json (part timing); voice.py attaches them.

Usage: python tools/lipsync.py --dry-run | --only ep02_002 | --limit 5 | (all)   [--parallel 3]
Keys/base URL: same as kling.py.
"""
import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kling import CLIPS, ROOT, call, load_env  # noqa: E402
from voice import npx  # noqa: E402

LIPS = CLIPS / "lips"
STATE = CLIPS / "lipsync_tasks.json"
FPS = 30


def split_point(line: dict) -> float:
    """Line-local seconds of the word start closest to the middle of the line."""
    starts = [(w["start"] - line["from"]) / FPS for page in line["pages"] for w in page][1:]
    mid = line["duration"] / FPS / 2
    return min(starts, key=lambda s: abs(s - mid))


def cut_audio(src: Path, dst: Path, start: float, end: float | None) -> None:
    args = [npx(), "remotion", "ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ss", f"{start:.3f}"]
    if end is not None:
        args += ["-to", f"{end:.3f}"]
    subprocess.run(args + ["-c:a", "libmp3lame", "-q:a", "3", str(dst)], check=True, cwd=ROOT)


def candidates() -> list[dict]:
    """One entry per lip-sync part, with a reason when it can't be sent yet."""
    faces = json.loads((CLIPS / "prompts.json").read_text(encoding="utf-8"))["_faces"]
    out = []
    for tl in sorted((ROOT / "src" / "timelines").glob("ep*.json")):
        t = json.loads(tl.read_text(encoding="utf-8"))
        for shot in t["shots"]:
            img = shot.get("img")
            for line in shot["lines"]:
                if line["who"] not in faces.get(img, []):
                    continue
                cid = img.replace("/", "_")
                meta_path = CLIPS / "in" / f"{cid}.json"
                meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
                clip_s = float(meta.get("duration") or 10)
                lip_id = f"{t['id']}_{Path(line['audio']).stem}"
                audio = ROOT / "public" / line["audio"]
                length = line["duration"] / FPS
                if length <= clip_s - 0.1:
                    parts = [("", 0.0, length)]
                else:
                    cut = split_point(line)
                    parts = [("_a", 0.0, cut), ("_b", cut, length)]
                reason = None
                if not meta:
                    reason = "no clip yet"
                elif not meta.get("video_id"):
                    reason = "clip has no Kling video_id"
                elif time.time() - meta["created"] > 29 * 86400:
                    reason = "clip older than 30 days (regenerate)"
                elif any(e - s > clip_s - 0.1 for _, s, e in parts):
                    reason = f"line {length:.1f}s too long even when split"
                audio_key = json.loads(audio.with_suffix(".json").read_text(encoding="utf-8"))["key"]
                for suffix, s, e in parts:
                    out.append({"lip_id": lip_id, "part_id": lip_id + suffix, "who": line["who"],
                                "audio": audio, "audio_key": audio_key,
                                "start_s": round(s, 3), "end_s": round(e, 3),
                                "split": bool(suffix), "clip_id": cid,
                                "video_id": meta.get("video_id"), "skip": reason})
    return out


def write_manifest(lip_id: str, parts: list[dict]) -> None:
    """Record the parts and the voice clip they are synced to; a re-voiced line's old takes move to stale/."""
    path = LIPS / f"{lip_id}.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if old and old.get("audio_key") != parts[0]["audio_key"]:
        (LIPS / "stale").mkdir(exist_ok=True)
        for p in old["parts"]:
            if (LIPS / p["file"]).exists():
                (LIPS / p["file"]).replace(LIPS / "stale" / p["file"])
    path.write_text(json.dumps({"parts": [
        {"file": f"{p['part_id']}.mp4", "start_s": p["start_s"], "end_s": p["end_s"]} for p in parts],
        "audio_key": parts[0]["audio_key"]}), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="line ids like ep02_002")
    ap.add_argument("--limit", type=int, help="max lines to send")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    load_env()
    LIPS.mkdir(parents=True, exist_ok=True)

    parts = candidates()
    by_line: dict[str, list[dict]] = {}
    for p in parts:
        by_line.setdefault(p["lip_id"], []).append(p)
    stale = set()
    for lid, ps in by_line.items():
        path = LIPS / f"{lid}.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")).get("audio_key") != ps[0]["audio_key"]:
            stale.add(lid)
    if not args.dry_run:
        for lid, ps in by_line.items():
            write_manifest(lid, ps)

    todo = [p for p in parts if p["lip_id"] in stale or not (LIPS / f"{p['part_id']}.mp4").exists()]
    if args.only:
        todo = [p for p in todo if p["lip_id"] in args.only]
    ready = [p for p in todo if not p["skip"]]
    if args.limit:
        keep = list(dict.fromkeys(p["lip_id"] for p in ready))[:args.limit]
        ready = [p for p in ready if p["lip_id"] in keep]
    print(f"{len({p['lip_id'] for p in todo})} lines ({len(todo)} parts) still to sync; "
          f"{len(ready)} parts ready, {sum(p['end_s'] - p['start_s'] for p in ready):.0f} s of audio")
    if args.dry_run:
        for p in todo:
            print(f"  {p['part_id']:12s} {p['who']:7s} {p['end_s'] - p['start_s']:5.1f}s  "
                  f"{p['clip_id']:16s} {p['skip'] or 'ready'}")
        return

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    active = {p["part_id"]: state[p["part_id"]] for p in ready if p["part_id"] in state}
    pending = [p for p in ready if p["part_id"] not in active]
    failed = []
    while pending or active:
        while pending and len(active) < args.parallel:
            p = pending.pop(0)
            audio = p["audio"]
            if p["split"]:
                audio = LIPS / f"{p['part_id']}.mp3"
                cut_audio(p["audio"], audio, p["start_s"], p["end_s"] if p["part_id"].endswith("_a") else None)
            data = call("POST", "/v1/videos/lip-sync", {"input": {
                "video_id": p["video_id"], "mode": "audio2video", "audio_type": "file",
                "audio_file": base64.b64encode(Path(audio).read_bytes()).decode()}})
            active[p["part_id"]] = state[p["part_id"]] = data["task_id"]
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
            print(f"submitted {p['part_id']} ({p['who']}) -> {data['task_id']}")
        time.sleep(15)
        for pid, tid in list(active.items()):
            data = call("GET", f"/v1/videos/lip-sync/{tid}")
            status = data.get("task_status")
            if status == "succeed":
                urllib.request.urlretrieve(data["task_result"]["videos"][0]["url"], LIPS / f"{pid}.mp4")
                print(f"done {pid}")
            elif status == "failed":
                print(f"FAILED {pid}: {data.get('task_status_msg')}")
                failed.append(pid)
            else:
                continue
            del active[pid]
            state.pop(pid, None)
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(f"finished; failed: {failed or 'none'}")


if __name__ == "__main__":
    main()
