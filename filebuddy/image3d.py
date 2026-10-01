"""
File Buddy - picture to 3D.

Three engines:
  1. relief  : picture -> raised surface / lithophane STL (offline, instant, exact to the picture)
  2. triposr : local AI on your NVIDIA GPU (free, ~10-30 s per model)
  3. meshy   : cloud AI (best accuracy, takes 1-4 photos from different angles, needs API key)

All engines finish with `finish_mesh()` which repairs the mesh, scales it to a
real-world size in millimetres, and sits it flat on the print bed.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ROOT / "engines"
TRIPOSR_DIR = ENGINES / "TripoSR"

Log = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


def _unique(out_dir: Path, stem: str, ext: str) -> Path:
    p = out_dir / f"{stem}.{ext}"
    i = 1
    while p.exists():
        p = out_dir / f"{stem} ({i}).{ext}"
        i += 1
    return p


# ---------------------------------------------------------------------------
# Shared clean-up / sizing
# ---------------------------------------------------------------------------
def finish_mesh(mesh_path: Path, out_path: Path, real_size_mm: float = 0.0,
                size_axis: str = "longest", log: Log = _noop) -> Path:
    """Repair, scale to real size, place on bed, export in out_path's format."""
    import trimesh

    loaded = trimesh.load(str(mesh_path), force="scene")
    mesh = loaded.to_geometry() if isinstance(loaded, trimesh.Scene) else loaded

    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
    # Keep only the biggest piece (drops floating AI "dust")
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        mesh = max(parts, key=lambda m: len(m.faces))
        log(f"Removed {len(parts) - 1} tiny floating bits.")

    ext = (mesh.extents if mesh.extents is not None else np.ones(3))
    if real_size_mm and real_size_mm > 0:
        idx = {"x (width)": 0, "y (depth)": 1, "z (height)": 2}.get(size_axis)
        current = ext[idx] if idx is not None else ext.max()
        if current > 0:
            mesh.apply_scale(real_size_mm / current)
            log(f"Scaled to {real_size_mm:g} mm on {size_axis}.")

    # Center on X/Y, sit on Z=0 (print bed)
    b = mesh.bounds
    mesh.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])

    fmt = out_path.suffix.lstrip(".").lower()
    mesh.export(str(out_path), file_type=fmt)
    e = mesh.extents
    log(f"Final size: {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm, "
        f"{len(mesh.faces):,} triangles, watertight={mesh.is_watertight}")
    return out_path


# ---------------------------------------------------------------------------
# 1. Relief / lithophane (pure numpy, no AI)
# ---------------------------------------------------------------------------
def image_to_relief_stl(src: Path, out_dir: Path, opts: dict, log: Log = _noop) -> Path:
    from PIL import Image, ImageFilter, ImageOps
    import trimesh

    width_mm = float(opts.get("width_mm", 100))
    max_h = float(opts.get("relief_height_mm", 3.0))
    base = float(opts.get("base_mm", 0.8))
    detail = int(opts.get("detail_px", 300))      # samples along the long side
    mode = opts.get("relief_mode", "lithophane")  # lithophane: dark = thick ; emboss: bright = tall
    smooth = float(opts.get("smooth", 0.6))
    fmt = opts.get("format", "stl")

    img = Image.open(src)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    g = img.convert("L")
    scale = detail / max(g.size)
    g = g.resize((max(2, round(g.width * scale)), max(2, round(g.height * scale))), Image.LANCZOS)
    if smooth > 0:
        g = g.filter(ImageFilter.GaussianBlur(smooth))

    a = np.asarray(g, dtype=np.float32) / 255.0
    h = (1.0 - a) if mode == "lithophane" else a
    z = base + h * max_h                                   # (rows, cols)
    rows, cols = z.shape
    step = width_mm / (cols - 1)

    xs = np.arange(cols) * step
    ys = (rows - 1 - np.arange(rows)) * step               # flip so the picture isn't mirrored
    X, Y = np.meshgrid(xs, ys)
    top = np.column_stack([X.ravel(), Y.ravel(), z.ravel()])
    bot = np.column_stack([X.ravel(), Y.ravel(), np.zeros(rows * cols)])
    verts = np.vstack([top, bot])
    n = rows * cols

    idx = np.arange(n).reshape(rows, cols)
    a0, b0 = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c0, d0 = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    top_f = np.vstack([np.column_stack([a0, c0, b0]), np.column_stack([b0, c0, d0])])
    bot_f = top_f[:, ::-1] + n

    # side walls along the border loop
    ring = np.concatenate([idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]])
    nxt = np.roll(ring, -1)
    walls = np.vstack([np.column_stack([ring, nxt, ring + n]),
                       np.column_stack([nxt, nxt + n, ring + n])])

    mesh = trimesh.Trimesh(vertices=verts, faces=np.vstack([top_f, bot_f, walls]), process=True)
    trimesh.repair.fix_normals(mesh)
    out = _unique(out_dir, f"{src.stem}_{mode}", fmt)
    mesh.export(str(out), file_type=fmt)
    log(f"Relief: {mesh.extents[0]:.1f} x {mesh.extents[1]:.1f} x {mesh.extents[2]:.1f} mm, "
        f"{len(mesh.faces):,} triangles, watertight={mesh.is_watertight}")
    return out


