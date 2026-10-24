from enum import IntEnum

from PySide6.QtCore import Qt

_BASE = int(Qt.ItemDataRole.UserRole)


class HostRole(IntEnum):
    ADDRESS = _BASE + 1
    STATUS = _BASE + 2
    RTT_MS = _BASE + 3
    OK_STREAK = _BASE + 4
    ICON = _BASE + 5
    ENABLED = _BASE + 6
