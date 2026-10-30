"""ChessX unified menu (Team 1). Thin layer: lazy-imports each package and calls only public APIs."""
from .registry import ENTRIES, Entry, availability, MISSING_I18N
from .runner import Menu
__all__ = ["ENTRIES", "Entry", "availability", "MISSING_I18N", "Menu"]
