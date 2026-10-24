from .models import ErrorKind, Event, EventType, HostState, PingResult, Status
from .config import Settings

class Monitor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.host_states: dict[int, HostState] = {}
        self.network_down = False

    def process_cycle(self, results: list[PingResult]) -> list[Event]:
        events: list[Event] = []

        current_ids = {result.host_id for result in results}
        for stale_id in self.host_states.keys() - current_ids:
            del self.host_states[stale_id]

        for result in results:
            if result.host_id not in self.host_states:
                self.host_states[result.host_id] = HostState()
            self._update_host_state(self.host_states[result.host_id], result)

        network_event = self._check_network(results)
        if network_event is not None:
            events.append(network_event)

        if not self.network_down:
            for result in results:
                event = self._check_alerts(result, self.host_states[result.host_id])
                if event is not None:
                    events.append(event)

        return events

    def _check_network(self, results: list[PingResult]) -> Event | None:
        down = self._is_network_down(results)
        if down and not self.network_down:
            self.network_down = True
            return Event(event_type=EventType.NETWORK_DOWN)
        if not down and self.network_down:
            self.network_down = False
            return Event(event_type=EventType.NETWORK_UP)
        return None

    def _is_network_down(self, results: list[PingResult]) -> bool:
        total = len(results)
        if total < self.settings.network_min_hosts:
            return False
        failing = sum(
            1 for r in results
            if self.host_states[r.host_id].fail_streak >= self.settings.fail_alert_threshold
        )
        return failing / total * 100 >= self.settings.network_down_percent

    def _update_host_state(self, host_state: HostState, result: PingResult) -> None:
        old_status = host_state.status
        if result.ok:
            host_state.ok_streak += 1
            host_state.fail_streak = 0
            host_state.total_ok += 1
            host_state.last_rtt_ms = result.rtt_ms
        else:
            host_state.fail_streak += 1
            host_state.ok_streak = 0
            host_state.total_fail += 1
            host_state.last_rtt_ms = None
        if result.ok:
            host_state.status = Status.UP
        elif host_state.fail_streak >= self.settings.icon_change_threshold:
            host_state.status = Status.DOWN
        if old_status != host_state.status:
            host_state.last_change = result.timestamp


    def _check_alerts(self, result: PingResult, host_state: HostState) -> Event | None:
        if host_state.fail_streak >= self.settings.fail_alert_threshold and not host_state.down_alerted:
            host_state.down_alerted = True
            return Event(event_type=EventType.HOST_DOWN, host_id=result.host_id, timestamp=result.timestamp)
        elif host_state.ok_streak >= self.settings.ok_alert_threshold and host_state.down_alerted:
            host_state.down_alerted = False
            return Event(event_type=EventType.HOST_UP, host_id=result.host_id, timestamp=result.timestamp)
        return None


if __name__ == "__main__":
    from datetime import datetime

    def run(monitor, cycles):
        all_events = []
        for i, cycle in enumerate(cycles, 1):
            results = [PingResult(host_id=h, ok=ok) for h, ok in enumerate(cycle, 1)]
            for e in monitor.process_cycle(results):
                all_events.append((i, e.event_type.name, e.host_id))
        return all_events

    events = run(Monitor(Settings()), [[False]*5]*8 + [[True]*5]*3)
    assert events == [(6, "NETWORK_DOWN", None), (9, "NETWORK_UP", None)], events
    print("D OK")

    events = run(Monitor(Settings()), [[False] + [True]*4]*8)
    assert events == [(6, "HOST_DOWN", 1)], events
    print("E OK")

    events = run(Monitor(Settings()), [[False]*5]*8 + [[False] + [True]*4]*3)
    assert events == [(6, "NETWORK_DOWN", None), (9, "NETWORK_UP", None), (9, "HOST_DOWN", 1)], events
    print("F OK")

    events = run(Monitor(Settings()), [[False]*2]*8)
    assert events == [(6, "HOST_DOWN", 1), (6, "HOST_DOWN", 2)], events
    print("G OK")

    monitor = Monitor(Settings())
    run(monitor, [[False, True]] * 6)
    monitor.process_cycle([PingResult(host_id=2, ok=True)])
    assert set(monitor.host_states) == {2}, monitor.host_states
    print("H OK")
