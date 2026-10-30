"""Chip registry: name -> Chip instance."""
from .base import Chip
from .nes import NES, GameBoy
from .sid import SID
from .psg import AY8910, SN76489
from .fm import YM2612, OPL2
from .wavetable import SNES, PS1

CHIPS = {c.name: c for c in (NES(), GameBoy(), SID(), AY8910(), SN76489(), YM2612(), OPL2(), SNES(), PS1())}


def chip(name):
    try:
        return CHIPS[name]
    except KeyError:
        raise KeyError(f"unknown chip {name!r}; choose from {sorted(CHIPS)}") from None


__all__ = ["CHIPS", "chip", "Chip"]
