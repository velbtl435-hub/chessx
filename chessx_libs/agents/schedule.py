"""Calendar scheduling for agents: one-shot or recurring every N second/minute/hour/day/week/month/year.
Months/years use calendar arithmetic (Jan 31 + 1 month = Feb 28/29). Jobs persist to <home>/schedule.json;
`Runner` is the loop (use it in foreground or in a thread). Missed slots are skipped, not replayed."""
import calendar, datetime as dt, json, os, threading, time, traceback, uuid
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional

UNITS = ("second", "minute", "hour", "day", "week", "month", "year")
_SECS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800}


def norm_unit(u: str) -> str:
    u = u.lower().strip()
    aliases = {"sec": "second", "s": "second", "min": "minute", "m": "minute", "h": "hour", "d": "day", "w": "week",
               "mo": "month", "mon": "month", "y": "year", "yr": "year",
               "segundo": "second", "minuto": "minute", "hora": "hour", "dia": "day", "semana": "week",
               "mê": "month", "me": "month", "mes": "month", "mese": "month", "ano": "year"}
    if u not in aliases and u not in UNITS and u.endswith("s"):
        u = u[:-1]
    u = aliases.get(u, u)
    if u not in UNITS:
        raise ValueError("unit must be one of %s" % (UNITS,))
    return u


def add_months(t: dt.datetime, n: int) -> dt.datetime:
    m = t.month - 1 + n
    y, m = t.year + m // 12, m % 12 + 1
    return t.replace(year=y, month=m, day=min(t.day, calendar.monthrange(y, m)[1]))


def step(t: dt.datetime, every: int, unit: str) -> dt.datetime:
    if unit == "month":
        return add_months(t, every)
    if unit == "year":
        return add_months(t, 12 * every)
    return t + dt.timedelta(seconds=every * _SECS[unit])


@dataclass
class ScheduledJob:
    agent: str
    start: float                      # epoch of first run (anchor)
    every: int = 0                    # 0 = one-shot
    unit: str = "second"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    next_run: float = 0.0
    runs: int = 0
    max_runs: Optional[int] = None
    errors: int = 0
    last_error: str = ""
    enabled: bool = True

    def __post_init__(self):
        self.unit = norm_unit(self.unit)
        if not self.next_run:
            self.next_run = self.start

    def advance(self, now: float):
        """Compute next slot from the anchor so months don't drift (Jan31->Feb28->Mar31)."""
        if not self.every:
            self.enabled = False; return
        anchor, k = dt.datetime.fromtimestamp(self.start), 0
        if self.unit in _SECS:
            period = self.every * _SECS[self.unit]
            k = int((now - self.start) // period) + 1
            self.next_run = self.start + k * period
        else:
            months = self.every * (12 if self.unit == "year" else 1)
            k = max(1, self.runs)
            while True:
                nxt = add_months(anchor, months * k).timestamp()
                if nxt > now:
                    break
                k += 1
            self.next_run = nxt
        if self.max_runs is not None and self.runs >= self.max_runs:
            self.enabled = False


def parse_when(s: str, now: float = None) -> float:
    """'now', '+30s', '+5m', '+2h', '+1d', ISO 'YYYY-MM-DD[ HH:MM[:SS]]', or 'HH:MM' (next occurrence)."""
    now = now or time.time()
    s = s.strip()
    if s == "now":
        return now
    if s.startswith("+"):
        num = "".join(ch for ch in s[1:] if ch.isdigit())
        unit = norm_unit(s[1 + len(num):] or "s")
        return step(dt.datetime.fromtimestamp(now), int(num), unit).timestamp()
    if len(s) == 5 and s[2] == ":":
        h, m = map(int, s.split(":"))
        t = dt.datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0)
        return (t if t.timestamp() > now else t + dt.timedelta(days=1)).timestamp()
    return dt.datetime.fromisoformat(s).timestamp()


class AgentScheduler:
    def __init__(self, path: str, run_agent: Callable[[str], object], clock=time.time):
        self.path, self.run_agent, self.clock = path, run_agent, clock
        self.jobs: Dict[str, ScheduledJob] = {}
        self.lock = threading.RLock()
        self.log: List[tuple] = []
        if os.path.exists(path):
            self.load()

    def add(self, agent: str, every: int = 0, unit: str = "second", start: float = None, max_runs: int = None) -> ScheduledJob:
        j = ScheduledJob(agent, start if start is not None else self.clock() + (0 if not every else 0), every, unit, max_runs=max_runs)
        with self.lock:
            self.jobs[j.id] = j; self.save()
        return j

    def remove(self, job_id: str):
        with self.lock:
            self.jobs.pop(job_id); self.save()

    def list(self):
        return sorted(self.jobs.values(), key=lambda j: j.next_run)

    def run_pending(self) -> int:
        now, ran = self.clock(), 0
        with self.lock:
            due = [j for j in self.list() if j.enabled and j.next_run <= now]
        for j in due:
            try:
                self.run_agent(j.agent)
            except Exception as e:
                j.errors += 1; j.last_error = "%s: %s" % (type(e).__name__, e)
                self.log.append((now, j.agent, traceback.format_exc(limit=2)))
            j.runs += 1; ran += 1
            j.advance(self.clock())
        if due:
            self.save()
        return ran

    def next_delay(self):
        nxt = [j.next_run for j in self.jobs.values() if j.enabled]
        return max(0.0, min(nxt) - self.clock()) if nxt else None

    def run(self, duration: float = None, stop: threading.Event = None, max_sleep: float = 1.0):
        stop = stop or threading.Event()
        end = None if duration is None else self.clock() + duration
        while not stop.is_set() and (end is None or self.clock() < end):
            self.run_pending()
            d = self.next_delay()
            wait = max_sleep if d is None else min(max_sleep, d)
            if end is not None:
                wait = min(wait, max(0.0, end - self.clock()))
            stop.wait(wait)

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([asdict(j) for j in self.jobs.values()], fh, indent=1)
        os.replace(tmp, self.path)

    def load(self):
        with open(self.path, encoding="utf-8") as fh:
            for d in json.load(fh):
                j = ScheduledJob(**d); self.jobs[j.id] = j
