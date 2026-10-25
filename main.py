import ctypes
import html
import sys
import time
from dataclasses import fields
from datetime import datetime
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibraryInfo, QLockFile, QModelIndex, QObject, Qt, QTimer, QTranslator, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QWidget

from core import autostart, storage
from core.history import EventLog, RttHistory
from core.i18n import language, set_language, system_language, tr, tr_count
from core.config import Settings
from core.models import Event, HostState, Status
from core.monitor import Monitor
from core.notify import Notifier
from core.scheduler import Scheduler
from core.storage import (
    DATA_DIR,
    export_config,
    import_config,
    load_hosts,
    load_settings,
    save_hosts,
    save_settings,
)
from ui.charts import ChartsDialog
from ui.host_dialog import HostDialog
from ui.help import open_help
from ui.icons import app_icon
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.table_model import HostListModel
from ui.trace_dialog import TraceDialog


class CycleBridge(QObject):
    cycle_done = Signal(object, object)
    notify_error = Signal(str)
    mail_sent = Signal(str)


class CzechCancelTranslator(QTranslator):
    def translate(self, context, source, disambiguation=None, n=-1):
        return "Storno" if source == "Cancel" else None


def install_qt_translation(app: QApplication) -> None:
    translator = QTranslator(app)
    folders = [QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
               str(Path(PySide6.__file__).parent / "translations")]
    if any(translator.load(f"qtbase_{language()}", folder) for folder in folders):
        app.installTranslator(translator)
    if language() == "cs":
        app.installTranslator(CzechCancelTranslator(app))


def acquire_single_instance_lock() -> QLockFile | None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA_DIR / "warden.lock"))
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(200) else None


def save_or_warn(parent: QWidget, action, what: str) -> bool:
    try:
        action()
        return True
    except OSError as e:
        QMessageBox.warning(parent, tr("Uložení se nezdařilo"),
                            tr("{what} se nepodařilo uložit:\n{error}", what=what, error=e))
        return False


def as_text(template: str, **values) -> str:
    safe = {key: html.escape(str(value)) for key, value in values.items()}
    return "<p>" + tr(template, **safe).replace("\n", "<br>") + "</p>"


def set_windows_app_id() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Svandik42.Warden")
    except (AttributeError, OSError):
        pass


