from collections import Counter

WEIGHT = {"high": 10, "medium": 3, "low": 1}


def score(findings) -> int:
    return max(0, 100 - sum(WEIGHT[f.severity] for f in findings))


def render_report(findings, root: str = ".") -> str:
    by_cat = Counter(f.category for f in findings)
    by_sev = Counter(f.severity for f in findings)
    lines = [f"ChessX audit: {len(findings)} findings, score {score(findings)}/100",
             "by category: " + ", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())),
             "by severity: " + ", ".join(f"{k}={by_sev.get(k, 0)}" for k in ("high", "medium", "low")), ""]
    order = {"high": 0, "medium": 1, "low": 2}
    for f in sorted(findings, key=lambda f: (order[f.severity], f.category, f.path, f.line)):
        p = f.path[len(root):].lstrip("/") if f.path.startswith(root) else f.path
        lines.append(f"[{f.severity:6}] {f.category:14} {p}:{f.line}  {f.message}")
    return "\n".join(lines)
