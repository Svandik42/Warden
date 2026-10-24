from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from core.models import Host, HostState, Status

from .roles import HostRole


class HostListModel(QAbstractListModel):
    def __init__(self, hosts: list[Host]) -> None:
        super().__init__()
        self._hosts = hosts
        self._states: dict[int, HostState] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._hosts)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        host = self._hosts[index.row()]
        state = self._states.get(host.id)
        if role == Qt.ItemDataRole.DisplayRole:
            return host.description
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{host.description}\n{host.address}" if host.description else host.address
        if role == HostRole.STATUS:
            return state.status if state else Status.UNKNOWN
        if role == HostRole.RTT_MS:
            return state.last_rtt_ms if state else None
        if role == HostRole.OK_STREAK:
            return state.ok_streak if state else 0
        if role == HostRole.ICON:
            return host.icon
        if role == HostRole.ADDRESS:
            return host.address
        if role == HostRole.ENABLED:
            return host.enabled
        return None

    def update_states(self, states: dict[int, HostState]) -> None:
        self._states = states
        if self._hosts:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._hosts) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right)

    def host_at(self, row: int) -> Host:
        return self._hosts[row]

    def add_host(self, host: Host) -> None:
        row = len(self._hosts)
        self.beginInsertRows(QModelIndex(), row, row)
        self._hosts.append(host)
        self.endInsertRows()

    def replace_host(self, row: int, host: Host) -> None:
        self._hosts[row] = host
        index = self.index(row)
        self.dataChanged.emit(index, index)

    def set_hosts(self, hosts: list[Host]) -> None:
        self.beginResetModel()
        self._hosts[:] = hosts
        self._states = {}
        self.endResetModel()

    def remove_host(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._hosts[row]
        self.endRemoveRows()


if __name__ == "__main__":
    import sys

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from core.storage import load_hosts

    from .main_window import MainWindow

    app = QApplication(sys.argv)
    hosts = load_hosts()
    model = HostListModel(hosts)
    window = MainWindow()
    window.host_view.setModel(model)

    model.update_states({
        1: HostState(status=Status.UP, last_rtt_ms=7, ok_streak=12),
        2: HostState(status=Status.DOWN),
    })

    QTimer.singleShot(3000, lambda: model.update_states({1: HostState(status=Status.DOWN)}))

    window.show()
    sys.exit(app.exec())
