"""Generate the ending image (script: "Aarav sits at the table. The form in front of him. He picks up a pencil")
by editing the classroom plate with FLUX.1 Kontext on a free Hugging Face Space (ZeroGPU).

Needs quota: set HF_TOKEN in aarav_video/.env (free 'Read' token) or wait for the anonymous daily reset.
Takes are saved to clips/classroom_takes/; copy the chosen one to assets/scenes/p01_17_<w>x<h>.png, run
prepare_assets.py, and point the "What do I actually want?" shot in episodes/ep14.json at scenes/p01_17.

Usage: python tools/classroom_aarav.py [takes]
"""
import shutil
import sys
from pathlib import Path

from gradio_client import Client, handle_file

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I drops the script dir from sys.path
from hf_video import hf_token  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "clips" / "classroom_takes"
SPACE = "black-forest-labs/FLUX.1-Kontext-Dev"
PROMPT = ("Add a 17-year-old Indian boy with messy dark hair, wearing a mustard-yellow V-neck sweater over a white "
          "collared shirt, sitting on a wooden chair at the wooden table in the foreground, facing the camera, the "
          "paper form lying on the table in front of him, holding a pencil in his right hand above the form, "
          "thoughtful quiet expression, looking down at the form. Keep everything else in the classroom exactly the "
          "same: empty desks, warm sunlight, ceiling fan, blackboard, same camera angle, photorealistic.")


def main(takes: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    room = ROOT / "assets" / "scenes" / "p01_07_826x461.png"
    client = Client(SPACE, token=hf_token(), verbose=False)
    for k in range(takes):
        res, seed = client.predict(input_image=handle_file(str(room)), prompt=PROMPT, seed=0, randomize_seed=True,
                                   guidance_scale=2.5, steps=28, api_name="/infer")
        dst = OUT / f"take{k}_{int(seed)}.png"
        shutil.copy(res if isinstance(res, str) else res["path"], dst)
        print("saved", dst, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
