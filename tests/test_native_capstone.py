import os, unittest
from chessx_libs.native import capstone as ncs

CODE = bytes.fromhex("554889e5c3")


class TestNativeCapstone(unittest.TestCase):
    def test_backend_name(self):
        self.assertIn(ncs.backend(), ("native", "pip", "python"))

    def test_disasm_any_backend(self):
        ins = ncs.disasm(CODE, "x86", "64", 0x1000)
        self.assertEqual([i[2] for i in ins], ["push", "mov", "ret"])
        self.assertEqual(ins[1][0], 0x1001)

    def test_mode_parsing(self):
        self.assertEqual(ncs._num("mips32+big", ncs.MODE), 4 | (1 << 31))
        self.assertEqual(ncs._c32(1 << 31), -(1 << 31))

    @unittest.skipUnless(ncs._lib() is not None, "native capstone not built (make -f Makefile -f capstone/module.mk)")
    def test_native_matches_pip(self):
        try:
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest("pip capstone missing")
        for arch, mode, hx in ((3, 8, "4883ec28c3"), (1, 0, "fd7bbfa9c0035fd6"), (15, 6, "0145828082")):
            b = bytes.fromhex(hx)
            self.assertEqual(ncs.disasm_native(b, arch, mode, 0x400000), ncs.disasm_pip(b, arch, mode, 0x400000))

    @unittest.skipUnless(ncs._lib() is not None, "native capstone not built")
    def test_native_big_output_and_bad_arch(self):
        self.assertEqual(len(ncs.disasm_native(b"\x90" * 5000)), 5000)
        with self.assertRaises(ValueError):
            ncs.disasm_native(b"\x90", 99, 0)

    def test_python_fallback(self):
        old_l, old_p = ncs._lib, ncs._pip
        ncs._lib = lambda: None; ncs._pip = lambda: None
        try:
            self.assertEqual(ncs.backend(), "python")
            self.assertEqual([i[2] for i in ncs.disasm(CODE)], ["push", "mov", "ret"])
            with self.assertRaises(RuntimeError):
                ncs.disasm(b"\x00", "arm", "arm")
        finally:
            ncs._lib, ncs._pip = old_l, old_p


if __name__ == "__main__":
    unittest.main()
