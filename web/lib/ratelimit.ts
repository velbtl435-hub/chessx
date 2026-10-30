// Per-IP sliding-window rate limit. Uses Upstash Redis / Vercel KV REST if configured, else in-memory.
const WINDOW_MS = Number(process.env.SEARCH_RATE_WINDOW_MS) || 60_000;
const MAX = Number(process.env.SEARCH_RATE_MAX) || 20;
const mem = new Map<string, number[]>();

export function clientIp(req: Request) {
  return (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || req.headers.get("x-real-ip") || "unknown";
}

async function redis(cmds: (string | number)[][]) {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  const r = await fetch(url.replace(/\/$/, "") + "/pipeline", {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(cmds), cache: "no-store", signal: AbortSignal.timeout(2000),
  });
  if (!r.ok) throw new Error("ratelimit store HTTP " + r.status);
  return (await r.json()) as { result: unknown }[];
}

export async function rateLimit(ip: string): Promise<{ ok: boolean; retryAfter: number }> {
  const now = Date.now(), key = `chessx:rl:search:${ip}`;
  try {
    const res = await redis([
      ["ZREMRANGEBYSCORE", key, 0, now - WINDOW_MS],
      ["ZADD", key, now, `${now}-${Math.random().toString(36).slice(2)}`],
      ["ZCARD", key],
      ["ZRANGE", key, 0, 0, "WITHSCORES"],
      ["PEXPIRE", key, WINDOW_MS],
    ]);
    if (res) {
      const count = Number(res[2].result), oldest = Number((res[3].result as string[])[1] ?? now);
      return count > MAX ? { ok: false, retryAfter: Math.ceil((oldest + WINDOW_MS - now) / 1000) } : { ok: true, retryAfter: 0 };
    }
  } catch { /* store down: fall back to memory */ }
  const hits = (mem.get(ip) || []).filter(t => t > now - WINDOW_MS);
  if (hits.length >= MAX) { mem.set(ip, hits); return { ok: false, retryAfter: Math.ceil((hits[0] + WINDOW_MS - now) / 1000) }; }
  hits.push(now); mem.set(ip, hits);
  if (mem.size > 10_000) for (const [k, v] of mem) if (!v.length || v[v.length - 1] < now - WINDOW_MS) mem.delete(k);
  return { ok: true, retryAfter: 0 };
}
