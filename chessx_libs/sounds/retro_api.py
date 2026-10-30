"""Convenience API over the retro.* events (master list section 27).

    list_retro(chip=None)  -> {chip: {"sfx": [...], "music": [...]}}  or  {"sfx": [...], "music": [...]}
    render_retro(chip, name, **kw) -> np.ndarray (mono float, peak <= 0.89)
    play_retro(chip, name, **kw)   -> player name or "noop"  (same contract as play())

`name` is an sfx ('coin') or music ('music.battle'); kw e.g. seed, loops, loop, bars, rate.
Unknown chip/name -> UnknownSound (KeyError) listing valid chips / names for that chip.
Without numpy: list_retro() returns {} and render_retro/play_retro raise MissingDependency.
"""
from ._deps import MissingDependency
from ._errors import UnknownSound


def _events():
    try:
        from . import events
        from . import retro  # noqa: F401  (numpy needed)
    except (MissingDependency, ImportError) as e:
        raise MissingDependency("retro sounds need numpy: pip install numpy") from e
    return events


def _listing(events):
    out = {}
    for n in events.list_events("retro"):
        _, chip, rest = n.split(".", 2)
        d = out.setdefault(chip, {"sfx": [], "music": []})
        (d["music"] if rest.startswith("music.") else d["sfx"]).append(rest)
    return out


def list_retro(chip=None):
    try:
        listing = _listing(_events())
    except MissingDependency:
        return {}
    if chip is None:
        return listing
    if chip not in listing:
        raise UnknownSound(f"unknown retro chip {chip!r}; valid chips: {sorted(listing)}")
    return listing[chip]


def _resolve(chip, name):
    events = _events()
    listing = _listing(events)
    if chip not in listing:
        raise UnknownSound(f"unknown retro chip {chip!r}; valid chips: {sorted(listing)}")
    names = listing[chip]["sfx"] + listing[chip]["music"]
    if name not in names:
        raise UnknownSound(f"unknown retro sound {name!r} for chip {chip!r}; valid names: {names}")
    return events, f"retro.{chip}.{name}"


def render_retro(chip, name, **kw):
    events, ev = _resolve(chip, name)
    return events.render(ev, **kw)


def play_retro(chip, name, **kw):
    events, ev = _resolve(chip, name)
    return events.play(ev, **kw)
