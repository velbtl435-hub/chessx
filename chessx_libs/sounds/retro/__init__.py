"""Retro video-game sounds (master list section 27): software approximations of
NES 2A03, Game Boy DMG, C64 SID, AY-3-8910 / SN76489 PSG, YM2612/OPL FM, SNES S-DSP, PS1 SPU.
All procedural (numpy, scipy optional). See README in chessx_libs/sounds."""
from .crush import bitcrush, srcrush, era_crush, stereo, write_wav_stereo, ERAS
from .chips import CHIPS, chip, Chip
from .sfx import RECIPES, render_sfx, ERA_OF
__all__ = ["bitcrush", "srcrush", "era_crush", "stereo", "write_wav_stereo", "ERAS", "CHIPS", "chip", "Chip",
           "RECIPES", "render_sfx", "ERA_OF"]
