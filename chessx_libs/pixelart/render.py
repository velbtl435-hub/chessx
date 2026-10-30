"""Half-block renderer (▀ with fg=top pixel, bg=bottom pixel) and animation loop."""
import shutil, sys, time
from .sprites import Sprite, get_sprite

UP, LOW, FULL = "\u2580", "\u2584", "\u2588"


def _px(sprite, frame, x, y):
    rows = sprite.frames[frame]
    if y < len(rows) and x < len(rows[y]):
        return sprite.palette.get(rows[y][x])
    return None


def render_frame(sprite, i=0, color=True, offset=0):
    """Return one frame as text; two pixel rows per text line. color=False gives a mono glyph map."""
    s = sprite if isinstance(sprite, Sprite) else get_sprite(sprite)
    f = i % len(s.frames)
    lines = []
    for y in range(0, s.height, 2):
        line = " " * offset
        for x in range(s.width):
            t, b = _px(s, f, x, y), _px(s, f, x, y + 1)
            if not color:
                line += FULL if t and b else UP if t else LOW if b else " "
            elif t and b:
                line += f"\033[38;2;{t[0]};{t[1]};{t[2]};48;2;{b[0]};{b[1]};{b[2]}m{UP}\033[0m"
            elif t:
                line += f"\033[38;2;{t[0]};{t[1]};{t[2]}m{UP}\033[0m"
            elif b:
                line += f"\033[38;2;{b[0]};{b[1]};{b[2]}m{LOW}\033[0m"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)


def animate(name, frames=None, fps=8, walk=True, out=None, sleep=time.sleep, color=True):
    """Play a sprite. frames=None: walk across the terminal once (or 2s if walk=False).
    Ctrl+C stops cleanly. Returns number of frames drawn."""
    s = get_sprite(name)
    out = out or sys.stdout
    cols = shutil.get_terminal_size((80, 24)).columns
    span = max(1, cols - s.width - 1)
    total = frames if frames is not None else (span if walk else fps * 2)
    h = (s.height + 1) // 2
    drawn = 0
    try:
        for i in range(total):
            if i:
                out.write(f"\033[{h}F")  # cursor up to redraw in place
            off = (i % span) if walk else 0
            out.write("\n".join("\033[2K" + l for l in render_frame(s, i, color, off).split("\n")) + "\n")
            out.flush(); drawn += 1
            sleep(1.0 / max(1, fps))
    except KeyboardInterrupt:
        pass
    return drawn
