import copy
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import traceback

from .config import Settings
from .models import Event, Host, HostState
from .monitor import Monitor
from .pinger import ping

CycleCallback = Callable[[dict[int, HostState], list[Event]], None]


class Scheduler:
    def __init__(self, hosts: list[Host], monitor: Monitor,
                 settings: Settings, on_cycle_done: CycleCallback):
        self.hosts = hosts
        self.monitor = monitor
        self.settings = settings
        self.on_cycle_done = on_cycle_done
        self._wake = threading.Event()
        self._stopping = False
        self._thread: threading.Thread | None = None
        self.next_cycle_at: float | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._thread is not None:
            self._thread.join()

    def ping_now(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stopping:
            started = time.monotonic()
            try:
                self.run_cycle()
            except Exception:
                traceback.print_exc()
            elapsed = time.monotonic() - started
            remaining = max(0, self.settings.ping_interval - elapsed)
            if self.settings.auto_ping:
                self.next_cycle_at = time.monotonic() + remaining
                self._wake.wait(timeout=remaining)
            else:
                self.next_cycle_at = None
                self._wake.wait()

            self._wake.clear()

    def run_cycle(self) -> None:
        hosts_copy = [host for host in self.hosts if host.enabled]
        max_workers = len(hosts_copy) or 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(lambda host: ping(host_id=host.id, address=host.address, timeout_ms=host.timeout_ms), hosts_copy))
        events = self.monitor.process_cycle(results)
        self.on_cycle_done({host_id: copy.copy(state) for host_id, state in self.monitor.host_states.items()}, events)


if __name__ == "__main__":
    from datetime import datetime


    hosts = [
        Host(id=1, address="8.8.8.8", timeout_ms=1000),
        Host(id=2, address="1.1.1.1", timeout_ms=1000),
        Host(id=3, address="192.168.255.254", timeout_ms=1000)
    ]
    settings = Settings()
    settings.ping_interval = 5
    monitor = Monitor(settings)
    def on_cycle_done(states, events):
        print(f"--- {datetime.now():%H:%M:%S} ---")
        for host_id, state in states.items():
            print(f"Host ID: {host_id}, Status: {state.status}, Fail Streak: {state.fail_streak}, OK Streak: {state.ok_streak}, Total OK: {state.total_ok}, Total Fail: {state.total_fail}, Last RTT: {state.last_rtt_ms}, Last Change: {state.last_change}, Down Alerted: {state.down_alerted}")
        if events != []:
            print("Events:")
            for event in events:
                print(f"  {event.event_type} for host_id {event.host_id} at {event.timestamp}")
    scheduler = Scheduler(hosts, monitor, settings, on_cycle_done)
    scheduler.start()
    time.sleep(35)
    scheduler.stop()
    print("hotovo, scheduler zastaven")
