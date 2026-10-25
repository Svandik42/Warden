import json
import os
import tempfile
from dataclasses import asdict,fields
from pathlib import Path

from .config import Settings, SmtpSettings

from .models import Host
from .secret import protect, unprotect
from .validation import SECURITY_VALUES, coerce, is_valid_address, is_valid_email, single_line

DATA_DIR = Path(os.environ["APPDATA"]) / "Warden"
warnings: list[tuple[str, dict]] = []


def _coerced(instance, data: dict, skip: tuple[str, ...] = ()):
    for field in fields(instance):
        if field.name in skip or field.name not in data:
            continue
        setattr(instance, field.name, coerce(field.name, data[field.name], getattr(instance, field.name)))
    return instance


def _settings_from(data) -> Settings:
    data = data if isinstance(data, dict) else {}
    smtp_data = data.get("smtp") if isinstance(data.get("smtp"), dict) else {}
    settings = _coerced(Settings(), data, skip=("smtp",))
    settings.smtp = _coerced(SmtpSettings(), smtp_data)
    smtp = settings.smtp
    if smtp.security not in SECURITY_VALUES:
        smtp.security = SmtpSettings().security
    smtp.server = single_line(smtp.server, 253)
    smtp.source_email = single_line(smtp.source_email, 254)
    smtp.username = single_line(smtp.username, 254)
    settings.subject = single_line(settings.subject, 200)
    settings.addresses = [a.strip() for a in settings.addresses if is_valid_email(a.strip())]
    return settings


def _host_from(data) -> Host | None:
    if not isinstance(data, dict):
        return None
    host_id, address = data.get("id"), data.get("address")
    if isinstance(host_id, bool) or not isinstance(host_id, int) or host_id < 1:
        return None
    if not isinstance(address, str) or not is_valid_address(address.strip()):
        return None
    host = _coerced(Host(id=host_id, address=address.strip()), data, skip=("id", "address"))
    host.description = single_line(host.description, 200)
    return host


def _hosts_from(items) -> tuple[list[Host], int]:
    hosts: list[Host] = []
    seen: set[int] = set()
    items = items if isinstance(items, list) else []
    for item in items:
        host = _host_from(item)
        if host is not None and host.id not in seen:
            hosts.append(host)
            seen.add(host.id)
    return hosts, len(items) - len(hosts)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, path)


def _quarantine(path: Path) -> None:
    backup = path.with_suffix(".corrupt")
    os.replace(path, backup)
    warnings.append(("Soubor {file} byl poškozený a nešel načíst. Původní obsah je uložený v {backup}.",
                     {"file": path.name, "backup": backup}))


def _read_json(path: Path, expected: type):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError):
        _quarantine(path)
        return None
    if not isinstance(data, expected):
        _quarantine(path)
        return None
    return data


def save_hosts(hosts: list[Host], directory: Path = DATA_DIR) -> None:
    _write_json(directory / "hosts.json", [asdict(host) for host in hosts])


def load_hosts(directory: Path = DATA_DIR) -> list[Host]:
    data = _read_json(directory / "hosts.json", list)
    if data is None:
        return []
    hosts, skipped = _hosts_from(data)
    if skipped:
        warnings.append(("V souboru {file} bylo {count} neplatných prvků, přeskočily se.",
                         {"file": "hosts.json", "count": skipped}))
    return hosts


def save_settings(settings: Settings, directory: Path = DATA_DIR) -> None:
    data = asdict(settings)
    data["smtp"]["password"] = protect(settings.smtp.password)
    _write_json(directory / "settings.json", data)


def load_settings(directory: Path = DATA_DIR) -> Settings:
    data = _read_json(directory / "settings.json", dict)
    if data is None:
        return Settings()
    settings = _settings_from(data)
    try:
        settings.smtp.password = unprotect(settings.smtp.password)
    except (OSError, ValueError):
        warnings.append(("Uložené heslo SMTP nejde dešifrovat (jiný uživatel nebo počítač). Zadej ho prosím znovu v Nastavení.", {}))
        settings.smtp.password = ""
    return settings


CONFIG_FORMAT = "warden-config"


def export_config(path: Path, hosts: list[Host], settings: Settings) -> None:
    settings_data = asdict(settings)
    settings_data["smtp"]["password"] = ""
    _write_json(path, {
        "format": CONFIG_FORMAT,
        "version": 1,
        "settings": settings_data,
        "hosts": [asdict(host) for host in hosts],
    })


