from PySide6.QtCore import QModelIndex, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from core.i18n import tr
from core.models import Status

from .icons import get_icon
from .roles import HostRole

TILE_SIZE = QSize(150, 104)
ICON_SIZE = 44
TEXT_COLOR = QColor("#212121")
SELECTION_COLOR = QColor("#1E88E5")
DISABLED_COLOR = QColor("#9E9E9E")

STATUS_COLORS = {
    Status.UP: (QColor("#2E7D32"), QColor("#43A047"), None),
    Status.DOWN: (QColor("#C62828"), QColor("#E53935"), QColor("#FDE3E1")),
    Status.UNKNOWN: (QColor("#757575"), QColor("#9E9E9E"), None),
}


def status_text(status: Status, rtt_ms: float | None, ok_streak: int, enabled: bool = True) -> str:
    if not enabled:
        return tr("nesledováno")
    if status == Status.DOWN:
        return tr("nedostupný")
    if status == Status.UNKNOWN:
        return tr("čekám na odpověď")
    rtt = f"{rtt_ms:.0f} ms" if rtt_ms is not None else "– ms"
    return f"{rtt} ({ok_streak}x OK)"


class HostDelegate(QStyledItemDelegate):
    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return TILE_SIZE

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        enabled = index.data(HostRole.ENABLED) is not False
        status = Status(index.data(HostRole.STATUS) or Status.UNKNOWN) if enabled else Status.UNKNOWN
        line_color, dot_color, tile_color = STATUS_COLORS[status]
        rect = option.rect.adjusted(3, 3, -3, -3)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_background(painter, option, QRectF(rect), tile_color)

        icon_rect = QRect(rect.center().x() - ICON_SIZE // 2, rect.top() + 6, ICON_SIZE, ICON_SIZE)
        painter.setOpacity(1.0 if enabled else 0.35)
        get_icon(index.data(HostRole.ICON) or "").paint(painter, icon_rect)
        painter.setOpacity(1.0)
        if enabled:
            painter.setPen(QPen(QColor("white"), 2))
            painter.setBrush(dot_color)
            painter.drawEllipse(QRectF(icon_rect.right() - 10, icon_rect.bottom() - 10, 13, 13))

        name = index.data(Qt.ItemDataRole.DisplayRole) or index.data(HostRole.ADDRESS) or ""
        bold = QFont(option.font)
        bold.setBold(True)
        name_rect = QRect(rect.left() + 4, icon_rect.bottom() + 5, rect.width() - 8, 18)
        self._draw_line(painter, bold, TEXT_COLOR if enabled else DISABLED_COLOR, name_rect, name)

        line = status_text(status, index.data(HostRole.RTT_MS), index.data(HostRole.OK_STREAK) or 0, enabled)
        line_rect = name_rect.translated(0, 18)
        self._draw_line(painter, option.font, line_color, line_rect, line)

        painter.restore()

    @staticmethod
    def _paint_background(painter: QPainter, option: QStyleOptionViewItem,
                          rect: QRectF, tile_color: QColor | None) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            background = QColor(SELECTION_COLOR)
            background.setAlpha(45)
        elif tile_color is not None:
            background = tile_color
        elif hovered:
            background = QColor(0, 0, 0, 16)
        else:
            return

        painter.setPen(QPen(SELECTION_COLOR, 1.5) if selected else Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 6, 6)

    @staticmethod
    def _draw_line(painter: QPainter, font: QFont, color: QColor, rect: QRect, text: str) -> None:
        painter.setFont(font)
        painter.setPen(color)
        elided = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided)
