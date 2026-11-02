# The Man Who Stopped Wanting — video pipeline

Motion-comic adaptation of `source/story_script_final.pdf`, built from the panels in `source/pictographic script.pdf`, the location plates in `source/Aaravs study room.pdf`, and the character sheets in `source/plannee.pdf`.

## Pipeline
| Step | Command | Output |
|---|---|---|
| 1. Extract images from PDFs | `.\.venv\Scripts\python.exe -I tools\extract_assets.py` | `assets/panels`, `assets/scenes`, `assets/characters` |
| 2. Upscale + sharpen for video | `.\.venv\Scripts\python.exe -I tools\prepare_assets.py` | `public/img/{panels,scenes}/*.jpg` |
| 3. Sound effects + ambience beds | `.\.venv\Scripts\python.exe -I tools\make_sfx.py`; `.\.venv\Scripts\python.exe -I tools\make_ambience.py` | `public/sfx/*.wav` |
| 4. Voices + timelines | `.\.venv\Scripts\python.exe -I tools\voice.py all` | `public/audio/epNN/*.mp3` (+ room-processed `*.fxN.mp3`), `src/timelines/*.json` |
| 4b. Depth maps + grain (visual FX) | `.\.venv\Scripts\python.exe -I tools\depth_maps.py`; `.\.venv\Scripts\python.exe -I tools\make_fx.py` | `public/img/depth/*.png`, `public/fx/grain_*.png` |
| 4c. Dialogue clarity check (local Whisper) | `.\.venv\Scripts\python.exe -I tools\clarity_check.py` | word-error table, worst lines first |
| 5. Preview | `npx remotion studio` | browser studio |
| 6. Render (1080p, linear gain to ~-16 LUFS) | `.\tools\render_all.ps1` | `out/epNN.mp4`, `out/full_film.mp4` |

Edit the story in `episodes/epNN.json` (schema: `.claude/skills/episode-script`), voices in `tools/cast.json`, then rerun steps 4 and 6 (run 4b after adding a new photo plate). A line can carry `"say"` — what the voice reads when it differs from the caption text, e.g. `82%` spoken as "eighty-two percent".

Node: portable Node 24 at `%USERPROFILE%\tools\node-v24.22.1-win-x64` (render_all.ps1 adds it to PATH automatically).

## Episodes
| id | Title | Concept |
|---|---|---|
| ep01 | Opening — A Pencil on Paper | the dream |
| ep02 | Six Months In | adaptive preferences |
| ep03 | Same Week | counteradaptive preferences |
| ep04 | Nine Months In | learning |
| ep05 | One Year In | precommitment |
| ep06 | Thirteen Months In | manipulation |
| ep07 | Fifteen Months In | character planning |
| ep08 | Eighteen Months In | attribute weights |
| ep09 | Twenty Months In | addiction |
| ep10 | Two Years In | rationalization + state-dependence |
| ep11 | The Knock | Sen's capability argument |
| ep12 | Thin and Broad Rationality | consistency vs formation |
| ep13 | The Mirror | welfarism, Pareto, industrialisation paradox |
| ep14 | The Ending | three futures, final question |

Generated media (`public/img`, `public/audio`, `clips/*` intermediates, `out/`) is not in git; rebuild it with steps 2–6. The scipy/numpy/opencv packages in `.venv` are used by `voice_fx.py`, `make_ambience.py` and image clean-up.
