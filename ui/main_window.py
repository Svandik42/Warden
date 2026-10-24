from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr

from .host_delegate import TILE_SIZE, HostDelegate

INTERVALS = [
    ("10 vteřinách", 10),
    ("15 vteřinách", 15),
    ("20 vteřinách", 20),
    ("30 vteřinách", 30),
    ("1 minutě", 60),
    ("5 minutách", 300),
    ("10 minutách", 600),
    ("30 minutách", 1800),
    ("1 hodině", 3600),
]

GRID_STYLE = """
QListView#hostGrid {
    background: #EEF7EE;
    border: 1px solid #CFE3CF;
    border-radius: 6px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Warden[*]")
        self.resize(900, 540)
        self.confirm_close: Callable[[], bool] = lambda: True

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(self._build_top_bar())

        middle = QHBoxLayout()
        middle.addWidget(self._build_host_view(), 1)
        middle.addLayout(self._build_side_buttons())
        layout.addLayout(middle, 1)

        self.setCentralWidget(central)
        self.mail_label = QLabel()
        self.statusBar().addPermanentWidget(self.mail_label)
        self.statusBar().showMessage(tr("Připraveno"))


    def _build_top_bar(self) -> QHBoxLayout:
        self.ping_button = QPushButton(tr("Ping 1x"))

        self.auto_check = QCheckBox(tr("Auto po"))
        self.auto_check.setChecked(True)

        self.interval_combo = QComboBox()
        for label, seconds in INTERVALS:
            self.interval_combo.addItem(tr(label), seconds)
        self.set_interval(15)

        self.cycle_progress = QProgressBar()
        self.cycle_progress.setRange(0, 1000)
        self.cycle_progress.setTextVisible(False)
        self.cycle_progress.setFixedHeight(10)

        bar = QHBoxLayout()
        bar.addWidget(self.ping_button)
        bar.addSpacing(12)
        bar.addWidget(self.auto_check)
        bar.addWidget(self.interval_combo)
        bar.addSpacing(12)
        bar.addWidget(self.cycle_progress, 1)
        return bar

    def _build_host_view(self) -> QListView:
        view = QListView()
        view.setObjectName("hostGrid")
        view.setStyleSheet(GRID_STYLE)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setMovement(QListView.Movement.Static)
        view.setGridSize(TILE_SIZE + QSize(6, 6))
        view.setUniformItemSizes(True)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setMouseTracking(True)
        view.setItemDelegate(HostDelegate(view))
        self.host_view = view
        return view

    def _build_side_buttons(self) -> QVBoxLayout:
        self.add_button = QPushButton(tr("Přidat…"))
        self.delete_button = QPushButton(tr("Smazat…"))
        self.save_button = QPushButton(tr("Uložit"))
        self.connect_button = QPushButton(tr("Propojení"))
        self.trace_button = QPushButton(tr("Trasování…"))
        self.settings_button = QPushButton(tr("Nastavení…"))
        self.charts_button = QPushButton(tr("Grafy a logy"))
        self.help_button = QPushButton(tr("Nápověda"))
        self.help_button.setToolTip(tr("Návod k použití (F1)"))
        self.quit_button = QPushButton(tr("Konec"))

        self.connect_button.setEnabled(False)
        self.connect_button.setToolTip(tr("V originálu IPWatch také nedostupné"))
        self.trace_button.setToolTip(tr("Trasa paketů k vybranému prvku (tracert)"))
        self.charts_button.setToolTip(tr("Graf odezvy a log výpadků"))

        column = QVBoxLayout()
        for group in ((self.add_button, self.delete_button, self.save_button),
                      (self.connect_button, self.trace_button),
                      (self.settings_button, self.charts_button)):
            for button in group:
                button.setFixedWidth(130)
                column.addWidget(button)
            column.addSpacing(14)
        column.addStretch(1)
        self.help_button.setFixedWidth(130)
        column.addWidget(self.help_button)
        self.quit_button.setFixedWidth(130)
        column.addWidget(self.quit_button)
        return column


    def interval_seconds(self) -> int:
        return self.interval_combo.currentData()

    def set_interval(self, seconds: int) -> None:
        index = self.interval_combo.findData(seconds)
        if index < 0:
            self.interval_combo.addItem(f"{seconds} s", seconds)
            index = self.interval_combo.count() - 1
        self.interval_combo.setCurrentIndex(index)

    def show_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def show_mail_status(self, text: str, ok: bool) -> None:
        self.mail_label.setStyleSheet("" if ok else "color: #E53935;")
        self.mail_label.setText(text)
        self.mail_label.setToolTip(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.confirm_close():
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    import sys

    from PySide6.QtGui import QStandardItem, QStandardItemModel
    from PySide6.QtWidgets import QApplication

    from core.models import Status

    from .roles import HostRole

    demo = [
        ("", "188.120.203.181", "antenna", Status.UP, 0.4, 22164),
        ("Server", "192.168.1.10", "server", Status.UP, 0.6, 22164),
        ("Kerio", "192.168.1.1", "computer", Status.UP, 0.9, 1295),
        ("DC", "192.168.1.5", "computer", Status.UP, 0.5, 22164),
        ("Server_backup", "192.168.1.11", "server", Status.UP, 1.2, 3636),
        ("Benice", "10.10.1.1", "antenna", Status.UP, 3.1, 9002),
        ("OU_Pe", "185.160.20.156", "antenna", Status.DOWN, None, 0),
        ("Hala", "10.10.3.1", "antenna", Status.UP, 16.0, 361),
        ("Hospoda", "10.10.4.1", "antenna", Status.UP, 15.2, 1021),
        ("VOIP", "192.168.1.30", "globe", Status.UP, 0.7, 22164),
        ("Canon", "192.168.1.40", "printer", Status.UP, 0.8, 22164),
        ("TercieVDSL", "10.10.5.1", "antenna", Status.UP, 16.4, 6113),
        ("Tercie", "10.10.5.2", "antenna", Status.UP, 15.9, 5325),
        ("VDSL_domu", "10.20.0.1", "network", Status.UNKNOWN, None, 0),
    ]

    app = QApplication(sys.argv)
    window = MainWindow()
    model = QStandardItemModel()
    for name, address, icon, status, rtt, ok in demo:
        item = QStandardItem(name)
        item.setData(address, HostRole.ADDRESS)
        item.setData(status, HostRole.STATUS)
        item.setData(rtt, HostRole.RTT_MS)
        item.setData(ok, HostRole.OK_STREAK)
        item.setData(icon, HostRole.ICON)
        model.appendRow(item)
    window.host_view.setModel(model)
    window.show()
    sys.exit(app.exec())
