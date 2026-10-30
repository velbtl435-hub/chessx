# chessx_libs.audit
Origin: written for ChessX (2026); checks inspired by pyflakes/bandit rule ideas (no code copied). License: MIT.
Stdlib (ast, py_compile, re). Categories: bug, security, optimization, modularization, scalability.
`python3 -c "from chessx_libs.audit import *; print(render_report(audit_tree('chessx_libs')))"`.
For deeper scans optionally run bandit / ruff / pip-audit (not required).
