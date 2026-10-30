"use client";
import { useState } from "react";
type R = { title: string; url: string; score: number; engines: string[] };
export default function Page() {
  const [q, setQ] = useState(""); const [res, setRes] = useState<R[]>([]);
  async function go(e: React.FormEvent) { e.preventDefault(); const d = await (await fetch("/api/search?q=" + encodeURIComponent(q))).json(); setRes(d.results || []); }
  return (<main style={{ fontFamily: "monospace", padding: 16 }}>
    <h1>ChessX v0.6 web</h1>
    <form onSubmit={go}><input value={q} onChange={e => setQ(e.target.value)} placeholder="search..." /> <button>go</button></form>
    <ol>{res.map(r => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> [{r.engines.join(",")} {r.score.toFixed(2)}]</li>)}</ol>
  </main>);
}
