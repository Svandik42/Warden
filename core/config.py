from dataclasses import dataclass, field

@dataclass
class SmtpSettings:
    server: str = ""
    port: int = 587
    source_email: str = ""
    use_auth: bool = True
    username: str = ""
    password: str = ""
    security: str = "starttls"

@dataclass
class Settings:
    smtp: SmtpSettings = field(default_factory=SmtpSettings)
    alert_down: bool = True
    alert_up: bool = True
    icon_change_threshold: int = 4
    fail_alert_threshold: int = 6
    ok_alert_threshold: int = 6
    addresses: list[str] = field(default_factory=list)
    subject: str = "OUT"
    body_up: str = "IN (<ip>)"
    body_down: str = "IP: <ip> ; <tm> IPWarden"
    ping_interval: int = 15
    auto_ping: bool = True
    network_down_percent: float = 80
    network_min_hosts: int = 3
    language: str = ""

SMTP_PRESETS = {
    "Seznam":  ("smtp.seznam.cz", 465, "ssl"),
    "Gmail":   ("smtp.gmail.com", 587, "starttls"),
    "Outlook": ("smtp-mail.outlook.com", 587, "starttls"),
}
