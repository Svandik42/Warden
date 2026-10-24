import smtplib
import ssl
import getpass
import socket
import queue
import threading
from collections.abc import Callable

from datetime import datetime
from email.message import EmailMessage
from .config import Settings, SmtpSettings
from .i18n import tr
from .models import Event, EventType, Host


def render(template: str, ip: str, when: datetime) -> str:
    return template.replace("<ip>", ip).replace("<dt>", when.strftime("%d.%m.%Y")).replace("<tm>", when.strftime("%H:%M:%S"))

def build_message(event: Event, hosts: list[Host], settings: Settings) -> tuple[str, str] | None:
    if event.event_type == EventType.HOST_DOWN:
        enabled, template = settings.alert_down, settings.body_down
    elif event.event_type == EventType.HOST_UP:
        enabled, template = settings.alert_up, settings.body_up
    elif event.event_type == EventType.NETWORK_DOWN:
        enabled, template = settings.alert_down, tr("Síť nedostupná <dt> <tm>")
    elif event.event_type == EventType.NETWORK_UP:
        enabled, template = settings.alert_up, tr("Síť obnovena <dt> <tm>")
    else:
        return None

    if not enabled:
        return None

    host = next((h for h in hosts if h.id == event.host_id), None)
    ip = host.address if host else f"host {event.host_id}"
    return settings.subject, render(template, ip, event.timestamp)

def send_email(smtp: SmtpSettings, recipients: list[str], subject: str, body: str) -> None:
    if not recipients:
        raise ValueError(tr("Není nastaven žádný příjemce."))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp.source_email
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    if smtp.security == "ssl":
        server = smtplib.SMTP_SSL(smtp.server, smtp.port, timeout=10,
                                  context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(smtp.server, smtp.port, timeout=10)

    with server:
        if smtp.security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if smtp.use_auth:
            server.login(smtp.username or smtp.source_email, smtp.password)
        server.send_message(msg)

def supports_starttls(smtp: SmtpSettings) -> bool:
    with smtplib.SMTP(smtp.server, smtp.port, timeout=10) as server:
        server.ehlo()
        return server.has_extn("starttls")


def explain_smtp_error(e: Exception) -> str:
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return tr("Server odmítl jméno nebo heslo. U Gmailu (a u Seznamu s dvoufázovým ověřením) je potřeba heslo pro aplikace.")
    if isinstance(e, smtplib.SMTPServerDisconnected):
        return tr("Server ukončil spojení. Nejspíš nesedí port a šifrování (465 = SSL, 587 = STARTTLS).")
    if isinstance(e, smtplib.SMTPSenderRefused):
        return tr("Server odmítl odesílatele. Adresa odesílatele musí být stejná jako přihlašovací jméno.")
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return tr("Server odmítl adresu příjemce.")
    if isinstance(e, socket.gaierror):
        return tr("Server s tímto názvem neexistuje. Zkontroluj název (např. smtp.seznam.cz, bez @).")
    if isinstance(e, ssl.SSLError):
        return tr("Chyba šifrování. Nesedí port a šifrování (465 = SSL, 587 = STARTTLS).")
    if isinstance(e, TimeoutError):
        return tr("Server neodpovídá. Zkontroluj port, případně firewall.")
    if isinstance(e, ConnectionRefusedError):
        return tr("Na tomto portu server nepřijímá spojení.")
    if isinstance(e, ValueError):
        return str(e)
    return tr("Neočekávaná chyba: {error}", error=f"{type(e).__name__}: {e}")


PERMANENT_ERRORS = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPRecipientsRefused,
    ValueError,
)

