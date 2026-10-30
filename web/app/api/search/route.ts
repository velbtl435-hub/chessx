import { multiSearch } from "@/lib/search";
export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  const u = new URL(req.url);
  const q = (u.searchParams.get("q") || "").trim();
  if (!q) return Response.json({ error: "missing q" }, { status: 400 });
  const limit = Math.min(Number(u.searchParams.get("limit")) || 10, 30);
  return Response.json(await multiSearch(q, limit));
}
