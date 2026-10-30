import random, unittest
from chessx_libs.crypto.netsec import FingerprintRotator

class T(unittest.TestCase):
    def test_default_uses_systemrandom(self):
        self.assertIsInstance(FingerprintRotator().rng, random.SystemRandom)
    def test_seed_reproducible(self):
        a, b = FingerprintRotator(1), FingerprintRotator(1)
        self.assertEqual([a.headers() for _ in range(5)], [b.headers() for _ in range(5)])
        self.assertIn("User-Agent", FingerprintRotator().headers())
if __name__ == "__main__": unittest.main()
