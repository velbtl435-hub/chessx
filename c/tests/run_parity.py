#!/usr/bin/env python3
"""Parity test: every vector in c/<mod>/vectors.txt must give identical output on
native CLI, wasm CLI (wasmtime, and wasmer if installed), ctypes .so, and pure Python."""
import argparse, os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(C))
from chessx_libs.native import hello_fusion as hf  # noqa: E402


def py_run(args, crc, fuse):
    cmd, rest = args[0], args[1:]
    if cmd == "crc":
        return "%08x" % crc((rest[0] if rest else "").encode())
    if cmd == "crchex":
        return "%08x" % crc(bytes.fromhex(rest[0] if rest else ""))
    if cmd == "fuse":
        pairs = [tuple(int(x) for x in p.split(":")) for p in rest]
        return " ".join("%d:%d" % p for p in fuse(pairs))
    raise ValueError(cmd)


def search_run(v, ns):
    cmd, rest = v[0], v[1:]
    if cmd == "norm":
        return "[%s]" % ns["norm"](rest[0] if rest else "")
    if cmd == "rank":
        return " ".join(map(str, ns["rank"]([int(x) for x in rest])))
    if cmd == "fuse":
        items = []
        for t in rest:
            e, s, u = t.split(":", 2)
            items.append((int(e), int(s), u))
        _, gs, order = ns["fuse"](items)
        return " ".join("%d:%d" % (g, gs[g]) for g in order)
    raise ValueError(cmd)


def run_search(build, wasmtime):
    """c/search parity: pure Python (fusion.py semantics) == ctypes == native CLI == wasmtime."""
    from chessx_libs.native import search as cs
    assert cs.backend() == "native", "ctypes could not load libcx_search"
    cli, wasm = os.path.join(build, "native", "search_cli"), os.path.join(build, "wasm", "search.wasm")
    runners = {"python": lambda v: search_run(v, {"norm": cs.norm_url_py, "rank": cs.rank_py, "fuse": cs.fuse_py}),
               "ctypes": lambda v: search_run(v, {"norm": cs.norm_url, "rank": cs.rank, "fuse": cs.fuse_indices}),
               "native-cli": lambda v: subprocess.run([cli] + v, capture_output=True, text=True,
                                                      check=True).stdout.strip()}
    if shutil.which(wasmtime):
        runners["wasmtime"] = lambda v: subprocess.run([wasmtime, "run", wasm] + v, capture_output=True, text=True,
                                                       check=True).stdout.strip()
    vectors = []
    for line in open(os.path.join(C, "search", "vectors.txt"), encoding="utf-8"):
        line = line.rstrip("\n")
        if line.strip() and not line.startswith("#"):
            cmd, _, rest = line.partition(" ")
            vectors.append([cmd] + ([rest] if cmd == "norm" else rest.split()))
    fails = 0
    for v in vectors:
        outs = {k: f(v) for k, f in runners.items()}
        same = len(set(outs.values())) == 1
        fails += not same
        print("%-4s %-60s %s" % ("ok" if same else "FAIL", " ".join(v)[:60], outs["python"] if same else outs))
    print("search parity: %d vectors x %d backends (%s): %s" % (len(vectors), len(runners), ",".join(runners),
                                                                "ALL MATCH" if not fails else "%d FAIL" % fails))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=os.path.join(C, "build"))
    ap.add_argument("--wasmtime", default="wasmtime")
    a = ap.parse_args()
    build = os.path.abspath(os.path.join(C, a.build) if not os.path.isabs(a.build) else a.build)
    os.environ["CHESSX_NATIVE_DIR"] = os.path.join(build, "native")
    assert hf.backend() == "native", "ctypes could not load libcx_hello_fusion from " + os.environ["CHESSX_NATIVE_DIR"]
    cli, wasm = os.path.join(build, "native", "hello_fusion_cli"), os.path.join(build, "wasm", "hello_fusion.wasm")
    runners = {
        "python": lambda v: py_run(v, hf.crc32_py, hf.fuse_py),
        "ctypes": lambda v: py_run(v, hf.crc32, hf.fuse),
        "native-cli": lambda v: subprocess.run([cli] + v, capture_output=True, text=True, check=True).stdout.strip(),
    }
    if shutil.which(a.wasmtime):
        runners["wasmtime"] = lambda v: subprocess.run([a.wasmtime, "run", wasm] + v,
                                                       capture_output=True, text=True, check=True).stdout.strip()
    else:
        print("WARN: wasmtime not found, wasm leg skipped"); 
    if shutil.which("wasmer"):
        runners["wasmer"] = lambda v: subprocess.run(["wasmer", "run", wasm, "--"] + v,
                                                     capture_output=True, text=True, check=True).stdout.strip()
    vectors = []
    for line in open(os.path.join(C, "hello_fusion", "vectors.txt"), encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            cmd, _, rest = line.rstrip("\n").partition(" ")
            vectors.append([cmd] + ([rest] if cmd == "crc" else rest.split()))
    fails = 0
    for v in vectors:
        outs = {k: f(v) for k, f in runners.items()}
        same = len(set(outs.values())) == 1
        fails += not same
        print("%-4s %-60s %s" % ("ok" if same else "FAIL", " ".join(v)[:60], outs["python"] if same else outs))
    print("parity: %d vectors x %d backends (%s): %s" % (len(vectors), len(runners), ",".join(runners),
                                                         "ALL MATCH" if not fails else "%d FAIL" % fails))
    if "wasmtime" in runners:  # reactor build exposes the C API as wasm exports (what web/ loads)
        r = os.path.join(build, "wasm", "hello_fusion.reactor.wasm")
        out = subprocess.run([a.wasmtime, "run", "--invoke", "cx_abi_version", r], capture_output=True, text=True)
        ok = out.stdout.strip().splitlines()[-1:] == ["1"]
        fails += not ok
        print("%-4s reactor export cx_abi_version() == 1" % ("ok" if ok else "FAIL"))
    fails += run_search(build, a.wasmtime)
    # known-answer checks
    assert hf.crc32_py(b"123456789") == 0xCBF43926
    import zlib
    assert all(hf.crc32(s) == zlib.crc32(s) for s in (b"", b"a", b"ChessX", bytes(range(256))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
