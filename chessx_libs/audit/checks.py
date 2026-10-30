import ast, os, py_compile, re
from dataclasses import dataclass


@dataclass
class Finding:
    path: str
    line: int
    category: str   # bug | security | optimization | modularization | scalability
    severity: str   # high | medium | low
    message: str


SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|passw(or)?d)\s*=\s*['\"][^'\"]{8,}['\"]")
DANGEROUS_CALLS = {"eval": "eval() on dynamic input", "exec": "exec() on dynamic input",
                   "os.system": "shell command via os.system", "pickle.loads": "unpickling untrusted data",
                   "marshal.loads": "unmarshal untrusted data", "yaml.load": "yaml.load without SafeLoader"}


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


class _Visitor(ast.NodeVisitor):
    def __init__(self, path):
        self.path, self.f, self.loop = path, [], 0

    def add(self, node, cat, sev, msg):
        self.f.append(Finding(self.path, getattr(node, "lineno", 0), cat, sev, msg))

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.add(node, "bug", "medium", "bare except: hides errors (catch specific exceptions)")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.add(node, "bug", "low", "exception silently swallowed (except: pass)")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for d in node.args.defaults + node.args.kw_defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                self.add(d, "bug", "high", f"mutable default argument in {node.name}()")
        n = node.end_lineno - node.lineno + 1 if node.end_lineno else 0
        if n > 80:
            self.add(node, "modularization", "medium", f"{node.name}() is {n} lines; split it")
        branches = sum(isinstance(x, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)) for x in ast.walk(node))
        if branches > 15:
            self.add(node, "modularization", "low", f"{node.name}() complexity ~{branches}")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        n = _name(node.func)
        if n in DANGEROUS_CALLS:
            self.add(node, "security", "high", DANGEROUS_CALLS[n])
        if n.startswith("subprocess.") and any(k.arg == "shell" and getattr(k.value, "value", False) for k in node.keywords):
            self.add(node, "security", "high", "subprocess with shell=True")
        if n in ("urllib.request.urlopen", "urlopen", "requests.get", "requests.post") and \
                not any(k.arg == "timeout" for k in node.keywords):
            self.add(node, "scalability", "medium", f"{n} without timeout can hang workers")
        if n in ("hashlib.md5", "hashlib.sha1"):
            self.add(node, "security", "low", f"{n}: weak hash (ok for fingerprints, not for security)")
        if n in ("random.random", "random.choice", "random.randint") and self.loop == 0:
            pass
        if self.loop and n == "open":
            self.add(node, "optimization", "low", "open() inside loop")
        self.generic_visit(node)

    def _loop(self, node):
        self.loop += 1
        for x in ast.walk(node):
            if isinstance(x, ast.AugAssign) and isinstance(x.op, ast.Add) and isinstance(x.value, (ast.JoinedStr, ast.Constant)) \
                    and isinstance(getattr(x.value, "value", ""), str):
                self.add(x, "optimization", "low", "string += in loop; use list + ''.join()")
                break
        self.generic_visit(node)
        self.loop -= 1

    visit_For = visit_While = _loop

    def visit_Assert(self, node):
        self.add(node, "bug", "low", "assert used for validation is stripped under python -O")
        self.generic_visit(node)


def audit_file(path: str):
    out = []
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        return [Finding(path, 0, "bug", "high", f"does not compile: {e.msg.strip()[:200]}")]
    with open(path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    tree = ast.parse(src)
    v = _Visitor(path)
    v.visit(tree)
    out += v.f
    for i, line in enumerate(src.splitlines(), 1):
        if "audit: ignore" in line:
            continue
        if SECRET_RE.search(line):
            out.append(Finding(path, i, "security", "high", "possible hard-coded secret"))
        if re.search(r"verify\s*=\s*False|CERT_NONE|_create_unverified_context", line):  # audit: ignore
            out.append(Finding(path, i, "security", "high", "TLS verification disabled"))
        if re.search(r"\b(TODO|FIXME|XXX)\b", line):  # audit: ignore
            out.append(Finding(path, i, "bug", "low", "unresolved TODO/FIXME"))  # audit: ignore
    lines = src.count("\n") + 1
    if lines > 400:
        out.append(Finding(path, 1, "modularization", "medium", f"file has {lines} lines; split into modules"))
    if re.search(r"^\s*(import|from)\s+\S+\s+import\s+\*", src, re.M):
        out.append(Finding(path, 1, "modularization", "low", "wildcard import"))
    return out


def audit_tree(root: str, exclude=("__pycache__", ".git", "venv", ".venv")):
    findings = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in exclude]
        for f in sorted(files):
            if f.endswith(".py"):
                findings += audit_file(os.path.join(d, f))
    return findings
