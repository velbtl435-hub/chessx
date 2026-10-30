# chessx_libs.sounds
Origin: written for ChessX (2026). License: MIT. **Everything is synthesized in code — no audio samples.**
Implements master list section 24 (procedural audio, PRIORITY_LIST #22) and #9 (sounds beyond basic).

## Dependencies
- Legacy `sfx` (`synth`, `save_wav`, `EFFECTS`, `PLAYER`, `play`): stdlib only, always works.
- Procedural audio: `numpy` (required for it). `scipy` optional — `scipy.signal` Butterworth filters when present,
  numpy one-pole fallback otherwise. If numpy is missing, `sounds.play` falls back to the stdlib sfx (`PROCEDURAL=False`).
- Output: 16-bit mono WAV via stdlib `wave`, default 22050 Hz.
- Playback: winsound / aplay / paplay / ffplay / afplay; silent `"noop"` if none, on error, or with `CHESSX_MUTE=1`.

## Integration API (for TamagoX and others)
```python
from chessx_libs import sounds
sounds.list_events()            # all names; sounds.categories() -> {category: [names]}
x = sounds.render("hdd", seed=1, seconds=3)   # float64 np.ndarray in [-1,1], deterministic per seed
sounds.save("synthwave_loop", "loop.wav")      # -> path (temp file if omitted)
sounds.play("capture")          # -> player name or "noop"; never raises; accepts legacy names too
sounds.register("pet.purr", lambda rate=22050, seed=0, **kw: my_array)   # or @sounds.register("x")
sounds.sonify(b"any bytes / text / stats")      # procedural melody from data (section 24.1)
```

| category | events |
|---|---|
| chess | move, capture, check, castle, promote, game_end (+ `chess.*` aliases; note tables reused from `media.gen.audio`) |
| ui | click, error, notify, boot, select, success, found, alert, result |
| cabinet | hdd, fan, floppy, keyboard, crt |
| music | chiptune_theme, synthwave_loop, data, jingle.{win,lose,coin,powerup,notify,boot} |

Extra kwargs go to the generator, e.g. `render("hdd", seconds=4, seeks=20)`, `render("keyboard", keys=40, wpm=100)`,
`render("crt", degauss=False)`, `render("synthwave_loop", bars=4, bpm=95)`, `render("data", data=b"...")`.

## Modules
- `dsp`: `note_freq`, `osc` (sine/square/pulse+duty/triangle/saw/noise), `nes_noise`, `adsr`, `exp_decay`,
  `lowpass/highpass/bandpass`, `delay`, `chorus`, `mix`, `place`, `normalize`, `fade`, `write_wav`.
- `chiptune`: `chip_note` (instruments pulse12/pulse25/square/triangle/noise, arpeggio, vibrato),
  tracker `render_pattern({"lead": ("pulse25", "C5 - E5:047 . x")}, bpm=)`, `jingle`, `JINGLES`, `theme`.
  Pattern tokens: note starts, `-` holds, `.` rests, `NOTE:047` arpeggio, `x` noise hit.
- `synthwave`: `supersaw`, `pad` (detuned saws + lowpass + chorus), `bass`, `arp` (+delay), `drums` (kick, gated snare), `loop`.
- `cabinet`: `hdd` (spin-up + seek clicks), `fan`, `floppy` (stepper steps + grind), `keyboard` (blue/brown), `crt` (hum, flyback whine, degauss).
- `events`: registry and `render/save/play/play_file/find_player/sonify`.

## Tests
`python3 -m unittest discover -s chessx_libs/sounds/tests -t .` — offline, no playback.

## Retro video-game sounds (master list section 27) — `sounds.retro`

Sample-less software approximations, numpy (+ optional scipy):

| chip | era | model |
|---|---|---|
| `nes` | 8bit | 2A03: 11-bit quantized pulse (duties 12.5/25/50/75%), 4-bit triangle, 15-bit LFSR noise (long/short), DPCM-ish |
| `gb` | 8bit | Game Boy DMG: pulse + 32×4-bit wave RAM |
| `sid` | 8bit | C64 SID: saw/tri/pulse+PWM/noise, ring mod, hard sync, exp ADSR, resonant SVF LP/BP/HP |
| `ay`, `sn` | 8bit | AY-3-8910 (period quant, hw envelopes, log volume) / SN76489 (periodic + white noise) |
| `fm`, `opl` | 16bit | YM2612 4-op FM, 8 algorithms, feedback / OPL2 2-op, 4 waveforms |
| `snes` | 16bit | S-DSP: BRR-like 4-bit tables, FIR echo |
| `ps1` | 32bit | SPU: 16-bit tables, detune, reverb, stereo (`PS1().render_stereo`) |

SFX: coin, jump, hit, powerup, 1up, select, game_over, laser, explosion, level_complete,
chess_move, chess_capture, chess_check, chess_mate. Events: `retro.<chip>.<sfx>` (category `retro`,
e.g. `retro.nes.coin`, `retro.sid.laser`), deterministic per seed, peak <= 0.89.
Utilities: `bitcrush`, `srcrush`, `era_crush` (8bit 4-bit/11 kHz, 16bit 12-bit/22 kHz, 32bit 16-bit/44 kHz),
`stereo(x, pan, width)`, `write_wav_stereo`.

```python
from chessx_libs.sounds import events
events.save("retro.sid.laser", "laser.wav", seed=1)
from chessx_libs.sounds.retro import render_sfx; x = render_sfx("fm", "explosion")
```
