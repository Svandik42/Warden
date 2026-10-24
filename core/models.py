from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Status(str, Enum):
    UNKNOWN = "UNKNOWN"
    UP = "UP"
    DOWN = "DOWN"

class EventType(str, Enum):
    HOST_DOWN = "DOWN"
    HOST_UP = "UP"
    NETWORK_DOWN = "NETWORK_DOWN"
    NETWORK_UP = "NETWORK_UP"

class ErrorKind(str, Enum):
    TIMEOUT = "timeout"
    UNKNOWN_HOST = "unknown host"
    INSUFFICIENT_PERMISSIONS = "insufficient permissions"
    ICMP_SOCKET_ERROR = "ICMP socket error"
    OTHER = "other error"


@dataclass
class Host:
    id: int
    address: str
    description: str = ""
    timeout_ms: int = 3000
    icon: str = "antenna"
    enabled: bool = True


@dataclass
class PingResult:
    host_id: int
    ok: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: ErrorKind | None = None
    rtt_ms: float | None = None
    details: str | None = None

@dataclass
class HostState:
    status: Status = Status.UNKNOWN
    fail_streak: int = 0
    ok_streak: int = 0
    total_ok: int = 0
    total_fail: int = 0
    last_rtt_ms: float | None = None
    last_change: datetime | None = None
    down_alerted: bool = False

@dataclass
class Event:
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    host_id: int | None = None
