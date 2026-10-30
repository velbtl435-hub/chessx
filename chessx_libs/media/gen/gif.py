"""Animated GIF of a FEN sequence or a move list (Pillow optional)."""
from ._deps import need_pil
from .board import START_FEN, apply_uci
from .image import board_image


def fens_from_moves(moves, start_fen=START_FEN):
    """UCI moves -> list of FENs including the start position."""
    fens = [start_fen]
    for mv in moves:
        fens.append(apply_uci(fens[-1], mv))
    return fens


def animate_fens(fens, path, duration=700, loop=0, highlights=None, last_frame_hold=3, **kw):
    need_pil()
    if not fens:
        raise ValueError("need at least one FEN")
    hl = highlights or [()] * len(fens)
    frames = [board_image(f, highlight=h, **kw).convert("P", palette=1, colors=64) for f, h in zip(fens, hl)]
    durs = [duration] * len(frames)
    durs[-1] = duration * last_frame_hold
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durs, loop=loop, optimize=False)
    return str(path)


def animate_moves(moves, path, start_fen=START_FEN, **kw):
    fens = fens_from_moves(moves, start_fen)
    hl = [()] + [(m[:2], m[2:4]) for m in moves]
    return animate_fens(fens, path, highlights=hl, **kw)
