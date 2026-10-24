import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .i18n import tr
from .models import Event, EventType, Host, HostState

EVENT_LABELS = {
    EventType.HOST_DOWN: "Výpadek",
    EventType.HOST_UP: "Obnoveno",
    EventType.NETWORK_DOWN: "Výpadek sítě",
    EventType.NETWORK_UP: "Síť obnovena",
}
_LABEL_TO_TYPE = {label: event_type for event_type, label in EVENT_LABELS.items()}
TIME_FORMAT = "%d.%m.%Y %H:%M:%S"
_FORMULA_START = ("=", "+", "-", "@")


def _safe_cell(text: str) -> str:
    return "'" + text if text.startswith(_FORMULA_START) else text


@dataclass(slots=True)
class LogEntry:
    timestamp: datetime
    event_type: EventType | None
    label: str
    name: str
    address: str

    def display_label(self) -> str:
        return tr(EVENT_LABELS[self.event_type]) if self.event_type else self.label


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, events: list[Event], hosts: list[Host]) -> None:
        if not events:
            return
        by_id = {h.id: h for h in hosts}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()
        with open(self.path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            if new_file:
                writer.writerow([tr("čas"), tr("událost"), tr("prvek"), tr("adresa"), tr("kód")])
            for event in events:
                host = by_id.get(event.host_id)
                writer.writerow([
                    event.timestamp.strftime(TIME_FORMAT),
                    tr(EVENT_LABELS[event.event_type]),
                    _safe_cell(host.description) if host else "",
                    _safe_cell(host.address) if host else "",
                    event.event_type.name,
                ])

    def read(self, limit: int = 2000) -> list[LogEntry]:
        try:
            with open(self.path, encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader, None)
                rows = deque(reader, maxlen=limit)
        except FileNotFoundError:
            return []
        entries = []
        for row in rows:
            try:
                timestamp = datetime.strptime(row[0], TIME_FORMAT)
            except (ValueError, IndexError):
                continue
            label = row[1] if len(row) > 1 else ""
            code = row[4] if len(row) > 4 else ""
            event_type = EventType.__members__.get(code) or _LABEL_TO_TYPE.get(label)
            name = row[2].removeprefix("'") if len(row) > 2 else ""
            address = row[3].removeprefix("'") if len(row) > 3 else ""
            entries.append(LogEntry(timestamp, event_type, label, name, address))
        entries.reverse()
        return entries


@dataclass(slots=True)
class Sample:
    timestamp: datetime
    rtt_ms: float | None


class RttHistory:
    def __init__(self, max_samples: int = 8640) -> None:
        self.max_samples = max_samples
        self._samples: dict[int, deque[Sample]] = {}

    def add(self, states: dict[int, HostState], when: datetime) -> None:
        for host_id, state in states.items():
            samples = self._samples.setdefault(host_id, deque(maxlen=self.max_samples))
            ok = state.fail_streak == 0 and state.last_rtt_ms is not None
            samples.append(Sample(when, state.last_rtt_ms if ok else None))

    def samples(self, host_id: int) -> list[Sample]:
        return list(self._samples.get(host_id, ()))


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.csv"
        log = EventLog(path)
        hosts = [Host(id=1, address="10.0.0.1", description="=HYPERLINK(\"x\")")]
        when = datetime(2026, 10, 23, 10, 9, 24)
        log.append([Event(event_type=EventType.HOST_DOWN, host_id=1, timestamp=when)], hosts)
        log.append([Event(event_type=EventType.NETWORK_UP, timestamp=when.replace(minute=15))], hosts)
        assert "'=HYPERLINK" in path.read_text(encoding="utf-8-sig")
        entries = log.read()
        assert [(e.event_type, e.name) for e in entries] == [
            (EventType.NETWORK_UP, ""), (EventType.HOST_DOWN, "=HYPERLINK(\"x\")")]
        assert entries[1].timestamp == when

        old = Path(tmp) / "old.csv"
        old.write_text("čas;událost;prvek;adresa\n23.10.2026 18:18:08;Výpadek;Hospoda;10.0.0.1\n", encoding="utf-8-sig")
        assert EventLog(old).read()[0].event_type == EventType.HOST_DOWN

    history = RttHistory(max_samples=3)
    for i in range(5):
        history.add({1: HostState(last_rtt_ms=float(i))}, datetime(2026, 1, 1, 0, 0, i))
    history.add({1: HostState(fail_streak=1)}, datetime(2026, 1, 1, 0, 0, 9))
    assert [s.rtt_ms for s in history.samples(1)] == [3.0, 4.0, None]
    print("History OK")
