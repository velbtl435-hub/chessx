import { multiSearch } from "@/lib/search";
import { clientIp, rateLimit } from "@/lib/ratelimit";
export const dynamic = "force-dynamic";
const MAX_Q = 200;
export async function GET(req: Request) {
  const u = new URL(req.url);
  const q = (u.searchParams.get("q") || "").trim();
  if (!q) return Response.json({ error: "missing q" }, { status: 400 });
  if (q.length > MAX_Q) return Response.json({ error: `q too long (max ${MAX_Q} chars)` }, { status: 400 });
  const rl = await rateLimit(clientIp(req));
  if (!rl.ok) return Response.json({ error: "rate limited" }, { status: 429, headers: { "Retry-After": String(Math.max(1, rl.retryAfter)) } });
  const limit = Math.min(Math.max(Number(u.searchParams.get("limit")) || 10, 1), 30);
  return Response.json(await multiSearch(q, limit));
}
