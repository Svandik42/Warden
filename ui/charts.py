from datetime import datetime, timedelta

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.history import EventLog, RttHistory
from core.i18n import tr
from core.models import EventType, Host

from .chart_widget import RttChart
from .icons import tile_pixmap

RANGES = [
    ("Posledních 15 minut", 900),
    ("Poslední hodina", 3600),
    ("Posledních 6 hodin", 21600),
    ("Posledních 24 hodin", 86400),
    ("Vše od spuštění", 0),
]
LOG_HEADERS = ["Čas", "Událost", "Prvek", "Adresa"]
DOWN_COLOR = QColor("#E53935")
UP_COLOR = QColor("#43A047")


class ChartsDialog(QDialog):
    def __init__(self, hosts: list[Host], history: RttHistory, event_log: EventLog,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Grafy a logy"))
        self.resize(1000, 660)
        self.hosts = hosts
        self.history = history
        self.event_log = event_log
        self._shown_ids: list[int] = []

        self.host_list = QListWidget()
        self.host_list.setIconSize(QSize(28, 28))
        self.host_list.setFixedWidth(220)

        self.range_combo = QComboBox()
        for label, seconds in RANGES:
            self.range_combo.addItem(tr(label), seconds)
        self.range_combo.setCurrentIndex(1)
        self.stats_label = QLabel()

        top_row = QHBoxLayout()
        top_row.addWidget(self.range_combo)
        top_row.addSpacing(12)
        top_row.addWidget(self.stats_label, 1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_chart())
        splitter.addWidget(self._build_log())
        splitter.setSizes([380, 240])

        right = QVBoxLayout()
        right.addLayout(top_row)
        right.addWidget(splitter, 1)

        layout = QHBoxLayout(self)
        layout.addWidget(self.host_list)
        layout.addLayout(right, 1)

        self.host_list.currentRowChanged.connect(self.refresh)
        self.range_combo.currentIndexChanged.connect(self.refresh)
        self.only_selected_check.toggled.connect(self.refresh)
        self.refresh()

    def _build_chart(self) -> QWidget:
        self.chart = RttChart()
        return self.chart

    def _build_log(self) -> QWidget:
        self.only_selected_check = QCheckBox(tr("Jen vybraný prvek"))
        self.log_table = QTableWidget(0, len(LOG_HEADERS))
        self.log_table.setHorizontalHeaderLabels([tr(h) for h in LOG_HEADERS])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("<b>" + tr("Log událostí") + "</b>"))
        title_row.addStretch(1)
        title_row.addWidget(self.only_selected_check)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.addLayout(title_row)
        layout.addWidget(self.log_table)
        return page

    def refresh(self) -> None:
        self._refresh_host_list()
        self._refresh_chart()
        self._refresh_log()

    def _current_host(self) -> Host | None:
        item = self.host_list.currentItem()
        if item is None:
            return None
        host_id = item.data(Qt.ItemDataRole.UserRole)
        return next((h for h in self.hosts if h.id == host_id), None)

    def _refresh_host_list(self) -> None:
        ids = [h.id for h in self.hosts]
        if ids == self._shown_ids:
            return
        current = self._current_host()
        self.host_list.blockSignals(True)
        self.host_list.clear()
        ratio = self.devicePixelRatioF()
        for host in self.hosts:
            item = QListWidgetItem(QIcon(tile_pixmap(host.icon, 28, ratio)), host.description or host.address)
            item.setData(Qt.ItemDataRole.UserRole, host.id)
            item.setToolTip(host.address)
            self.host_list.addItem(item)
        rows = [i for i, h in enumerate(self.hosts) if current and h.id == current.id]
        self.host_list.setCurrentRow(rows[0] if rows else (0 if self.hosts else -1))
        self.host_list.blockSignals(False)
        self._shown_ids = ids

    def _refresh_chart(self) -> None:
        host = self._current_host()
        samples = self.history.samples(host.id) if host else []
        seconds = self.range_combo.currentData()
        now = datetime.now()
        if seconds:
            cutoff = now - timedelta(seconds=seconds)
            samples = [s for s in samples if s.timestamp >= cutoff]
        start = samples[0].timestamp if samples else now - timedelta(minutes=1)
        start = min(start, now - timedelta(minutes=1))
        title = f"{host.description or host.address}  ({host.address})" if host else ""
        self.chart.set_data(samples, start, now, title, tr("odezva [ms]"))
        self.stats_label.setText(self._stats_text(samples))

    @staticmethod
    def _stats_text(samples: list) -> str:
        if not samples:
            return tr("Zatím žádná data, historie se sbírá od spuštění programu.")
        rtts = [s.rtt_ms for s in samples if s.rtt_ms is not None]
        success = 100 * len(rtts) / len(samples)
        text = tr("Pingů: {count}  ·  úspěšnost {success} %", count=len(samples), success=f"{success:.1f}")
        if rtts:
            text += tr("  ·  odezva min {min} / průměr {avg} / max {max} ms",
                       min=f"{min(rtts):.0f}", avg=f"{sum(rtts) / len(rtts):.0f}", max=f"{max(rtts):.0f}")
        return text

    def _refresh_log(self) -> None:
        entries = self.event_log.read()
        host = self._current_host()
        if self.only_selected_check.isChecked() and host is not None:
            entries = [e for e in entries if e.address == host.address]
        self.log_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            down = entry.event_type in (EventType.HOST_DOWN, EventType.NETWORK_DOWN)
            color = DOWN_COLOR if down else UP_COLOR
            values = [entry.timestamp.strftime("%d.%m.%Y %H:%M:%S"), entry.display_label(), entry.name, entry.address]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1:
                    item.setForeground(color)
                self.log_table.setItem(row, column, item)