def import_config(path: Path) -> tuple[list[Host], Settings]:
    if path.stat().st_size > 5_000_000:
        raise ValueError("configuration file too large")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("format") != CONFIG_FORMAT:
        raise ValueError("not a Warden configuration file")
    settings = _settings_from(data.get("settings"))
    settings.smtp.password = ""
    hosts, _ = _hosts_from(data.get("hosts"))
    return hosts, settings


if __name__ == "__main__":
    hosts = [Host(id=1, address="8.8.8.8", description="Google"),
             Host(id=2, address="10.0.0.1", description="Hospoda")]
    settings = Settings()
    settings.smtp.server = "smtp.seznam.cz"
    settings.ping_interval = 20

    with tempfile.TemporaryDirectory() as tmp:
        test_dir = Path(tmp)
        save_settings(settings, test_dir)
        loaded_settings = load_settings(test_dir)
        assert loaded_settings == settings
        assert loaded_settings.smtp.server == "smtp.seznam.cz"
        save_hosts(hosts, test_dir)
        assert load_hosts(test_dir) == hosts
        empty_dir = test_dir / "prazdna"
        assert load_hosts(empty_dir) == []
        assert load_settings(empty_dir) == Settings()
        (test_dir / "settings.json").write_text(
            '{"ping_interval": 30, "stare_pole": 1, "smtp": {"server": "x", "stary_klic": 2}}',
            encoding="utf-8")
        loaded = load_settings(test_dir)
        assert loaded.ping_interval == 30
        assert loaded.smtp.server == "x"
        (test_dir / "hosts.json").write_text('[{"id": 1, "addr', encoding="utf-8")
        assert load_hosts(test_dir) == []
        assert (test_dir / "hosts.corrupt").exists()

        settings.smtp.password = "Tajné heslo 123"
        save_settings(settings, test_dir)
        raw = (test_dir / "settings.json").read_text(encoding="utf-8")
        assert "Tajné heslo 123" not in raw and '"password": "dpapi:' in raw
        assert load_settings(test_dir).smtp.password == "Tajné heslo 123"
        (test_dir / "settings.json").write_text('{"smtp": {"password": "stare-nesifrovane"}}', encoding="utf-8")
        assert load_settings(test_dir).smtp.password == "stare-nesifrovane"

        settings.smtp.password = "Tajné heslo 123"
        export_config(test_dir / "export.json", hosts, settings)
        assert "Tajné heslo" not in (test_dir / "export.json").read_text(encoding="utf-8")
        imported_hosts, imported_settings = import_config(test_dir / "export.json")
        assert imported_hosts == hosts
        assert imported_settings.smtp.server == settings.smtp.server and imported_settings.smtp.password == ""
        (test_dir / "jiny.json").write_text('{"neco": 1}', encoding="utf-8")
        try:
            import_config(test_dir / "jiny.json")
            raise AssertionError("cizí soubor neměl projít")
        except ValueError:
            pass

        for content in ('{"a": 1}', '["8.8.8.8"]', '42'):
            (test_dir / "hosts.json").write_text(content, encoding="utf-8")
            assert load_hosts(test_dir) == [], content
        (test_dir / "settings.json").write_text("[1, 2]", encoding="utf-8")
        assert load_settings(test_dir) == Settings()
        (test_dir / "settings.json").write_text(json.dumps({
            "ping_interval": 0, "fail_alert_threshold": "abc", "network_down_percent": 500,
            "alert_down": "ano", "addresses": ["ok@firma.cz", "zly\nBcc: x@y.cz", 7],
            "subject": "OUT\r\nBcc: utok@x.cz", "smtp": {"port": 99999, "security": "cokoli"}}), encoding="utf-8")
        hardened = load_settings(test_dir)
        assert hardened.ping_interval == 2 and hardened.fail_alert_threshold == 6
        assert hardened.network_down_percent == 100 and hardened.alert_down is True
        assert hardened.addresses == ["ok@firma.cz"] and "\n" not in hardened.subject
        assert hardened.smtp.port == 65535 and hardened.smtp.security == "starttls"
        (test_dir / "hosts.json").write_text(json.dumps([
            {"id": 1, "address": "8.8.8.8", "timeout_ms": 0},
            {"id": 1, "address": "1.1.1.1"},
            {"id": 2, "address": "-?"},
            {"id": "3", "address": "9.9.9.9"},
            {"id": 4, "address": "10.0.0.1", "enabled": "ne", "description": "a\nb"}]), encoding="utf-8")
        loaded = load_hosts(test_dir)
        assert [(h.id, h.address) for h in loaded] == [(1, "8.8.8.8"), (4, "10.0.0.1")]
        assert loaded[0].timeout_ms == 100 and loaded[1].enabled is True and loaded[1].description == "a b"


    print("Storage OK")
