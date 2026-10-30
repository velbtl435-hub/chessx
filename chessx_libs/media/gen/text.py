"""Text/caption generation from PGN and moves (stdlib only)."""
import re

PIECE_NAMES = {"K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight"}
RESULTS = {"1-0": "White wins", "0-1": "Black wins", "1/2-1/2": "Draw", "*": "Game in progress"}


def parse_pgn(pgn: str):
    """Return (headers dict, list of SAN moves, result)."""
    headers = dict(re.findall(r'\[(\w+)\s+"([^"]*)"\]', pgn))
    body = re.sub(r"\[[^\]]*\]", " ", pgn)
    body = re.sub(r"\{[^}]*\}|;[^\n]*", " ", body)
    while re.search(r"\([^()]*\)", body):
        body = re.sub(r"\([^()]*\)", " ", body)
    body = re.sub(r"\$\d+", " ", body)
    toks = body.split()
    result = next((t for t in toks if t in RESULTS), headers.get("Result", "*"))
    moves = [re.sub(r"^\d+\.(\.\.)?", "", t) for t in toks if t not in RESULTS]
    return headers, [m for m in moves if m and not re.fullmatch(r"\d+\.+", m)], result


def describe_san(san: str) -> str:
    """'Nxe5+' -> 'Knight takes e5, check'."""
    s = san.rstrip("!?")
    suffix = ", checkmate" if s.endswith("#") else ", check" if s.endswith("+") else ""
    s = s.rstrip("+#")
    if s in ("O-O", "0-0"):
        return "Castles kingside" + suffix
    if s in ("O-O-O", "0-0-0"):
        return "Castles queenside" + suffix
    promo = ""
    if "=" in s:
        s, p = s.split("=")
        promo = f", promotes to {PIECE_NAMES.get(p[0].upper(), p)}"
    piece = PIECE_NAMES.get(s[0], "Pawn")
    dest = s[-2:]
    verb = "takes" if "x" in s else "to"
    return f"{piece} {verb} {dest}{promo}{suffix}"


def move_list_text(moves, describe=False):
    out = []
    for i in range(0, len(moves), 2):
        pair = moves[i:i + 2]
        if describe:
            pair = [describe_san(m) for m in pair]
        out.append(f"{i // 2 + 1}. " + (" / " if describe else " ").join(pair))
    return "\n".join(out) if describe else " ".join(out)


def summarize_pgn(pgn: str) -> str:
    h, moves, result = parse_pgn(pgn)
    w, b = h.get("White", "White"), h.get("Black", "Black")
    caps = sum("x" in m for m in moves)
    checks = sum(m.rstrip("!?").endswith(("+", "#")) for m in moves)
    where = ", ".join(x for x in (h.get("Event"), h.get("Site"), h.get("Date")) if x and x != "?")
    lines = [f"{w} vs {b}" + (f" ({where})" if where else ""),
             f"{(len(moves) + 1) // 2} moves, {caps} captures, {checks} checks. Result: {RESULTS.get(result, result)}."]
    if moves:
        lines.append(f"Opening: {' '.join(moves[:6])}. Final move: {moves[-1]} ({describe_san(moves[-1])}).")
    return "\n".join(lines)


def caption(fen_or_text: str, title: str = None, max_len: int = 80) -> str:
    """Short caption for an image: side to move from a FEN, or truncated text."""
    parts = fen_or_text.split()
    if len(parts) >= 2 and parts[0].count("/") == 7:
        cap = f"{'White' if parts[1] == 'w' else 'Black'} to move"
    else:
        cap = " ".join(parts)
    cap = f"{title}: {cap}" if title else cap
    return cap if len(cap) <= max_len else cap[:max_len - 1] + "…"