def main() -> None:
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Warden")
    app.setWindowIcon(app_icon())

    settings = load_settings()
    set_language(settings.language or system_language())
    install_qt_translation(app)

    lock = acquire_single_instance_lock()
    if lock is None:
        QMessageBox.information(None, "Warden", tr("Warden už běží. Najdeš ho na hlavním panelu."))
        return

    hosts = load_hosts()
    history = RttHistory()
    event_log = EventLog(DATA_DIR / "events.csv")
    charts_dialog: ChartsDialog | None = None

    window = MainWindow()
    model = HostListModel(hosts)
    window.host_view.setModel(model)
    window.set_interval(settings.ping_interval)
    window.auto_check.setChecked(settings.auto_ping)
    window.interval_combo.setEnabled(settings.auto_ping)
    if not hosts:
        window.show_status(tr("Zatím nic nesleduješ. Přidej první prvek tlačítkem Přidat…"))

    bridge = CycleBridge()
    monitor = Monitor(settings)
    notifier = Notifier(settings, on_error=bridge.notify_error.emit, on_sent=bridge.mail_sent.emit)

    def on_cycle_done(states: dict[int, HostState], events: list[Event]) -> None:
        notifier.submit(events, hosts)
        bridge.cycle_done.emit(states, events)

    scheduler = Scheduler(hosts, monitor, settings, on_cycle_done)

    def show_cycle(states: dict[int, HostState], events: list[Event]) -> None:
        now = datetime.now()
        model.update_states(states)
        history.add(states, now)
        try:
            event_log.append(events, hosts)
        except OSError as e:
            window.show_mail_status(tr("Log událostí nejde zapsat: {error}", error=e), ok=False)
        down = sum(1 for h in hosts if (s := states.get(h.id)) is not None and s.status == Status.DOWN)
        window.show_status(tr(
            "Poslední ping {time}  ·  {hosts}  ·  {down}",
            time=f"{now:%H:%M:%S}",
            hosts=tr_count(len(hosts), "prvek|prvky|prvků"),
            down=tr_count(down, "nedostupný|nedostupné|nedostupných"),
        ))
        if charts_dialog is not None and charts_dialog.isVisible():
            charts_dialog.refresh()

    def show_mail_error(text: str) -> None:
        window.show_mail_status(f"{datetime.now():%H:%M:%S}  {text}", ok=False)

    def show_mail_sent(body: str) -> None:
        window.show_mail_status(tr("Mail odeslán {time}: {body}", time=f"{datetime.now():%H:%M:%S}", body=body), ok=True)

    def on_interval_changed() -> None:
        settings.ping_interval = window.interval_seconds()
        save_or_warn(window, lambda: save_settings(settings), tr("Nastavení"))
        scheduler.ping_now()

    def on_auto_ping_changed(checked: bool) -> None:
        settings.auto_ping = checked
        save_or_warn(window, lambda: save_settings(settings), tr("Nastavení"))
        window.interval_combo.setEnabled(checked)
        scheduler.ping_now()

    def update_progress() -> None:
        next_at = scheduler.next_cycle_at
        if next_at is None:
            window.cycle_progress.setValue(0)
            return
        remaining = max(0.0, next_at - time.monotonic())
        window.cycle_progress.setValue(int(1000 * (1 - remaining / max(1, settings.ping_interval))))

    def next_host_id() -> int:
        return max((h.id for h in hosts), default=0) + 1

    def selected_row() -> int | None:
        index = window.host_view.currentIndex()
        return index.row() if index.isValid() else None

    def on_add() -> None:
        dialog = HostDialog(window, tr("Přidat prvek"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        model.add_host(dialog.get_host(next_host_id()))
        window.setWindowModified(True)
        scheduler.ping_now()

    def on_edit(index: QModelIndex) -> None:
        host = model.host_at(index.row())
        dialog = HostDialog(window)
        dialog.set_host(host)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        host_id = host.id if dialog.address() == host.address else next_host_id()
        model.replace_host(index.row(), dialog.get_host(host_id))
        window.setWindowModified(True)
        scheduler.ping_now()

    def on_delete() -> None:
        row = selected_row()
        if row is None:
            window.show_status(tr("Nejdřív klikni na prvek, který chceš smazat."))
            return
        host = model.host_at(row)
        answer = QMessageBox.question(window, tr("Smazat prvek"),
                                      as_text("Opravdu smazat „{name}“?", name=host.description or host.address))
        if answer == QMessageBox.StandardButton.Yes:
            model.remove_host(row)
            window.setWindowModified(True)

    def on_save() -> bool:
        if not save_or_warn(window, lambda: save_hosts(hosts), tr("Seznam prvků")):
            return False
        window.setWindowModified(False)
        window.show_status(tr("Prvky uloženy."))
        return True

    def on_trace() -> None:
        row = selected_row()
        if row is None:
            window.show_status(tr("Nejdřív klikni na prvek, ke kterému chceš trasovat."))
            return
        dialog = TraceDialog(model.host_at(row), window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def on_charts() -> None:
        nonlocal charts_dialog
        if charts_dialog is None:
            charts_dialog = ChartsDialog(hosts, history, event_log, window)
        charts_dialog.refresh()
        charts_dialog.show()
        charts_dialog.raise_()
        charts_dialog.activateWindow()

    def on_export() -> None:
        path, _ = QFileDialog.getSaveFileName(window, tr("Exportovat konfiguraci"),
                                              str(Path.home() / "warden-konfigurace.json"), "Warden (*.json)")
        if not path:
            return
        if save_or_warn(window, lambda: export_config(Path(path), hosts, settings), tr("Konfiguraci")):
            window.show_status(tr("Konfigurace uložena do {path}", path=path))

    def on_import() -> None:
        path, _ = QFileDialog.getOpenFileName(window, tr("Importovat konfiguraci"), str(Path.home()), "Warden (*.json)")
        if not path:
            return
        try:
            new_hosts, new_settings = import_config(Path(path))
        except (OSError, ValueError, TypeError):
            QMessageBox.warning(window, tr("Import se nezdařil"),
                                as_text("Soubor {path} není platná konfigurace Wardenu.", path=path))
            return
        answer = QMessageBox.question(
            window, tr("Importovat konfiguraci"),
            tr("Import nahradí současné prvky ({current}) a nastavení obsahem souboru ({new}). Pokračovat?",
               current=len(hosts), new=len(new_hosts)))
        if answer != QMessageBox.StandardButton.Yes:
            return
        old_language = settings.language
        if not new_settings.smtp.password and new_settings.smtp.server == settings.smtp.server:
            new_settings.smtp.password = settings.smtp.password
        for field in fields(Settings):
            setattr(settings, field.name, getattr(new_settings, field.name))
        first_id = next_host_id()
        for offset, host in enumerate(new_hosts):
            host.id = first_id + offset
        model.set_hosts(new_hosts)
        save_or_warn(window, lambda: save_hosts(hosts), tr("Seznam prvků"))
        save_or_warn(window, lambda: save_settings(settings), tr("Nastavení"))
        window.setWindowModified(False)
        window.set_interval(settings.ping_interval)
        window.auto_check.setChecked(settings.auto_ping)
        scheduler.ping_now()
        message = tr("Konfigurace načtena: {count}.", count=tr_count(len(hosts), "prvek|prvky|prvků"))
        if settings.smtp.use_auth and not settings.smtp.password:
            message += "\n\n" + tr("Heslo SMTP se neexportuje. Zadej ho v Nastavení → SMTP server.")
        if settings.language != old_language:
            message += "\n\n" + tr("Jazyk se změní po restartu Wardenu.")
        QMessageBox.information(window, tr("Importovat konfiguraci"), message)

    def on_settings() -> None:
        dialog = SettingsDialog(window)
        dialog.set_settings(settings, autostart.is_enabled())
        result = dialog.exec()
        if dialog.requested_action == "export":
            on_export()
            return
        if dialog.requested_action == "import":
            on_import()
            return
        if result != QDialog.DialogCode.Accepted:
            return
        old_language = settings.language
        dialog.apply_to(settings)
        if not save_or_warn(window, lambda: save_settings(settings), tr("Nastavení")):
            return
        if dialog.autostart() != autostart.is_enabled():
            try:
                autostart.set_enabled(dialog.autostart())
            except OSError as e:
                window.show_status(tr("Automatické spuštění nejde nastavit: {error}", error=e))
        window.show_status(tr("Nastavení uloženo."))
        if settings.language != old_language:
            QMessageBox.information(window, tr("Jazyk"),
                                    tr("Jazyk se změní po restartu Wardenu."))

    def confirm_close() -> bool:
        if not window.isWindowModified():
            return True
        answer = QMessageBox.question(
            window, tr("Neuložené změny"), tr("Seznam prvků byl změněn. Uložit před ukončením?"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return on_save()
        return answer == QMessageBox.StandardButton.Discard

    def shutdown() -> None:
        window.hide()
        scheduler.stop()
        notifier.stop()
        lock.unlock()

    def show_startup_warnings() -> None:
        for template, values in storage.warnings:
            QMessageBox.warning(window, "Warden", tr(template, **values))
        storage.warnings.clear()

    bridge.cycle_done.connect(show_cycle)
    bridge.notify_error.connect(show_mail_error)
    bridge.mail_sent.connect(show_mail_sent)

    window.confirm_close = confirm_close
    window.ping_button.clicked.connect(scheduler.ping_now)
    window.interval_combo.currentIndexChanged.connect(on_interval_changed)
    window.auto_check.toggled.connect(on_auto_ping_changed)
    window.add_button.clicked.connect(on_add)
    window.host_view.doubleClicked.connect(on_edit)
    window.delete_button.clicked.connect(on_delete)
    window.save_button.clicked.connect(on_save)
    window.trace_button.clicked.connect(on_trace)
    window.settings_button.clicked.connect(on_settings)
    window.charts_button.clicked.connect(on_charts)
    window.quit_button.clicked.connect(window.close)
    window.help_button.clicked.connect(open_help)
    QShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents), window, open_help)
    QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), window.host_view, on_delete)
    app.aboutToQuit.connect(shutdown)

    progress_timer = QTimer(window)
    progress_timer.timeout.connect(update_progress)
    progress_timer.start(100)

    notifier.start()
    scheduler.start()
    window.show()
    QTimer.singleShot(0, show_startup_warnings)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
