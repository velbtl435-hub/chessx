"""SQLite response cache with per-entry TTL (stdlib only)."""
import os, sqlite3, threading, time


def default_dir() -> str:
    return os.environ.get("CHESSX_OSINT_DIR") or os.path.join(os.path.expanduser("~"), ".chessx", "osint")


class Cache:
    def __init__(self, path: str = None, clock=time.time):
        if path is None:
            os.makedirs(default_dir(), exist_ok=True)
            path = os.path.join(default_dir(), "cache.db")
        self.clock = clock
        self._lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB, expires REAL)")
        self.db.commit()

    def get(self, key: str, allow_stale: bool = False):
        with self._lock:
            row = self.db.execute("SELECT value, expires FROM cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        if row[1] < self.clock() and not allow_stale:
            return None
        return row[0]

    def set(self, key: str, value: bytes, ttl: float):
        with self._lock:
            self.db.execute("REPLACE INTO cache VALUES (?,?,?)", (key, value, self.clock() + ttl))
            self.db.commit()

    def purge(self, expired_only: bool = True) -> int:
        with self._lock:
            cur = self.db.execute("DELETE FROM cache WHERE expires < ?", (self.clock(),)) if expired_only \
                else self.db.execute("DELETE FROM cache")
            self.db.commit()
            return cur.rowcount

    def close(self):
        self.db.close()
