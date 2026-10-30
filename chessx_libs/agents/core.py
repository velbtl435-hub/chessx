"""Recursive sub-agent tree: unbounded by default, but guarded (budget, cycle detection, kill switch)."""
import itertools, os, threading, time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

INF = float("inf")


class AgentLimitError(RuntimeError):
    """Raised when a spawn would break a guard (depth/count/budget/cycle/kill)."""


@dataclass
class Limits:
    """Soft limits. None = unlimited (bounded only by the guards below)."""
    max_depth: Optional[int] = None
    max_children: Optional[int] = None      # per agent
    max_total: Optional[int] = None         # per tree
    budget: float = INF                     # abstract cost units shared by the tree
    spawn_cost: float = 0.0
    min_free_mem_mb: int = 64               # resource guard: refuse spawn if machine is low on RAM
    max_spawn_rate: float = 1000.0          # spawns/second per tree (anti fork-bomb)


def free_mem_mb() -> Optional[int]:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


class Tree:
    """Shared state for one agent tree: counters, budget, kill switch, lineage."""

    def __init__(self, limits: Limits = None):
        self.limits = limits or Limits()
        self.lock = threading.RLock()
        self.total = 0
        self.spent = 0.0
        self.killed = threading.Event()
        self._ids = itertools.count(1)
        self._window = []  # spawn timestamps for rate limit
        self.agents: Dict[str, "Agent"] = {}

    def charge(self, cost: float):
        with self.lock:
            if self.spent + cost > self.limits.budget:
                raise AgentLimitError("budget exhausted (%.2f/%.2f)" % (self.spent, self.limits.budget))
            self.spent += cost

    def kill(self):
        self.killed.set()
        for a in list(self.agents.values()):
            a.state = "killed"


class Agent:
    """An agent with a role and an optional task. Can spawn sub-agents recursively."""

    def __init__(self, name: str, role: str = "generic", task: Callable = None, kind: str = None,
                 parent: "Agent" = None, tree: Tree = None, limits: Limits = None, meta: dict = None):
        self.name, self.role, self.task = name, role, task
        self.kind = kind or role
        self.parent = parent
        self.tree = tree or (parent.tree if parent else Tree(limits))
        self.depth = parent.depth + 1 if parent else 0
        self.children: List[Agent] = []
        self.meta = dict(meta or {})
        self.state = "idle"   # idle | running | done | error | off | killed
        self.log: List[tuple] = []
        self.inbox: List[tuple] = []
        self.result = None
        self.listeners: List[Callable] = []   # (agent, event, data) hooks, e.g. TamagóX
        with self.tree.lock:
            self.id = "%s#%d" % (name, next(self.tree._ids))
            self.tree.agents[self.id] = self

    # ---- lineage ------------------------------------------------------
    def lineage(self):
        a, out = self, []
        while a:
            out.append(a)
            a = a.parent
        return out

    def path(self):
        return "/".join(a.name for a in reversed(self.lineage()))

    def emit(self, event, data=None):
        self.log.append((time.time(), event, data))
        if len(self.log) > 2000:
            del self.log[:1000]
        for a in self.lineage():
            for fn in a.listeners:
                try:
                    fn(self, event, data)
                except Exception:
                    pass

    # ---- spawning -----------------------------------------------------
    def _check_spawn(self, kind):
        t, L = self.tree, self.tree.limits
        if t.killed.is_set() or self.state in ("killed", "off"):
            raise AgentLimitError("kill switch active")
        if L.max_depth is not None and self.depth + 1 > L.max_depth:
            raise AgentLimitError("max_depth %d reached" % L.max_depth)
        if L.max_children is not None and len(self.children) >= L.max_children:
            raise AgentLimitError("max_children %d reached" % L.max_children)
        if L.max_total is not None and t.total + 1 > L.max_total:
            raise AgentLimitError("max_total %d reached" % L.max_total)
        # cycle detection: same kind+task signature repeated in the ancestry = runaway recursion
        sig = kind
        if self.meta.get("no_cycles", True) and sum(1 for a in self.lineage() if a.kind == sig and a.meta.get("cycle_guard", True)) >= self.meta.get("cycle_repeat", 64):
            raise AgentLimitError("cycle detected: kind %r repeated in lineage" % sig)
        now = time.time()
        t._window = [x for x in t._window if now - x < 1.0]
        if len(t._window) >= L.max_spawn_rate:
            raise AgentLimitError("spawn rate limit (%s/s)" % L.max_spawn_rate)
        mem = free_mem_mb()
        if mem is not None and mem < L.min_free_mem_mb:
            raise AgentLimitError("low memory: %d MB free" % mem)
        t._window.append(now)

    def spawn(self, name: str, role: str = None, task: Callable = None, kind: str = None, **meta) -> "Agent":
        kind = kind or role or self.kind
        with self.tree.lock:
            self._check_spawn(kind)
            self.tree.charge(self.tree.limits.spawn_cost)
            child = Agent(name, role or self.role, task, kind, parent=self, meta={**{k: v for k, v in self.meta.items() if k.startswith("cycle")}, **meta})
            self.tree.total += 1
            self.children.append(child)
        self.emit("spawn", child.id)
        return child

    # ---- run ----------------------------------------------------------
    def run(self, *args, **kw):
        """Run own task (task(agent, *args)); task may call agent.spawn(...).run() recursively."""
        if self.tree.killed.is_set() or self.state in ("killed", "off"):
            raise AgentLimitError("kill switch active")
        self.state = "running"
        self.emit("start")
        try:
            self.result = self.task(self, *args, **kw) if self.task else None
            self.state = "done"
            self.emit("done", self.result)
        except AgentLimitError as e:
            self.state = "error"
            self.emit("limit", str(e))
            raise
        except Exception as e:
            self.state = "error"
            self.emit("error", "%s: %s" % (type(e).__name__, e))
            raise
        return self.result

    def send(self, other: "Agent", msg):
        other.inbox.append((self.id, msg))
        other.emit("message", msg)

    def turn_off(self):
        self.state = "off"
        for c in self.children:
            c.turn_off()

    def kill(self):
        """Kill this subtree (or the whole tree if called on the root)."""
        if self.parent is None:
            self.tree.kill()
        self.state = "killed"
        for c in self.children:
            c.kill()

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def render(self, indent=0):
        lines = ["%s%s [%s/%s] %s" % ("  " * indent, self.name, self.kind, self.state, "")]
        for c in self.children:
            lines.append(c.render(indent + 1))
        return "\n".join(l.rstrip() for l in lines)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "role": self.role, "kind": self.kind, "state": self.state,
                "depth": self.depth, "children": [c.to_dict() for c in self.children]}
