import json
import os
import tempfile
from dataclasses import asdict,fields
from pathlib import Path

from .config import Settings, SmtpSettings

from .models import Host
from .secret import protect, unprotect

DATA_DIR = Path(os.environ["APPDATA"]) / "Warden"
warnings: list[tuple[str, dict]] = []


def _from_dict(cls, data: dict):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})

def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, path)

def _read_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        backup = path.with_suffix(".corrupt")
        os.replace(path, backup)
        warnings.append(("Soubor {file} byl poškozený a nešel načíst. Původní obsah je uložený v {backup}.",
                         {"file": path.name, "backup": backup}))
        return None
    except FileNotFoundError:
        return None

def save_hosts(hosts: list[Host], directory: Path = DATA_DIR) -> None:
    _write_json(directory / "hosts.json", [asdict(host) for host in hosts])

def load_hosts(directory: Path = DATA_DIR) -> list[Host]:
    loaded_hosts_data = _read_json(directory / "hosts.json")
    if loaded_hosts_data is None:
        return []
    return [_from_dict(Host, data) for data in loaded_hosts_data]

def save_settings(settings: Settings, directory: Path = DATA_DIR) -> None:
    data = asdict(settings)
    data["smtp"]["password"] = protect(settings.smtp.password)
    _write_json(directory / "settings.json", data)

def load_settings(directory: Path = DATA_DIR) -> Settings:
    data = _read_json(directory / "settings.json")
    if data is None:
        return Settings()
    smtp_data = data.pop("smtp", {})
    settings = _from_dict(Settings, data)
    settings.smtp = _from_dict(SmtpSettings, smtp_data)
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
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("format") != CONFIG_FORMAT:
        raise ValueError("not a Warden configuration file")
    settings_data = dict(data.get("settings") or {})
    smtp_data = settings_data.pop("smtp", {}) or {}
    settings = _from_dict(Settings, settings_data)
    settings.smtp = _from_dict(SmtpSettings, smtp_data)
    settings.smtp.password = ""
    hosts = [_from_dict(Host, item) for item in data.get("hosts") or []]
    if len({h.id for h in hosts}) != len(hosts):
        raise ValueError("duplicate host ids")
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


    print("Storage OK")
