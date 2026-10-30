"""ChessX sounds: legacy stdlib sfx + procedural audio (numpy; scipy optional).

Integration API: list_events(), categories(), render(event), save(event, path), play(event), register(name, fn).
"""
from .sfx import synth, save_wav, EFFECTS, PLAYER
from ._deps import MissingDependency
try:
    from .events import (play, render, save, register, list_events, categories, play_file,
                         find_player, sonify)
    from . import dsp, chiptune, synthwave, cabinet
    PROCEDURAL = True
except MissingDependency:  # numpy missing: keep the stdlib sfx API alive
    from .sfx import play
    PROCEDURAL = False
__all__ = ["play", "synth", "save_wav", "EFFECTS", "PLAYER", "render", "save", "register", "list_events",
           "categories", "play_file", "find_player", "sonify", "dsp", "chiptune", "synthwave", "cabinet",
           "MissingDependency", "PROCEDURAL"]
