import { revalidateTag } from "next/cache";
import { getFeed } from "@/lib/feed";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.get("authorization") !== `Bearer ${secret}`)
    return Response.json({ error: "unauthorized" }, { status: 401 });
  revalidateTag("chessx-feed");
  const feed = await getFeed();
  return Response.json({ ok: true, refreshed: feed.map(f => ({ query: f.query, results: f.results.length, errors: f.errors })), at: new Date().toISOString() });
}
