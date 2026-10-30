"use client";
import { useCallback, useEffect, useRef, useState } from "react";

type R = { title: string; url: string; snippet: string; score: number; engines: string[] };
const PALETTE = ["var(--teal)", "var(--purple)", "var(--blue)", "var(--orange)"];
const PER_PAGE = 12;
const LOGO = String.raw`   _____ _                   __   __
  / ____| |                  \ \ / /     .::.
 | |    | |__   ___  ___ ___  \ V /      _::_
 | |    | '_ \ / _ \/ __/ __|  > <     _/____\_
 | |____| | | |  __/\__ \__ \ / . \    \      /
  \_____|_| |_|\___||___/___//_/ \_\    \____/  v0.6 web`;

export default function Page() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [res, setRes] = useState<R[]>([]);
  const [sel, setSel] = useState(0);
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState(false);
  const [status, setStatus] = useState("type a query and press Enter. press ? for help.");
  const [auto, setAuto] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const run = useCallback(async (term: string) => {
    if (!term) return;
    setStatus(`searching ${term} ...`);
    try {
      const d = await (await fetch(`/api/search?limit=30&q=${encodeURIComponent(term)}`)).json();
      setRes(d.results || []); setSel(0); setPage(0); setQuery(term);
      const errs = Object.entries(d.errors || {}).map(([k, v]) => `${k}: ${v}`).join(" | ");
      setStatus(`${(d.results || []).length} results @ ${new Date(d.at).toLocaleTimeString()}${errs ? "\n! " + errs : ""}`);
    } catch (e) { setStatus("error: " + (e as Error).message); }
  }, []);

  useEffect(() => {
    if (!auto || !query) return;
    const id = setInterval(() => run(query), auto * 1000);
    return () => clearInterval(id);
  }, [auto, query, run]);

  const pages = Math.max(1, Math.ceil(res.length / PER_PAGE));
  const view = res.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  const cur = view[sel];

  function save(fmt: "json" | "csv") {
    const body = fmt === "json" ? JSON.stringify(res, null, 1)
      : "title,url,score\n" + res.map(r => `"${r.title.replace(/"/g, "'")}",${r.url},${r.score.toFixed(3)}`).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([body], { type: fmt === "json" ? "application/json" : "text/csv" }));
    a.download = "chessx_results." + fmt; a.click();
  }

  useEffect(() => {
    let lastA = 0;
    function onKey(e: KeyboardEvent) {
      if (document.activeElement === input.current) {
        if (e.key === "Escape") input.current?.blur();
        return;
      }
      const n = view.length;
      const k = e.key;
      if (k === "/" || k === "i") { e.preventDefault(); input.current?.focus(); return; }
      if (k === "Tab" || k === "ArrowRight" || k === "l") { e.preventDefault(); if (n) setSel(s => (e.shiftKey ? (s - 1 + n) % n : (s + 1) % n)); }
      else if (k === "ArrowLeft" || k === "h") { if (n) setSel(s => (s - 1 + n) % n); }
      else if (k === "Enter") { if (cur) window.open(cur.url, "_blank", "noopener"); }
      else if (k === "d") setDetail(v => !v);
      else if (k === "n") { setPage(p => Math.min(p + 1, pages - 1)); setSel(0); }
      else if (k === "p") { setPage(p => Math.max(p - 1, 0)); setSel(0); }
      else if (k === "r") run(query);
      else if (k === "s") save(e.shiftKey ? "csv" : "json");
      else if (k === "a") {
        const now = Date.now();
        if (now - lastA < 500) { setAuto(0); setStatus("auto-refresh off"); }
        else { setAuto(30); setStatus("auto-refresh every 30s (aa = off)"); }
        lastA = now;
      } else if (k === "?") setStatus("keys: / search | Tab/←→ move | Enter open | d detail | n/p page | r refresh | a auto (aa off) | s json / S csv");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <main>
      <pre className="logo">{LOGO}</pre>
      <form className="prompt" onSubmit={e => { e.preventDefault(); run(q.trim()); input.current?.blur(); }}>
        <span>chessx&gt;</span>
        <input ref={input} autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="search the web..." aria-label="query" />
      </form>
      <div className="status">{status}{res.length ? <> {"  "}<b>page {page + 1}/{pages}</b>{auto ? `  auto:${auto}s` : ""}</> : null}</div>
      <div className="board">
        {view.map((r, i) => (
          <div key={r.url + i} className={"cell" + (i === sel ? " sel" : "")}
            style={{ ["--c" as string]: PALETTE[(i + Math.floor(i / 4)) % 4] }}
            onClick={() => setSel(i)} onDoubleClick={() => window.open(r.url, "_blank", "noopener")}>
            <span className="n">[{String(page * PER_PAGE + i + 1).padStart(2, "0")}] {"█".repeat(Math.max(1, Math.round(Math.min(r.score, 2) * 4)))}</span>
            <span className="t">{r.title.slice(0, 80) || r.url}</span>
            <span className="m">{r.engines.join(",")} {r.score.toFixed(2)}</span>
          </div>
        ))}
      </div>
      {detail && cur && <div className="detail">{`#${page * PER_PAGE + sel + 1} ${cur.title}\n${cur.url}\nengines: ${cur.engines.join(", ")}  score: ${cur.score.toFixed(3)}\n\n${cur.snippet}`}</div>}
      <div className="help"><kbd>/</kbd> search · <kbd>Tab</kbd>/<kbd>←→</kbd> move · <kbd>Enter</kbd> open · <kbd>d</kbd> detail · <kbd>n</kbd>/<kbd>p</kbd> page · <kbd>r</kbd> refresh · <kbd>a</kbd>/<kbd>aa</kbd> auto · <kbd>s</kbd>/<kbd>S</kbd> save json/csv</div>
    </main>
  );
}
