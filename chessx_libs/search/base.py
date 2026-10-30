"""Common search types + guarded HTTP helper (urllib, stdlib)."""
import json, urllib.request, urllib.error
from dataclasses import dataclass, field, asdict
from typing import List

UA = "Mozilla/5.0 (X11; Linux x86_64) ChessX/0.5"


@dataclass
class Result:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""
    score: float = 0.0
    engines: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class SearchError(Exception):
    pass


def http_get(url: str, headers: dict = None, timeout: float = 10.0, data: bytes = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, OSError) as e:
        raise SearchError(f"{url}: {e}") from e


def http_json(url: str, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8", "replace"))


class Engine:
    name = "base"

    def search(self, query: str, limit: int = 10) -> List[Result]:
        raise NotImplementedError

    def safe_search(self, query: str, limit: int = 10) -> List[Result]:
        """Never raises: returns [] on network/parse failure."""
        try:
            return self.search(query, limit)
        except Exception:
            return []

    @staticmethod
    def rank_score(i: int, n: int) -> float:
        return round(1.0 - i / max(n, 1), 3)
