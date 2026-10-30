import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.mathx import dispatch
from chessx_libs.mathx import steps as st


class TestSteps(unittest.TestCase):
    def test_linear(self):
        self.assertEqual(st.solve_steps("2x+3=11")[-1], "Solution: x = 4")

    def test_quadratic(self):
        out = st.solve_steps("x^2-5x+6=0")
        self.assertTrue(any("Discriminant" in l and "= 1" in l for l in out))
        self.assertIn("3", out[-1]); self.assertIn("2", out[-1])

    def test_rational_discard(self):
        out = st.solve_steps("(x^2-1)/(x-1)=0")
        self.assertTrue(any("Discard" in l for l in out))
        self.assertEqual(out[-1], "Solution: x = -1")

    def test_system(self):
        self.assertIn("{x: 2, y: 1}", st.system_steps(["2x+y=5", "x-y=1"])[-1])

    def test_diff_rules(self):
        out = st.diff_steps("x^2*sin(x)")
        self.assertTrue(any("product rule" in l for l in out))
        out = st.diff_steps("exp(3x)/x")
        self.assertTrue(any("quotient rule" in l for l in out) and any("chain rule" in l for l in out))

    def test_integrate_parts(self):
        out = st.integrate_steps("x*exp(x)")
        self.assertTrue(any("by parts" in l for l in out))
        self.assertIn("(x - 1)*exp(x)", out[-1])

    def test_integrate_substitution(self):
        self.assertTrue(any("substitution" in l for l in st.integrate_steps("2x*cos(x^2)")))

    def test_limit_lhopital(self):
        out = st.limit_steps("sin(x)/x -> 0")
        self.assertTrue(any("L'Hôpital" in l for l in out)); self.assertEqual(out[-1], "Result: 1")

    def test_limit_cancel(self):
        self.assertEqual(st.limit_steps("(x^2-4)/(x-2) -> 2")[-1], "Result: 4")

    def test_simplify(self):
        self.assertEqual(st.simplify_steps("(x^2-1)/(x-1)")[-1], "Result: x + 1")

    def test_matrix(self):
        self.assertEqual(st.matrix_steps("det [[1,2,3],[0,1,4],[5,6,0]]")[-1], "Result: det = 1")
        self.assertIn("[[17], [39]]", st.matrix_steps("mul [[1,2],[3,4]] [[5],[6]]")[-1])
        self.assertIn("3/2", st.matrix_steps("inv [[1,2],[3,4]]")[-1])

    def test_check_flags_first_wrong(self):
        idx, rep = st.check_work(["2x+4=10", "2x=6", "x=4"])
        self.assertEqual(idx, 2)
        idx, _ = st.check_work(["2x+4=10", "2x=6", "x=3"])
        self.assertIsNone(idx)
        idx, _ = st.check_work(["(x+1)^2", "x^2+2x+1", "x^2+x+1"])
        self.assertEqual(idx, 2)

    def test_dispatch(self):
        self.assertIn("1. ", dispatch("steps solve 2x=4"))
        out = dispatch("check", read_block=lambda: ["3x-3=0", "x=2"])
        self.assertIn("WRONG", out)


if __name__ == "__main__":
    unittest.main()
