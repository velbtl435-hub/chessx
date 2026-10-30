"""Square board of results with cursor and expandable sub-boards."""
import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Cell:
    title: str
    url: str = ""
    kind: str = "web"
    score: float = 0.0
    children: List["Cell"] = field(default_factory=list)


class Board:
    def __init__(self, cells: List[Cell], parent: Optional["Board"] = None):
        self.cells = cells
        self.parent = parent
        self.size = max(1, math.ceil(math.sqrt(len(cells) or 1)))
        self.row = self.col = 0

    @property
    def index(self) -> int:
        return self.row * self.size + self.col

    def current(self) -> Optional[Cell]:
        return self.cells[self.index] if self.index < len(self.cells) else None

    def move(self, dr: int, dc: int):
        r, c = (self.row + dr) % self.size, (self.col + dc) % self.size
        if r * self.size + c < len(self.cells):
            self.row, self.col = r, c

    def expand(self) -> "Board":
        cur = self.current()
        return Board(cur.children, parent=self) if cur and cur.children else self

    def collapse(self) -> "Board":
        return self.parent or self

    def render(self, cell_w: int = 14) -> str:
        line = "+" + ("-" * cell_w + "+") * self.size
        out = [line]
        for r in range(self.size):
            row = "|"
            for c in range(self.size):
                i = r * self.size + c
                txt = self.cells[i].title[:cell_w - 2] if i < len(self.cells) else ""
                mark = ">" if (r, c) == (self.row, self.col) else " "
                row += (mark + txt).ljust(cell_w) + "|"
            out += [row, line]
        return "\n".join(out)
