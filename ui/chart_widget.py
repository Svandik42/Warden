import math
from datetime import datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.history import Sample

LINE_COLOR = QColor("#1E88E5")
DOWN_COLOR = QColor("#E53935")
GRID_COLOR = QColor("#E6E6E6")
AXIS_TEXT = QColor("#555555")
BACKGROUND = QColor("#FFFFFF")


def nice_step(span: float, ticks: int = 5) -> float:
    raw = span / max(1, ticks)
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


class RttChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._samples: list[Sample] = []
        self._start = datetime.now() - timedelta(minutes=1)
        self._end = datetime.now()
        self._title = ""
        self._y_title = ""

    def set_data(self, samples: list[Sample], start: datetime, end: datetime, title: str, y_title: str) -> None:
        self._samples = samples
        self._start, self._end = start, max(end, start + timedelta(seconds=1))
        self._title = title
        self._y_title = y_title
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BACKGROUND)
        painter.drawRoundedRect(QRectF(self.rect()), 6, 6)

        font = QFont(self.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - 1))
        painter.setFont(font)
        metrics = painter.fontMetrics()
        plot = QRectF(58, 30, self.width() - 58 - 18, self.height() - 30 - 32)
        if plot.width() < 40 or plot.height() < 40:
            return

        rtts = [s.rtt_ms for s in self._samples if s.rtt_ms is not None]
        step = nice_step(max(10.0, max(rtts, default=0) * 1.15))
        top = step * math.ceil(max(10.0, max(rtts, default=0) * 1.15) / step)
        span = (self._end - self._start).total_seconds()

        def x_of(when: datetime) -> float:
            return plot.left() + (when - self._start).total_seconds() / span * plot.width()

        def y_of(value: float) -> float:
            return plot.bottom() - value / top * plot.height()

        painter.setPen(AXIS_TEXT)
        painter.drawText(QRectF(0, 6, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self._title)

        value = 0.0
        while value <= top + 1e-9:
            y = y_of(value)
            painter.setPen(QPen(GRID_COLOR, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(AXIS_TEXT)
            label = f"{value:g}"
            painter.drawText(QRectF(plot.left() - 50, y - 9, 44, 18),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)
            value += step

        time_format = "%H:%M:%S" if span <= 3600 else "%d.%m. %H:%M"
        for i in range(5):
            when = self._start + timedelta(seconds=span * i / 4)
            x = x_of(when)
            painter.setPen(QPen(GRID_COLOR, 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(AXIS_TEXT)
            text = when.strftime(time_format)
            width = metrics.horizontalAdvance(text)
            left = min(max(x - width / 2, 2), self.width() - width - 2)
            painter.drawText(QPointF(left, plot.bottom() + 18), text)

        painter.save()
        painter.translate(14, plot.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-plot.height() / 2, -8, plot.height(), 16), Qt.AlignmentFlag.AlignCenter, self._y_title)
        painter.restore()

        painter.setClipRect(plot.adjusted(-6, -6, 6, 6))
        path = QPainterPath()
        singles: list[QPointF] = []
        segment: list[QPointF] = []
        for sample in self._samples + [Sample(self._end, None)]:
            if sample.rtt_ms is None:
                if len(segment) == 1:
                    singles.append(segment[0])
                elif segment:
                    path.moveTo(segment[0])
                    for point in segment[1:]:
                        path.lineTo(point)
                segment = []
            else:
                segment.append(QPointF(x_of(sample.timestamp), y_of(sample.rtt_ms)))
        painter.setPen(QPen(LINE_COLOR, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(LINE_COLOR)
        for point in singles:
            painter.drawEllipse(point, 2.5, 2.5)
        painter.setBrush(DOWN_COLOR)
        for sample in self._samples:
            if sample.rtt_ms is None:
                painter.drawEllipse(QPointF(x_of(sample.timestamp), plot.bottom()), 4, 4)
        painter.end()
