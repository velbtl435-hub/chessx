"""Retro computer-cabinet sounds, fully synthesized (no samples): HDD, fan, floppy,
mechanical keyboard, CRT. All functions take `seed` for deterministic output."""
from ._deps import need_numpy
from . import dsp
from .dsp import RATE


def _click(rate, seed, length=0.012, lo=1500, hi=8000, tau=0.002):
    need_numpy()
    x = dsp.bandpass(dsp.osc("noise", 0, length, rate, seed=seed), lo, hi, rate)
    return x * dsp.exp_decay(len(x), tau, rate)


def _resonance(freq, seconds, tau, rate):
    x = dsp.osc("sine", freq, seconds, rate)
    return x * dsp.exp_decay(len(x), tau, rate)


def hdd(seconds=2.0, seeks=8, spinup=True, rate=RATE, seed=0):
    """Spindle whine (spin-up glide to 7200rpm=120Hz harmonics) + random seek clicks."""
    np = need_numpy()
    n = int(seconds * rate)
    t = np.arange(n) / rate
    ramp = 1 - np.exp(-t / 0.4) if spinup else np.ones(n)
    f = 120 * ramp
    spin = sum(a * dsp.osc("sine", f * h, seconds, rate) for h, a in ((1, .5), (2, .25), (30, .05)))
    spin = spin * (0.3 + 0.7 * ramp) * 0.3 + 0.05 * dsp.lowpass(dsp.osc("noise", 0, seconds, rate, seed=seed), 400, rate)
    r = dsp.rng(seed)
    for k in range(seeks):
        at = r.uniform(0.25 if spinup else 0, seconds - 0.05) * rate
        c = dsp.mix(_click(rate, seed + k + 1, tau=0.0015), 0.4 * _resonance(r.uniform(1800, 3200), 0.02, 0.004, rate))
        dsp.place(spin, 0.9 * c, at)
        if r.random() < 0.5:  # double-tick seek
            dsp.place(spin, 0.6 * c, at + r.uniform(0.006, 0.02) * rate)
    return dsp.fade(dsp.normalize(spin), 0.01, rate)


def fan(seconds=2.0, rpm=2400, blades=7, rate=RATE, seed=0):
    """Broadband airflow noise + blade-pass tone + mains-ish motor hum."""
    np = need_numpy()
    bpf = rpm / 60 * blades
    air = dsp.bandpass(dsp.osc("noise", 0, seconds, rate, seed=seed), 80, 2500, rate)
    wob = 1 + 0.03 * np.sin(2 * np.pi * 0.7 * np.arange(len(air)) / rate)
    tone = 0.3 * dsp.osc("sine", bpf, seconds, rate) + 0.15 * dsp.osc("sine", bpf * 2, seconds, rate)
    hum = 0.1 * dsp.osc("sine", 100, seconds, rate)
    return dsp.fade(dsp.normalize((air + tone + hum) * wob, 0.6), 0.05, rate)


def floppy(seconds=1.5, steps=24, grind=True, rate=RATE, seed=0):
    """Stepper-motor head steps (tonal buzz per step) + optional media grind."""
    np = need_numpy()
    n = int(seconds * rate)
    out = np.zeros(n)
    step_dt = min(0.006, seconds / max(steps, 1) / 2)
    r = dsp.rng(seed)
    at = 0.05
    for k in range(steps):
        s = dsp.mix(0.5 * _resonance(r.uniform(380, 460), 0.03, 0.006, rate), _click(rate, seed + k, 0.008, 300, 3000, 0.002))
        dsp.place(out, s, at * rate)
        at += step_dt * (3 if k % 8 == 7 else 1)
    if grind:
        g0 = int(min(at + 0.05, seconds * 0.5) * rate)
        gn = n - g0
        g = dsp.bandpass(dsp.osc("noise", 0, gn / rate, rate, seed=seed + 99), 200, 1500, rate)
        g = g * (0.6 + 0.4 * dsp.osc("square", 5, gn / rate, rate)) * 0.4  # 300rpm disk rubbing
        g = g + 0.2 * dsp.osc("saw", 60, gn / rate, rate)
        dsp.place(out, g, g0)
    return dsp.fade(dsp.normalize(out), 0.01, rate)


def keyboard(keys=12, wpm=80, rate=RATE, seed=0, switch="blue"):
    """Mechanical keyboard typing: click + bottom-out thock + spring ping per key."""
    np = need_numpy()
    r = dsp.rng(seed)
    gap = 60 / (wpm * 5)
    n = int((keys * gap + 0.2) * rate)
    out = np.zeros(n)
    at = 0.02
    for k in range(keys):
        key = 0.8 * dsp.lowpass(_click(rate, seed + k, 0.03, 200, 1200, 0.008), 1500, rate)  # thock
        if switch == "blue":
            dsp.place(key, 0.7 * _click(rate, seed + 500 + k, 0.006, 3000, 9000, 0.0008), 0)
        dsp.place(key, 0.08 * _resonance(r.uniform(4000, 6000), 0.03, 0.01, rate), int(0.004 * rate))
        if r.random() < 0.15:  # spacebar: lower, longer
            key = dsp.lowpass(key, 900, rate) * 1.2
        dsp.place(out, key * r.uniform(0.7, 1.0), at * rate)
        at += gap * r.uniform(0.6, 1.4)
    return dsp.normalize(out)


def crt(seconds=2.0, degauss=True, rate=RATE, seed=0, flyback=15734.0):
    """CRT: mains hum (60Hz+harmonics), flyback whine (aliased down if above Nyquist),
    optional degauss 'thunk-wobble' at the start."""
    np = need_numpy()
    n = int(seconds * rate)
    t = np.arange(n) / rate
    hum = sum(a * np.sin(2 * np.pi * 60 * h * t) for h, a in ((1, .4), (2, .2), (3, .1)))
    fw = flyback if flyback < rate / 2 else min(rate / 2 - 300, flyback - rate / 2)  # alias-ish
    whine = 0.04 * np.sin(2 * np.pi * fw * t)
    static = 0.03 * dsp.highpass(dsp.osc("noise", 0, seconds, rate, seed=seed), 3000, rate)
    out = hum * 0.4 + whine + static
    if degauss:
        dn = min(n, int(1.2 * rate))
        td = t[:dn]
        env = np.exp(-td / 0.35)
        dg = np.sin(2 * np.pi * 60 * td) * env * (1 + 0.5 * np.sin(2 * np.pi * 4 * td))
        thunk = _resonance(55, 0.3, 0.08, rate)
        dsp.place(out, 1.5 * dg, 0)
        dsp.place(out, 1.2 * thunk, 0)
    return dsp.fade(dsp.normalize(out), 0.01, rate)
