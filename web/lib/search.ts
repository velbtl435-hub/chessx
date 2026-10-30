// TS port of chessx_libs/search (engines + fusion by normalized URL).
export type Result = { title: string; url: string; snippet: string; engine: string; score: number; engines: string[] };

const UA = "Mozilla/5.0 (X11; Linux x86_64) ChessX/0.6-web";
const AGREEMENT_BONUS = 0.25;
const rank = (i: number, n: number) => Math.round((1 - i / Math.max(n, 1)) * 1000) / 1000;
const clean = (s: string) =>
  s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'")
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();

async function get(url: string, headers: Record<string, string> = {}) {
  const r = await fetch(url, { headers: { "User-Agent": UA, ...headers }, signal: AbortSignal.timeout(8000), cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r;
}

export async function duckduckgo(q: string, limit: number): Promise<Result[]> {
  const page = await (await get("https://html.duckduckgo.com/html/?q=" + encodeURIComponent(q), { "Accept-Language": "en-US,en;q=0.8" })).text();
  if (/anomaly|bot challenge/i.test(page) && !/result__a/.test(page)) throw new Error("duckduckgo anti-bot page");
  const links = [...page.matchAll(/<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g)];
  const snips = [...page.matchAll(/class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)<\/(?:a|div|td)>/g)];
  return links.slice(0, limit).map((m, i) => {
    let url = m[1];
    try { url = new URL(url, "https://duckduckgo.com").searchParams.get("uddg") || url; } catch {}
    if (url.startsWith("//")) url = "https:" + url;
    return { title: clean(m[2]), url, snippet: snips[i] ? clean(snips[i][1]) : "", engine: "duckduckgo", score: rank(i, limit), engines: [] };
  });
}

export async function brave(q: string, limit: number): Promise<Result[]> {
  const key = process.env.BRAVE_API_KEY;
  if (!key) throw new Error("BRAVE_API_KEY not set");
  const d = await (await get(`https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(q)}&count=${Math.min(limit, 20)}`,
    { Accept: "application/json", "X-Subscription-Token": key })).json();
  const items: any[] = (d?.web?.results || []).slice(0, limit);
  return items.map((r, i) => ({ title: clean(r.title || ""), url: r.url || "", snippet: clean(r.description || ""), engine: "brave", score: rank(i, items.length), engines: [] }));
}

export async function searxng(q: string, limit: number): Promise<Result[]> {
  const base = process.env.SEARXNG_URL;
  if (!base) throw new Error("SEARXNG_URL not set");
  const d = await (await get(`${base.replace(/\/$/, "")}/search?q=${encodeURIComponent(q)}&format=json`)).json();
  const rows: any[] = (d?.results || []).slice(0, limit);
  return rows.map((r, i) => ({ title: clean(r.title || ""), url: r.url || "", snippet: clean(r.content || ""), engine: "searxng", score: Number(r.score) || rank(i, rows.length), engines: [] }));
}

export async function mock(q: string, limit: number): Promise<Result[]> {
  const seeds = ["https://example.com/a", "https://example.org/b", "https://example.net/c"].slice(0, limit);
  return seeds.map((u, i) => ({ title: `${q} - ${u.split("/").pop()}`, url: u, snippet: `mock result for ${q}`, engine: "mock", score: rank(i, seeds.length), engines: [] }));
}

export function normUrl(u: string) {
  try { const p = new URL(u); return p.host.toLowerCase().replace(/^www\./, "") + p.pathname.replace(/\/$/, "") + p.search; } catch { return u; }
}

export function fuse(lists: Result[][]): Result[] {
  const m = new Map<string, Result>();
  for (const list of lists) for (const r of list) {
    const k = normUrl(r.url), e = m.get(k);
    if (e) { e.score += r.score + AGREEMENT_BONUS; if (!e.engines.includes(r.engine)) e.engines.push(r.engine); if (r.snippet.length > e.snippet.length) e.snippet = r.snippet; }
    else m.set(k, { ...r, engines: [r.engine] });
  }
  return [...m.values()].sort((a, b) => b.score - a.score);
}

const ENGINES = { duckduckgo, brave, searxng, mock } as const;
export type EngineName = keyof typeof ENGINES;

export async function multiSearch(q: string, limit = 10, names?: EngineName[]) {
  const use = names || (["duckduckgo", "brave", "searxng"] as EngineName[]);
  const errors: Record<string, string> = {};
  const lists = await Promise.all(use.map(n => ENGINES[n](q, limit).catch((e: Error) => { errors[n] = e.message; return [] as Result[]; })));
  let results = fuse(lists);
  if (!results.length && !names) results = fuse([await mock(q, limit)]), (errors.fallback = "all engines failed, showing mock");
  return { query: q, results: results.slice(0, limit), errors, at: new Date().toISOString() };
}
