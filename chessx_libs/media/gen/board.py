"""Minimal FEN board model (stdlib): parse, serialize, apply UCI moves (no legality check)."""
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def parse_fen(fen: str):
    """Return 8x8 list (rank 8 first) of piece chars or None, plus side to move."""
    parts = fen.split()
    rows = parts[0].split("/")
    if len(rows) != 8:
        raise ValueError(f"bad FEN: {fen!r}")
    board = []
    for row in rows:
        r = []
        for c in row:
            if c.isdigit():
                r.extend([None] * int(c))
            elif c in "prnbqkPRNBQK":
                r.append(c)
            else:
                raise ValueError(f"bad FEN char {c!r}")
        if len(r) != 8:
            raise ValueError(f"bad FEN row {row!r}")
        board.append(r)
    return board, (parts[1] if len(parts) > 1 else "w")


def board_to_fen(board, side="w"):
    rows = []
    for r in board:
        s, n = "", 0
        for c in r:
            if c is None:
                n += 1
            else:
                s += (str(n) if n else "") + c
                n = 0
        rows.append(s + (str(n) if n else ""))
    return "/".join(rows) + f" {side} - - 0 1"


def _sq(s):
    return 8 - int(s[1]), "abcdefgh".index(s[0])


def apply_uci(fen: str, move: str) -> str:
    """Apply a UCI move like e2e4 / e7e8q; handles castling and en passant captures."""
    board, side = parse_fen(fen)
    (r1, c1), (r2, c2) = _sq(move[:2]), _sq(move[2:4])
    p = board[r1][c1]
    if p is None:
        raise ValueError(f"no piece on {move[:2]}")
    if p in "Kk" and abs(c2 - c1) == 2:  # castling: move rook too
        rc, nc = (7, 5) if c2 > c1 else (0, 3)
        board[r1][nc], board[r1][rc] = board[r1][rc], None
    if p in "Pp" and c1 != c2 and board[r2][c2] is None:  # en passant
        board[r1][c2] = None
    board[r2][c2], board[r1][c1] = p, None
    if len(move) == 5:
        board[r2][c2] = move[4].upper() if p.isupper() else move[4].lower()
    return board_to_fen(board, "b" if side == "w" else "w")
