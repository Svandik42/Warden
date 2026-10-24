from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from core.i18n import language

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def help_file() -> Path:
    localized = DOCS_DIR / f"help_{language()}.html"
    return localized if localized.exists() else DOCS_DIR / "help_cs.html"


def open_help() -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_file())))
