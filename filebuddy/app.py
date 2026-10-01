"""File Buddy - desktop companion for converting files and turning photos into 3D models."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QMenu, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
    QSpinBox, QStackedWidget, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from . import converters as conv
from . import image3d
from .buddy import DesktopBuddy, buddy_pixmap, make_icons

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path.home() / ".filebuddy" / "settings.json"
DEFAULT_OUT = Path.home() / "Documents" / "File Buddy"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_settings(s: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(s, indent=2))


# ---------------------------------------------------------------------------
# Background worker (keeps the window from freezing)
# ---------------------------------------------------------------------------
class Worker(QObject):
    log = Signal(str)
    progress = Signal(int, int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(self.log.emit, self.progress.emit) or [])
        except Exception as exc:  # noqa: BLE001
            self.log.emit(traceback.format_exc(limit=2))
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Drop-friendly file list
# ---------------------------------------------------------------------------
class DropList(QListWidget):
    changed = Signal()

    def __init__(self, placeholder: str, max_files: int | None = None, filter_fn=None):
        super().__init__()
        self.placeholder = placeholder
        self.max_files = max_files
        self.filter_fn = filter_fn
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(150)
        self.setObjectName("drop")

    def paintEvent(self, e):  # show hint text when empty
        super().paintEvent(e)
        if self.count() == 0:
            from PySide6.QtGui import QPainter

            p = QPainter(self.viewport())
            p.setPen(Qt.gray)
            p.drawText(self.viewport().rect(), Qt.AlignCenter, self.placeholder)

    def dragEnterEvent(self, e):
        e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_paths([u.toLocalFile() for u in e.mimeData().urls()])

    def add_paths(self, paths):
        existing = set(self.paths())
        for p in paths:
            pp = Path(p)
            files = [f for f in pp.rglob("*") if f.is_file()] if pp.is_dir() else [pp]
            for f in files:
                if str(f) in existing or (self.filter_fn and not self.filter_fn(f)):
                    continue
                if self.max_files and self.count() >= self.max_files:
                    break
                item = QListWidgetItem(f"{f.name}    ({conv.category_of(f)})")
                item.setData(Qt.UserRole, str(f))
                self.addItem(item)
                existing.add(str(f))
        self.changed.emit()

    def paths(self) -> list[str]:
        return [self.item(i).data(Qt.UserRole) for i in range(self.count())]


def open_path(p: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))


# ---------------------------------------------------------------------------
# Convert tab
# ---------------------------------------------------------------------------
class ConvertTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)

        self.files = DropList("Drop any files or folders here\n(images, PDFs, docs, audio, video, 3D models...)")
        self.files.changed.connect(self.refresh_targets)
        lay.addWidget(self.files)

        row = QHBoxLayout()
        add = QPushButton("Add files...")
        add.clicked.connect(self.pick)
        rem = QPushButton("Remove selected")
        rem.clicked.connect(self.remove_sel)
        clr = QPushButton("Clear")
        clr.clicked.connect(lambda: (self.files.clear(), self.refresh_targets()))
        row.addWidget(add)
        row.addWidget(rem)
        row.addWidget(clr)
        row.addStretch()
        lay.addLayout(row)

        form = QFormLayout()
        self.target = QComboBox()
        self.target.setMinimumWidth(220)
        form.addRow("Convert to:", self.target)

        self.quality = QSpinBox()
        self.quality.setRange(10, 100)
        self.quality.setValue(92)
        self.quality.setSuffix(" %")
        form.addRow("Image quality:", self.quality)

        self.dpi = QSpinBox()
        self.dpi.setRange(72, 600)
        self.dpi.setValue(200)
        self.dpi.setSuffix(" dpi")
        form.addRow("PDF page resolution:", self.dpi)

        out_row = QHBoxLayout()
        self.same_folder = QCheckBox("Save next to the original file")
        self.same_folder.setChecked(True)
        self.out_dir = QLineEdit(main.settings.get("out_dir", str(DEFAULT_OUT)))
        browse = QPushButton("...")
        browse.setFixedWidth(32)
        browse.clicked.connect(self.pick_out)
        out_row.addWidget(self.same_folder)
        out_row.addWidget(self.out_dir, 1)
        out_row.addWidget(browse)
        form.addRow("Output:", out_row)
        lay.addLayout(form)

        self.go = QPushButton("Convert")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self.run)
        lay.addWidget(self.go)
        self.refresh_targets()

    def pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files")
        self.files.add_paths(paths)

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.out_dir.text())
        if d:
            self.out_dir.setText(d)
            self.same_folder.setChecked(False)

    def remove_sel(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))
        self.refresh_targets()

    def refresh_targets(self):
        paths = self.files.paths()
        current = self.target.currentText()
        self.target.clear()
        if not paths:
            self.target.addItem("(add files first)")
            self.go.setEnabled(False)
            return
        common = None
        for p in paths:
            t = conv.targets_for(p)
            common = t if common is None else [x for x in common if x in t]
        if not common:
            self.target.addItem("(no shared format - convert one type at a time)")
            self.go.setEnabled(False)
            return
        self.target.addItems(common)
        if current in common:
            self.target.setCurrentText(current)
        self.go.setEnabled(True)

    def run(self):
        paths = self.files.paths()
        target = self.target.currentText()
        opts = {"quality": self.quality.value(), "dpi": self.dpi.value()}
        same = self.same_folder.isChecked()
        out_dir = Path(self.out_dir.text())

        def job(log, progress):
            outs = []
            for i, p in enumerate(paths):
                progress(i, len(paths))
                dest = Path(p).parent if same else out_dir
                log(f"Converting {Path(p).name} -> .{target.split()[0]}")
                try:
                    res = conv.convert(p, dest, target, opts)
                    outs += res
                    for r in res:
                        log(f"  saved {r}")
                except Exception as exc:  # noqa: BLE001
                    log(f"  FAILED: {exc}")
            progress(len(paths), len(paths))
            return outs

        self.main.start(job, self.go)


class QuickConvertDialog(QDialog):
    """Small tray companion for one-file conversions."""

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("File Buddy Quick Convert")
        self.setWindowIcon(main.windowIcon())
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        title = QLabel("Quick Convert")
        title.setFont(QFont(title.font().family(), 16, QFont.Bold))
        subtitle = QLabel("Drop one file here, pick a new format, and you're done.")
        subtitle.setStyleSheet("color:#8a93a8")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.files = DropList("Drop a file here", max_files=1)
        self.files.setMinimumHeight(105)
        self.files.changed.connect(self.refresh_targets)
        layout.addWidget(self.files)

        browse = QPushButton("Choose file...")
        browse.clicked.connect(self.pick)
        layout.addWidget(browse)

        form = QFormLayout()
        self.target = QComboBox()
        form.addRow("Change to:", self.target)
        self.same_folder = QCheckBox("Save beside original")
        self.same_folder.setChecked(True)
        form.addRow("Output:", self.same_folder)
        layout.addLayout(form)

        self.status = QLabel("Ready when you are.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#aab4ca")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.convert = QPushButton("Convert")
        self.convert.setObjectName("primary")
        self.convert.clicked.connect(self.run)
        open_main = QPushButton("Open File Buddy")
        open_main.clicked.connect(self.open_main)
        buttons.addWidget(self.convert)
        buttons.addWidget(open_main)
        layout.addLayout(buttons)
        self.refresh_targets()

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose a file")
        self.files.add_paths(paths[:1])

    def refresh_targets(self):
        self.target.clear()
        paths = self.files.paths()
        if not paths:
            self.target.addItem("(choose a file first)")
            self.convert.setEnabled(False)
            return
        targets = conv.targets_for(paths[0])
        self.target.addItems(targets or ["(no compatible formats)"])
        self.convert.setEnabled(bool(targets))

    def open_main(self):
        self.main.showNormal()
        self.main.activateWindow()
        self.main.raise_()
        self.hide()

    def run(self):
        source = Path(self.files.paths()[0])
        target = self.target.currentText()
        destination = source.parent if self.same_folder.isChecked() else Path(self.main.settings.get("out_dir", str(DEFAULT_OUT)))
        options = {"quality": 92, "dpi": 200}
        self.convert.setEnabled(False)
        self.status.setText(f"Converting {source.name}...")

        def job(log, progress):
            return conv.convert(source, destination, target, options)

        thread = QThread(self)
        worker = Worker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        q = Qt.QueuedConnection  # update the window from the main thread only
        worker.log.connect(self.status.setText, q)
        worker.done.connect(self._finished, q)
        worker.failed.connect(self._failed, q)
        worker.done.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._quick_thread = thread
        thread.start()

    def _finished(self, outputs):
        self.convert.setEnabled(True)
        if outputs:
            self.status.setText(f"Done! {Path(outputs[0]).name} is ready.")
            self.main.last_outputs = [Path(o) for o in outputs]
        else:
            self.status.setText("Nothing was created.")

    def _failed(self, message):
        self.convert.setEnabled(True)
        self.status.setText(f"Could not convert: {message}")


# ---------------------------------------------------------------------------
# 3D Studio tab
# ---------------------------------------------------------------------------
class StudioTab(QWidget):
    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        lay = QHBoxLayout(self)

        # --- left: photos + preview
        left = QVBoxLayout()
        self.photos = DropList("Drop 1-4 photos of the SAME object\n(front, side, back, top)",
                               max_files=4, filter_fn=lambda f: conv.category_of(f) == "image")
        self.photos.changed.connect(self.update_preview)
        self.photos.currentRowChanged.connect(lambda _: self.update_preview())
        left.addWidget(self.photos)
        row = QHBoxLayout()
        add = QPushButton("Add photos...")
        add.clicked.connect(self.pick)
        clr = QPushButton("Clear")
        clr.clicked.connect(lambda: (self.photos.clear(), self.update_preview()))
        row.addWidget(add)
        row.addWidget(clr)
        left.addLayout(row)
        self.preview = QLabel("No photo yet")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(260, 220)
        self.preview.setObjectName("preview")
        left.addWidget(self.preview, 1)
        lay.addLayout(left, 1)

        # --- right: engine + settings
        right = QVBoxLayout()
        eng_box = QGroupBox("3D engine")
        eb = QVBoxLayout(eng_box)
        self.rb_meshy = QRadioButton("Cloud AI (Meshy) - most accurate, uses up to 4 photos")
        self.rb_local = QRadioButton("Local AI (TripoSR on your NVIDIA GPU) - free, uses 1 photo")
        self.rb_relief = QRadioButton("Relief / lithophane - instant, offline, flat raised picture")
        self.engines = QButtonGroup(self)
        for i, rb in enumerate([self.rb_meshy, self.rb_local, self.rb_relief]):
            self.engines.addButton(rb, i)
            eb.addWidget(rb)
        self.rb_meshy.setChecked(True)
        self.engines.idToggled.connect(lambda *_: self.stack.setCurrentIndex(self.engines.checkedId()))
        right.addWidget(eng_box)

        self.stack = QStackedWidget()
        # Meshy options
        mw = QWidget()
        mf = QFormLayout(mw)
        self.m_model = QComboBox()
        self.m_model.addItems(["latest", "meshy-7.1", "meshy-6", "meshy-6-lite"])
        mf.addRow("Model:", self.m_model)
        self.m_geo = QComboBox()
        self.m_geo.addItems(["standard", "2k", "4k"])
        self.m_geo.setToolTip("Higher = finer detail (costs more credits). 4k may only work with 1 photo.")
        mf.addRow("Geometry detail:", self.m_geo)
        self.m_poly = QSpinBox()
        self.m_poly.setRange(10000, 300000)
        self.m_poly.setSingleStep(10000)
        self.m_poly.setValue(300000)
        mf.addRow("Max triangles:", self.m_poly)
        self.m_tex = QCheckBox("Also make a colored .glb (textures)")
        mf.addRow("", self.m_tex)
        self.stack.addWidget(mw)
        # Local options
        lw = QWidget()
        lf = QFormLayout(lw)
        self.l_res = QComboBox()
        self.l_res.addItems(["Fast (256)", "High (320)", "Ultra (448)", "Max (512 - needs 10GB+ VRAM)"])
        self.l_res.setCurrentIndex(1)
        lf.addRow("Mesh quality:", self.l_res)
        self.l_fg = QDoubleSpinBox()
        self.l_fg.setRange(0.5, 1.0)
        self.l_fg.setSingleStep(0.05)
        self.l_fg.setValue(0.85)
        lf.addRow("Object fill ratio:", self.l_fg)
        self.l_nobg = QCheckBox("Photo already has a clean/transparent background")
        lf.addRow("", self.l_nobg)
        status = "Installed" if image3d.triposr_installed() else "Not installed - run install_ai_engine"
        lf.addRow("Engine:", QLabel(status))
        self.stack.addWidget(lw)
        # Relief options
        rw = QWidget()
        rf = QFormLayout(rw)
        self.r_mode = QComboBox()
        self.r_mode.addItems(["lithophane", "emboss"])
        self.r_mode.setToolTip("lithophane: dark = thick (glow when backlit)\nemboss: bright = tall")
        rf.addRow("Style:", self.r_mode)
        self.r_width = self._dspin(10, 500, 100, " mm")
        rf.addRow("Width:", self.r_width)
        self.r_height = self._dspin(0.2, 50, 3, " mm")
        rf.addRow("Raise height:", self.r_height)
        self.r_base = self._dspin(0.2, 20, 0.8, " mm")
        rf.addRow("Base thickness:", self.r_base)
        self.r_detail = QSpinBox()
        self.r_detail.setRange(50, 1000)
        self.r_detail.setValue(300)
        self.r_detail.setSuffix(" px")
        rf.addRow("Detail:", self.r_detail)
        self.stack.addWidget(rw)
        right.addWidget(self.stack)

        out_box = QGroupBox("Output")
        of = QFormLayout(out_box)
        self.fmt = QComboBox()
        self.fmt.addItems(["stl", "3mf", "obj", "glb", "ply"])
        of.addRow("File type:", self.fmt)
        size_row = QHBoxLayout()
        self.real_size = self._dspin(0, 2000, 0, " mm")
        self.real_size.setSpecialValueText("keep AI size")
        self.size_axis = QComboBox()
        self.size_axis.addItems(["longest", "x (width)", "y (depth)", "z (height)"])
        size_row.addWidget(self.real_size)
        size_row.addWidget(QLabel("on"))
        size_row.addWidget(self.size_axis)
        of.addRow("Real size:", size_row)
        of.addRow("", QLabel("<small>Tip: an Xbox controller is about 153 mm wide.</small>"))
        right.addWidget(out_box)

        tips = QLabel(
            "<b>For the most accurate model:</b><br>"
            "- Plain background, good even light, no hands in the shot<br>"
            "- Whole object in frame, sharp focus<br>"
            "- Cloud AI: add front, back, side & top photos<br>"
            "- Set Real size so the STL prints at the true size"
        )
        tips.setWordWrap(True)
        tips.setObjectName("tips")
        right.addWidget(tips)
        right.addStretch()

        self.go = QPushButton("Make 3D model")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self.run)
        right.addWidget(self.go)
        lay.addLayout(right, 1)

    @staticmethod
    def _dspin(lo, hi, val, suffix):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setSuffix(suffix)
        s.setDecimals(1)
        return s

    def pick(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose photos", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.heic)")
        self.photos.add_paths(paths)

    def update_preview(self):
        paths = self.photos.paths()
        if not paths:
            self.preview.setText("No photo yet")
            self.preview.setPixmap(QPixmap())
            return
        row = max(self.photos.currentRow(), 0)
        pm = QPixmap(paths[min(row, len(paths) - 1)])
        if pm.isNull():
            self.preview.setText("(can't preview this format)")
        else:
            self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def run(self):
        photos = [Path(p) for p in self.photos.paths()]
        if not photos:
            QMessageBox.information(self, "File Buddy", "Add at least one photo first.")
            return
        engine = self.engines.checkedId()
        out_dir = Path(self.main.settings.get("out_dir", str(DEFAULT_OUT))) / "3D"
        out_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "format": self.fmt.currentText(),
            "real_size_mm": self.real_size.value(),
            "size_axis": self.size_axis.currentText(),
            "meshy_key": self.main.settings.get("meshy_key", ""),
            "meshy_model": self.m_model.currentText(),
            "geometry_resolution": self.m_geo.currentText(),
            "polycount": self.m_poly.value(),
            "texture": self.m_tex.isChecked(),
            "mc_resolution": [256, 320, 448, 512][self.l_res.currentIndex()],
            "foreground_ratio": self.l_fg.value(),
            "no_remove_bg": self.l_nobg.isChecked(),
            "relief_mode": self.r_mode.currentText(),
            "width_mm": self.r_width.value(),
            "relief_height_mm": self.r_height.value(),
            "base_mm": self.r_base.value(),
            "detail_px": self.r_detail.value(),
        }

        sel_row = min(max(self.photos.currentRow(), 0), len(photos) - 1)

        def job(log, progress):
            progress(0, 0)  # busy animation
            if engine == 0:
                return [image3d.image_to_3d_meshy(photos, out_dir, opts, log)]
            if engine == 1:
                if len(photos) > 1:
                    log("Local AI uses one photo - using the selected/first one.")
                return [image3d.image_to_3d_triposr(photos[sel_row], out_dir, opts, log)]
            return [image3d.image_to_relief_stl(p, out_dir, opts, log) for p in photos]

        self.main.start(job, self.go)


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File Buddy settings")
        self.settings = settings
        f = QFormLayout(self)
        self.key = QLineEdit(settings.get("meshy_key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("msy_...")
        f.addRow("Meshy API key:", self.key)
        f.addRow("", QLabel("<small>Get one at meshy.ai (account -> API). Stored only on this computer.</small>"))
        self.out = QLineEdit(settings.get("out_dir", str(DEFAULT_OUT)))
        f.addRow("Default output folder:", self.out)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def values(self) -> dict:
        return {**self.settings, "meshy_key": self.key.text().strip(), "out_dir": self.out.text().strip()}


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
STYLE = """
* { font-family: "Trebuchet MS"; font-size: 13px; }
QMainWindow, QWidget#root { background: #fff7ec; color: #3b3542; }
QLabel, QCheckBox, QRadioButton, QGroupBox { color: #3b3542; }
QLabel#title { color: #302b3b; font-size: 24px; font-weight: bold; }
QLabel#eyebrow { color: #e87967; font-size: 10px; font-weight: bold; }
QLabel#subtitle { color: #98716b; font-size: 13px; }
QGroupBox { background: #fffdf9; border: 2px solid #eadbd0; border-radius: 12px; margin-top: 14px; padding: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #e87967; font-weight: bold; }
QListWidget#drop { background: #fffdf8; border: 2px dashed #edaa95; border-radius: 14px; color: #5e5260; padding: 8px; }
QListWidget#drop::item { padding: 6px; border-radius: 8px; }
QListWidget#drop::item:selected { background: #ffe0d5; color: #3b3542; }
QLabel#preview { background: #fff3e8; border: 2px dashed #edc7b6; border-radius: 14px; color: #a78379; }
QLabel#tips { background: #e2f3e9; border: 1px solid #b9dfc9; border-radius: 12px; padding: 10px; color: #456556; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: #fffdf9; color: #3b3542; border: 2px solid #eadbd0; border-radius: 8px; padding: 5px; selection-background-color: #ffc9bb; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #e87967; }
QPushButton { background: #fffdf9; color: #594d59; border: 2px solid #eadbd0; border-radius: 9px; padding: 7px 13px; font-weight: bold; }
QPushButton:hover { background: #fff0df; border-color: #e7ae96; }
QPushButton#primary { background: #ed7968; color: white; border: none; font-weight: bold; padding: 11px; font-size: 14px; }
QPushButton#primary:hover { background: #df6556; }
QPushButton:disabled { background: #f0e7df; color: #b6a8a0; border-color: #eadbd0; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #f6e9df; color: #93736d; padding: 9px 20px; margin-right: 4px; border-top-left-radius: 10px; border-top-right-radius: 10px; }
QTabBar::tab:selected { background: #dff1e7; color: #3e6a54; font-weight: bold; }
QScrollBar:vertical { background: #f6e9df; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #e6b6a5; border-radius: 5px; min-height: 20px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QProgressBar { background: #f0e5dc; border: none; border-radius: 6px; height: 10px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #77c89a; border-radius: 6px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.setWindowTitle("File Buddy")
        icon = APP_DIR / "assets" / "icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(980, 720)
        self.last_outputs: list[Path] = []
        self.thread: QThread | None = None

        root = QWidget()
        root.setObjectName("root")
        v = QVBoxLayout(root)

        head = QHBoxLayout()
        mascot = QLabel()
        mascot.setPixmap(buddy_pixmap(64, "happy"))
        mascot.setFixedSize(66, 66)
        head.addWidget(mascot)
        copy = QVBoxLayout()
        eyebrow = QLabel("YOUR DESKTOP FORMAT FRIEND")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("File Buddy")
        title.setObjectName("title")
        sub = QLabel("Drop it in, pick a format, and let Buddy do the tidy-up.")
        sub.setObjectName("subtitle")
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(sub)
        head.addLayout(copy)
        gear = QPushButton("Settings")
        gear.clicked.connect(self.open_settings)
        head.addStretch()
        self.buddy_btn = QPushButton("Hide Buddy")
        self.buddy_btn.clicked.connect(lambda: self.toggle_buddy())
        head.addWidget(self.buddy_btn)
        head.addWidget(gear)
        v.addLayout(head)

        tabs = QTabWidget()
        tabs.addTab(ConvertTab(self), "Convert files")
        tabs.addTab(StudioTab(self), "Photo -> 3D")
        v.addWidget(tabs, 1)

        self.bar = QProgressBar()
        self.bar.setMaximumHeight(10)
        v.addWidget(self.bar)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumHeight(150)
        v.addWidget(self.logbox)

        br = QHBoxLayout()
        self.open_file_btn = QPushButton("Open result")
        self.open_file_btn.clicked.connect(lambda: self.last_outputs and open_path(self.last_outputs[-1]))
        self.open_dir_btn = QPushButton("Open folder")
        self.open_dir_btn.clicked.connect(lambda: self.last_outputs and open_path(self.last_outputs[-1].parent))
        for b in (self.open_file_btn, self.open_dir_btn):
            b.setEnabled(False)
            br.addWidget(b)
        br.addStretch()
        v.addLayout(br)

        self.setCentralWidget(root)
        self.log("Hey! Drop some files in and I'll convert them.")

        self.quick_convert = QuickConvertDialog(self)
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            tray_menu = QMenu()
            quick_action = QAction("Quick Convert", self)
            quick_action.triggered.connect(self.show_quick_convert)
            open_action = QAction("Open File Buddy", self)
            open_action.triggered.connect(self.showNormal)
            self.buddy_action = QAction("Show desktop Buddy", self, checkable=True)
            self.buddy_action.triggered.connect(lambda on: self.toggle_buddy(on))
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit_app)
            tray_menu.addAction(quick_action)
            tray_menu.addAction(open_action)
            tray_menu.addAction(self.buddy_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)
            self.tray.setContextMenu(tray_menu)
            self.tray.activated.connect(self._tray_activated)
            self.tray.setToolTip("File Buddy - quick format conversion")
            self.tray.show()

        # the cute floating helper that sits above the taskbar
        self.buddy = DesktopBuddy(self)
        self.toggle_buddy(self.settings.get("show_buddy", True))

    def log(self, msg: str):
        self.logbox.appendPlainText(msg)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_quick_convert()

    def show_quick_convert(self):
        self.quick_convert.show()

    def toggle_buddy(self, show=None):
        if show is None:
            show = not self.buddy.isVisible()
        show = bool(show)
        self.buddy.setVisible(show)
        if show:
            self.buddy.raise_()
        self.buddy_btn.setText("Hide Buddy" if show else "Show Buddy")
        if self.tray:
            self.buddy_action.setChecked(show)
        if self.settings.get("show_buddy", True) != show:
            self.settings["show_buddy"] = show
            save_settings(self.settings)

    def quit_app(self):
        self.buddy.hide()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray and self.tray.isVisible():
            self.hide()
            if self.buddy.isVisible():
                self.buddy.say("I'm still here! Drop files on me anytime.", 4)
            else:
                self.tray.showMessage("File Buddy is ready", "Use the tray icon for Quick Convert.", QSystemTrayIcon.Information, 2500)
            event.ignore()
            return
        event.accept()

    def open_settings(self):
        d = SettingsDialog(self.settings, self)
        if d.exec():
            self.settings = d.values()
            save_settings(self.settings)
            self.log("Settings saved.")

    def start(self, fn, button: QPushButton):
        if self.thread and self.thread.isRunning():
            return
        self._busy_button = button
        button.setEnabled(False)
        self.thread = QThread()
        self.worker = Worker(fn)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        q = Qt.QueuedConnection  # always update the window from the main thread
        self.worker.log.connect(self._on_log, q)
        self.worker.progress.connect(self._on_progress, q)
        self.worker.done.connect(self._on_done, q)
        self.worker.failed.connect(self._on_failed, q)
        self.thread.start()

    @Slot(str)
    def _on_log(self, msg):
        self.log(msg)

    @Slot(int, int)
    def _on_progress(self, i, n):
        self.bar.setRange(0, n)
        self.bar.setValue(i)

    @Slot(list)
    def _on_done(self, outs):
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        if outs:
            self.last_outputs = [Path(o) for o in outs]
            self.open_file_btn.setEnabled(True)
            self.open_dir_btn.setEnabled(True)
            self.log(f"Done! {len(outs)} file(s) ready.")
        self._cleanup()

    @Slot(str)
    def _on_failed(self, msg):
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self._cleanup()
        QMessageBox.warning(self, "File Buddy", msg)

    def _cleanup(self):
        self._busy_button.setEnabled(True)
        self.thread.quit()
        self.thread.wait()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("File Buddy")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    if not (APP_DIR / "assets" / "buddy_512.png").exists():
        try:
            make_icons(APP_DIR / "assets")
        except Exception:  # noqa: BLE001
            pass
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
