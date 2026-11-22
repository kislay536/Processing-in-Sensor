#!/usr/bin/env bash
# Downloads everything that is not stored in git. Safe to re-run: what is already there is skipped.
#   scripts/download.sh             yolo + vlm
#   scripts/download.sh yolo        yolo11n-pose.pt (via ultralytics, ~6 MB)
#   scripts/download.sh vlm         builds llama.cpp with CUDA and downloads Qwen3-VL-2B and LFM3-Omni-2B (GGUF, ~3 GB)
#   scripts/download.sh datasets    public datasets for rebuilding the face model (LFW ~240 MB, Imagenette ~100 MB, COCO128 ~7 MB)
#   scripts/download.sh all         everything above
# Needs scripts/setup.sh to have run first (uses .venv). Own recordings (data/sensors, data/rec, events/) cannot be downloaded.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -x .venv/bin/python ] || { echo "run scripts/setup.sh first"; exit 1; }

fetch() {   # fetch <url> <dest>   (resumable, retries)
  curl -fL --retry 3 --retry-delay 3 -C - --progress-bar -o "$2" "$1"
}

do_yolo() {
  if [ -f yolo11n-pose.pt ]; then echo "yolo11n-pose.pt: present"; return; fi
  echo "downloading yolo11n-pose.pt"
  .venv/bin/python -c "from ultralytics import YOLO; YOLO('yolo11n-pose.pt')"      # ultralytics fetches a bare weights name into the current directory
  [ -f yolo11n-pose.pt ] || { echo "yolo11n-pose.pt was not downloaded"; exit 1; }
}

do_vlm() {
  command -v cmake >/dev/null && command -v nvcc >/dev/null || { echo "cmake and the CUDA toolkit (nvcc) are needed to build llama.cpp"; exit 1; }
  bash vlm_agent/setup.sh          # clones + builds llama.cpp (CUDA), downloads Qwen3-VL-2B Q4_K_M + projector, writes vlm_agent/models/manifest.json
  bash vlm_agent/setup_lfm.sh      # adds LFM3-Omni-2B Q4_K_M + projector (the active profile in vlm_agent/profile.json)
}

do_datasets() {
  mkdir -p data/public
  if [ ! -d data/public/lfw_funneled ]; then
    [ -f data/public/lfw.tgz ] || fetch "https://ndownloader.figshare.com/files/5976015" data/public/lfw.tgz     # LFW, funneled
    tar -xzf data/public/lfw.tgz -C data/public
  fi
  if [ ! -d data/public/imagenette2-160 ]; then
    [ -f data/public/imagenette.tgz ] || fetch "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-160.tgz" data/public/imagenette.tgz
    tar -xzf data/public/imagenette.tgz -C data/public
  fi
  if [ ! -d data/public/coco128 ]; then
    [ -f data/public/coco128.zip ] || fetch "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip" data/public/coco128.zip
    unzip -q -o data/public/coco128.zip -d data/public
  fi
  for d in lfw_funneled imagenette2-160 coco128; do [ -d "data/public/$d" ] || { echo "missing data/public/$d after download"; exit 1; }; done
  echo "datasets ready in data/public. Rebuild the face training set with: .venv/bin/python model/build_public_dataset.py"
}

case "${1:-default}" in
  default)  do_yolo; do_vlm ;;
  yolo)     do_yolo ;;
  vlm)      do_vlm ;;
  datasets) do_datasets ;;
  all)      do_yolo; do_vlm; do_datasets ;;
  *)        sed -n '2,9p' "$0"; exit 1 ;;
esac
echo "DOWNLOAD_DONE"
