import re

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.models import Host

from .icons import ICON_NAMES, icon_key, tile_pixmap
from .widgets import NumberField, with_unit

ADDRESS_PATTERN = re.compile(r"[A-Za-z0-9_\[][A-Za-z0-9_.:%\[\]-]*")


def address_problem(address: str) -> str:
    if not address:
        return ""
    if "@" in address:
        return tr("Adresa nesmí obsahovat @. Zadej IP adresu nebo jméno počítače.")
    if any(ch.isspace() for ch in address):
        return tr("Adresa nesmí obsahovat mezery.")
    if address.startswith("-"):
        return tr("Adresa nesmí začínat pomlčkou.")
    if not ADDRESS_PATTERN.fullmatch(address):
        return tr("Adresa obsahuje nepovolené znaky.")
    return ""


class HostDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, title: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or tr("Vlastnosti prvku"))
        self.setMinimumWidth(420)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText(tr("IP adresa nebo jméno, např. 192.168.1.1"))
        self.address_hint = QLabel()
        self.address_hint.setStyleSheet("color: #E53935;")
        self.address_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.address_hint.setWordWrap(True)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText(tr("Popis místa, např. OU_Pe"))

        self.timeout_spin = NumberField(100, 10000, width=80)
        self.timeout_spin.setSingleStep(500)
        self.timeout_spin.setValue(3000)

        self.icon_combo = QComboBox()
        self.icon_combo.setIconSize(QSize(26, 26))
        ratio = self.devicePixelRatioF()
        for key, label in ICON_NAMES.items():
            self.icon_combo.addItem(QIcon(tile_pixmap(key, 26, ratio)), tr(label), key)

        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(52, 52)

        self.enabled_check = QCheckBox(tr("Sledovat tento prvek"))
        self.enabled_check.setChecked(True)

        icon_row = QHBoxLayout()
        icon_row.addWidget(self.icon_combo, 1)
        icon_row.addWidget(self.icon_preview)

        form = QFormLayout()
        form.addRow(tr("Host:"), self.address_edit)
        form.addRow("", self.address_hint)
        form.addRow(tr("Popis:"), self.description_edit)
        form.addRow(tr("Timeout:"), with_unit(self.timeout_spin, "ms"))
        form.addRow(tr("Ikona:"), icon_row)
        form.addRow("", self.enabled_check)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Storno"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.address_edit.textChanged.connect(self._update_ok_button)
        self.icon_combo.currentIndexChanged.connect(self._update_preview)
        self._update_ok_button()
        self._update_preview()

    def icon(self) -> str:
        return self.icon_combo.currentData()

    def set_icon(self, name: str) -> None:
        self.icon_combo.setCurrentIndex(max(0, self.icon_combo.findData(icon_key(name))))

    def address(self) -> str:
        return self.address_edit.text().strip()

    def set_host(self, host: Host) -> None:
        self.address_edit.setText(host.address)
        self.description_edit.setText(host.description)
        self.timeout_spin.setValue(host.timeout_ms)
        self.set_icon(host.icon)
        self.enabled_check.setChecked(host.enabled)

    def get_host(self, host_id: int) -> Host:
        return Host(
            id=host_id,
            address=self.address(),
            description=self.description_edit.text().strip(),
            timeout_ms=self.timeout_spin.value(),
            icon=self.icon(),
            enabled=self.enabled_check.isChecked(),
        )

    def _update_ok_button(self) -> None:
        address = self.address()
        problem = address_problem(address)
        self.address_hint.setText(problem)
        self.address_hint.setVisible(bool(problem))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(address) and not problem)

    def _update_preview(self) -> None:
        self.icon_preview.setPixmap(tile_pixmap(self.icon(), 52, self.devicePixelRatioF()))


if __name__ == "__main__":
    for ok in ("192.168.1.1", "fe80::1%12", "[2001:db8::1]", "server-01.firma.cz", "OU_Pe"):
        assert address_problem(ok) == "", ok
    for bad in ("-?", "smtp@seznam.cz", "a b", "x;calc", "x&y", "\"q\""):
        assert address_problem(bad), bad
    print("HostDialog OK")
