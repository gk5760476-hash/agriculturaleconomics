"""Write the live-narration cue sheet: every silent (presenter) line with its time in its episode and in the full film.

Usage: python tools/cue_sheet.py   ->  out/narration_cue_sheet.txt
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def stamp(frames: int, fps: int) -> str:
    s = frames // fps
    return f"{s // 60:02d}:{s % 60:02d}"


def main() -> None:
    out = ["THE MAN WHO STOPPED WANTING - live narration cue sheet",
           "Times: [full film] (episode). Lines with a name are voiced in the video; >> lines are yours.", ""]
    offset = 0
    for path in sorted((ROOT / "src" / "timelines").glob("ep*.json")):
        t = json.loads(path.read_text(encoding="utf-8"))
        fps = t["fps"]
        out.append(f"=== Episode {int(t['id'][2:])}: {t['title']} ({t['subtitle']}) - starts {stamp(offset, fps)}")
        for shot in t["shots"]:
            if shot.get("card"):
                out.append(f"[{stamp(offset + shot['from'], fps)}]          (title card: {shot['card'].replace(chr(10), ' ')})")
            for line in shot["lines"]:
                text = " ".join(w["text"] for page in line["pages"] for w in page)
                when = f"[{stamp(offset + line['from'], fps)}] ({stamp(line['from'], fps)})"
                if line.get("silent"):
                    secs = line["duration"] / fps
                    out.append(f"{when} >> {text}   [~{secs:.0f}s]")
                else:
                    out.append(f"{when}    {line['name'].upper()}: {text}")
        offset += t["durationInFrames"]
        out.append("")
    out.append(f"Total running time {stamp(offset, 30)}")
    dst = ROOT / "out" / "narration_cue_sheet.txt"
    dst.write_text("\n".join(out), encoding="utf-8-sig")
    print(dst)


if __name__ == "__main__":
    main()
