from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

ICONS_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"

ICON_NAMES = {
    "antenna": "Anténa / radiový spoj",
    "wifi": "Wi-Fi access point",
    "network": "Router",
    "switch": "Switch",
    "firewall": "Firewall",
    "server": "Server",
    "nas": "NAS / úložiště",
    "computer": "Počítač",
    "phone": "VoIP telefon",
    "printer": "Tiskárna",
    "camera": "IP kamera",
    "globe": "Internet",
    "cloud": "Cloudová služba",
}
DEFAULT_ICON = "antenna"


def icon_key(name: str) -> str:
    key = Path(name).stem
    return key if key in ICON_NAMES else DEFAULT_ICON


@lru_cache(maxsize=None)
def get_icon(name: str) -> QIcon:
    return QIcon(str(ICONS_DIR / f"{icon_key(name)}.svg"))


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(tile_pixmap(DEFAULT_ICON, size))
    return icon


def tile_pixmap(name: str, size: int, ratio: float = 1.0) -> QPixmap:
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#EEF7EE"))
    painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.18, size * 0.18)
    margin = round(size * 0.1)
    get_icon(name).paint(painter, QRect(margin, margin, size - 2 * margin, size - 2 * margin))
    painter.end()
    return pixmap
