import { getFeed } from "@/lib/feed";
export const dynamic = "force-dynamic";
export async function GET() {
  return Response.json({ feed: await getFeed() });
}
