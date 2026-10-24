import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import SMTP_PRESETS, Settings, SmtpSettings
from core.i18n import LANGUAGES, tr
from core.notify import explain_smtp_error, send_email, supports_starttls

from .widgets import NumberField, with_unit

CUSTOM_PRESET = "Vlastní server"
SECURITY_OPTIONS = [
    ("Bez šifrování (obvykle port 25)", "none"),
    ("STARTTLS (obvykle port 587)", "starttls"),
    ("SSL/TLS (obvykle port 465)", "ssl"),
]
HINT_STYLE = "color: #8a8a8a;"
ERROR_STYLE = "color: #E53935;"
WARNING_STYLE = "color: #FB8C00;"


class _TestSignals(QObject):
    finished = Signal(bool, str)


def _hint(text: str, style: str = HINT_STYLE) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setStyleSheet(style)
    label.setWordWrap(True)
    return label


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Nastavení"))
        self.setMinimumWidth(540)

        tabs = QTabWidget()
        tabs.addTab(self._build_alerts_tab(), tr("Upozornění"))
        tabs.addTab(self._build_message_tab(), tr("Příjemci a zpráva"))
        tabs.addTab(self._build_smtp_tab(), tr("SMTP server"))
        tabs.addTab(self._build_general_tab(), tr("Obecné"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Storno"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self.requested_action: str | None = None

        self._test_signals = _TestSignals(self)
        self._test_signals.finished.connect(self._show_test_result)

    def _build_alerts_tab(self) -> QWidget:
        self.alert_down_check = QCheckBox(tr("Upozornit e-mailem na ztrátu spojení"))
        self.alert_up_check = QCheckBox(tr("Upozornit e-mailem na obnovení spojení"))
        self.fail_spin = NumberField(1, 1000)
        self.ok_spin = NumberField(1, 1000)
        self.icon_spin = NumberField(1, 1000)

        mail_box = QGroupBox(tr("Prvky"))
        mail_form = QFormLayout(mail_box)
        mail_form.addRow(self.alert_down_check)
        mail_form.addRow(self.alert_up_check)
        mail_form.addRow(tr("Výpadek hlásit po:"), with_unit(self.fail_spin, tr(" selháních v řadě").strip()))
        mail_form.addRow(tr("Obnovu hlásit po:"), with_unit(self.ok_spin, tr(" úspěších v řadě").strip()))
        mail_form.addRow(tr("Ikonu zčervenat po:"), with_unit(self.icon_spin, tr(" selháních v řadě").strip()))

        self.network_percent_spin = NumberField(1, 100)
        self.network_min_spin = NumberField(1, 1000)
        network_box = QGroupBox(tr("Výpadek celé sítě"))
        network_form = QFormLayout(network_box)
        network_form.addRow(_hint(tr("Když najednou vypadne většina prvků, pošle se jeden mail "
                                     "„Síť nedostupná“ místo mailu za každý prvek.")))
        network_form.addRow(tr("Nedostupných aspoň:"), with_unit(self.network_percent_spin, tr(" % prvků").strip()))
        network_form.addRow(tr("Sledovaných aspoň:"), with_unit(self.network_min_spin, tr(" prvků").strip()))

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(mail_box)
        layout.addWidget(network_box)
        layout.addStretch(1)
        return page

    def _build_message_tab(self) -> QWidget:
        self.address_list = QListWidget()
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText(tr("adresa@domena.cz"))
        add_button = QPushButton(tr("Přidat"))
        remove_button = QPushButton(tr("Odebrat"))
        add_button.clicked.connect(self._add_address)
        self.address_edit.returnPressed.connect(self._add_address)
        remove_button.clicked.connect(self._remove_address)

        address_row = QHBoxLayout()
        address_row.addWidget(self.address_edit, 1)
        address_row.addWidget(add_button)
        address_row.addWidget(remove_button)

        recipients_box = QGroupBox(tr("Příjemci"))
        recipients_layout = QVBoxLayout(recipients_box)
        recipients_layout.addWidget(self.address_list)
        recipients_layout.addLayout(address_row)
        recipients_layout.addWidget(_hint(tr("Pro SMS přidej e-mailovou adresu SMS brány svého operátora "
                                             "nebo SMS služby.")))

        self.subject_edit = QLineEdit()
        self.body_down_edit = QLineEdit()
        self.body_up_edit = QLineEdit()
        message_box = QGroupBox(tr("Zpráva"))
        message_form = QFormLayout(message_box)
        message_form.addRow(tr("Předmět:"), self.subject_edit)
        message_form.addRow(tr("Výpadek:"), self.body_down_edit)
        message_form.addRow(tr("Obnovení:"), self.body_up_edit)
        message_form.addRow(_hint(tr("<dt> datum, <tm> čas, <ip> sledovaná IP, ostatní jako text.")))

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(recipients_box, 1)
        layout.addWidget(message_box)
        return page

    def _build_smtp_tab(self) -> QWidget:
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(tr(CUSTOM_PRESET), "")
        for name in SMTP_PRESETS:
            self.preset_combo.addItem(name, name)
        self.preset_combo.activated.connect(self._apply_preset)

        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText(tr("např. smtp.seznam.cz"))
        self.server_hint = _hint("", ERROR_STYLE)
        self.server_edit.textChanged.connect(self._check_server)

        self.port_spin = NumberField(1, 65535)
        self.security_combo = QComboBox()
        for label, value in SECURITY_OPTIONS:
            self.security_combo.addItem(tr(label), value)

        self.from_edit = QLineEdit()
        self.from_edit.setPlaceholderText(tr("tvůj e-mail, např. jmeno@seznam.cz"))
        self.auth_check = QCheckBox(tr("Server vyžaduje přihlášení"))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText(tr("prázdné = stejné jako odesílatel"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.plain_warning = _hint(tr("Pozor: bez šifrování se heslo posílá po síti jako čitelný text. "
                                      "Pokud server umí STARTTLS, zvol ho a heslo půjde šifrovaně. "
                                      "Bez šifrování používej jen server ve vlastní síti."), WARNING_STYLE)
        self.auth_check.toggled.connect(self._update_auth_fields)
        self.security_combo.currentIndexChanged.connect(self._update_auth_fields)

        self.test_button = QPushButton(tr("Test SMTP"))
        self.test_button.clicked.connect(self._run_test)
        self.test_result = _hint(tr("Pošle zkušební mail na první adresu v seznamu příjemců."))

        form = QFormLayout()
        form.addRow(tr("Poskytovatel:"), self.preset_combo)
        form.addRow(tr("SMTP server:"), self.server_edit)
        form.addRow("", self.server_hint)
        form.addRow(tr("Port:"), self.port_spin)
        form.addRow(tr("Šifrování:"), self.security_combo)
        form.addRow(tr("Odesílatel (Od):"), self.from_edit)
        form.addRow(self.auth_check)
        form.addRow(tr("Uživ. jméno (e-mail):"), self.username_edit)
        form.addRow(tr("Heslo:"), self.password_edit)
        form.addRow(self.plain_warning)
        form.addRow(_hint(tr("Gmail a Seznam s dvoufázovým ověřením vyžadují heslo pro aplikace. "
                             "Heslo se ukládá zašifrované pro tvůj účet Windows.")))

        self._check_server()
        self._update_auth_fields()

        test_row = QHBoxLayout()
        test_row.addWidget(self.test_button)
        test_row.addWidget(self.test_result, 1)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addLayout(test_row)
        layout.addStretch(1)
        return page

    def _build_general_tab(self) -> QWidget:
        self.autostart_check = QCheckBox(tr("Spouštět Warden po přihlášení do Windows"))
        self.language_combo = QComboBox()
        self.language_combo.addItem(tr("Podle Windows"), "")
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)

        language_row = QFormLayout()
        language_row.addRow(tr("Jazyk / Language:"), self.language_combo)

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self.autostart_check)
        layout.addSpacing(10)
        layout.addLayout(language_row)
        layout.addWidget(_hint(tr("Změna jazyka se projeví po restartu Wardenu.")))
        layout.addSpacing(10)
        layout.addWidget(_hint(tr("Data a nastavení jsou uložená ve složce %APPDATA%\\Warden.")))

        export_button = QPushButton(tr("Exportovat konfiguraci…"))
        import_button = QPushButton(tr("Importovat konfiguraci…"))
        export_button.clicked.connect(lambda: self._request("export"))
        import_button.clicked.connect(lambda: self._request("import"))
        transfer_row = QHBoxLayout()
        transfer_row.addWidget(export_button)
        transfer_row.addWidget(import_button)
        transfer_row.addStretch(1)
        transfer_box = QGroupBox(tr("Přenos na jiný počítač"))
        transfer_layout = QVBoxLayout(transfer_box)
        transfer_layout.addLayout(transfer_row)
        transfer_layout.addWidget(_hint(tr("Uloží prvky i nastavení do jednoho souboru. Heslo SMTP se z bezpečnostních "
                                           "důvodů neexportuje, po importu ho zadej znovu.")))
        layout.addSpacing(10)
        layout.addWidget(transfer_box)
        layout.addStretch(1)
        return page

    def _request(self, action: str) -> None:
        self.requested_action = action
        self.reject()

    def set_settings(self, settings: Settings, autostart: bool) -> None:
        self.alert_down_check.setChecked(settings.alert_down)
        self.alert_up_check.setChecked(settings.alert_up)
        self.fail_spin.setValue(settings.fail_alert_threshold)
        self.ok_spin.setValue(settings.ok_alert_threshold)
        self.icon_spin.setValue(settings.icon_change_threshold)
        self.network_percent_spin.setValue(round(settings.network_down_percent))
        self.network_min_spin.setValue(settings.network_min_hosts)

        self.address_list.clear()
        self.address_list.addItems(settings.addresses)
        self.subject_edit.setText(settings.subject)
        self.body_down_edit.setText(settings.body_down)
        self.body_up_edit.setText(settings.body_up)

        smtp = settings.smtp
        self.server_edit.setText(smtp.server)
        self.port_spin.setValue(smtp.port)
        self.security_combo.setCurrentIndex(max(0, self.security_combo.findData(smtp.security)))
        self.from_edit.setText(smtp.source_email)
        self.auth_check.setChecked(smtp.use_auth)
        self.username_edit.setText(smtp.username)
        self.password_edit.setText(smtp.password)
        self._select_matching_preset()
        self._update_auth_fields()

        self.autostart_check.setChecked(autostart)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(settings.language)))

    def apply_to(self, settings: Settings) -> None:
        settings.alert_down = self.alert_down_check.isChecked()
        settings.alert_up = self.alert_up_check.isChecked()
        settings.fail_alert_threshold = self.fail_spin.value()
        settings.ok_alert_threshold = self.ok_spin.value()
        settings.icon_change_threshold = self.icon_spin.value()
        settings.network_down_percent = self.network_percent_spin.value()
        settings.network_min_hosts = self.network_min_spin.value()
        settings.addresses = self.addresses()
        settings.subject = self.subject_edit.text()
        settings.body_down = self.body_down_edit.text()
        settings.body_up = self.body_up_edit.text()
        settings.smtp = self.smtp_settings()
        settings.language = self.language_combo.currentData()

    def autostart(self) -> bool:
        return self.autostart_check.isChecked()

    def addresses(self) -> list[str]:
        return [self.address_list.item(i).text() for i in range(self.address_list.count())]

    def smtp_settings(self) -> SmtpSettings:
        return SmtpSettings(
            server=self.server_edit.text().strip(),
            port=self.port_spin.value(),
            source_email=self.from_edit.text().strip(),
            use_auth=self.auth_check.isChecked(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            security=self.security_combo.currentData(),
        )

    def _add_address(self) -> None:
        address = self.address_edit.text().strip()
        if "@" not in address or " " in address or address in self.addresses():
            return
        self.address_list.addItem(address)
        self.address_edit.clear()

    def _remove_address(self) -> None:
        for item in self.address_list.selectedItems():
            self.address_list.takeItem(self.address_list.row(item))

    def _apply_preset(self) -> None:
        preset = SMTP_PRESETS.get(self.preset_combo.currentData())
        if preset is None:
            return
        server, port, security = preset
        self.server_edit.setText(server)
        self.port_spin.setValue(port)
        self.security_combo.setCurrentIndex(self.security_combo.findData(security))
        self.auth_check.setChecked(True)

    def _select_matching_preset(self) -> None:
        server = self.server_edit.text().strip().lower()
        for name, (preset_server, _, _) in SMTP_PRESETS.items():
            if server == preset_server:
                self.preset_combo.setCurrentIndex(self.preset_combo.findData(name))
                return
        self.preset_combo.setCurrentIndex(0)

    def _check_server(self) -> None:
        server = self.server_edit.text().strip()
        if "@" in server:
            self.server_hint.setText(tr("Název serveru nesmí obsahovat @, například smtp.seznam.cz."))
        elif " " in server:
            self.server_hint.setText(tr("Název serveru nesmí obsahovat mezery."))
        else:
            self.server_hint.setText("")
        self.server_hint.setVisible(bool(self.server_hint.text()))

    def _update_auth_fields(self) -> None:
        auth = self.auth_check.isChecked()
        self.username_edit.setEnabled(auth)
        self.password_edit.setEnabled(auth)
        self.plain_warning.setVisible(auth and self.security_combo.currentData() == "none")

    def _run_test(self) -> None:
        recipients = self.addresses()[:1]
        smtp = self.smtp_settings()
        self.test_button.setEnabled(False)
        self.test_result.setStyleSheet(HINT_STYLE)
        self.test_result.setText(tr("Odesílám zkušební mail…"))
        signals = self._test_signals
        subject = tr("Warden: test SMTP")
        body = tr("Zkušební zpráva z Wardenu. Nastavení SMTP funguje.")
        starttls_tip = tr("Server umí STARTTLS, doporučuji ho zapnout v poli Šifrování.")

        def work() -> None:
            try:
                send_email(smtp, recipients, subject, body)
                result = (True, tr("Odesláno na {address}.", address=recipients[0]))
            except Exception as e:
                result = (False, explain_smtp_error(e))
            if smtp.security == "none":
                try:
                    if supports_starttls(smtp):
                        result = (result[0], result[1] + " " + starttls_tip)
                except Exception:
                    pass
            try:
                signals.finished.emit(*result)
            except RuntimeError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _show_test_result(self, ok: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        self.test_result.setStyleSheet("color: #43A047;" if ok else ERROR_STYLE)
        self.test_result.setText(message)
