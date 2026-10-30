// Node check of the WEB.md browser recipe: node c/tests/js_shim_test.mjs (needs npm i @bjorn3/browser_wasi_shim)
import { WASI, OpenFile, File, ConsoleStdout } from "@bjorn3/browser_wasi_shim";
import fs from "fs";
const wasi = new WASI([], [], [new OpenFile(new File([])), ConsoleStdout.lineBuffered(console.log), ConsoleStdout.lineBuffered(console.error)]);
const { instance } = await WebAssembly.instantiate(fs.readFileSync(process.argv[2] || new URL("../build/wasm/hello_fusion.reactor.wasm", import.meta.url)), { wasi_snapshot_preview1: wasi.wasiImport });
wasi.initialize(instance);
const x = instance.exports; const mem = () => new Uint8Array(x.memory.buffer);
function crc32(bytes){const p=x.cx_alloc(bytes.length);mem().set(bytes,p);const r=x.cx_crc32(p,bytes.length)>>>0;x.cx_free(p);return r;}
function fuse(pairs){const n=pairs.length,ids=x.cx_alloc(4*n),sc=x.cx_alloc(8*n),oi=x.cx_alloc(4*n),os=x.cx_alloc(8*n);
const b=x.memory.buffer;const I=new Int32Array(b,ids,n),S=new BigInt64Array(b,sc,n);pairs.forEach(([i,s],k)=>{I[k]=i;S[k]=s;});
const m=x.cx_fuse(ids,sc,n,oi,os);const OI=new Int32Array(x.memory.buffer,oi,m),OS=new BigInt64Array(x.memory.buffer,os,m);
const out=Array.from({length:m},(_,k)=>[OI[k],OS[k]]);[ids,sc,oi,os].forEach(x.cx_free);return out;}
console.log(x.cx_abi_version(), crc32(new TextEncoder().encode("123456789")).toString(16), JSON.stringify(fuse([[1,10n],[2,5n],[1,3n],[3,7n]]),(k,v)=>typeof v==="bigint"?v.toString():v));
const got = crc32(new TextEncoder().encode("123456789")) >>> 0, f = fuse([[1,10n],[2,5n],[1,3n],[3,7n]]);
if (x.cx_abi_version() !== 1 || got !== 0xcbf43926 || JSON.stringify(f, (k, v) => typeof v === "bigint" ? Number(v) : v) !== "[[1,13],[3,7],[2,5]]") {
  console.error("JS shim parity FAIL"); process.exit(1);
}
console.log("JS shim parity ok");
