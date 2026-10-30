"""Sprite format: palette {char: (r,g,b)} + frames of equal-size char grids ('.' = transparent)."""
from dataclasses import dataclass


@dataclass
class Sprite:
    name: str
    palette: dict
    frames: list  # list[list[str]]

    @property
    def width(self):
        return max(len(r) for f in self.frames for r in f)

    @property
    def height(self):
        return max(len(f) for f in self.frames)


SPRITES = {
    "cat": Sprite("cat", {"k": (40, 40, 40), "o": (240, 150, 50), "w": (255, 255, 255), "p": (255, 120, 160)}, [
        ["o...o...", "oo.oo...", "owkwo..o", "ooooo.o.", ".oooooo.", ".o.o.o.o", ".o...o.."],
        ["o...o...", "oo.oo...", "owkwo...", "ooooo.oo", ".oooooo.", "..o.o.o.", ".o.o...."],
    ]),
    "frog": Sprite("frog", {"g": (60, 190, 70), "w": (255, 255, 255), "k": (0, 0, 0), "r": (220, 60, 60)}, [
        [".ww..ww.", ".wk..wk.", "gggggggg", "grrrrrrg", "gggggggg", "g......g"],
        [".ww..ww.", ".wk..wk.", "gggggggg", "gggggggg", ".gggggg.", "gg....gg"],
    ]),
    "bird": Sprite("bird", {"b": (70, 140, 230), "y": (250, 210, 40), "k": (0, 0, 0)}, [
        ["b......b", ".b.bb.b.", "..bkbby.", "...bbb..", "...y.y.."],
        ["........", "...bb...", "bbbkbbby", "...bbb..", "...y.y.."],
    ]),
    "slime": Sprite("slime", {"s": (120, 220, 255), "k": (0, 0, 0), "w": (230, 250, 255)}, [
        ["........", "..ssss..", ".swsssk.", "ssssssss", "ssssssss"],
        ["...ss...", ".ssssss.", "swssskss", "ssssssss", ".ssssss."],
        ["........", "........", ".ssssss.", "swsssksss"[:8], "ssssssss"],
    ]),
    "knight": Sprite("knight", {"w": (235, 235, 235), "k": (30, 30, 30), "g": (150, 150, 150)}, [
        ["..ww....", ".wwkw...", "wwwww...", "...ww...", "..www...", ".wwwww..", "ggggggg."],
        ["...ww...", "..wwkw..", ".wwwww..", "....ww..", "...www..", "..wwwww.", ".ggggggg"],
    ]),
}


def list_sprites():
    return sorted(SPRITES)


def get_sprite(name):
    try:
        return SPRITES[name]
    except KeyError:
        raise KeyError(f"unknown sprite {name!r}; available: {', '.join(list_sprites())}") from None
