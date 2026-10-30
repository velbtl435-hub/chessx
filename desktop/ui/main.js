// xterm.js front end: bridges keystrokes <-> the ChessX sidecar running in a PTY (Rust side).
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const term = new Terminal({
  cursorBlink: true,
  fontFamily: '"DejaVu Sans Mono", Menlo, Consolas, monospace',
  fontSize: 14,
  theme: { background: "#0b0f0c", foreground: "#d8ffd8", cursor: "#39ff6a" },
});
const fit = new FitAddon.FitAddon();
term.loadAddon(fit);
term.open(document.getElementById("term"));
fit.fit();

(async () => {
  await listen("pty-data", (e) => term.write(e.payload));
  await listen("pty-exit", (e) => {
    term.write(`\r\n\x1b[33m[ChessX exited (${e.payload}). Close the window or press any key to restart]\x1b[0m\r\n`);
    const d = term.onData(() => { d.dispose(); term.reset(); start(); });
  });
  term.onData((data) => invoke("pty_write", { data }));
  window.addEventListener("resize", () => {
    fit.fit();
    invoke("pty_resize", { cols: term.cols, rows: term.rows });
  });
  start();
})();

function start() {
  invoke("pty_start", { cols: term.cols, rows: term.rows }).catch((err) =>
    term.write(`\r\n\x1b[31mFailed to start ChessX engine: ${err}\x1b[0m\r\n`)
  );
}
