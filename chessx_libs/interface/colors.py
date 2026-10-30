"""ANSI 256-color palette: teal / purple / blue / orange."""
import os, sys


class Color:
    TEAL = "\033[38;5;37m"
    PURPLE = "\033[38;5;135m"
    BLUE = "\033[38;5;33m"
    ORANGE = "\033[38;5;208m"
    GRAY = "\033[38;5;245m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


TYPE_COLORS = {"web": Color.TEAL, "news": Color.PURPLE, "docs": Color.BLUE, "media": Color.ORANGE}


def enabled() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(text: str, color: str, force: bool = False) -> str:
    return f"{color}{text}{Color.RESET}" if (force or enabled()) else text
