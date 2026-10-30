"""Exact-username lookups via OFFICIAL public APIs only (GitHub, Mastodon, Bluesky, Lichess, Chess.com).

Rules: one exact username per query, no fuzzy matching, no scraping, no private data, no follower/following
lists (only the public profile document). Every request goes through Client, so it is audited and rate limited.
"""
import re
from urllib.parse import quote, urlencode
from ..base import Source, SourceError, register
from ..types import Finding
from ..http import HTTPError

USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def check_username(u: str, allow_at=False) -> str:
    base, _, inst = u.partition("@")
    if not USERNAME.match(base) or (inst and not (allow_at and re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", inst.lower()))):
        raise SourceError("invalid username for exact lookup: %r" % u)
    return u


class ProfileSource(Source):
    accepts = frozenset({"username"})
    ttl = 86400
    rate = (1, 1.0)
    API = ""
    FIELDS = ()

    def fetch(self, username, client):
        raise NotImplementedError

    def profile(self, d) -> tuple:
        """-> (display title, public profile url, data dict)"""
        raise NotImplementedError

    def lookup(self, e, client):
        check_username(e.value, allow_at=self.name == "mastodon")
        try:
            d = self.fetch(e.value, client)
        except HTTPError as ex:
            if ex.status in (404, 400):  # not found (Bluesky answers 400 "Profile not found")
                return []
            raise
        if not d:
            return []
        title, url, data = self.profile(d)
        return [Finding(e, self.name, "profile", title, data, url, confidence=0.9)]

    def pick(self, d):
        return {k: d.get(k) for k in self.FIELDS if d.get(k) not in (None, "", [], {})}


@register
class GitHubProfile(ProfileSource):
    name = "github"
    host = "api.github.com"
    rate = (1, 2.0)   # unauthenticated limit: 60 requests/hour
    license = "GitHub REST API (public data, unauthenticated: 60 req/h)"
    FIELDS = ("login", "name", "company", "blog", "location", "bio", "public_repos", "created_at", "type")

    def fetch(self, u, client):
        return client.get_json("https://api.github.com/users/" + quote(u), source=self,
                               headers={"Accept": "application/vnd.github+json"})

    def profile(self, d):
        return "GitHub %s (%s)" % (d.get("login"), d.get("name") or "-"), d.get("html_url", ""), self.pick(d)


@register
class MastodonProfile(ProfileSource):
    name = "mastodon"
    host = "mastodon.social"
    license = "Mastodon public API (accounts/lookup), instance terms apply"
    INSTANCE = "https://mastodon.social"
    FIELDS = ("acct", "display_name", "created_at", "bot", "url")

    def fetch(self, u, client):
        return client.get_json(self.INSTANCE + "/api/v1/accounts/lookup?" + urlencode({"acct": u}), source=self)

    def profile(self, d):
        data = self.pick(d)
        if d.get("discoverable") is False or d.get("indexable") is False:
            data = {"acct": d.get("acct"), "opted_out_of_discovery": True}  # respect the user's choice
        else:
            data["note"] = re.sub(r"<[^>]+>", "", d.get("note", ""))[:280]
        return "Mastodon %s (%s)" % (d.get("acct"), d.get("display_name") or "-"), d.get("url", ""), data


@register
class BlueskyProfile(ProfileSource):
    name = "bluesky"
    host = "public.api.bsky.app"
    license = "Bluesky public AppView API"
    FIELDS = ("handle", "displayName", "did", "createdAt", "description")

    def fetch(self, u, client):
        handle = u if "." in u else u + ".bsky.social"
        return client.get_json("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?" +
                               urlencode({"actor": handle}), source=self)

    def profile(self, d):
        return ("Bluesky %s (%s)" % (d.get("handle"), d.get("displayName") or "-"),
                "https://bsky.app/profile/" + d.get("handle", ""), self.pick(d))


@register
class LichessProfile(ProfileSource):
    name = "lichess"
    host = "lichess.org"
    license = "Lichess public API (free, AGPL project; 1 request at a time)"
    FIELDS = ("username", "title", "createdAt", "seenAt", "disabled", "tosViolation")

    def fetch(self, u, client):
        return client.get_json("https://lichess.org/api/user/" + quote(u), source=self)

    def profile(self, d):
        data = self.pick(d)
        data["ratings"] = {k: v.get("rating") for k, v in (d.get("perfs") or {}).items() if isinstance(v, dict)
                           and v.get("games")}
        return ("Lichess %s%s" % ((d.get("title") + " ") if d.get("title") else "", d.get("username")),
                d.get("url") or "https://lichess.org/@/" + d.get("username", ""), data)


@register
class ChessComProfile(ProfileSource):
    name = "chesscom"
    host = "api.chess.com"
    license = "Chess.com Published-Data API (public, serial requests)"
    FIELDS = ("username", "name", "title", "location", "joined", "last_online", "status")

    def fetch(self, u, client):
        return client.get_json("https://api.chess.com/pub/player/" + quote(u.lower()), source=self)

    def profile(self, d):
        data = self.pick(d)
        if d.get("country"):
            data["country"] = d["country"].rsplit("/", 1)[-1]
        return ("Chess.com %s%s" % ((d.get("title") + " ") if d.get("title") else "", d.get("username")),
                d.get("url", ""), data)
