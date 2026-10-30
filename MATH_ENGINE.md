# ChessX Math Engine (`chessx_libs/mathx`)

A math/engineering assistant built on SymPy. Input is parsed by walking a
whitelisted AST (no `eval`/`exec`). Messages are available in en/pt/ja (`lang <code>`).

## Commands
| Command | What it does |
|---|---|
| `prof <question>` / `professor` | PhD professor mode: math, electrical engineering, computing, software, systems analysis |
| `math <expr>` | Quick evaluation (exact + numeric) |
| `draw` | Multi-line ASCII-art equation (empty line ends input) → parsed, pretty-printed, solved |
| `render <expr>` | 2D pretty print |
| `steps <kind> <input>` | Step-by-step: `solve`, `system`, `diff`, `integrate`, `simplify`, `limit`, `matrix` |
| `check` | Paste your own working line by line; flags the first wrong step |
| `export <lang\|all> <expr>` | python, numpy, sympy, matlab/octave, julia, r, latex, wolfram, c |
| `translate <from> <to> <expr>` | Convert notation between those languages |
| `calc <a = 3; b = a^2; sqrt(b)>` | Sandboxed evaluator (timeout, size limits) |

### Professor topics
solve, simplify, diff, integrate, limit, matrix, ode, stats, ncr, gcd, factor,
ohm, series, parallel, divider, kirchhoff, impedance, rc, rl, rlc, phasor, power,
db, filter, bigo, base, bool, dfa, tf, laplace, ilaplace, routh, explain.
Examples: `prof rlc R=10 L=1m C=1u`, `prof bigo merge sort`, `prof routh s^3+2s^2+3s+1`.

## ASCII example
```
> draw
  x^2 - 1
---------- = 0
   x + 3

expr: ((x^2 - 1)/(x + 3)) = 0
solve : x = [-1, 1]
```
Supported shapes: fraction bars (the longest bar is the main one), superscripts/subscripts, `\/` or `√` roots,
matrices `[ ]`, `⎡⎤`, `| |`, integrals `∫` or `/ | /` with limits, `Σ` with limits.
Separate pieces drawn side by side with blank columns.

## Limits
- Requires `sympy` (in `requirements.txt`).
- The professor mode is rule-based; `set_llm()` is an optional hook (the repo ships no LLM).
- ASCII parsing is heuristic: ambiguous drawings may need parentheses.
- `calc` uses SIGALRM for its timeout (POSIX only; on Windows only the size limits apply).
