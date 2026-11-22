#!/usr/bin/env bash
# One-time setup of the local VLM runtime. Everything lands inside vlm_agent/ (delete the folder to remove it all).
#   vlm_agent/setup.sh            -> build llama.cpp (CUDA) + download Qwen3-VL-2B Q4_K_M and mmproj
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
LLAMA_TAG="${LLAMA_TAG:-v1.0.0}"
REPO="Qwen/Qwen3-VL-2B-Instruct-GGUF"
MODEL="Qwen3VL-2B-Instruct-Q4_K_M.gguf"
MMPROJ="mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"     # Q8_0 projector: smaller than F16, keeps the 4 GB budget

if [ ! -d "$HERE/third_party/llama.cpp" ]; then
  git clone --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp "$HERE/third_party/llama.cpp"
fi
cd "$HERE/third_party/llama.cpp"
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86 -DLLAMA_CURL=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j"$(nproc)" --target llama-server
COMMIT="$(git rev-parse HEAD 2>/dev/null || echo "$LLAMA_TAG")"

"$ROOT/.venv/bin/pip" install -q huggingface_hub
"$ROOT/.venv/bin/python" - <<PY
import hashlib, json, subprocess, os
from huggingface_hub import hf_hub_download
d = "$HERE/models"
files = {}
for fn in ("$MODEL", "$MMPROJ"):
    p = hf_hub_download("$REPO", fn, local_dir=d)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    files[fn] = dict(path=p, sha256=h, bytes=os.path.getsize(p))
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
json.dump(dict(repo="$REPO", files=files, llama_cpp_tag="$LLAMA_TAG", llama_cpp_commit="$COMMIT", gpu=gpu), open(d + "/manifest.json", "w"), indent=1)
print("manifest written")
PY
echo SETUP_DONE