class Notifier:
    def __init__(self, settings: Settings, on_error: Callable[[str], None] = print,
                 retry_delay: float = 60, on_sent: Callable[[str], None] | None = None):
        self.settings = settings
        self.on_error = on_error
        self.on_sent = on_sent
        self.retry_delay = retry_delay
        self._queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join()

    def submit(self, events: list[Event], hosts: list[Host]) -> None:
        for event in events:
            message = build_message(event, hosts, self.settings)
            if message is not None:
                self._queue.put(message)

    def _worker(self) -> None:
        while True:
            message = self._queue.get()
            if message is None:
                return
            subject, body = message
            self._send_with_retry(subject, body)

    def _send_with_retry(self, subject: str, body: str) -> None:
        while not self._stop.is_set():
            try:
                send_email(self.settings.smtp, self.settings.addresses, subject, body)
                if self.on_sent is not None:
                    self.on_sent(body)
                return
            except PERMANENT_ERRORS as e:
                self.on_error(tr("Mail zahozen: {reason}", reason=explain_smtp_error(e)))
                return
            except Exception as e:
                self.on_error(tr("Mail neodešel, další pokus za {seconds} s: {reason}",
                                  seconds=round(self.retry_delay), reason=explain_smtp_error(e)))
                self._stop.wait(self.retry_delay)


if __name__ == "__main__":
    when = datetime(2026, 10, 19, 10, 9, 24)
    assert render("IP: <ip> ; <tm>IPWatch", "192.168.1.4", when) == "IP: 192.168.1.4 ; 10:09:24IPWatch"
    assert render("IN (<ip>)", "10.0.0.1", when) == "IN (10.0.0.1)"
    assert render("<dt> <tm>", "", when) == "19.10.2026 10:09:24"
    assert render("bez značek", "1.2.3.4", when) == "bez značek"
    print("Krok 1 OK")
    hosts = [Host(id=1, address="192.168.1.4", description="Server")]
    settings = Settings()

    down = Event(event_type=EventType.HOST_DOWN, host_id=1, timestamp=when)
    assert build_message(down, hosts, settings) == ("OUT", "IP: 192.168.1.4 ; 10:09:24 IPWarden")

    up = Event(event_type=EventType.HOST_UP, host_id=1, timestamp=when)
    assert build_message(up, hosts, settings) == ("OUT", "IN (192.168.1.4)")

    settings.alert_up = False
    assert build_message(up, hosts, settings) is None

    net = Event(event_type=EventType.NETWORK_DOWN, timestamp=when)
    assert build_message(net, hosts, settings) == ("OUT", "Síť nedostupná 19.10.2026 10:09:24")
    print("Krok 2 OK")

    import sys
    if "--smtp" in sys.argv:
        smtp = SmtpSettings(server="localhost", port=1025, security="none",
                            use_auth=False, source_email="warden@test.local")
        subject, body = build_message(down, hosts, Settings())
        send_email(smtp, ["admin@test.local"], subject, body)
        print("Krok 3a OK, mail odeslán")
    if "--real" in sys.argv:
        email = input("Tvůj e-mail (odesílatel i příjemce): ")
        smtp = SmtpSettings(
            server=input("SMTP server: ").strip(),
            port=int(input("Port: ")),
            security=input("Šifrování (none/starttls/ssl): ").strip(),
            use_auth=True,
            username=email,
            password=getpass.getpass("Email heslo: "),
            source_email=email,
        )
        subject, body = build_message(down, hosts, Settings())
        send_email(smtp, [email], subject, body)
        print("Krok 3b OK, zkontroluj schránku")
    if "--queue" in sys.argv:
        import time
        settings = Settings()
        settings.smtp = SmtpSettings(server="localhost", port=1025, security="none",
                                     use_auth=False, source_email="warden@test.local")
        settings.addresses = ["admin@test.local"]
        notifier = Notifier(settings, retry_delay=3)
        notifier.start()

        t = time.monotonic()
        notifier.submit([down], hosts)
        print(f"submit trval {time.monotonic() - t:.3f} s")

        print("Čekám 20 s. Během nich spusť v druhém terminálu SMTP server...")
        time.sleep(20)
        notifier.stop()
