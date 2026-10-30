"""TST-01: chessx_libs.audit (offline, temp files only)."""
import os, tempfile, textwrap, unittest
from chessx_libs.audit import audit_file, audit_tree, Finding, render_report, score


def _audit(src, name="m.py"):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(src))
        return audit_file(p)


def _msgs(fs):
    return [f.message for f in fs]


class TestChecks(unittest.TestCase):
    def test_clean_file_has_no_findings(self):
        self.assertEqual(_audit("def f(x):\n    return x + 1\n"), [])

    def test_syntax_error_single_high_bug(self):
        fs = _audit("def f(:\n")
        self.assertEqual(len(fs), 1)
        self.assertEqual((fs[0].category, fs[0].severity, fs[0].line), ("bug", "high", 0))
        self.assertIn("does not compile", fs[0].message)

    def test_bare_except_and_swallow(self):
        fs = _audit("try:\n    x = 1\nexcept:\n    pass\n")
        m = _msgs(fs)
        self.assertTrue(any("bare except" in x for x in m))
        self.assertTrue(any("silently swallowed" in x for x in m))
        self.assertEqual([f.line for f in fs if "bare" in f.message], [3])

    def test_typed_except_with_body_is_fine(self):
        self.assertEqual(_audit("try:\n    x = 1\nexcept ValueError:\n    x = 2\n"), [])

    def test_mutable_defaults(self):
        fs = _audit("def f(a=[], b={}, *, c=set()):\n    return a\ndef g(*, k={}):\n    return k\n")
        hi = [f for f in fs if "mutable default" in f.message]
        self.assertEqual(len(hi), 3)  # [] {} and kw-only {} (set() is a Call, not ast.Set)
        self.assertTrue(all(f.severity == "high" for f in hi))

    def test_long_and_complex_function(self):
        body = "".join("    if x == %d:\n        x += 1\n" % i for i in range(45))
        fs = _audit("def big(x):\n" + body + "    return x\n")
        m = _msgs(fs)
        self.assertTrue(any("big() is" in x and "split it" in x for x in m))
        self.assertTrue(any("big() complexity ~45" in x for x in m))

    def test_async_function_visited(self):
        self.assertTrue(any("mutable default in h()" in x or "mutable default argument in h()" in x
                            for x in _msgs(_audit("async def h(a=[]):\n    return a\n"))))

    def test_dangerous_calls(self):
        src = ("import os, pickle, subprocess, yaml\n"
               "eval(s)\nexec(s)\nos.system(s)\npickle.loads(b)\nyaml.load(s)\n"
               "subprocess.run(s, shell=True)\nsubprocess.run([s], shell=False)\n")
        fs = [f for f in _audit(src) if f.category == "security"]
        self.assertEqual(len(fs), 6)
        self.assertEqual(sorted(f.line for f in fs), [2, 3, 4, 5, 6, 7])

    def test_requests_without_timeout(self):
        fs = _audit("import requests\nrequests.get(u)\nrequests.get(u, timeout=5)\n")
        sc = [f for f in fs if f.category == "scalability"]
        self.assertEqual([f.line for f in sc], [2])

    def test_weak_hash_low(self):
        fs = _audit("import hashlib\nhashlib.md5(b'')\nhashlib.sha256(b'')\n")
        self.assertEqual([(f.line, f.severity) for f in fs], [(2, "low")])

    def test_loop_open_and_string_concat(self):
        fs = _audit("s = ''\nfor p in ps:\n    open(p)\n    s += 'x'\nwhile 0:\n    s += f'{s}'\n")
        m = _msgs(fs)
        self.assertEqual(sum("open() inside loop" in x for x in m), 1)
        self.assertEqual(sum("string +=" in x for x in m), 2)

    def test_open_outside_loop_ok(self):
        self.assertEqual(_audit("open('x')\nimport random\nrandom.random()\n"), [])

    def test_assert(self):
        fs = _audit("assert x\n")
        self.assertEqual([(f.category, f.line) for f in fs], [("bug", 1)])

    def test_line_rules_and_ignore(self):
        src = ('api_key = "abcdefgh12345"\n'
               'token = "short"\n'
               'requests_kw = dict(verify=False)\n'
               '# TODO fix\n'
               'password = "abcdefghijk"  # audit: ignore\n')
        fs = _audit(src)
        self.assertEqual(sorted((f.line, f.message) for f in fs),
                         [(1, "possible hard-coded secret"), (3, "TLS verification disabled"),
                          (4, "unresolved TODO/FIXME")])

    def test_big_file_and_wildcard(self):
        fs = _audit("from os import *\n" + "x = 1\n" * 410)
        m = _msgs(fs)
        self.assertTrue(any("split into modules" in x for x in m))
        self.assertTrue(any("wildcard import" in x for x in m))

    def test_audit_tree_walks_and_excludes(self):
        with tempfile.TemporaryDirectory() as d:
            for sub in ("pkg", ".git", "venv", "__pycache__"):
                os.makedirs(os.path.join(d, sub))
                with open(os.path.join(d, sub, "a.py"), "w") as f:
                    f.write("eval(x)\n")
            with open(os.path.join(d, "pkg", "note.txt"), "w") as f:
                f.write("eval(x)\n")
            fs = audit_tree(d)
        self.assertEqual(len(fs), 1)
        self.assertIn(os.path.join("pkg", "a.py"), fs[0].path)


class TestReport(unittest.TestCase):
    def F(self, sev, cat="bug", path="/r/a.py", line=1):
        return Finding(path, line, cat, sev, "m")

    def test_score(self):
        self.assertEqual(score([]), 100)
        self.assertEqual(score([self.F("high"), self.F("medium"), self.F("low")]), 86)
        self.assertEqual(score([self.F("high")] * 20), 0)  # clamped

    def test_render_order_and_relpath(self):
        fs = [self.F("low", "security", line=9), self.F("high", "bug", "/r/b.py", 2),
              self.F("medium", "optimization", "/other/c.py", 3)]
        out = render_report(fs, root="/r").splitlines()
        self.assertEqual(out[0], "ChessX audit: 3 findings, score 86/100")
        self.assertEqual(out[1], "by category: bug=1, optimization=1, security=1")
        self.assertEqual(out[2], "by severity: high=1, medium=1, low=1")
        self.assertTrue(out[4].startswith("[high  ]") and out[4].endswith("b.py:2  m"))
        self.assertIn("/other/c.py:3", out[5])
        self.assertIn(" a.py:9", out[6])

    def test_render_empty(self):
        out = render_report([])
        self.assertIn("0 findings, score 100/100", out)
        self.assertIn("high=0, medium=0, low=0", out)


if __name__ == "__main__":
    unittest.main()
