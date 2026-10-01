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
DEFAULT_CHARACTER = "paper"
CHARACTERS = {
    "paper": "Buddy (Paper)",
    "fox": "Pip (Fox)",
    "cat": "Mochi (Cat)",
    "atty": "Atty (Serious Tuxedo Cat)",
    "nyx": "Nyx (Night Sprite)",
    "robot": "Byte (Robot)",
}

_CHARACTER_COLORS = {
    "paper": {
        "ink": INK, "paper": PAPER, "shade": PAPER_SHADE, "accent": CORAL,
        "accent_dark": CORAL_DARK, "secondary": MINT, "secondary_dark": MINT_DARK,
        "cheek": BLUSH, "extra": SKY,
    },
    "fox": {
        "ink": QColor("#49352e"), "paper": QColor("#fff2dd"),
        "shade": QColor("#f4d4b0"), "accent": QColor("#ed8747"),
        "accent_dark": QColor("#c65c31"), "secondary": QColor("#81c5a5"),
        "secondary_dark": QColor("#509777"), "cheek": QColor(246, 151, 111, 150),
        "extra": QColor("#7cc4ff"),
    },
    "cat": {
        "ink": QColor("#3b3542"), "paper": QColor("#fcf3ff"),
        "shade": QColor("#e8d8f0"), "accent": QColor("#ba83d3"),
        "accent_dark": QColor("#925bb0"), "secondary": QColor("#91d5c2"),
        "secondary_dark": QColor("#59a993"), "cheek": QColor(244, 145, 181, 150),
        "extra": QColor("#8cbbff"),
    },
    "atty": {
        "ink": QColor("#111217"), "paper": QColor("#292a30"),
        "shade": QColor("#15161b"), "accent": QColor("#f4f3f0"),
        "accent_dark": QColor("#d9d7d2"), "secondary": QColor("#c52b45"),
        "secondary_dark": QColor("#941d33"), "cheek": QColor(255, 170, 184, 130),
        "extra": QColor("#6de0a1"),
    },
    "nyx": {
        "ink": QColor("#171321"), "paper": QColor("#302a3f"),
        "shade": QColor("#1e192a"), "accent": QColor("#cbb8ff"),
        "accent_dark": QColor("#9b80df"), "secondary": QColor("#f2c66d"),
        "secondary_dark": QColor("#d49a42"), "cheek": QColor(193, 133, 211, 100),
        "extra": QColor("#f5d48a"),
    },
    "robot": {
        "ink": QColor("#344453"), "paper": QColor("#edf8ff"),
        "shade": QColor("#cfe5f2"), "accent": QColor("#55a9d1"),
        "accent_dark": QColor("#337da5"), "secondary": QColor("#f2aa62"),
        "secondary_dark": QColor("#d77b3e"), "cheek": QColor(119, 196, 225, 135),
        "extra": QColor("#efa75e"),
    },
}


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def _draw_atty(p: QPainter, blink: float, look: float, shadow: bool) -> None:
    """Draw Atty as a stern, seated black-and-white tuxedo cat."""
    fur = QColor("#17181d")
    fur_light = QColor("#303139")
    white = QColor("#f4f3ee")
    whiskers = QColor("#fffdf7")
    amber = QColor("#d5a54c")
    outline = QPen(QColor("#101115"), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    if shadow:
        gradient = QRadialGradient(QPointF(100, 188), 62)
        gradient.setColorAt(0, QColor(8, 8, 12, 90))
        gradient.setColorAt(1, QColor(8, 8, 12, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(gradient)
        p.drawEllipse(QRectF(34, 174, 132, 24))

    # Curled tail and seated body establish a recognizable feline silhouette.
    tail = QPainterPath()
    tail.moveTo(130, 158)
    tail.cubicTo(185, 171, 184, 115, 159, 119)
    tail.cubicTo(144, 121, 149, 145, 167, 142)
    p.setPen(QPen(QColor("#101115"), 20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(tail)
    p.setPen(QPen(QColor("#34353d"), 10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(tail)

    torso = QPainterPath()
    torso.moveTo(75, 96)
    torso.cubicTo(51, 108, 46, 133, 51, 161)
    torso.cubicTo(54, 177, 68, 181, 82, 174)
    torso.lineTo(119, 174)
    torso.cubicTo(133, 181, 147, 177, 150, 161)
    torso.cubicTo(154, 133, 147, 108, 125, 96)
    torso.closeSubpath()
    torso_gradient = QLinearGradient(48, 110, 153, 176)
    torso_gradient.setColorAt(0, QColor("#101115"))
    torso_gradient.setColorAt(0.55, QColor("#24252b"))
    torso_gradient.setColorAt(1, QColor("#111216"))
    p.setPen(outline)
    p.setBrush(torso_gradient)
    p.drawPath(torso)

    bib = QPainterPath()
    bib.moveTo(79, 105)
    bib.cubicTo(72, 126, 71, 147, 79, 166)
    bib.lineTo(87, 158)
    bib.lineTo(94, 168)
    bib.lineTo(101, 158)
    bib.lineTo(108, 168)
    bib.lineTo(116, 158)
    bib.cubicTo(125, 141, 125, 122, 119, 105)
    bib.cubicTo(106, 112, 93, 112, 79, 105)
    bib.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(bib)

    # Forelegs and white paws sit in front of the chest.
    p.setPen(outline)
    p.setBrush(fur)
    p.drawRoundedRect(QRectF(65, 135, 28, 40), 13, 13)
    p.drawRoundedRect(QRectF(107, 135, 28, 40), 13, 13)
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawRoundedRect(QRectF(66, 160, 27, 16), 8, 8)
    p.drawRoundedRect(QRectF(108, 160, 27, 16), 8, 8)
    p.setPen(QPen(QColor("#c9c7c1"), 1.4, Qt.SolidLine, Qt.RoundCap))
    for x in (75, 82, 117, 124):
        p.drawLine(QPointF(x, 166), QPointF(x, 172))

    # Upright ears behind a broad, rounded adult-cat head.
    ears = QPainterPath()
    ears.moveTo(49, 65)
    ears.lineTo(53, 25)
    ears.quadTo(55, 17, 63, 24)
    ears.lineTo(83, 43)
    ears.quadTo(100, 37, 117, 43)
    ears.lineTo(137, 24)
    ears.quadTo(145, 17, 147, 25)
    ears.lineTo(151, 65)
    ears.closeSubpath()
    p.setPen(outline)
    p.setBrush(fur)
    p.drawPath(ears)

    for points in (
        ((57, 51), (59, 30), (76, 47)),
        ((124, 47), (141, 30), (143, 51)),
    ):
        inner = QPainterPath()
        inner.moveTo(*points[0])
        inner.lineTo(*points[1])
        inner.lineTo(*points[2])
        inner.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8f6264"))
        p.drawPath(inner)

    head_gradient = QLinearGradient(50, 44, 146, 130)
    head_gradient.setColorAt(0, QColor("#101115"))
    head_gradient.setColorAt(0.5, fur_light)
    head_gradient.setColorAt(1, QColor("#14151a"))
    p.setPen(outline)
    p.setBrush(head_gradient)
    p.drawEllipse(QRectF(45, 39, 110, 91))
    p.setPen(QPen(QColor("#45464d"), 1.2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(56, 77), QPointF(61, 73))
    p.drawLine(QPointF(58, 82), QPointF(64, 78))
    p.drawLine(QPointF(144, 77), QPointF(139, 73))
    p.drawLine(QPointF(142, 82), QPointF(136, 78))
    p.setPen(Qt.NoPen)
    p.setBrush(fur_light)
    p.drawArc(QRectF(53, 45, 94, 76), 25 * 16, 130 * 16)

    # White muzzle cheeks, forehead blaze, and whisker pads form the tuxedo markings.
    blaze = QPainterPath()
    blaze.moveTo(94, 49)
    blaze.cubicTo(97, 62, 91, 73, 94, 82)
    blaze.cubicTo(96, 88, 104, 88, 106, 82)
    blaze.cubicTo(109, 72, 103, 61, 106, 49)
    blaze.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(white)
    p.drawPath(blaze)
    p.drawEllipse(QRectF(59, 83, 43, 29))
    p.drawEllipse(QRectF(98, 83, 43, 29))
    p.setPen(QPen(QColor("#d7d5cf"), 1, Qt.SolidLine, Qt.RoundCap))
    for x in (62, 68, 74, 80, 86, 114, 120, 126, 132, 138):
        p.drawLine(QPointF(x, 107), QPointF(x + (2 if x < 100 else -2), 110))
    p.setPen(QPen(QColor("#777880"), 1.1, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(64, 131), QPointF(59, 150))
    p.drawLine(QPointF(136, 131), QPointF(141, 150))
    p.drawLine(QPointF(59, 132), QPointF(57, 145))
    p.drawLine(QPointF(141, 132), QPointF(143, 145))

    # Heavy angled brows and half-lidded amber eyes give him a composed, masculine look.
    pupil_shift = max(-1.0, min(1.0, look)) * 2.5
    eye_height = max(1.5, 9 * (1 - max(0.0, min(1.0, blink))))
    p.setPen(QPen(QColor("#090a0c"), 6, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(63, 66), QPointF(88, 72))
    p.drawLine(QPointF(112, 72), QPointF(137, 66))
    for x in (72, 80, 120, 128):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#8d8581"))
        p.drawEllipse(QPointF(x, 99 if x in (72, 128) else 103), 1.2, 1.2)
    for x in (76, 124):
        p.setPen(QPen(QColor("#191715"), 1.5))
        p.setBrush(amber)
        p.drawEllipse(QRectF(x - 10 + pupil_shift, 72, 20, eye_height))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#18140f"))
        p.drawEllipse(QRectF(x - 2 + pupil_shift, 72, 4, eye_height))
        p.setBrush(QColor("#fff1c8"))
        p.drawEllipse(QPointF(x - 4 + pupil_shift, 74), 1.6, 1.6)

    # Nose, firm mouth, chin, and long white whiskers.
    nose = QPainterPath()
    nose.moveTo(94, 91)
    nose.quadTo(100, 87, 106, 91)
    nose.lineTo(100, 97)
    nose.closeSubpath()
    p.setPen(QPen(QColor("#312226"), 1))
    p.setBrush(QColor("#a86f75"))
    p.drawPath(nose)
    p.setPen(QPen(QColor("#373239"), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(100, 96), QPointF(100, 102))
    p.drawLine(QPointF(93, 104), QPointF(107, 104))
    p.setPen(QPen(whiskers, 1.4, Qt.SolidLine, Qt.RoundCap))
    for y, end_y in ((94, 86), (100, 100), (105, 114)):
        p.drawLine(QPointF(67, 98), QPointF(42, end_y))
        p.drawLine(QPointF(133, 98), QPointF(158, end_y))


def draw_buddy(p: QPainter, rect: QRectF, mood: str = "idle", blink: float = 0.0,
               t: float = 0.0, look: float = 0.0, shadow: bool = True,
               character: str = DEFAULT_CHARACTER) -> None:
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
    if character == "atty":
        _draw_atty(p, blink, look, shadow)
        p.restore()
        return
    colors = _CHARACTER_COLORS.get(character, _CHARACTER_COLORS[DEFAULT_CHARACTER])
    ink_color = colors["ink"]
    paper, paper_shade = colors["paper"], colors["shade"]
    coral, coral_dark = colors["accent"], colors["accent_dark"]
    mint, mint_dark = colors["secondary"], colors["secondary_dark"]
    blush, sky = colors["cheek"], colors["extra"]
    face_color = colors["extra"] if character == "nyx" else ink_color
    ink = QPen(ink_color, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

    # ground shadow
    if shadow:
        g = QRadialGradient(QPointF(100, 188), 60)
        g.setColorAt(0, QColor(59, 53, 66, 70))
        g.setColorAt(1, QColor(59, 53, 66, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QRectF(40, 178, 120, 20))

    # Character details are drawn behind the shared face and badge.
    if character == "fox":
        tail = QPainterPath()
        tail.moveTo(145, 144)
        tail.quadTo(188, 140, 176, 105)
        tail.quadTo(171, 127, 149, 126)
        p.setPen(QPen(ink_color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(coral)
        p.drawPath(tail)
        for x in (54, 146):
            ear = QPainterPath()
            ear.moveTo(x - 15, 47)
            ear.lineTo(x, 12)
            ear.lineTo(x + 17, 47)
            ear.closeSubpath()
            p.setPen(QPen(ink_color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(coral)
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(x - 7, 41)
            inner.lineTo(x, 24)
            inner.lineTo(x + 8, 41)
            inner.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(paper_shade)
            p.drawPath(inner)
    elif character == "cat":
        for x in (57, 143):
            ear = QPainterPath()
            ear.moveTo(x - 20, 50)
            ear.lineTo(x - 15, 15)
            ear.lineTo(x + 2, 32)
            ear.lineTo(x + 18, 15)
            ear.lineTo(x + 23, 50)
            ear.closeSubpath()
            p.setPen(QPen(ink_color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(paper)
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(x - 11, 43)
            inner.lineTo(x - 10, 27)
            inner.lineTo(x + 1, 39)
            inner.lineTo(x + 11, 27)
            inner.lineTo(x + 13, 43)
            inner.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(coral)
            p.drawPath(inner)
        p.setPen(QPen(ink_color, 3, Qt.SolidLine, Qt.RoundCap))
        for y in (105, 113):
            p.drawLine(QPointF(40, y), QPointF(17, y - 5))
            p.drawLine(QPointF(40, y + 7), QPointF(17, y + 11))
            p.drawLine(QPointF(160, y), QPointF(183, y - 5))
            p.drawLine(QPointF(160, y + 7), QPointF(183, y + 11))
    elif character == "nyx":
        for x in (55, 145):
            ear = QPainterPath()
            ear.moveTo(x - 19, 54)
            ear.lineTo(x - 12, 16)
            ear.lineTo(x + 1, 34)
            ear.lineTo(x + 17, 18)
            ear.lineTo(x + 21, 54)
            ear.closeSubpath()
            p.setPen(QPen(ink_color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(paper)
            p.drawPath(ear)
            inner = QPainterPath()
            inner.moveTo(x - 10, 47)
            inner.lineTo(x - 8, 29)
            inner.lineTo(x + 1, 40)
            inner.lineTo(x + 10, 30)
            inner.lineTo(x + 12, 47)
            inner.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(coral_dark)
            p.drawPath(inner)
    elif character == "robot":
        p.setPen(QPen(ink_color, 6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(100, 22), QPointF(100, 9))
        p.setPen(QPen(ink_color, 4))
        p.setBrush(coral)
        p.drawEllipse(QPointF(100, 8), 7, 7)
        p.setPen(QPen(ink_color, 5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(mint)
        p.drawRoundedRect(QRectF(22, 83, 18, 38), 8, 8)
        p.drawRoundedRect(QRectF(160, 83, 18, 38), 8, 8)

    # little feet
    p.setPen(ink)
    p.setBrush(coral)
    p.drawRoundedRect(QRectF(62, 166, 30, 18), 9, 9)
    p.drawRoundedRect(QRectF(108, 166, 30, 18), 9, 9)

    # arms (one waves when happy / done)
    wave = math.sin(t * 9) * 18 if mood in ("happy", "done", "excited") else 0
    p.setPen(QPen(ink_color, 7, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(38, 114), QPointF(27, 126))                      # left arm resting
    rx, ry = 162, 108
    ang = math.radians(-55 + wave) if wave else math.radians(50)
    p.drawLine(QPointF(rx, ry), QPointF(rx + 13 * math.cos(ang), ry + 13 * math.sin(ang)))
    p.setPen(QPen(ink_color, 5))
    p.setBrush(coral)
    p.drawEllipse(QPointF(24, 129), 9, 9)
    p.drawEllipse(QPointF(rx + 17 * math.cos(ang), ry + 17 * math.sin(ang)), 9, 9)

    # body = a chubby page with a folded corner
    body = QPainterPath()
    if character == "robot":
        body.addRoundedRect(QRectF(38, 24, 124, 148), 28, 28)
    elif character == "nyx":
        body.moveTo(38, 69)
        body.lineTo(50, 43)
        body.lineTo(76, 48)
        body.lineTo(100, 20)
        body.lineTo(124, 48)
        body.lineTo(150, 43)
        body.lineTo(162, 69)
        body.lineTo(162, 150)
        body.quadTo(162, 172, 140, 172)
        body.lineTo(60, 172)
        body.quadTo(38, 172, 38, 150)
        body.closeSubpath()
    elif character == "cat":
        body.moveTo(48, 49)
        body.lineTo(48, 39)
        body.lineTo(65, 49)
        body.lineTo(135, 49)
        body.lineTo(152, 39)
        body.lineTo(152, 49)
        body.lineTo(162, 58)
        body.lineTo(162, 150)
        body.quadTo(162, 172, 140, 172)
        body.lineTo(60, 172)
        body.quadTo(38, 172, 38, 150)
        body.lineTo(38, 58)
        body.closeSubpath()
    elif character == "fox":
        body.moveTo(55, 37)
        body.lineTo(128, 22)
        body.lineTo(162, 56)
        body.lineTo(162, 150)
        body.quadTo(162, 172, 140, 172)
        body.lineTo(60, 172)
        body.quadTo(38, 172, 38, 150)
        body.lineTo(38, 53)
        body.closeSubpath()
    else:
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
    grad.setColorAt(0, paper)
    grad.setColorAt(1, paper_shade)
    p.setPen(ink)
    p.setBrush(grad)
    p.drawPath(body)

    if character == "nyx":
        p.setPen(QPen(coral, 2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        hood_rim = QPainterPath()
        hood_rim.moveTo(51, 75)
        hood_rim.quadTo(100, 47, 149, 75)
        p.drawPath(hood_rim)
        p.setPen(Qt.NoPen)
        p.setBrush(mint)
        p.drawEllipse(QPointF(100, 53), 7, 7)
        p.setBrush(paper)
        p.drawEllipse(QPointF(104, 50), 6, 6)
        _star(p, 72, 66, 4, mint)
        _star(p, 128, 66, 4, mint)

    # folded corner (mint)
    fold = QPainterPath()
    fold.moveTo(128, 22)
    fold.lineTo(128, 46)
    fold.quadTo(128, 56, 138, 56)
    fold.lineTo(162, 56)
    fold.closeSubpath()
    if character == "paper":
        p.setBrush(mint)
        p.drawPath(fold)

    # belly badge: two swirly convert arrows (spin while working)
    p.save()
    p.translate(100, 140)
    if mood == "working":
        p.rotate((t * 360) % 360)
    p.setPen(QPen(coral, 6, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    r = QRectF(-15, -15, 30, 30)
    p.drawArc(r, 20 * 16, 140 * 16)
    p.drawArc(r, 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(coral)
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
    p.setBrush(blush)
    p.drawEllipse(QRectF(48, 96, 22, 13))
    p.drawEllipse(QRectF(130, 96, 22, 13))

    # eyes
    lx, rx2, ey = 72, 128, 80
    look_dx = max(-1.0, min(1.0, look)) * 4
    if mood in ("happy", "done"):
        p.setPen(QPen(face_color, 7, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for x in (lx, rx2):  # ^ ^
            p.drawArc(QRectF(x - 12, ey - 6, 24, 22), 20 * 16, 140 * 16)
    elif mood == "sleepy" or blink > 0.85:
        p.setPen(QPen(face_color, 6, Qt.SolidLine, Qt.RoundCap))
        for x in (lx, rx2):
            p.drawLine(QPointF(x - 11, ey + 4), QPointF(x + 11, ey + 4))
    else:
        big = 1.25 if mood == "excited" else 1.0
        h = 26 * big * (1 - blink)
        w = 20 * big
        p.setPen(Qt.NoPen)
        p.setBrush(face_color)
        for x in (lx, rx2):
            p.drawEllipse(QRectF(x - w / 2 + look_dx, ey - h / 2 + 2, w, max(h, 3)))
        if h > 8:  # sparkle highlights
            p.setBrush(QColor("white"))
            for x in (lx, rx2):
                p.drawEllipse(QRectF(x - 6 + look_dx, ey - h / 2 + 5, 8 * big, 8 * big))
                p.drawEllipse(QRectF(x + 3 + look_dx, ey + 3, 4 * big, 4 * big))
        if mood == "sad":
            p.setPen(QPen(face_color, 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(lx - 12, ey - 20), QPointF(lx + 8, ey - 26))
            p.drawLine(QPointF(rx2 + 12, ey - 20), QPointF(rx2 - 8, ey - 26))

    # mouth
    p.setPen(QPen(face_color, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    if mood in ("excited", "done"):
        m = QPainterPath()
        m.moveTo(88, 104)
        m.quadTo(100, 108, 112, 104)
        m.quadTo(110, 124, 100, 124)
        m.quadTo(90, 124, 88, 104)
        p.setBrush(coral_dark)
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
        p.setPen(QPen(ink_color, 3))
        p.setBrush(sky)
        p.drawPath(d)
    if mood == "done":  # sparkles
        for i, (sx, sy) in enumerate(((20, 40), (182, 30), (178, 140))):
            k = 0.6 + 0.4 * math.sin(t * 6 + i * 2)
            _star(p, sx, sy, 10 * k, mint_dark if i % 2 else coral)
    if mood == "sleepy":
        p.setPen(ink_color)
        f = QFont()
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


def buddy_image(size: int, mood: str = "idle", shadow: bool = False,
                character: str = DEFAULT_CHARACTER) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    draw_buddy(p, QRectF(0, 0, size, size), mood, shadow=shadow, character=character)
    p.end()
    return img


def buddy_pixmap(size: int, mood: str = "idle", character: str = DEFAULT_CHARACTER) -> QPixmap:
    return QPixmap.fromImage(buddy_image(size, mood, character=character))


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
        draw_buddy(p, rect, self.mood, self.blink, self.t, self.look,
                   character=self._settings().get("character", DEFAULT_CHARACTER))
        if self.bubble:
            self._draw_bubble(p, self.bubble, QPointF(rect.center().x() - 20, rect.top() + 18))
        p.end()

    def _draw_bubble(self, p: QPainter, text: str, tail: QPointF):
        f = QFont()
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
        dark = self._settings().get("theme") == "dark"
        bubble_ink = QColor("#eeeaf1") if dark else INK
        bubble_border = QColor(self._settings().get("accent_color", "#ed7968")) if dark else INK
        if not bubble_border.isValid():
            bubble_border = INK
        p.setPen(QPen(bubble_border, 3))
        p.setBrush(QColor("#292b33") if dark else QColor("#fffdf9"))
        p.drawPath(path)
        p.setPen(bubble_ink)
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
