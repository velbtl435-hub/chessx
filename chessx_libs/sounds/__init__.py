"""Basic sound effects: synthesized WAV (stdlib wave) played via OS player; silent fallback."""
from .sfx import play, synth, save_wav, EFFECTS, PLAYER
__all__ = ["play", "synth", "save_wav", "EFFECTS", "PLAYER"]
