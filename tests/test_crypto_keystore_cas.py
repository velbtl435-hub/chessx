"""CRY-05: concurrent keystore handles must not silently lose each other's keys."""
import os, sys, unittest, importlib, tempfile, multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs import crypto
K = importlib.import_module("chessx_libs.crypto.keystore")
FL = importlib.import_module("chessx_libs.crypto._filelock")
FAST = {"m": 8 * 1024, "t": 1, "p": 1}


def _hold(path, q):
    with FL.locked(path):
        q.put("held")
        q.get()


class TestKeystoreCAS(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.d.name, "ks.json")
        try:
            K.Keystore.create(self.p, "pw", kdf_params=FAST).close()
        except crypto.Argon2Unavailable:
            self.skipTest("no argon2 backend")

    def tearDown(self):
        self.d.cleanup()

    def test_second_writer_gets_conflict_not_lost_update(self):
        a, b = K.Keystore.open(self.p, "pw"), K.Keystore.open(self.p, "pw")
        a.put("from_a")
        with self.assertRaises(K.KeystoreConflict):
            b.put("from_b")
        self.assertTrue(issubclass(K.KeystoreConflict, K.KeystoreError))
        c = K.Keystore.open(self.p, "pw")  # reopen + retry works and keeps both
        c.put("from_b")
        self.assertEqual(sorted(K.Keystore.open(self.p, "pw").names()), ["from_a", "from_b"])

    def test_same_handle_keeps_working(self):
        a = K.Keystore.open(self.p, "pw")
        a.put("x"); a.put("y"); a.put("x"); a.retire("x", 1)
        self.assertIn("y", K.Keystore.open(self.p, "pw").names())

    def test_overwrite_create(self):
        K.Keystore.create(self.p, "pw2", kdf_params=FAST, overwrite=True).put("z")
        self.assertEqual(K.Keystore.open(self.p, "pw2").names(), ["z"])

    @unittest.skipUnless(hasattr(os, "fork"), "posix")
    def test_lock_is_exclusive_across_processes(self):
        q = mp.get_context("fork").Queue()
        pr = mp.get_context("fork").Process(target=_hold, args=(self.p, q))
        pr.start()
        self.assertEqual(q.get(timeout=10), "held")
        import fcntl
        fd = os.open(self.p + ".lock", os.O_RDWR)
        try:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
            q.put("go"); pr.join(10)


if __name__ == "__main__":
    unittest.main()
