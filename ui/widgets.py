from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QAbstractSpinBox, QHBoxLayout, QLabel, QSpinBox, QWidget


class NumberField(QSpinBox):
    def __init__(self, minimum: int, maximum: int, width: int = 70) -> None:
        super().__init__()
        self.setRange(minimum, maximum)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFixedWidth(width)
        self.setAccelerated(True)

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


def with_unit(field: QWidget, unit: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(field)
    layout.addWidget(QLabel(unit))
    layout.addStretch(1)
    return row
