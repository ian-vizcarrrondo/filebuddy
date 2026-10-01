# File Buddy

Desktop companion that converts pretty much any file, and turns photos into 3D models (STL, 3MF, OBJ, GLB).

## Setup (one time)

**Windows (no Python needed - setup installs it for you)**
1. Double-click `setup_windows.bat`. If you don't have Python it installs it, then makes a "File Buddy" shortcut on your desktop.
2. (Optional, for free local AI 3D) double-click `install_ai_engine.bat` (~3 GB download).

**From VS Code:** File > Open Folder > FileBuddy. Then Terminal > Run Task > "1. Setup File Buddy". After that, Run Task > "Run File Buddy" (or press F5 once the Python extension is installed).

**Mac**
1. Install Python 3.11 from python.org.
2. In Terminal: `bash setup_mac.sh`, then double-click `Start File Buddy.command`.
3. (Optional) `bash install_ai_engine.sh`. Macs don't have NVIDIA, so local AI runs slow on CPU. Use Cloud AI instead.

Extras:
- Word/PowerPoint/Excel to PDF needs [LibreOffice](https://www.libreoffice.org) (free).
- Audio/video conversion works out of the box (ffmpeg comes bundled).

## What it converts

| You drop | You can get |
|---|---|
| PNG, JPG, WEBP, BMP, GIF, TIFF, ICO, HEIC | any of those + PDF + **STL relief/lithophane** |
| PDF | PNG, JPG, WEBP, TIFF (one per page), TXT, DOCX, HTML |
| DOCX, DOC, ODT, RTF, PPTX, XLS... | PDF (DOCX also to TXT) |
| TXT, MD | PDF, HTML, DOCX |
| CSV, XLSX, JSON | each other + HTML table |
| MP3, WAV, FLAC, OGG, M4A, AAC | each other |
| MP4, MOV, MKV, WEBM, AVI | each other + GIF + MP3/WAV (pull the audio) |
| STL, OBJ, PLY, GLB, GLTF, OFF, 3MF | STL, OBJ, PLY, GLB, OFF, 3MF |

You can drop whole folders, and batch-convert many files at once.

## Photo -> 3D

Three engines in the **Photo -> 3D** tab:

1. **Cloud AI (Meshy)** - most accurate. Takes up to 4 photos of the same object (front, back, side, top) and builds the full shape. Needs an API key from meshy.ai (paid credits). Paste it in **Settings**.
2. **Local AI (TripoSR)** - free, runs on your NVIDIA GPU, 1 photo, ~10-30 sec. Good shape, less fine detail.
3. **Relief / lithophane** - instant and offline. Turns the picture into a raised plate (great for logos, signs, lithophane night lights). It's not a full 3D object.

Every AI result gets cleaned up automatically: holes filled, floating bits removed, centered, set flat on the print bed, and scaled to your **Real size** (e.g. 153 mm wide for an Xbox controller).

### Getting the most accurate model (like the Xbox controller)
- Shoot on a plain table/wall with even light, no shadows, no hands.
- Take front, back, left side, and top shots. Use all 4 with Cloud AI.
- Fill the frame but don't cut anything off.
- Set Real size to the actual measurement so it prints at true size.
- Glossy/black plastic is hard for any AI. Soft light helps a lot.
- For a perfect fit (e.g. printing a part that attaches to it), AI won't be exact to the millimeter. Use calipers and check key dimensions in your slicer.

## Files
- `filebuddy/app.py` - the window
- `filebuddy/converters.py` - all file conversions (also works from the command line: `python -m filebuddy.converters file.pdf png`)
- `filebuddy/image3d.py` - photo-to-3D engines + mesh cleanup
- `engines/` - local AI engine gets installed here. `shims/torchmcubes.py` lets it run without needing a C++ compiler.
- Settings are saved in `~/.filebuddy/settings.json`
