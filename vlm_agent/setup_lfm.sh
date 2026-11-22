#!/usr/bin/env bash
# Adds the LFM3-Omni-2B profile files (Q4_K_M model + Q8_0 projector + LICENSE) to vlm_agent/models and records them in manifest.json.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
"$ROOT/.venv/bin/python" - <<PY
import hashlib, json, os
from huggingface_hub import hf_hub_download, HfApi
d = "$HERE/models"; repo = "LiquidAI/LFM3-Omni-2B-GGUF"
rev = HfApi().model_info(repo).sha
m = json.load(open(d + "/manifest.json"))
for fn in ("LFM3-Omni-2B-Q4_K_M.gguf", "mmproj-LFM3-Omni-2B-Q8_0.gguf", "LICENSE"):
    p = hf_hub_download(repo, fn, local_dir=d + "/lfm3_omni", revision=rev)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    m.setdefault("lfm3_omni", {"repo": repo, "revision": rev, "files": {}})["files"][fn] = dict(path=p, sha256=h, bytes=os.path.getsize(p))
json.dump(m, open(d + "/manifest.json", "w"), indent=1)
print("LFM_DONE")
PY
