# chessx_libs/native (Team 1)
Python side of the C/WASI pipeline (`c/`). `load("<module>")` returns a `ctypes.CDLL` for
`libcx_<module>.so|.dylib|.dll` or `None`; every wrapper falls back to pure Python.

| Env | Effect |
|---|---|
| `CHESSX_NATIVE_DIR` | extra directory searched first |
| `CHESSX_NATIVE=0` | force pure-Python fallbacks |

Build the libs with `make -C c native`. Wrappers: `hello_fusion.crc32(data)`, `hello_fusion.fuse(pairs)`,
`hello_fusion.backend()`. Add one `<module>.py` wrapper per C module (see `c/README.md`).
