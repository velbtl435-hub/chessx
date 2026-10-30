import datetime as dt, heapq, itertools, threading, time, traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

UNITS = {"second": 1, "seconds": 1, "minute": 60, "minutes": 60, "hour": 3600, "hours": 3600,
         "day": 86400, "days": 86400}


@dataclass(order=True)
class Job:
    next_run: float
    seq: int
    name: str = field(compare=False)
    func: Callable = field(compare=False)
    interval: float = field(compare=False, default=0)
    at: Optional[str] = field(compare=False, default=None)   # "HH:MM" for daily jobs
    runs: int = field(compare=False, default=0)
    errors: int = field(compare=False, default=0)
    last_error: str = field(compare=False, default="")
    cancelled: bool = field(compare=False, default=False)

    def schedule_next(self, now: float):
        if self.at:
            h, m = map(int, self.at.split(":"))
            t = dt.datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0)
            if t.timestamp() <= now:
                t += dt.timedelta(days=1)
            self.next_run = t.timestamp()
        else:
            # drift-free: step from previous slot, skip missed slots
            self.next_run += self.interval
            if self.next_run <= now:
                self.next_run = now + self.interval


class Scheduler:
    """Heap-based scheduler. When nothing is due, runs registered idle tasks (bounded slices)
    instead of sleeping; it only sleeps when there is no idle work (the 'reason' is logged)."""

    def __init__(self, clock=time.time, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self._heap, self._seq = [], itertools.count()
        self.idle_tasks = []
        self.log = []
        self._stop = threading.Event()
        self.idle_slices = self.sleeps = 0

    def add(self, name, func, interval: float = 0, at: str = None, start_now: bool = False) -> Job:
        now = self.clock()
        j = Job(now if start_now else now + interval, next(self._seq), name, func, interval, at)
        if at:
            j.schedule_next(now)
        heapq.heappush(self._heap, j)
        return j

    def every(self, n: float, unit: str = "seconds"):
        def deco(f):
            self.add(f.__name__, f, n * UNITS[unit])
            return f
        return deco

    def daily(self, at: str):
        def deco(f):
            self.add(f.__name__, f, at=at)
            return f
        return deco

    def add_idle(self, func: Callable[[], bool]):
        """Idle task returns True if it did useful work (keeps system busy)."""
        self.idle_tasks.append(func)

    def _run(self, j: Job):
        try:
            j.func()
        except Exception as e:
            j.errors += 1
            j.last_error = f"{type(e).__name__}: {e}"
            self.log.append((self.clock(), j.name, "error", traceback.format_exc(limit=2)))
        j.runs += 1

    def run_pending(self) -> int:
        now, ran = self.clock(), 0
        while self._heap and self._heap[0].next_run <= now:
            j = heapq.heappop(self._heap)
            if j.cancelled:
                continue
            self._run(j)
            ran += 1
            j.schedule_next(self.clock())
            heapq.heappush(self._heap, j)
        return ran

    def next_delay(self):
        return max(0.0, self._heap[0].next_run - self.clock()) if self._heap else None

    def tick(self, max_sleep: float = 1.0):
        if self.run_pending():
            return "ran"
        for task in self.idle_tasks:
            try:
                if task():
                    self.idle_slices += 1
                    return "idle-work"
            except Exception as e:
                self.log.append((self.clock(), getattr(task, "__name__", "idle"), "error", str(e)))
        d = self.next_delay()
        reason = "no idle work; waiting for next job" if d is not None else "no jobs"
        self.sleeps += 1
        self.log.append((self.clock(), "scheduler", "sleep", reason))
        if len(self.log) > 1000:
            del self.log[:500]
        self.sleep(min(max_sleep, d if d is not None else max_sleep))
        return "sleep"

    def run(self, duration: float = None):
        end = None if duration is None else self.clock() + duration
        while not self._stop.is_set() and (end is None or self.clock() < end):
            self.tick(max_sleep=0.25 if end is None else max(0.0, min(0.25, end - self.clock())))

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self.run, daemon=True, name="chessx-scheduler")
        t.start()
        return t

    def stop(self):
        self._stop.set()

    def status(self):
        return [{"name": j.name, "runs": j.runs, "errors": j.errors, "next": j.next_run}
                for j in sorted(self._heap)]


_default = Scheduler()


def every(n, unit="seconds"):
    return _default.every(n, unit)
