# ChessX Agent Factory + TamagóX

Stdlib only. Packages: `chessx_libs/agents` (core, types, factory, workspace, schedule, cli) and `chessx_libs/tamagox`.
Data lives in `$CHESSX_AGENTS_HOME` (default `~/.chessx/agents`):

```
definitions/<agent>.json   agent definitions (factory)
types.json                 generated agent types
workspaces/<agent>/        isolated workspace (files/ materials/ logs/ tmp/ state.json, sub/<child>/)
schedule.json              scheduled jobs
pets/<agent>.json          TamagóX pets
```

## CLI (`python3 chessx.py agent ...`  or  `python3 -m chessx_libs.agents ...`)

```bash
# 1) build an agent: prompt, sub-prompts, script, code, materials, links
python3 chessx.py agent create openings --type researcher --prompt "Estude aberturas" \
  --sub "Siciliana" --sub "Francesa" --script "ls ../materials" --code "print('oi')" \
  --material notas.pgn --link https://lichess.org --max-depth 8 --budget 1000
python3 chessx.py agent new            # interactive wizard
python3 chessx.py agent list | show NAME | run NAME | delete NAME | import def.json

# 2) agent types: list, generate from a description, derive from an existing type
python3 chessx.py agent types
python3 chessx.py agent gen-type "pesquisa a web e traduz para japonês" --name tradutor_pesquisador
python3 chessx.py agent gen-type "pesquisa profunda" --name deep --from researcher

# 3) scheduling (second|minute|hour|day|week|month|year; PT: segundo, minuto, hora, dia, mes, ano)
python3 chessx.py agent schedule openings --every 1 --unit dia --at 09:00
python3 chessx.py agent schedule openings --at "2026-12-31 23:59"      # one-shot
python3 chessx.py agent schedule openings --every 30 --unit second --times 10
python3 chessx.py agent jobs | unschedule JOB_ID
python3 chessx.py agent runner [--duration 60]                         # runner loop

# 4) TamagóX
python3 chessx.py agent run openings --pet
python3 chessx.py agent pet openings [show|feed|play|sleep|revive|json]
```

## Python API

```python
from chessx_libs.agents import Agent, Limits, Factory, Registry, Generator, Workspace, AgentScheduler
from chessx_libs import tamagox

def task(agent, n):                       # recursive sub-agents
    return n if n < 2 else sum(agent.spawn("f", kind="fib%d" % (n - k), task=task).run(n - k) for k in (1, 2))
root = Agent("root", task=task, limits=Limits(budget=10_000, spawn_cost=1))
root.run(15); print(root.tree.total); root.kill()   # kill switch for the whole tree
```

## Design

- **Sub-agents (unbounded but guarded):** `Limits` defaults to no depth/count limit. Guards that are always on:
  shared tree *budget* (`budget`/`spawn_cost`), *cycle detection* (same `kind` repeated `cycle_repeat`=64 times in
  the lineage, configurable via agent `meta`), *spawn rate* (`max_spawn_rate`/s per tree), *free RAM* check
  (`min_free_mem_mb`, Linux `/proc/meminfo`) and a *kill switch* (`agent.kill()`, `turn_off()`).
  Agents run in-process (synchronous); only definition `script`/`code` run as subprocesses with `timeout`.
- **Types:** 5 built-ins (researcher, code_analyst, security_monitor, media_collector, translator). Capabilities are
  inferred from keywords (EN/PT) and map to ChessX packages. Generation: `from_description`, `from_template`,
  `derive`, `combine`, `from_usage(history)`. Inheritance via `parent`, resolved with cycle check.
- **Workspace:** each agent runs with `cwd=files/`, `HOME`/`TMPDIR` inside the workspace, file helpers refuse paths
  escaping `files/`. Sub-agents `nested` (inside parent) or `isolated` (sibling dir). Cleanup policy
  `keep | on_success | always | ttl` (+ `sweep(root, ttl)`), set via definition `"workspace": {"mode","cleanup","ttl"}`.
  This is directory isolation, **not a security sandbox** (no chroot/containers): only run code you trust.
- **Schedule:** months/years use calendar arithmetic anchored to the first run (Jan 31 -> Feb 28 -> Mar 31, no drift);
  missed slots are skipped, not replayed; errors are counted per job and never stop the runner.
- **TamagóX:** a `Pet` (mood, energy, hunger, xp/level) bound with `tamagox.attach(agent, pet)` reacts to agent
  events (start/done/error/spawn/message, including sub-agents) and decays per hour. Mode is off unless
  `CHESSX_TAMAGOX=1`, `tamagox.enable()` or `--pet`. Media activities from master list §23 are pluggable:
  `@tamagox.hook("watch_youtube")` then `tamagox.act(pet, "watch_youtube", url)`; shipped hooks: `analyze_text`,
  `play_audio` (sounds), `speak` (voice). Video/image/GIF/music analysis and generation are not implemented yet.
