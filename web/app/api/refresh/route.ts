import { timingSafeEqual } from "node:crypto";
import { revalidateTag } from "next/cache";
import { getFeed } from "@/lib/feed";
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Constant-time compare; length checked first (timingSafeEqual throws on mismatch).
function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  // Fail closed: without CRON_SECRET the endpoint stays disabled.
  if (!secret) return Response.json({ error: "CRON_SECRET not configured" }, { status: 503 });
  if (!safeEqual(req.headers.get("authorization") ?? "", `Bearer ${secret}`))
    return Response.json({ error: "unauthorized" }, { status: 401 });
  revalidateTag("chessx-feed");
  const feed = await getFeed();
  return Response.json({ ok: true, refreshed: feed.map(f => ({ query: f.query, results: f.results.length, errors: f.errors })), at: new Date().toISOString() });
}
