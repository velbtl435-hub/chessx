"""Game SFX recipes rendered on any chip: retro.<chip>.<sfx>.

Recipes are chip-agnostic segment lists; chip-specific voice keys (duty, shape, table, algorithm...)
are added per chip via VOICE. Output is era-crushed (8bit: 4-bit/11 kHz, 16bit: 12-bit, 32bit: clean)
and normalized to <= 0.89 so it never clips. Deterministic for a given seed."""
from .._deps import need_numpy
from .. import dsp
from .chips import chip
from .crush import era_crush

T, N, R = "tone", "noise", "rest"


def _s(wave, f0, dur, f1=None, **kw):
    d = {"wave": wave, "f0": f0, "dur": dur, **kw}
    if f1:
        d["f1"] = f1
    return d


RECIPES = {
    "coin": [_s(T, 988, .06, decay=.2), _s(T, 1319, .22, decay=.08)],
    "jump": [_s(T, 220, .22, 880, env=(.002, .05, .6, .05))],
    "hit": [_s(N, 1200, .12, 200, decay=.04), _s(T, 160, .08, 60, decay=.03)],
    "powerup": [_s(T, 262, .5, 1047, arp=[0, 4, 7, 12], arp_hz=30, env=(.002, .1, .7, .1))],
    "1up": [_s(T, f, .07, env=(.002, .02, .8, .02)) for f in (659, 784, 1319, 1047, 1175, 1568)],
    "select": [_s(T, 1568, .04, decay=.02), _s(T, 2093, .05, decay=.03)],
    "game_over": [_s(T, f, d, env=(.005, .05, .7, .08)) for f, d in ((523, .2), (392, .2), (330, .25), (262, .5))],
    "laser": [_s(T, 2400, .25, 180, decay=.12, vib=.02, vib_hz=40)],
    "explosion": [_s(N, 3000, .7, 60, decay=.22)],
    "level_complete": [_s(T, f, d, env=(.002, .05, .8, .05)) for f, d in
                       ((523, .1), (659, .1), (784, .1), (1047, .15), (R and 0, .05), (784, .1), (1047, .4))],
    "chess_move": [_s(N, 2500, .03, 800, decay=.01), _s(T, 196, .08, decay=.03)],
    "chess_capture": [_s(N, 4000, .06, 500, decay=.02), _s(T, 147, .12, 98, decay=.05)],
    "chess_check": [_s(T, 880, .08, decay=.05), _s(R, 0, .04), _s(T, 880, .12, decay=.08)],
    "chess_mate": [_s(T, f, .14, env=(.002, .05, .7, .05)) for f in (523, 466, 392)] + [_s(T, 262, .5, decay=.25)],
}
RECIPES["level_complete"][4] = _s(R, 0, .05)

VOICE = {  # chip -> extra segment keys for tone segments
    "nes": {"voice": "pulse", "duty": 0.25}, "gb": {"voice": "pulse", "duty": 0.5},
    "sid": {"shape": "pulse", "pw": 0.4, "pwm": 0.1, "env": (.002, .06, .6, .06)},
    "ay": {}, "sn": {}, "fm": {"algorithm": 4, "feedback": 0.6}, "opl": {"ws": 0},
    "snes": {"table": "brass"}, "ps1": {"table": "pad"},
}
SPECIAL = {  # chip-specific flavour per sfx
    ("sid", "laser"): {"shape": "saw", "sync": 1.7},
    ("sid", "explosion"): {"filter": {"from": 4000, "to": 200, "res": 0.7}},
    ("fm", "laser"): {"algorithm": 0, "feedback": 1.2},
    ("ay", "powerup"): {"hw_env": "tri", "env_hz": 25},
    ("nes", "jump"): {"duty": 0.5},
}


def ERA_OF(name):
    return chip(name).era


def render_sfx(chip_name, sfx, rate=dsp.RATE, seed=0, crush=True):
    if sfx not in RECIPES:
        raise KeyError(f"unknown retro sfx {sfx!r}; choose from {sorted(RECIPES)}")
    c = chip(chip_name)
    extra = {**VOICE.get(chip_name, {}), **SPECIAL.get((chip_name, sfx), {})}
    segs = [{**extra, **s} if s["wave"] == T else {**s, **{k: v for k, v in extra.items() if k == "filter"}}
            for s in RECIPES[sfx]]
    x = c.render(segs, rate, seed)
    if crush:
        x = era_crush(x, c.era, rate)
    np = need_numpy()
    return dsp.normalize(np.asarray(x, float), 0.89)
