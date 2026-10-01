#!/bin/bash
# Local AI 3D engine (TripoSR). Macs have no NVIDIA GPU, so it runs on CPU (slow, ~1-3 min).
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run setup_mac.sh first"; exit 1; }
if [ ! -f engines/TripoSR/run.py ]; then
  curl -L https://github.com/VAST-AI-Research/TripoSR/archive/refs/heads/main.zip -o engines/triposr.zip
  (cd engines && unzip -q triposr.zip && mv TripoSR-main TripoSR && rm triposr.zip)
fi
.venv/bin/python -m pip install torch torchvision
.venv/bin/python -m pip install omegaconf einops "transformers>=4.35,<4.46" "huggingface-hub<1.0" rembg onnxruntime "imageio[ffmpeg]" xatlas moderngl scikit-image
echo "Local AI engine installed."
