# chessx_libs.scheduler
Origin: written for ChessX (2026), API inspired by `schedule` (MIT) but no code copied. License: MIT. Stdlib only.
Jobs per second/minute/hour/day (`every`, `daily(at="HH:MM")`), drift-free, error-isolated.
"Never idle without reason": when no job is due it runs idle tasks; it only sleeps when idle tasks have no work,
and every sleep is logged with its reason. Run in foreground (`run`) or background thread (`start`).
