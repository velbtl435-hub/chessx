// Copies xterm.js assets from node_modules into ui/vendor (no bundler needed).
import { cpSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "ui", "vendor");
mkdirSync(out, { recursive: true });
const files = [
  ["@xterm/xterm/lib/xterm.js", "xterm.js"],
  ["@xterm/xterm/css/xterm.css", "xterm.css"],
  ["@xterm/addon-fit/lib/addon-fit.js", "addon-fit.js"],
];
for (const [src, dst] of files) cpSync(join(root, "node_modules", src), join(out, dst));
console.log("xterm vendor files copied to ui/vendor");
