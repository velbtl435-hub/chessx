"""Text widgets: panel, tabs, sidebar."""
from typing import List


def panel(title: str, lines: List[str], width: int = 40) -> str:
    inner = width - 2
    top = "┌─ " + title[:inner - 4] + " " + "─" * max(0, inner - len(title) - 3) + "┐"
    body = ["│" + l[:inner].ljust(inner) + "│" for l in lines]
    return "\n".join([top] + body + ["└" + "─" * inner + "┘"])


def tabs(names: List[str], active: int = 0) -> str:
    return " ".join(f"[{n}]" if i == active else f" {n} " for i, n in enumerate(names))


def sidebar(items: List[str], main: str, width: int = 18, selected: int = -1) -> str:
    main_lines = main.splitlines() or [""]
    n = max(len(items), len(main_lines))
    rows = []
    for i in range(n):
        it = items[i] if i < len(items) else ""
        it = ("> " if i == selected else "  ") + it
        rows.append(it[:width].ljust(width) + "│ " + (main_lines[i] if i < len(main_lines) else ""))
    return "\n".join(rows)
