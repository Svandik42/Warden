import re

ADDRESS_PATTERN = re.compile(r"[A-Za-z0-9_\[][A-Za-z0-9_.:%\[\]-]*")
SECURITY_VALUES = ("none", "starttls", "ssl")
MIN_PING_INTERVAL = 2

NUMBER_RANGES = {
    "icon_change_threshold": (1, 1000),
    "fail_alert_threshold": (1, 1000),
    "ok_alert_threshold": (1, 1000),
    "ping_interval": (MIN_PING_INTERVAL, 86400),
    "network_down_percent": (1, 100),
    "network_min_hosts": (1, 1000),
    "port": (1, 65535),
    "timeout_ms": (100, 10000),
}


def is_valid_address(address: str) -> bool:
    return (isinstance(address, str) and 0 < len(address) <= 253
            and not address.startswith("-") and bool(ADDRESS_PATTERN.fullmatch(address)))


def is_valid_email(address: str) -> bool:
    return (isinstance(address, str) and 3 <= len(address) <= 254 and "@" in address
            and not any(ch.isspace() or ch in "<>,;\"" for ch in address))


def single_line(text: str, limit: int = 500) -> str:
    return " ".join(text.split())[:limit]


def coerce(name: str, value, default):
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            return default
        low, high = NUMBER_RANGES.get(name, (float("-inf"), float("inf")))
        return type(default)(min(max(value, low), high))
    if isinstance(default, str):
        return value if isinstance(value, str) else default
    if isinstance(default, list):
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else default
    return default
