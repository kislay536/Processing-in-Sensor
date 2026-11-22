# vlm_agent - local scene-report agent (self-contained, delete this folder to remove it)

What it does: every chunk that reaches the laptop (motion chunk or periodic scene-context chunk) is described by
**Qwen3-VL-2B-Instruct (GGUF Q4_K_M + Q8_0 mmproj)** running in a resident `llama-server` (CUDA) on the 4 GB GPU.
Two profiles (`profiles.py`, switchable from the dashboard): `qwen3vl_rgb` (RGB only) and `lfm3_omni_av` (LFM3-Omni-2B: frames + the audio of the same interval, with a gated speech pass). `thermal` prompts exist but IR is not streamed from the board.

Files
- `setup_lfm.sh` adds the LFM3-Omni files; `checkpoints/qwen3vl_rgb_v1/` = saved Qwen setup with RESTORE.md; `profile.json` = last active profile
- `setup.sh`    one-time: builds llama.cpp (CUDA) into `third_party/`, downloads the models into `models/`, writes `models/manifest.json`
- `server.py`   starts/supervises llama-server (one slot, context 4096, temperature 0, max 256 new tokens), stays loaded while idle
- `agent.py`    validate frames -> 4 s windows (<= 4 frames, long edge 336 px) -> one stateless request per window -> synthesis -> JSON/Markdown
- `prompts.py`  prompts `scene-v1` (spec wording)
- `tests/`      checks from the project root: `.venv/bin/python -m vlm_agent.tests.check_agent` (Qwen) and `-m vlm_agent.tests.check_av` (LFM + switch; needs tests/_step3_* from tests/step3_audio.py)
- `logs/`       setup and llama-server logs

Hooks outside this folder (all guarded by try/except, the dashboard works without this folder):
`gpu/analyzers/__init__.py` (analyzer entry), `ui/server.py` (start, status, analysis worker), `ui/index.html` (rendering).

Output per chunk: `events/event_NNNN/scene.json` (+ `scene` key in `report.json`, section in `report.md`).
Limits: 2B 4-bit model, multi-image approximation of video, timestamps are laptop-clock times at frame read; thermal accuracy unvalidated and not wired.
