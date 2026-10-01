"""
Buddy - the File Buddy mascot.

* draw_buddy()  : paints the little file character at any size (vector, so it stays crisp)
* make_icons()  : writes assets/icon.png, icon.ico and buddy_512.png from the same drawing
* DesktopBuddy  : a floating, always-on-top Buddy that sits above your taskbar.
                  Drop a file on him -> pick a format -> he converts it.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import (
    QBrush, QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from . import converters as conv

# Palette (matches the cream / coral / mint app theme)
INK = QColor("#3b3542")
PAPER = QColor("#fffaf3")
PAPER_SHADE = QColor("#f6e6d8")
CORAL = QColor("#ed7968")
CORAL_DARK = QColor("#d65e4d")
MINT = QColor("#8fd9b0")
MINT_DARK = QColor("#5fb98a")
BLUSH = QColor(255, 140, 150, 150)
SKY = QColor("#7cc4ff")

MOODS = ("idle", "happy", "excited", "working", "done", "sad", "sleepy")


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def draw_buddy(p: QPainter, rect: QRectF, mood: str = "idle", blink: float = 0.0,
               t: float = 0.0, look: float = 0.0, shadow: bool = True) -> None:
    """Paint Buddy inside `rect`. Design space is 200 x 200.

    blink: 0 = eyes open, 1 = fully closed
    t    : seconds, drives little animations (wave, spin, sparkles)
    look : -1 .. 1, where the pupils look horizontally
    """
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    s = min(rect.width(), rect.height()) / 200.0
    p.translate(rect.x() + (rect.width() - 200 * s) / 2, rect.y() + (rect.height() - 200 * s) / 2)
    p.scale(s, s)
    ink = QPen(INK, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    # ground shadow
    if shadow:
        g = QRadialGradient(QPointF(100, 188), 60)
        g.setColorAt(0, QColor(59, 53, 66, 70))
        g.setColorAt(1, QColor(59, 53, 66, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QRectF(40, 178, 120, 20))

    # little feet
    p.setPen(ink)
    p.setBrush(CORAL)
    p.drawRoundedRect(QRectF(62, 166, 30, 18), 9, 9)
    p.drawRoundedRect(QRectF(108, 166, 30, 18), 9, 9)

    # arms (one waves when happy / done)
    wave = math.sin(t * 9) * 18 if mood in ("happy", "done", "excited") else 0
    p.setPen(QPen(INK, 7, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(38, 114), QPointF(27, 126))                      # left arm resting
    rx, ry = 162, 108
    ang = math.radians(-55 + wave) if wave else math.radians(50)
    p.drawLine(QPointF(rx, ry), QPointF(rx + 13 * math.cos(ang), ry + 13 * math.sin(ang)))
    p.setPen(QPen(INK, 5))
    p.setBrush(CORAL)
    p.drawEllipse(QPointF(24, 129), 9, 9)
    p.drawEllipse(QPointF(rx + 17 * math.cos(ang), ry + 17 * math.sin(ang)), 9, 9)

    # body = a chubby page with a folded corner
    body = QPainterPath()
    body.moveTo(52, 22)
    body.lineTo(128, 22)
    body.lineTo(162, 56)
    body.lineTo(162, 150)
    body.quadTo(162, 172, 140, 172)
    body.lineTo(60, 172)
    body.quadTo(38, 172, 38, 150)
    body.lineTo(38, 36)
    body.quadTo(38, 22, 52, 22)
    grad = QLinearGradient(0, 22, 0, 172)
    grad.setColorAt(0, PAPER)
    grad.setColorAt(1, PAPER_SHADE)
    p.setPen(ink)
    p.setBrush(grad)
    p.drawPath(body)

    # folded corner (mint)
    fold = QPainterPath()
    fold.moveTo(128, 22)
    fold.lineTo(128, 46)
    fold.quadTo(128, 56, 138, 56)
    fold.lineTo(162, 56)
    fold.closeSubpath()
    p.setBrush(MINT)
    p.drawPath(fold)

    # belly badge: two swirly convert arrows (spin while working)
    p.save()
    p.translate(100, 140)
    if mood == "working":
        p.rotate((t * 360) % 360)
    p.setPen(QPen(CORAL, 6, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    r = QRectF(-15, -15, 30, 30)
    p.drawArc(r, 20 * 16, 140 * 16)
    p.drawArc(r, 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(CORAL)
    for a in (20, 200):
        rad = math.radians(a)
        cx, cy = 15 * math.cos(rad), -15 * math.sin(rad)
        tri = QPainterPath()
        tri.moveTo(cx + 7, cy)
        tri.lineTo(cx - 7, cy)
        tri.lineTo(cx, cy + (8 if a == 20 else -8))
        tri.closeSubpath()
        p.drawPath(tri)
    p.restore()

    # cheeks
    p.setPen(Qt.NoPen)
    p.setBrush(BLUSH)
    p.drawEllipse(QRectF(48, 96, 22, 13))
    p.drawEllipse(QRectF(130, 96, 22, 13))

    # eyes
    lx, rx2, ey = 72, 128, 80
    look_dx = max(-1.0, min(1.0, look)) * 4
    if mood in ("happy", "done"):
        p.setPen(QPen(INK, 7, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for x in (lx, rx2):  # ^ ^
            p.drawArc(QRectF(x - 12, ey - 6, 24, 22), 20 * 16, 140 * 16)
    elif mood == "sleepy" or blink > 0.85:
        p.setPen(QPen(INK, 6, Qt.SolidLine, Qt.RoundCap))
        for x in (lx, rx2):
            p.drawLine(QPointF(x - 11, ey + 4), QPointF(x + 11, ey + 4))
    else:
        big = 1.25 if mood == "excited" else 1.0
        h = 26 * big * (1 - blink)
        w = 20 * big
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        for x in (lx, rx2):
            p.drawEllipse(QRectF(x - w / 2 + look_dx, ey - h / 2 + 2, w, max(h, 3)))
        if h > 8:  # sparkle highlights
            p.setBrush(QColor("white"))
            for x in (lx, rx2):
                p.drawEllipse(QRectF(x - 6 + look_dx, ey - h / 2 + 5, 8 * big, 8 * big))
                p.drawEllipse(QRectF(x + 3 + look_dx, ey + 3, 4 * big, 4 * big))
        if mood == "sad":
            p.setPen(QPen(INK, 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(lx - 12, ey - 20), QPointF(lx + 8, ey - 26))
            p.drawLine(QPointF(rx2 + 12, ey - 20), QPointF(rx2 - 8, ey - 26))

    # mouth
    p.setPen(QPen(INK, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if mood in ("excited", "done"):
        m = QPainterPath()
        m.moveTo(88, 104)
        m.quadTo(100, 108, 112, 104)
        m.quadTo(110, 124, 100, 124)
        m.quadTo(90, 124, 88, 104)
        p.setBrush(CORAL_DARK)
        p.drawPath(m)
    elif mood == "sad":
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(88, 108, 24, 16), 30 * 16, 120 * 16)
    elif mood == "working":
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(92, 112), QPointF(108, 112))
    else:  # cute little "w" smile
        p.setBrush(Qt.NoBrush)
        w = QPainterPath()
        w.moveTo(86, 104)
        w.quadTo(93, 116, 100, 106)
        w.quadTo(107, 116, 114, 104)
        p.drawPath(w)

    # extras
    if mood == "working":  # sweat drop
        d = QPainterPath()
        d.moveTo(158, 62)
        d.quadTo(150, 76, 158, 80)
        d.quadTo(166, 76, 158, 62)
        p.setPen(QPen(INK, 3))
        p.setBrush(SKY)
        p.drawPath(d)
    if mood == "done":  # sparkles
        for i, (sx, sy) in enumerate(((20, 40), (182, 30), (178, 140))):
            k = 0.6 + 0.4 * math.sin(t * 6 + i * 2)
            _star(p, sx, sy, 10 * k, MINT_DARK if i % 2 else CORAL)
    if mood == "sleepy":
        p.setPen(INK)
        f = QFont("Trebuchet MS")
        f.setBold(True)
        f.setPixelSize(22)
        p.setFont(f)
        p.drawText(QPointF(160, 34 - (t * 8) % 10), "z")
        f.setPixelSize(15)
        p.setFont(f)
        p.drawText(QPointF(176, 18 - (t * 8) % 10), "z")
    p.restore()


def _star(p: QPainter, x: float, y: float, r: float, color: QColor):
    path = QPainterPath()
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.35
        a = math.pi / 4 * i - math.pi / 2
        pt = QPointF(x + rr * math.cos(a), y + rr * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def buddy_image(size: int, mood: str = "idle", shadow: bool = False) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    draw_buddy(p, QRectF(0, 0, size, size), mood, shadow=shadow)
    p.end()
    return img


def buddy_pixmap(size: int, mood: str = "idle") -> QPixmap:
    return QPixmap.fromImage(buddy_image(size, mood))


def make_icons(assets_dir: Path) -> None:
    """Regenerate the app icons from the vector Buddy."""
    from PIL import Image
    import io

    assets_dir.mkdir(parents=True, exist_ok=True)
    buddy_image(512, "idle").save(str(assets_dir / "buddy_512.png"))
    buddy_image(256, "idle").save(str(assets_dir / "icon.png"))
    for mood in ("happy", "excited", "working", "done", "sad"):
        buddy_image(256, mood).save(str(assets_dir / f"buddy_{mood}.png"))
    # .ico with every Windows size
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    buddy_image(256, "idle").save(buf, "PNG")
    Image.open(io.BytesIO(bytes(ba))).save(
        assets_dir / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


# ---------------------------------------------------------------------------
# Floating desktop Buddy
# ---------------------------------------------------------------------------
class _ConvertWorker(QObject):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, files, target, same_folder, out_dir):
        super().__init__()
        self.files, self.target, self.same, self.out_dir = files, target, same_folder, out_dir

    @Slot()
    def run(self):
        outs, errors = [], []
        for f in self.files:
            try:
                dest = Path(f).parent if self.same else Path(self.out_dir)
                outs += conv.convert(f, dest, self.target, {"quality": 92, "dpi": 200})
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{Path(f).name}: {exc}")
        if errors and not outs:
            self.failed.emit("\n".join(errors))
        else:
            self.done.emit([str(o) for o in outs])


MENU_STYLE = """
QMenu { background: #fffdf9; border: 2px solid #edaa95; border-radius: 12px; padding: 6px;
        font-family: "Trebuchet MS"; font-size: 13px; color: #3b3542; }
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 8px; }
QMenu::item:selected { background: #ffe0d5; }
QMenu::item:disabled { color: #e87967; font-weight: bold; }
QMenu::separator { height: 2px; background: #f3e3d8; margin: 4px 8px; }
"""


class DesktopBuddy(QWidget):
    """Little always-on-top Buddy that lives above the taskbar."""

    W, H = 280, 230          # whole widget (speech bubble + Buddy)
    BUDDY = 130              # Buddy size in px

    def __init__(self, main_window=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.main = main_window
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setFixedSize(self.W, self.H)
        self.setWindowTitle("File Buddy")

        self.mood = "idle"
        self.t = 0.0
        self.blink = 0.0
        self._next_blink = 2.5
        self.look = 0.0
        self.bubble = ""
        self._bubble_until = 0.0
        self._mood_until = 0.0
        self._idle_time = 0.0
        self._drag_from: QPoint | None = None
        self._moved = False
        self.last_outputs: list[str] = []
        self._thread: QThread | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self._place()
        self.say(random.choice(["Hi! Drop a file on me!", "Need a new format? I got you.",
                                "Drag a file here and I'll convert it!"]), 4)

    # -- position -----------------------------------------------------------
    def _settings(self) -> dict:
        return getattr(self.main, "settings", {}) if self.main else {}

    def _place(self):
        pos = self._settings().get("buddy_pos")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        if pos and any(s.availableGeometry().contains(QPoint(*pos)) for s in QGuiApplication.screens()):
            self.move(*pos)
        else:  # bottom-right, sitting right on top of the taskbar
            self.move(screen.right() - self.W - 10, screen.bottom() - self.H + 6)

    def _save_pos(self):
        if self.main is not None and hasattr(self.main, "settings"):
            from .app import save_settings

            self.main.settings["buddy_pos"] = [self.x(), self.y()]
            save_settings(self.main.settings)

    # -- talking / moods ----------------------------------------------------
    def say(self, text: str, seconds: float = 3.5):
        self.bubble = text
        self._bubble_until = self.t + seconds
        self._idle_time = 0
        self.update()

    def set_mood(self, mood: str, seconds: float = 0):
        self.mood = mood
        self._mood_until = self.t + seconds if seconds else 0
        self._idle_time = 0

    def _tick(self):
        self.t += 0.033
        self._idle_time += 0.033
        # blinking
        if self.t >= self._next_blink:
            phase = (self.t - self._next_blink) / 0.16
            self.blink = 1 - abs(1 - 2 * phase) if phase < 1 else 0
            if phase >= 1:
                self._next_blink = self.t + random.uniform(2.5, 5.5)
        # mouse following eyes
        cur = self.mapFromGlobal(self.cursor().pos())
        cx = self.W - self.BUDDY / 2
        self.look = max(-1.0, min(1.0, (cur.x() - cx) / 300))
        # mood timeouts
        if self._mood_until and self.t > self._mood_until:
            self.mood, self._mood_until = "idle", 0
        if self.mood == "idle" and self._idle_time > 90:
            self.mood = "sleepy"
        if self.bubble and self.t > self._bubble_until:
            self.bubble = ""
        self.update()

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bob = math.sin(self.t * 2.4) * 4 if self.mood != "sleepy" else math.sin(self.t * 1.2) * 2
        if self.mood == "excited":
            bob = -abs(math.sin(self.t * 10)) * 10
        squish = 1 + (math.sin(self.t * 2.4) * 0.02)
        b = self.BUDDY
        rect = QRectF(self.W - b - 6, self.H - b * squish - 2 + bob, b, b * squish)
        draw_buddy(p, rect, self.mood, self.blink, self.t, self.look)
        if self.bubble:
            self._draw_bubble(p, self.bubble, QPointF(rect.center().x() - 20, rect.top() + 18))
        p.end()

    def _draw_bubble(self, p: QPainter, text: str, tail: QPointF):
        f = QFont("Trebuchet MS")
        f.setPixelSize(14)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        max_w = self.W - 20
        br = fm.boundingRect(0, 0, max_w - 24, 200, Qt.TextWordWrap, text)
        w, h = br.width() + 26, br.height() + 18
        x = max(4, min(tail.x() - w + 40, self.W - w - 4))
        y = max(4, tail.y() - h - 16)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), 14, 14)
        tp = QPainterPath()
        tp.moveTo(min(tail.x() - 6, x + w - 30), y + h - 1)
        tp.lineTo(tail.x() + 4, tail.y() - 2)
        tp.lineTo(min(tail.x() + 12, x + w - 14), y + h - 1)
        path = path.united(tp)
        p.setPen(QPen(INK, 3))
        p.setBrush(QColor("#fffdf9"))
        p.drawPath(path)
        p.setPen(INK)
        p.drawText(QRectF(x + 13, y + 9, w - 26, h - 18), Qt.TextWordWrap | Qt.AlignCenter, text)

    def _buddy_hit(self, pos) -> bool:
        b = self.BUDDY
        return QRectF(self.W - b - 6, self.H - b - 12, b, b + 12).contains(QPointF(pos))

    # -- mouse: drag to move, click to chat, double-click opens app ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._buddy_hit(e.position()):
            self._drag_from = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        elif e.button() == Qt.RightButton:
            self._context_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._drag_from is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_from)
            self._moved = True

    def mouseReleaseEvent(self, e):
        if self._drag_from is not None:
            if self._moved:
                self._save_pos()
            else:
                self.set_mood("happy", 1.5)
                self.say(random.choice(["Hehe, that tickles!", "Drop a file on me!",
                                        "Double-click me to open File Buddy.", "Right-click me for options."]), 2.5)
        self._drag_from = None

    def mouseDoubleClickEvent(self, _e):
        self.open_main()

    def _context_menu(self, at: QPoint):
        m = QMenu()
        m.setStyleSheet(MENU_STYLE)
        m.addAction("Open File Buddy", self.open_main)
        if self.main and hasattr(self.main, "show_quick_convert"):
            m.addAction("Quick Convert...", self.main.show_quick_convert)
        if self.last_outputs:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            last = Path(self.last_outputs[-1])
            m.addAction("Open last result", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(last))))
            m.addAction("Open its folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(last.parent))))
        m.addSeparator()
        m.addAction("Hide Buddy", self.hide)
        if self.main and hasattr(self.main, "quit_app"):
            m.addAction("Quit File Buddy", self.main.quit_app)
        m.exec(at)

    def open_main(self):
        if self.main:
            self.main.showNormal()
            self.main.activateWindow()
            self.main.raise_()

    # -- drag & drop files ---------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.set_mood("excited")
            self.say("Ooh! Gimme gimme!", 10)
        else:
            e.ignore()

    def dragLeaveEvent(self, _e):
        self.set_mood("idle")
        self.say("Aww... come back!", 2)

    def dropEvent(self, e):
        files = []
        for u in e.mimeData().urls():
            pth = Path(u.toLocalFile())
            files += [f for f in pth.rglob("*") if f.is_file()] if pth.is_dir() else [pth]
        files = [str(f) for f in files if conv.category_of(f) != "unknown"]
        if not files:
            self.set_mood("sad", 3)
            self.say("Hmm, I don't know that file type yet.", 3)
            return
        common = None
        for f in files:
            tg = conv.targets_for(f)
            common = tg if common is None else [x for x in common if x in tg]
        if not common:
            self.set_mood("sad", 3)
            self.say("Those files are too different. Try one type at a time!", 4)
            return
        self.set_mood("happy")
        label = Path(files[0]).name if len(files) == 1 else f"{len(files)} files"
        self.say(f"Turn {label} into...?", 30)
        m = QMenu()
        m.setStyleSheet(MENU_STYLE)
        head = m.addAction(f"Convert {label} to:")
        head.setEnabled(False)
        m.addSeparator()
        for tg in common:
            m.addAction(f"  .{tg}" if " " not in tg else f"  {tg}").setData(tg)
        choice = m.exec(self.mapToGlobal(QPoint(int(self.W - self.BUDDY), int(self.H - self.BUDDY))))
        if not choice or not choice.data():
            self.set_mood("idle")
            self.say("Okay, maybe later!", 2)
            return
        self._convert(files, choice.data())

    def _convert(self, files, target):
        if self._thread and self._thread.isRunning():
            self.say("Hold on, I'm still working!", 2)
            return
        self.set_mood("working")
        self.say(f"Working on it... -> .{target.split()[0]}", 120)
        settings = self._settings()
        from .app import DEFAULT_OUT

        self._thread = QThread(self)
        self._worker = _ConvertWorker(files, target, True, settings.get("out_dir", str(DEFAULT_OUT)))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._done, Qt.QueuedConnection)
        self._worker.failed.connect(self._failed, Qt.QueuedConnection)
        self._thread.start()

    @Slot(list)
    def _done(self, outs):
        self._thread.quit()
        self._thread.wait()
        self.last_outputs = outs
        if self.main is not None:
            self.main.last_outputs = [Path(o) for o in outs]
        self.set_mood("done", 4)
        n = len(outs)
        self.say(f"Ta-da! {Path(outs[0]).name if n == 1 else f'{n} files'} ready!\n(right-click to open)", 6)

    @Slot(str)
    def _failed(self, msg):
        self._thread.quit()
        self._thread.wait()
        self.set_mood("sad", 4)
        self.say("Oops, that didn't work: " + msg[:90], 6)


if __name__ == "__main__":  # quick preview: python -m filebuddy.buddy
    import sys

    app = QApplication(sys.argv)
    b = DesktopBuddy()
    b.show()
    sys.exit(app.exec())
