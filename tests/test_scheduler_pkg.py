"""TST-01: chessx_libs.scheduler with a fake clock (no real sleeping, no timing flakiness)."""
import datetime as dt, unittest
from chessx_libs.scheduler import Scheduler, Job, every
from chessx_libs.scheduler import core


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t, self.slept = t, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def mk(t=1_000_000.0):
    c = Clock(t)
    return Scheduler(clock=c, sleep=c.sleep), c


class TestScheduler(unittest.TestCase):
    def test_interval_job_runs_when_due(self):
        s, c = mk()
        calls = []
        j = s.add("a", lambda: calls.append(c.t), interval=10)
        self.assertEqual(s.run_pending(), 0)
        self.assertEqual(s.next_delay(), 10)
        c.t += 10
        self.assertEqual(s.run_pending(), 1)
        self.assertEqual((j.runs, j.next_run), (1, c.t + 10))
        self.assertEqual(len(calls), 1)

    def test_start_now_and_drift_free(self):
        s, c = mk()
        j = s.add("a", lambda: None, interval=5, start_now=True)
        self.assertEqual(s.run_pending(), 1)
        t0 = j.next_run
        c.t += 6  # late by 1s: next slot steps from previous slot, not from now
        s.run_pending()
        self.assertEqual(j.next_run, t0 + 5)

    def test_missed_slots_skipped(self):
        s, c = mk()
        j = s.add("a", lambda: None, interval=5)
        c.t += 100
        self.assertEqual(s.run_pending(), 1)  # runs once, not 20 times
        self.assertEqual(j.next_run, c.t + 5)

    def test_errors_recorded_not_raised(self):
        s, c = mk()
        j = s.add("bad", lambda: 1 / 0, interval=1, start_now=True)
        s.run_pending()
        self.assertEqual((j.runs, j.errors), (1, 1))
        self.assertEqual(j.last_error, "ZeroDivisionError: division by zero")
        self.assertEqual(s.log[-1][1:3], ("bad", "error"))

    def test_cancelled_job_dropped(self):
        s, c = mk()
        j = s.add("a", lambda: None, interval=1, start_now=True)
        j.cancelled = True
        self.assertEqual(s.run_pending(), 0)
        self.assertEqual(s.status(), [])
        self.assertIsNone(s.next_delay())

    def test_daily_today_and_tomorrow(self):
        base = dt.datetime(2026, 10, 30, 8, 0).timestamp()
        s, c = mk(base)
        j = s.add("d", lambda: None, at="09:30")
        self.assertEqual(j.next_run, dt.datetime(2026, 10, 30, 9, 30).timestamp())
        k = s.add("e", lambda: None, at="07:00")
        self.assertEqual(k.next_run, dt.datetime(2026, 10, 31, 7, 0).timestamp())
        c.t = j.next_run
        s.run_pending()
        self.assertEqual(j.next_run, dt.datetime(2026, 10, 31, 9, 30).timestamp())

    def test_decorators_and_units(self):
        s, c = mk()

        @s.every(2, "minutes")
        def job():
            pass

        @s.daily("23:59")
        def nightly():
            pass

        names = {x["name"] for x in s.status()}
        self.assertEqual(names, {"job", "nightly"})
        self.assertEqual(s.next_delay(), min(120, s.next_delay()))
        with self.assertRaises(KeyError):
            s.every(1, "fortnights")(lambda: None)

    def test_tick_ran_idle_sleep(self):
        s, c = mk()
        s.add("a", lambda: None, interval=3, start_now=True)
        self.assertEqual(s.tick(), "ran")
        work = [True, False]
        s.add_idle(lambda: work.pop(0) if work else False)
        self.assertEqual(s.tick(), "idle-work")
        self.assertEqual(s.idle_slices, 1)
        self.assertEqual(s.tick(max_sleep=1.0), "sleep")
        self.assertEqual(c.slept, [1.0])
        self.assertEqual(s.log[-1][3], "no idle work; waiting for next job")

    def test_tick_sleep_bounded_by_next_job_and_idle_errors(self):
        s, c = mk()
        s.add("a", lambda: None, interval=0.5)

        def boom():
            raise RuntimeError("x")
        s.add_idle(boom)
        self.assertEqual(s.tick(max_sleep=5), "sleep")
        self.assertEqual(c.slept, [0.5])
        self.assertIn((c.t - 0.5, "boom", "error", "x"), s.log)

    def test_no_jobs_reason_and_log_trim(self):
        s, c = mk()
        for _ in range(1001):
            s.tick(max_sleep=0.1)
        self.assertEqual(s.sleeps, 1001)
        self.assertLessEqual(len(s.log), 1000)
        self.assertEqual(s.log[-1][3], "no jobs")

    def test_run_duration_uses_fake_clock(self):
        s, c = mk()
        n = []
        s.add("a", lambda: n.append(1), interval=1)
        s.run(duration=5)
        self.assertEqual(len(n), 4)  # end is exclusive: slot at t+5 not run
        self.assertAlmostEqual(c.t, 1_000_005.0)

    def test_stop_before_run(self):
        s, c = mk()
        s.stop()
        s.run()  # returns immediately; would loop forever otherwise
        self.assertEqual(c.slept, [])

    def test_start_thread_and_stop(self):
        s, c = mk()
        s.stop()
        t = s.start()
        t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(t.name, "chessx-scheduler")

    def test_status_sorted_and_job_order(self):
        s, c = mk()
        s.add("late", lambda: None, interval=9)
        s.add("soon", lambda: None, interval=1)
        self.assertEqual([x["name"] for x in s.status()], ["soon", "late"])
        self.assertLess(Job(1, 0, "x", None), Job(1, 1, "y", None))

    def test_module_every_uses_default(self):
        before = len(core._default._heap)

        @every(1, "hour")
        def hourly():
            pass
        self.assertEqual(len(core._default._heap), before + 1)
        core._default._heap = [j for j in core._default._heap if j.name != "hourly"]


if __name__ == "__main__":
    unittest.main()
