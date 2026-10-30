"""CRY-01 callers: AEADUnavailable is reported as a skip (selftest) / message (menu), never a silent fallback."""
import unittest
from unittest import mock
import chessx
from chessx_libs import crypto
from chessx_libs.menu import registry


def _raise(*a, **k):
    if k.get("allow_fallback"):
        raise AssertionError("allow_fallback must not be used")
    raise crypto.AEADUnavailable("no cryptography")


class TestSelftest(unittest.TestCase):
    def test_skip_not_fail_without_cryptography(self):
        with mock.patch.object(crypto, "chacha20_poly1305_encrypt", _raise):
            res = chessx.selftest()
        self.assertEqual(res["crypto"], chessx.SKIP_NO_CRYPTOGRAPHY)
        self.assertIn("cryptography não instalado — pulado", res["crypto"])
        self.assertTrue(chessx.selftest_passed({"a": "ok", "crypto": res["crypto"]}))

    def test_other_errors_still_fail(self):
        with mock.patch.object(crypto, "chacha20_poly1305_encrypt", side_effect=ValueError("bad")):
            res = chessx.selftest()
        self.assertTrue(res["crypto"].startswith("FAIL"))
        self.assertFalse(chessx.selftest_passed(res))

    def test_selftest_passed(self):
        self.assertTrue(chessx.selftest_passed({"a": "ok"}))
        self.assertFalse(chessx.selftest_passed({"a": "FAIL: x"}))


class TestMenu(unittest.TestCase):
    def test_menu_reports_skip(self):
        with mock.patch.object(crypto, "chacha20_poly1305_encrypt", _raise):
            out = registry._crypto(None, lambda p: "")
        self.assertIn("roundtrip cryptography não instalado — pulado", out)
        self.assertIn("TOTP secret", out)

    @unittest.skipUnless(crypto.CRYPTO_BACKEND == "cryptography", "cryptography not installed")
    def test_menu_ok_with_cryptography(self):
        self.assertIn("roundtrip ok", registry._crypto(None, lambda p: ""))


if __name__ == "__main__":
    unittest.main()
