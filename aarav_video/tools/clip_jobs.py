"""Build the image-to-video job list: one clip per image the film uses.

Writes clips/jobs.json, clips/JOBS.md and clips/upload/<clip_id>.jpg (the image to upload).
Finished clips go in clips/in/<clip_id>.mp4 — voice.py picks them up automatically.
Usage: python tools/clip_jobs.py
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CLIPS = ROOT / "clips"


def clip_id(img: str) -> str:
    return img.replace("/", "_")


def main() -> None:
    prompts = json.loads((CLIPS / "prompts.json").read_text(encoding="utf-8"))
    style, skip = prompts["_style"], set(prompts["_skip"])

    usage: dict[str, dict] = {}
    for tl in sorted((ROOT / "src" / "timelines").glob("ep*.json")):
        t = json.loads(tl.read_text(encoding="utf-8"))
        for s in t["shots"]:
            if "img" in s and s["img"] not in skip:
                u = usage.setdefault(s["img"], {"episodes": [], "longest_shot_s": 0.0})
                if t["id"] not in u["episodes"]:
                    u["episodes"].append(t["id"])
                u["longest_shot_s"] = max(u["longest_shot_s"], round(s["duration"] / 30, 1))

    (CLIPS / "upload").mkdir(parents=True, exist_ok=True)
    (CLIPS / "in").mkdir(parents=True, exist_ok=True)
    jobs = []
    for img, u in usage.items():
        if img not in prompts:
            raise SystemExit(f"no prompt for {img} in clips/prompts.json")
        cid = clip_id(img)
        # Upload a clean 16:9-ish source at the original detail (from the upscaled master).
        with Image.open(ROOT / "public" / "img" / f"{img}.jpg") as im:
            im = im.convert("RGB")
            im.thumbnail((1920, 1920))
            im.save(CLIPS / "upload" / f"{cid}.jpg", quality=95)
        jobs.append({
            "clip_id": cid,
            "image": f"clips/upload/{cid}.jpg",
            # Generators offer 5 s or 10 s; longer shots are slowed/held by the renderer.
            # Dialogue panels always get 10 s so lip-sync has room for whole lines.
            "length_s": 10 if u["longest_shot_s"] > 7 or img in prompts["_faces"] else 5,
            "episodes": u["episodes"],
            "prompt": f"{prompts[img]} {style}",
            "done": (CLIPS / "in" / f"{cid}.mp4").exists(),
        })

    (CLIPS / "jobs.json").write_text(json.dumps(jobs, indent=1), encoding="utf-8")
    rows = ["| # | clip_id (save as clips/in/<clip_id>.mp4) | length | episodes | done | prompt |",
            "|---|---|---|---|---|---|"]
    for i, j in enumerate(jobs, 1):
        rows.append(f"| {i} | `{j['clip_id']}` | {j['length_s']} s | {', '.join(j['episodes'])} | "
                    f"{'yes' if j['done'] else ''} | {j['prompt'].replace('|', '/')} |")
    (CLIPS / "JOBS.md").write_text(
        "# Image-to-video jobs\n\nUpload `clips/upload/<clip_id>.jpg`, paste the prompt, generate at 16:9, "
        "download the MP4 as `clips/in/<clip_id>.mp4`. Then run `tools/voice.py all` and `tools/render_all.ps1`.\n\n"
        + "\n".join(rows) + "\n", encoding="utf-8")
    done = sum(j["done"] for j in jobs)
    print(f"{len(jobs)} jobs ({done} done), {sum(j['length_s'] for j in jobs)} s of footage to generate")


if __name__ == "__main__":
    main()
