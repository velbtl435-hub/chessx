"""CRY-04: TOTP replay protection/lockout must survive restarts and be shared across processes."""
import os, sys, unittest, importlib, tempfile, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto
O = importlib.import_module("chessx_libs.crypto.otp")
SECRET, T = "JBSWY3DPEHPK3PXP", 1_700_000_000


def _worker(path, code, q):
    q.put(O.TOTPVerifier(store=O.JSONFileStore(path)).verify("alice", SECRET, code, t=T))


class TestFileStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "totp.json")
        self.code = O.totp(SECRET, T)

    def tearDown(self):
        self.d.cleanup()

    def test_replay_rejected_after_restart(self):
        self.assertTrue(O.TOTPVerifier(store=O.JSONFileStore(self.p)).verify("alice", SECRET, self.code, t=T))
        fresh = O.TOTPVerifier(store=O.JSONFileStore(self.p))  # "restart"
        self.assertFalse(fresh.verify("alice", SECRET, self.code, t=T))
        self.assertEqual(oct(os.stat(self.p).st_mode & 0o777), "0o600")
        self.assertIs(crypto.JSONFileStore, O.JSONFileStore)

    def test_lockout_persists(self):
        v = O.TOTPVerifier(store=O.JSONFileStore(self.p), max_failures=2)
        v.verify("bob", SECRET, "000000", t=T); v.verify("bob", SECRET, "000001", t=T)
        w = O.TOTPVerifier(store=O.JSONFileStore(self.p), max_failures=2)
        self.assertTrue(w.locked("bob", now=T))
        with self.assertRaises(O.LockedOut):
            w.verify("bob", SECRET, self.code, t=T)

    @unittest.skipUnless(hasattr(os, "fork"), "posix")
    def test_concurrent_processes_accept_code_once(self):
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        ps = [ctx.Process(target=_worker, args=(self.p, self.code, q)) for _ in range(6)]
        for p in ps: p.start()
        res = [q.get(timeout=20) for _ in ps]
        for p in ps: p.join(10)
        self.assertEqual(res.count(True), 1)

    def test_dict_store_unchanged(self):
        v = O.TOTPVerifier()
        self.assertTrue(v.verify("a", SECRET, self.code, t=T))
        self.assertFalse(v.verify("a", SECRET, self.code, t=T))
        self.assertEqual(v.store["a"]["last_step"], T // 30)


if __name__ == "__main__":
    unittest.main()
