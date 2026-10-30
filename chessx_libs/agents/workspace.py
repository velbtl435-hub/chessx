"""Isolated workspace per agent: own dir (files/, materials/, logs/, tmp/), env, persisted state, cleanup policy.
Layout: <root>/<agent>/  and nested sub-agents at <root>/<agent>/sub/<child>/ (mode="nested") or
<root>/<agent>__<child>/ (mode="isolated")."""
import json, os, shutil, time

from .types import slug

POLICIES = ("keep", "on_success", "always", "ttl")


class Workspace:
    def __init__(self, root: str, name: str, parent: "Workspace" = None, mode: str = "nested",
                 cleanup: str = "keep", ttl: float = 86400):
        if cleanup not in POLICIES:
            raise ValueError("cleanup must be one of %s" % (POLICIES,))
        self.name, self.parent, self.mode, self.cleanup, self.ttl = slug(name, 64), parent, mode, cleanup, ttl
        if parent is None:
            self.path = os.path.join(os.path.abspath(root), self.name)
        elif mode == "nested":
            self.path = os.path.join(parent.path, "sub", self.name)
        else:
            self.path = os.path.join(os.path.dirname(parent.path), parent.name + "__" + self.name)
        for d in ("files", "materials", "logs", "tmp"):
            os.makedirs(os.path.join(self.path, d), exist_ok=True)
        self.children = []
        if parent:
            parent.children.append(self)

    # ---- files (confined to the workspace) ----------------------------
    def resolve(self, rel: str) -> str:
        p = os.path.realpath(os.path.join(self.path, "files", rel))
        if not p.startswith(os.path.realpath(os.path.join(self.path, "files")) + os.sep):
            raise PermissionError("path escapes workspace: " + rel)
        return p

    def write(self, rel, data):
        p = self.resolve(rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb" if isinstance(data, bytes) else "w") as fh:
            fh.write(data)
        return p

    def read(self, rel):
        with open(self.resolve(rel)) as fh:
            return fh.read()

    def add_material(self, src: str) -> str:
        dst = os.path.join(self.path, "materials", os.path.basename(src.rstrip("/")))
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
        return dst

    # ---- env / state / log --------------------------------------------
    def env(self, extra=None) -> dict:
        e = {"CHESSX_WORKSPACE": self.path, "HOME": self.path, "TMPDIR": os.path.join(self.path, "tmp")}
        e.update(self.state().get("env", {}))
        e.update(extra or {})
        return e

    def state(self) -> dict:
        p = os.path.join(self.path, "state.json")
        if not os.path.exists(p):
            return {}
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)

    def save_state(self, **kv):
        s = self.state(); s.update(kv); s["updated"] = time.time()
        tmp = os.path.join(self.path, "state.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(s, fh, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, os.path.join(self.path, "state.json"))

    def log(self, msg):
        with open(os.path.join(self.path, "logs", "agent.log"), "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))

    def child(self, name, mode=None, cleanup=None) -> "Workspace":
        return Workspace(None, name, self, mode or self.mode, cleanup or self.cleanup, self.ttl)

    # ---- cleanup ------------------------------------------------------
    def finish(self, success: bool):
        """Apply cleanup policy after a run. Returns True if removed."""
        self.save_state(last_success=success, finished=time.time())
        if self.cleanup == "always" or (self.cleanup == "on_success" and success):
            self.destroy(); return True
        return False

    def destroy(self):
        for c in self.children:
            if c.mode == "isolated":
                c.destroy()
        shutil.rmtree(self.path, ignore_errors=True)


def sweep(root: str, ttl: float, now: float = None) -> list:
    """Remove top-level workspaces whose state is older than ttl seconds (policy 'ttl')."""
    now, removed = now or time.time(), []
    if not os.path.isdir(root):
        return removed
    for n in os.listdir(root):
        p = os.path.join(root, n, "state.json")
        try:
            with open(p) as fh:
                s = json.load(fh)
        except (OSError, ValueError):
            continue
        if now - s.get("updated", now) > ttl:
            shutil.rmtree(os.path.join(root, n), ignore_errors=True); removed.append(n)
    return removed
