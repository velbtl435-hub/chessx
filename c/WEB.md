# Loading ChessX .wasm in the browser (for web/ — documentation only, web/ is not edited here)

Use the **reactor** build (`build/wasm/<mod>.reactor.wasm`, CI artifact `chessx-wasm`): no `main`,
only `CX_API` exports. Any WASI p1 imports (from libc) are satisfied by a tiny JS shim.

```bash
npm i @bjorn3/browser_wasi_shim      # in web/
cp c/build/wasm/hello_fusion.reactor.wasm web/public/wasm/
```

```ts
import { WASI, OpenFile, File, ConsoleStdout } from "@bjorn3/browser_wasi_shim";

export async function loadHelloFusion() {
  const wasi = new WASI([], [], [new OpenFile(new File([])), ConsoleStdout.lineBuffered(console.log),
                                 ConsoleStdout.lineBuffered(console.error)]);
  const { instance } = await WebAssembly.instantiateStreaming(fetch("/wasm/hello_fusion.reactor.wasm"),
                                                               { wasi_snapshot_preview1: wasi.wasiImport });
  wasi.initialize(instance as any);           // reactor: runs _initialize (libc ctors), not _start
  const x = instance.exports as any;
  const mem = () => new Uint8Array(x.memory.buffer);

  function crc32(bytes: Uint8Array): number {
    const p = x.cx_alloc(bytes.length); mem().set(bytes, p);
    const r = x.cx_crc32(p, bytes.length) >>> 0; x.cx_free(p); return r;
  }
  function fuse(pairs: [number, bigint][]): [number, bigint][] {
    const n = pairs.length, ids = x.cx_alloc(4 * n), sc = x.cx_alloc(8 * n), oi = x.cx_alloc(4 * n), os = x.cx_alloc(8 * n);
    const b = x.memory.buffer; const I = new Int32Array(b, ids, n), S = new BigInt64Array(b, sc, n);
    pairs.forEach(([i, s], k) => { I[k] = i; S[k] = s; });
    const m = x.cx_fuse(ids, sc, n, oi, os);
    const OI = new Int32Array(x.memory.buffer, oi, m), OS = new BigInt64Array(x.memory.buffer, os, m);
    const out = Array.from({ length: m }, (_, k) => [OI[k], OS[k]] as [number, bigint]);
    [ids, sc, oi, os].forEach(x.cx_free); return out;
  }
  return { crc32, fuse, abi: x.cx_abi_version() };
}
```

Notes: `int64_t` crosses the JS boundary as `BigInt`; re-create typed-array views after any call that
may grow memory; serve `.wasm` as `application/wasm` (Vercel does by default). Expected values:
`crc32("123456789") === 0xcbf43926`, `fuse([[1,10n],[2,5n],[1,3n],[3,7n]])` → `[[1,13n],[3,7n],[2,5n]]`.
Emscripten builds (`make emscripten`) instead ship their own JS glue (`cx_<mod>()` factory + `cwrap`).
