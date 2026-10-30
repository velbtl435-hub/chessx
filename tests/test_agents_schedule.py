import datetime as dt, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.agents import AgentScheduler, parse_when
from chessx_libs.agents.schedule import add_months, norm_unit


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


class TestSchedule(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "s.json"); self.ran = []

    def mk(self, clock):
        return AgentScheduler(self.path, self.ran.append, clock)

    def test_units_seconds_to_weeks(self):
        c = Clock(1000.0); s = self.mk(c)
        for u in ("second", "minute", "hour", "day"):
            s.add(u, every=2, unit=u, start=1000.0)
        s.run_pending(); self.assertEqual(len(self.ran), 4)
        c.t = 1002.0; s.run_pending(); self.assertEqual(self.ran[-1], "second")
        c.t = 1000.0 + 2 * 86400; s.run_pending()
        self.assertEqual(sorted(self.ran[5:]), ["day", "hour", "minute", "second"])

    def test_month_year_calendar(self):
        self.assertEqual(add_months(dt.datetime(2026, 1, 31), 1), dt.datetime(2026, 2, 28))
        self.assertEqual(add_months(dt.datetime(2028, 2, 29), 12), dt.datetime(2029, 2, 28))
        start = dt.datetime(2026, 1, 31, 9).timestamp(); c = Clock(start); s = self.mk(c)
        j = s.add("m", every=1, unit="mes", start=start); y = s.add("y", every=1, unit="ano", start=start)
        s.run_pending()
        self.assertEqual(dt.datetime.fromtimestamp(j.next_run), dt.datetime(2026, 2, 28, 9))
        c.t = j.next_run; s.run_pending()
        self.assertEqual(dt.datetime.fromtimestamp(j.next_run), dt.datetime(2026, 3, 31, 9))  # no drift
        self.assertEqual(dt.datetime.fromtimestamp(y.next_run).year, 2027)

    def test_one_shot_max_runs_persist(self):
        c = Clock(0.0); s = self.mk(c)
        s.add("once", start=5.0); s.add("thrice", every=1, unit="s", start=0.0, max_runs=3)
        for t in range(10):
            c.t = float(t); s.run_pending()
        self.assertEqual(self.ran.count("once"), 1); self.assertEqual(self.ran.count("thrice"), 3)
        self.assertEqual(len(AgentScheduler(self.path, print).jobs), 2)

    def test_parse_when(self):
        now = dt.datetime(2026, 10, 30, 10, 0).timestamp()
        self.assertEqual(parse_when("+30s", now), now + 30)
        self.assertEqual(parse_when("+1mo", now), dt.datetime(2026, 11, 30, 10).timestamp())
        self.assertEqual(parse_when("09:00", now), dt.datetime(2026, 10, 31, 9).timestamp())
        self.assertEqual(norm_unit("horas"), "hour")

    def test_errors_isolated(self):
        s = AgentScheduler(self.path, lambda n: 1 / 0, Clock(0.0)); j = s.add("x", start=0.0)
        s.run_pending(); self.assertEqual(j.errors, 1)


if __name__ == "__main__":
    unittest.main()
