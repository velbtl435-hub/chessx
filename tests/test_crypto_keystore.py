import json, os, stat, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.crypto import keystore as K

FAST = {"t": 1, "m": 8192, "p": 1}


class TestKeystore(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "ks.json")

    def test_lifecycle(self):
        ks = K.Keystore.create(self.path, "pw", FAST)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        v1 = ks.put("db")
        k1 = bytes(ks.get("db"))
        v2 = ks.rotate("db")
        self.assertEqual((v1, v2, ks.active_version("db")), (1, 2, 2))
        self.assertNotEqual(bytes(ks.get("db")), k1)
        self.assertEqual(bytes(ks.get("db", 1)), k1)
        ks.close()
        with self.assertRaises(K.KeystoreError):
            ks.get("db")
        raw = open(self.path).read()
        self.assertNotIn(k1.hex(), raw)
        with self.assertRaises(K.KeystoreError):
            K.Keystore.open(self.path, "wrong")
        with K.Keystore.open(self.path, "pw") as ks2:
            self.assertEqual(bytes(ks2.get("db", 1)), k1)
            with self.assertRaises(K.KeystoreError):
                ks2.retire("db", 2)
            ks2.retire("db", 1)
            self.assertEqual(ks2.versions("db"), [2])
            ks2.change_password("pw2", FAST)
            k2 = bytes(ks2.get("db"))
        with self.assertRaises(K.KeystoreError):
            K.Keystore.open(self.path, "pw")
        self.assertEqual(bytes(K.Keystore.open(self.path, "pw2").get("db")), k2)
        with self.assertRaises(FileExistsError):
            K.Keystore.create(self.path, "x", FAST)

    def test_tamper_swap_detected(self):
        ks = K.Keystore.create(self.path, "pw", FAST)
        ks.put("a"); ks.put("b")
        d = json.load(open(self.path))
        d["keys"]["a"]["versions"]["1"], d["keys"]["b"]["versions"]["1"] = d["keys"]["b"]["versions"]["1"], d["keys"]["a"]["versions"]["1"]
        json.dump(d, open(self.path, "w"))
        with self.assertRaises(K.KeystoreError):
            K.Keystore.open(self.path, "pw").get("a")

    def test_zeroize_and_keyring(self):
        b = bytearray(b"secret")
        K.zeroize(b)
        self.assertEqual(b, bytearray(6))
        ks = K.Keystore.create(self.path, "pw", FAST)
        kek = ks._kek
        ks.close()
        self.assertEqual(kek, bytearray(32))
        fake = mock.MagicMock()
        fake.get_password.return_value = "pw"
        with mock.patch.dict(sys.modules, {"keyring": fake}):
            K.keyring_store_password("chessx", "me", "pw")
            fake.set_password.assert_called_once_with("chessx", "me", "pw")
            K.Keystore.open(self.path, keyring_service="chessx", keyring_account="me").close()
        with mock.patch.dict(sys.modules, {"keyring": None}):
            with self.assertRaises(RuntimeError):
                K.keyring_get_password("chessx", "me")


if __name__ == "__main__":
    unittest.main()