# ---------------------------------------------------------------------------
# 2. TripoSR (local AI, NVIDIA GPU)
# ---------------------------------------------------------------------------
def triposr_installed() -> bool:
    return (TRIPOSR_DIR / "run.py").exists()


def image_to_3d_triposr(src: Path, out_dir: Path, opts: dict, log: Log = _noop) -> Path:
    if not triposr_installed():
        raise RuntimeError("The local AI engine isn't installed yet. Run install_ai_engine "
                           "(.bat on Windows / .sh on Mac) in the File Buddy folder first.")
    res = int(opts.get("mc_resolution", 320))
    fg = float(opts.get("foreground_ratio", 0.85))
    fmt = opts.get("format", "stl")
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, str(ENGINES / "triposr_runner.py"), str(src),
               "--output-dir", tmp, "--mc-resolution", str(res),
               "--foreground-ratio", str(fg), "--model-save-format", "obj"]
        if opts.get("no_remove_bg"):
            cmd.append("--no-remove-bg")
        log(f"Running local AI (mesh resolution {res})... first run downloads the model (~1.7 GB).")
        proc = subprocess.Popen(cmd, cwd=str(TRIPOSR_DIR), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if line:
                log("  " + line[-200:])
        if proc.wait() != 0:
            raise RuntimeError("Local AI engine failed (see log above).")
        mesh = Path(tmp) / "0" / "mesh.obj"
        if not mesh.exists():
            raise RuntimeError("Local AI engine didn't produce a mesh.")
        out = _unique(out_dir, f"{src.stem}_3d", fmt)
        return finish_mesh(mesh, out, float(opts.get("real_size_mm", 0)),
                           opts.get("size_axis", "longest"), log)


# ---------------------------------------------------------------------------
# 3. Meshy (cloud AI, best quality, 1-4 photos)
# ---------------------------------------------------------------------------
MESHY_BASE = "https://api.meshy.ai/openapi/v1"


def _data_uri(path: Path) -> str:
    from PIL import Image, ImageOps
    import io

    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if max(img.size) > 2048:  # keep uploads reasonable
        img.thumbnail((2048, 2048))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def image_to_3d_meshy(images: list[Path], out_dir: Path, opts: dict, log: Log = _noop) -> Path:
    import requests

    key = opts.get("meshy_key") or os.environ.get("MESHY_API_KEY", "")
    if not key:
        raise RuntimeError("Add your Meshy API key in Settings first (meshy.ai -> API).")
    headers = {"Authorization": f"Bearer {key}"}
    fmt = opts.get("format", "stl")
    want_formats = sorted({"glb", "stl", fmt} & {"glb", "obj", "fbx", "stl", "usdz", "3mf"})

    body = {
        "ai_model": opts.get("meshy_model", "latest"),
        "topology": "triangle",
        "target_polycount": int(opts.get("polycount", 300000)),
        "should_remesh": bool(opts.get("remesh", False)),
        "should_texture": bool(opts.get("texture", False)),
        "target_formats": want_formats,
    }
    if opts.get("geometry_resolution"):
        body["geometry_resolution"] = opts["geometry_resolution"]

    if len(images) > 1:
        endpoint = f"{MESHY_BASE}/multi-image-to-3d"
        body["image_urls"] = [_data_uri(p) for p in images[:4]]
        if body.get("geometry_resolution") == "4k":  # multi-image tops out at 2k
            body["geometry_resolution"] = "2k"
        log(f"Uploading {min(len(images), 4)} photos to Meshy (multi-angle = more accurate)...")
    else:
        endpoint = f"{MESHY_BASE}/image-to-3d"
        body["image_url"] = _data_uri(images[0])
        log("Uploading photo to Meshy...")

    r = requests.post(endpoint, headers=headers, json=body, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Meshy error {r.status_code}: {r.text[:300]}")
    task_id = r.json().get("result")
    log(f"Meshy task started: {task_id}")

    last = -1
    while True:
        time.sleep(5)
        t = requests.get(f"{endpoint}/{task_id}", headers=headers, timeout=60).json()
        status, prog = t.get("status"), t.get("progress", 0)
        if prog != last:
            log(f"  Meshy: {status} {prog}%")
            last = prog
        if status == "SUCCEEDED":
            break
        if status in {"FAILED", "CANCELED"}:
            msg = (t.get("task_error") or {}).get("message", "")
            raise RuntimeError(f"Meshy task {status.lower()}. {msg}")

    urls = t.get("model_urls", {})
    pick = fmt if fmt in urls else ("glb" if "glb" in urls else next(iter(urls)))
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f"meshy.{pick}"
        raw.write_bytes(requests.get(urls[pick], timeout=300).content)
        stem = images[0].stem
        if opts.get("texture") and "glb" in urls:  # keep the colored version too
            colored = _unique(out_dir, f"{stem}_3d_color", "glb")
            colored.write_bytes(requests.get(urls["glb"], timeout=300).content)
            log(f"Saved colored model: {colored.name}")
        out = _unique(out_dir, f"{stem}_3d", fmt)
        return finish_mesh(raw, out, float(opts.get("real_size_mm", 0)),
                           opts.get("size_axis", "longest"), log)
