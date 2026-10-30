# ChessX C / WASI pipeline (`c/`) — PRIORITY #23, master list section 25

The same C sources build as a **native shared library** (called from Python via ctypes)
and as **wasm32-wasi** (run by wasmtime/wasmer, or in the browser through a WASI shim).
Pure Python stays as the fallback, so ChessX never *requires* a compiler.

```
c/
  Makefile            build system (all modules auto-discovered)
  include/chessx.h    shared header: CX_API export macro, ABI version, cx_alloc/cx_free
  common/             code linked into every module (cx_common.c)
  hello_fusion/       proof module: CRC-32 + (id, score) dedupe/fusion   <- copy this layout
    hello_fusion.h    public API (CX_API on every exported function)
    src/*.c           library sources (no main)
    cli.c             optional WASI/native CLI (main) used by parity tests
    vectors.txt       shared test vectors
  search/             (empty) Search Engineer: ranking/fusion/dedupe core
  capstone/           (empty) Reversing Engineer: capstone -> wasm
  audio/              (empty) audio DSP kernel (section 24/27)
  tests/run_parity.py native CLI = wasmtime = wasmer = ctypes = pure Python
  WEB.md              how web/ loads the .wasm in the browser
```

## Toolchain (installed on the shared box 10/30/2026, same versions in CI)
| Tool | Version | Install |
|---|---|---|
| gcc (native) | Debian 13 system gcc | `apt install build-essential` |
| wasi-sdk | **34.0** (clang 23.1.0-wasi-sdk), target `wasm32-wasip1` | `curl -LO https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-34/wasi-sdk-34.0-x86_64-linux.tar.gz && sudo tar xzf wasi-sdk-34.0-x86_64-linux.tar.gz -C /opt && sudo ln -sfn /opt/wasi-sdk-34.0-x86_64-linux /opt/wasi-sdk` |
| wasmtime | **50.0.1** | `curl -LO https://github.com/bytecodealliance/wasmtime/releases/download/v50.0.1/wasmtime-v50.0.1-x86_64-linux.tar.xz && tar xJf wasmtime-*.tar.xz && sudo cp wasmtime-v50.0.1-x86_64-linux/wasmtime /usr/local/bin/` |
| wasmer (optional) | **7.5.0** | `curl -LO https://github.com/wasmerio/wasmer/releases/download/v7.5.0/wasmer-linux-amd64.tar.gz && mkdir wm && tar xzf wasmer-linux-amd64.tar.gz -C wm && sudo cp wm/bin/wasmer /usr/local/bin/` |
| emscripten (optional) | not installed (≈1 GB; WASI covers the current needs) | `git clone https://github.com/emscripten-core/emsdk && cd emsdk && ./emsdk install latest && ./emsdk activate latest && source emsdk_env.sh` |
| wasm-opt (optional) | not installed; `make size` uses it if present | `apt install binaryen` |

`wasm32-wasi` was renamed `wasm32-wasip1` in recent wasi-sdk; override with `make WASI_TARGET=...`.
Other paths: `make WASI_SDK=/path/to/wasi-sdk CC=clang`.

## Targets
| Command | Output |
|---|---|
| `make native` | `build/native/libcx_<mod>.so` (+ `<mod>_cli`). On macOS `.dylib`, on Windows (MSYS2/mingw `make`) `.dll`: picked automatically |
| `make wasm` | `build/wasm/<mod>.wasm` (WASI command, `_start` = `cli.c`) and `build/wasm/<mod>.reactor.wasm` (no `main`, exports only: for the browser / embedding) |
| `make emscripten` | `build/emscripten/<mod>.js` + `.wasm` (MODULARIZE, `ccall`/`cwrap`); errors clearly if `emcc` is missing |
| `make test` | builds all, runs `tests/run_parity.py` |
| `make size` | byte size per .wasm (+ `wasm-opt -Oz` size if installed) |
| `make list` / `make clean` | discovered modules / remove `build/` |

Python side: `chessx_libs/native` (`load("<mod>")` → ctypes or `None`), unit tests in `tests/test_native.py`.

## Adding a module (Search: `c/search/`, Reversing: `c/capstone/`)
1. Put the library sources in `c/<mod>/src/*.c` (no `main`). The Makefile picks the module up as soon as
   `src/` has a `.c`; nothing to register.
2. Public header `c/<mod>/<mod>.h`: `#include "chessx.h"` and mark **every exported function**
   `CX_API(name) ret name(args);` (the macro sets `export_name` on wasm, `dllexport` on Windows,
   default visibility on ELF/Mach-O; everything else stays hidden).
3. ABI rules so native == wasm: fixed-width ints (`int32_t`, `int64_t`, `uint8_t*` + `size_t` len),
   caller-owned output buffers, no global mutable state, no floats in anything you compare bit-for-bit
   (or compare with a tolerance), signed overflow done through `uint64_t` (C UB otherwise),
   no threads/sockets/filesystem in the core (WASI p1 sandbox). JS hosts allocate with `cx_alloc`/`cx_free`.
4. Optional `c/<mod>/cli.c` with `main()` → also gives `build/wasm/<mod>.wasm` runnable by `wasmtime run`.
5. `c/<mod>/vectors.txt` + a block in `tests/run_parity.py` (or your own `c/tests/run_<mod>.py`,
   then add it to the `test:` target) comparing native, wasm and your pure-Python fallback.
6. Python wrapper `chessx_libs/native/<mod>.py` using `from . import load`; keep the pure-Python
   path and call it when `load()` returns `None`. Add `tests/test_native_<mod>.py`.
7. **capstone specifically:** vendor capstone as a git submodule or tarball under `c/capstone/vendor/`,
   build only the needed archs (`CAPSTONE_ARCHS=x86 arm aarch64`, `CAPSTONE_USE_SYS_DYN_MEM=1`) and add
   its sources to `src/` via a small `c/capstone/src/cx_capstone.c` wrapper exposing `CX_API` functions.
   If it needs extra flags, add a `c/capstone/module.mk` and an `-include */module.mk` line (ask Coder).
   Desktop keeps the native capstone Python binding (`reversing/disasm.py`).
8. Run `make -C c test` and `python3 -m unittest discover tests`; CI (`.github/workflows/c-wasm.yml`)
   runs both and uploads `build/wasm/*.wasm` as the `chessx-wasm` artifact.
