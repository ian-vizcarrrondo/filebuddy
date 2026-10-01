@echo off
title File Buddy - install local AI 3D engine (TripoSR)
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe ( echo Run setup_windows.bat first. & pause & exit /b 1 )
echo === Downloading TripoSR ===
if not exist engines\TripoSR\run.py (
  powershell -NoProfile -Command "Invoke-WebRequest https://github.com/VAST-AI-Research/TripoSR/archive/refs/heads/main.zip -OutFile engines\triposr.zip; Expand-Archive engines\triposr.zip engines -Force; Rename-Item engines\TripoSR-main TripoSR; Remove-Item engines\triposr.zip"
)
echo === Installing PyTorch with NVIDIA CUDA (big download, ~3 GB) ===
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 || (echo PyTorch install failed & pause & exit /b 1)
echo === Installing AI engine packages ===
.venv\Scripts\python -m pip install omegaconf einops "transformers>=4.35,<4.46" "huggingface-hub<1.0" rembg onnxruntime "imageio[ffmpeg]" xatlas moderngl scikit-image || (echo Install failed & pause & exit /b 1)
.venv\Scripts\python -c "import torch;print('GPU ready:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
echo.
echo Local AI engine installed. The model (~1.7 GB) downloads the first time you use it.
pause
