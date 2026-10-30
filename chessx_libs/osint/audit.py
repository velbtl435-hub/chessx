"""Append-only local audit log (JSON lines) of every OSINT query. Stays on disk, deletable."""
import json, os, threading
from .types import utcnow

REDACT_KEYS = ("password", "secret", "token", "hash")


class AuditLog:
    def __init__(self, path: str = None):
        if path is None:
            from .cache import default_dir
            os.makedirs(default_dir(), exist_ok=True)
            path = os.path.join(default_dir(), "audit.jsonl")
        self.path = path
        self._lock = threading.Lock()

    def log(self, action: str, **fields):
        rec = {"ts": utcnow(), "action": action}
        for k, v in fields.items():
            rec[k] = "<redacted>" if any(r in k.lower() for r in REDACT_KEYS) else v
        if self.path == ":memory:":
            self.records = getattr(self, "records", []) + [rec]
            return rec
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def read(self):
        if self.path == ":memory:":
            return list(getattr(self, "records", []))
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def clear(self):
        if self.path == ":memory:":
            self.records = []
        elif os.path.exists(self.path):
            os.remove(self.path)
