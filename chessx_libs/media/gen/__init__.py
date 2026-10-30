"""Media generation: audio (numpy), image/gif (Pillow), text (stdlib). Imports are lazy."""
from ._deps import MissingDependency
from .board import parse_fen, board_to_fen, apply_uci, START_FEN
from . import text
__all__ = ["MissingDependency", "parse_fen", "board_to_fen", "apply_uci", "START_FEN", "text",
           "audio", "image", "gif"]


def __getattr__(name):  # lazy submodules so missing numpy/Pillow only fails on use
    if name in ("audio", "image", "gif"):
        import importlib
        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(name)
