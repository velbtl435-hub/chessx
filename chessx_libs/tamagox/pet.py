"""TamagóX: Tamagotchi-style pet bound to an agent. Stats (0-100) react to agent activity and decay over time.
Optional mode: on only when enabled (CHESSX_TAMAGOX=1 or tamagox.enable())."""
import json, os, time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict

_ENABLED = {"on": os.environ.get("CHESSX_TAMAGOX", "") in ("1", "on", "true")}

def enable(on=True): _ENABLED["on"] = bool(on)
def enabled(): return _ENABLED["on"]

clamp = lambda v: max(0.0, min(100.0, v))

# agent event -> stat deltas
REACTIONS = {
    "start":   {"energy": -3, "mood": +1},
    "done":    {"mood": +6, "xp": +10, "hunger": +4},
    "error":   {"mood": -10, "energy": -5},
    "limit":   {"mood": -4},
    "spawn":   {"mood": +2, "energy": -1, "xp": +2},   # gaining a sub-agent
    "message": {"mood": +3},
}
DECAY_PER_HOUR = {"energy": -2, "mood": -3, "hunger": +5}

FACES = {"happy": "(^o^)X", "ok": "(•‿•)X", "tired": "(-_-)zX", "hungry": "(°o°)X", "sad": "(╥_╥)X", "dead": "(x_x)X"}


@dataclass
class Pet:
    name: str
    agent: str = ""
    mood: float = 70.0
    energy: float = 80.0
    hunger: float = 20.0
    xp: float = 0.0
    alive: bool = True
    updated: float = field(default_factory=time.time)
    history: list = field(default_factory=list)

    @property
    def level(self): return 1 + int(self.xp // 100)

    def tick(self, now=None):
        now = now or time.time()
        h = max(0.0, (now - self.updated) / 3600.0)
        for k, d in DECAY_PER_HOUR.items():
            setattr(self, k, clamp(getattr(self, k) + d * h))
        self.updated = now
        if self.hunger >= 100 and self.energy <= 0:
            self.alive = False

    def apply(self, deltas: Dict[str, float], why=""):
        if not self.alive:
            return
        for k, d in deltas.items():
            setattr(self, k, getattr(self, k) + d if k == "xp" else clamp(getattr(self, k) + d))
        self.history = (self.history + [(time.time(), why)])[-50:]

    # user care actions
    def feed(self): self.apply({"hunger": -30, "mood": +5}, "feed")
    def play(self): self.apply({"mood": +15, "energy": -10, "hunger": +5}, "play")
    def sleep(self): self.apply({"energy": +40, "mood": +2}, "sleep")
    def revive(self): self.alive = True; self.mood = self.energy = 50.0; self.hunger = 50.0

    def status(self):
        if not self.alive: return "dead"
        if self.hunger > 80: return "hungry"
        if self.energy < 20: return "tired"
        if self.mood < 30: return "sad"
        return "happy" if self.mood > 75 else "ok"

    def render(self):
        bar = lambda v: "#" * int(v // 10) + "." * (10 - int(v // 10))
        return "%s %s Lv%d [%s]\n mood   %s %3d\n energy %s %3d\n hunger %s %3d" % (
            FACES[self.status()], self.name, self.level, self.status(),
            bar(self.mood), self.mood, bar(self.energy), self.energy, bar(self.hunger), self.hunger)

    def to_dict(self): return asdict(self)


class PetStore:
    """Persists pets as JSON (<dir>/<name>.json)."""
    def __init__(self, path): self.path = path; os.makedirs(path, exist_ok=True)
    def _p(self, n): return os.path.join(self.path, n + ".json")
    def exists(self, n): return os.path.exists(self._p(n))
    def load(self, n):
        with open(self._p(n), encoding="utf-8") as fh:
            p = Pet(**json.load(fh))
        p.tick(); return p
    def get(self, n, agent=""):
        return self.load(n) if self.exists(n) else Pet(n, agent or n)
    def save(self, p: Pet):
        tmp = self._p(p.name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(p.to_dict(), fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self._p(p.name))


def attach(agent, pet: Pet, store: PetStore = None, force=False) -> Callable:
    """Bind a pet to an agent tree: every event of the agent (or its sub-agents) moves the pet's stats.
    No-op unless TamagóX mode is on (or force=True). Returns the listener."""
    if not (force or enabled()):
        return None
    def on_event(a, event, data):
        d = REACTIONS.get(event)
        if d:
            pet.tick(); pet.apply(d, "%s:%s" % (a.name, event))
            if store: store.save(pet)
    agent.listeners.append(on_event)
    return on_event


# ---- media hooks (section 23.2/23.3): pluggable, filled by available backends ----
HOOKS: Dict[str, Callable] = {}

def hook(name):
    def deco(fn): HOOKS[name] = fn; return fn
    return deco

def act(pet: Pet, name: str, *args, **kw):
    """Run a TamagóX activity (play_audio, analyze_text, ...); playing makes the pet happier."""
    if name not in HOOKS:
        raise KeyError("no TamagóX hook %r (available: %s)" % (name, ", ".join(sorted(HOOKS))))
    out = HOOKS[name](*args, **kw)
    pet.apply({"mood": +4, "energy": -2, "xp": +3}, name)
    return out

@hook("analyze_text")
def _analyze_text(text):
    words = [w.lower() for w in text.split()]
    top = sorted(set(words), key=lambda w: (-words.count(w), w))[:5]
    return {"chars": len(text), "words": len(words), "lines": text.count("\n") + 1, "top": top}

@hook("play_audio")
def _play_audio(name="result"):
    from chessx_libs import sounds
    return sounds.play(name)

@hook("speak")
def _speak(text, dry_run=False):
    from chessx_libs import voice
    return voice.speak(text, dry_run=dry_run)
