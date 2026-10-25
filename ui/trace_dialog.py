from PySide6.QtCore import QProcess
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.models import Host
from core.validation import is_valid_address



class TraceDialog(QDialog):
    def __init__(self, host: Host, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.host = host
        self.setWindowTitle(tr("Trasování: {name}", name=host.description or host.address))
        self.resize(640, 460)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        self.status_label = QLabel()
        self.again_button = QPushButton(tr("Znovu"))
        close_button = QPushButton(tr("Zavřít"))
        self.again_button.clicked.connect(self.start)
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self.status_label, 1)
        buttons.addWidget(self.again_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.output)
        layout.addLayout(buttons)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._failed)
        self.start()

    def start(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.output.clear()
        if not is_valid_address(self.host.address):
            self.status_label.setText(tr("Adresa obsahuje nepovolené znaky."))
            return
        self.again_button.setEnabled(False)
        self.status_label.setText(tr("Trasuji cestu k {address}…", address=self.host.address))
        self.process.start("tracert", ["-d", "-w", "1000", "-h", "30", self.host.address])

    def _read_output(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("oem", errors="replace")
        self.output.insertPlainText(text.replace("\r", ""))
        self.output.ensureCursorVisible()

    def _finished(self) -> None:
        self.again_button.setEnabled(True)
        self.status_label.setText(tr("Hotovo."))

    def _failed(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.again_button.setEnabled(True)
            self.status_label.setText(tr("Příkaz tracert se nepodařilo spustit."))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(2000)
        event.accept()
