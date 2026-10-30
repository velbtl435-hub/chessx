"""Build-origin hints: which compiler/toolchain/packer produced a binary or script."""
import re
from .strings import extract_strings

SIGNATURES = [
    (r"GCC: \(([^)]*)\) ?([\d.]+)?", "GCC"), (r"clang version ([\d.]+)", "Clang/LLVM"),
    (r"Go build ID|go1\.\d+", "Go"), (r"rustc[ /-]?([\d.]+)?|/rustc/", "Rust"),
    (r"PyInstaller|_MEIPASS", "PyInstaller"), (r"Nuitka", "Nuitka"), (r"UPX!", "UPX packer"),
    (r"Microsoft \(R\) C/C\+\+|MSVCRT|VCRUNTIME", "MSVC"), (r"mingw", "MinGW"),
    (r"Electron/|electron\.asar", "Electron"), (r"\.NET Framework|mscoree\.dll", ".NET"),
    (r"Delphi|Borland", "Delphi/Borland"), (r"__pyarmor__", "PyArmor"),
    (r"javac|Created-By:", "Java"), (r"webpack|__webpack_require__", "webpack (JS)"),
]


def origin_hints(data: bytes) -> list:
    text = "\n".join(extract_strings(data, 4))
    hits = []
    for pat, name in SIGNATURES:
        m = re.search(pat, text, re.I)
        if m:
            hits.append({"toolchain": name, "evidence": m.group(0)[:80]})
    return hits
