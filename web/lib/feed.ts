import { unstable_cache } from "next/cache";
import { multiSearch } from "./search";

// Default "board" queries refreshed by the cron (override with CHESSX_FEED_QUERIES="a,b,c").
export const FEED_QUERIES = (process.env.CHESSX_FEED_QUERIES || "chess news,tech news,open source ai")
  .split(",").map(s => s.trim()).filter(Boolean);

export const getFeed = unstable_cache(
  async () => Promise.all(FEED_QUERIES.map(q => multiSearch(q, 8))),
  ["chessx-feed"],
  { tags: ["chessx-feed"], revalidate: 86400 },
);
