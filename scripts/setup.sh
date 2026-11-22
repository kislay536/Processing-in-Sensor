#!/usr/bin/env bash
# PiSe laptop-side setup: checks the tools, creates .venv, installs requirements.txt.
#   scripts/setup.sh            create / update the Python environment
#   scripts/setup.sh --test     ... and run the software-only unit tests afterwards
# Then run scripts/download.sh for the model weights, llama.cpp and (optionally) the public datasets.
# The Zedboard side (Vivado / Vitis HLS 2024.2) is not touched here; see CONTEXT.md and board/sw/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"

fail=0
need()  { command -v "$1" >/dev/null 2>&1 || { echo "MISSING (required): $1 - $2"; fail=1; }; }
want()  { command -v "$1" >/dev/null 2>&1 || echo "note: $1 not found - $2"; }

need "$PY" "Python 3.10 or newer"
need git "git"
[ "$fail" = 0 ] || exit 1
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Python 3.10+ needed, found: $("$PY" --version)"; exit 1; }
"$PY" -c 'import venv, ensurepip' 2>/dev/null || { echo "python venv module missing (Ubuntu: sudo apt install python3-venv)"; exit 1; }

want nvidia-smi "NVIDIA driver (GPU analysis, energy measurement)"
want nvcc       "CUDA toolkit (needed to build llama.cpp in scripts/download.sh vlm)"
want cmake      "needed to build llama.cpp"
want arecord    "alsa-utils (microphone capture)"
want v4l2-ctl   "v4l-utils (camera inspection, optional)"
[ -d /tools/Xilinx/Vivado ] || echo "note: /tools/Xilinx not found - only needed to rebuild the FPGA design, not to run the dashboard"

if [ ! -x .venv/bin/python ]; then
  echo "creating .venv"
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

.venv/bin/python - <<'PYEOF'
import cv2, numpy, torch
print(f"numpy {numpy.__version__}, opencv {cv2.__version__}, torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
PYEOF

if [ "${1:-}" = "--test" ]; then
  .venv/bin/python tests/test_all.py
fi
echo "SETUP_DONE - next: scripts/download.sh"
