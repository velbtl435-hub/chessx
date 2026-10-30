"""Agent Factory: build agents from prompt, sub-prompts, script, code, materials (files) and links.
Definitions are persisted as JSON in <home>/definitions/<name>.json (home = $CHESSX_AGENTS_HOME or ~/.chessx/agents)."""
import json, os, subprocess, sys, time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .core import Agent, Limits
from .types import Registry, slug
from .workspace import Workspace


def home() -> str:
    return os.environ.get("CHESSX_AGENTS_HOME") or os.path.join(os.path.expanduser("~"), ".chessx", "agents")


@dataclass
class AgentDefinition:
    name: str
    type: str = "researcher"
    prompt: str = ""
    sub_prompts: List[str] = field(default_factory=list)   # each becomes a sub-agent
    script: str = ""            # shell script, runs inside the agent workspace
    code: str = ""              # python code, runs inside the agent workspace
    materials: List[str] = field(default_factory=list)     # file paths copied into workspace/materials
    links: List[str] = field(default_factory=list)
    limits: Dict = field(default_factory=dict)             # Limits fields
    timeout: float = 60.0
    workspace: Dict = field(default_factory=lambda: {"mode": "nested", "cleanup": "keep"})
    env: Dict[str, str] = field(default_factory=dict)
    created: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def validate(self, registry: Registry = None):
        errs = []
        if not self.name or slug(self.name) != self.name:
            errs.append("name must be a slug (a-z0-9_): %r" % self.name)
        if registry and self.type not in registry.types:
            errs.append("unknown type %r" % self.type)
        for m in self.materials:
            if not os.path.exists(m):
                errs.append("material not found: " + m)
        for l in self.links:
            if not l.startswith(("http://", "https://")):
                errs.append("link must be http(s): " + l)
        return errs


def run_payload(defn: AgentDefinition, cwd: str, env: dict = None) -> dict:
    """Run script/code of a definition in cwd with a timeout. Returns outputs."""
    out = {}
    e = dict(os.environ, **(env or {}), **defn.env, CHESSX_AGENT=defn.name)
    for kind, cmd in (("script", ["bash", "-c", defn.script]), ("code", [sys.executable, "-c", defn.code])):
        if not getattr(defn, kind):
            continue
        try:
            p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=defn.timeout)
            out[kind] = {"rc": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-4000:]}
        except subprocess.TimeoutExpired:
            out[kind] = {"rc": -1, "stdout": "", "stderr": "timeout after %ss" % defn.timeout}
    return out


class Factory:
    def __init__(self, root: str = None, registry: Registry = None):
        self.root = root or home()
        self.defs_dir = os.path.join(self.root, "definitions")
        os.makedirs(self.defs_dir, exist_ok=True)
        self.registry = registry or Registry(os.path.join(self.root, "types.json"))

    # ---- persistence --------------------------------------------------
    def _path(self, name):
        return os.path.join(self.defs_dir, slug(name) + ".json")

    def create(self, overwrite=False, **fields) -> AgentDefinition:
        fields["name"] = slug(fields.get("name", "agent"))
        d = AgentDefinition.from_dict(fields)
        errs = d.validate(self.registry)
        if errs:
            raise ValueError("; ".join(errs))
        if os.path.exists(self._path(d.name)) and not overwrite:
            raise FileExistsError("agent exists: " + d.name)
        self.save(d)
        return d

    def save(self, d: AgentDefinition):
        tmp = self._path(d.name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d.to_dict(), fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self._path(d.name))

    def load(self, name) -> AgentDefinition:
        with open(self._path(name), encoding="utf-8") as fh:
            return AgentDefinition.from_dict(json.load(fh))

    def list(self) -> List[str]:
        return sorted(f[:-5] for f in os.listdir(self.defs_dir) if f.endswith(".json"))

    def delete(self, name):
        os.remove(self._path(name))

    def import_file(self, path) -> AgentDefinition:
        with open(path, encoding="utf-8") as fh:
            return self.create(overwrite=True, **json.load(fh))

    # ---- build / run --------------------------------------------------
    def workspace_for(self, d: AgentDefinition, parent_ws: Workspace = None) -> Workspace:
        w = d.workspace or {}
        if parent_ws is not None:
            return parent_ws.child(d.name, w.get("mode"), w.get("cleanup"))
        return Workspace(os.path.join(self.root, "workspaces"), d.name, mode=w.get("mode", "nested"),
                         cleanup=w.get("cleanup", "keep"), ttl=w.get("ttl", 86400))

    def build(self, name_or_def, parent: Agent = None, workdir: str = None) -> Agent:
        """Turn a definition into a live Agent tree (sub-prompts -> sub-agents)."""
        d = name_or_def if isinstance(name_or_def, AgentDefinition) else self.load(name_or_def)
        t = self.registry.resolve(d.type)
        meta = {"definition": d.to_dict(), "capabilities": t["capabilities"],
                "prompt": "\n".join(x for x in (t.get("prompt", ""), d.prompt) if x), "links": d.links}
        ws = None if workdir else self.workspace_for(d, parent.meta.get("workspace") if parent else None)
        if ws:
            for m in d.materials:
                if not os.path.exists(os.path.join(ws.path, "materials", os.path.basename(m))):
                    ws.add_material(m)
            ws.save_state(definition=d.name, links=d.links)
        meta["workspace"] = ws

        def task(agent):
            wd = workdir or os.path.join(ws.path, "files")
            ok = False
            try:
                res = {"prompt": agent.meta["prompt"], "links": d.links, "workspace": ws.path if ws else wd,
                       "payload": run_payload(d, wd, ws.env() if ws else None)}
                res["sub"] = [c.run() for c in agent.children]
                ok = all(p["rc"] == 0 for p in res["payload"].values())
                if ws:
                    ws.log("run ok=%s" % ok); ws.save_state(last_result=res)
                return res
            finally:
                if ws:
                    ws.finish(ok)

        if parent is None:
            a = Agent(d.name, t.get("role", d.type), task, d.type, limits=Limits(**d.limits), meta=meta)
        else:
            a = parent.spawn(d.name, t.get("role", d.type), task, d.type, **meta)
        for i, sp in enumerate(d.sub_prompts):
            sub = "%s_sub%d" % (d.name, i + 1)
            sws = ws.child(sub) if ws else None
            if sws:
                sws.write("prompt.txt", sp)
            a.spawn(sub, task=lambda ag: {"prompt": ag.meta["prompt"], "workspace": ag.meta["workspace"].path if ag.meta["workspace"] else None},
                    kind=d.type + "_sub", prompt=sp, parent_prompt=meta["prompt"], workspace=sws)
        return a

    def run(self, name, workdir: str = None) -> dict:
        return self.build(name, workdir=workdir).run()
