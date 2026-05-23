# OmbleCavalier Chess Engines

[![Engine CI](https://github.com/hu64/OmbleCavalier/actions/workflows/engine-ci.yml/badge.svg)](https://github.com/hu64/OmbleCavalier/actions/workflows/engine-ci.yml)

Two UCI-compatible chess engines — one in C++, one in Python — built to run as bots on [Lichess](https://lichess.org) via [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot).

> **Challenge them on Lichess:**
> [OmbleCavalier (Python)](https://lichess.org/@/OmbleCavalier) · [OmbleCavalierPP (C++)](https://lichess.org/@/OmbleCavalierPP)

---

## ♞ OmbleCavalier++ (C++)

<img src="https://i.imgur.com/0FmFSkX.jpg" width="400"/>

A modern C++ engine built for speed. Searches 5–8 plies deep in typical bullet/blitz time controls.

### How it works

The engine receives UCI commands from lichess-bot, sets up the board using [Disservin's chess.hpp](https://github.com/Disservin/chess-library), then runs **iterative deepening negamax** with **alpha-beta pruning**. Each iteration searches one ply deeper than the last, keeping the best move from the previous iteration in case time runs out. Move ordering (hash move → captures by MVV-LVA → killers → checks → history) ensures the most promising moves are searched first, maximising cutoffs. Static evaluation combines material, piece-square tables, pawn structure, and king safety. A **transposition table** (fixed-size 1M-entry array) caches results to avoid re-searching identical positions.

### Features

| Category | Feature |
|----------|---------|
| **Search** | Negamax with alpha-beta pruning |
| | Iterative deepening |
| | Aspiration windows |
| | Principal Variation Search (PVS) |
| | Null move pruning (R=3) |
| | Late Move Reduction (LMR) — depth-aware, up to 3 ply for deep/late moves |
| | Reverse Futility Pruning (RFP) at depth ≤ 5 |
| | Check extension (1 ply) |
| | Futility pruning at depth 1–2 (check-giving moves excluded) |
| | Delta pruning in quiescence search |
| | Quiescence search |
| **Move ordering** | Hash move (from TT) |
| | MVV-LVA capture ordering |
| | Killer move heuristic (2 per ply) |
| | Check bonus |
| | History heuristic |
| **Evaluation** | PESTO tapered evaluation (MG/EG interpolation via game phase) |
| | 12 piece-square tables (6 MG + 6 EG, Rofchade PESTO values) |
| | Separate MG/EG material values |
| | Pawn structure — phase-weighted (doubled, isolated, rank-scaled passed) |
| | King safety — phase-weighted (pawn shield, open files, pawn storm) |
| | Rook on open / semi-open file bonus |
| | Rook on 7th rank bonus |
| | Bishop pair bonus |
| | Mobility |
| **Infrastructure** | Fixed-size transposition table (~24 MB) |
| | Polyglot opening book (`gm2001.bin`) |
| | Adaptive time management |
| | `position fen` + `position startpos` |
| | Puzzle test suite (9 puzzles via CTest) |
| | Benchmarking utility |

### Build

Requires: GCC/Clang with C++20, CMake 3.10+.

```bash
cd src/OmbleCavalierPlusPlus
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

The binary is output to `build/omble_cavalier++`.

### Test

Puzzle positions are defined in [`tests/puzzles.json`](tests/puzzles.json) and shared by both engines. Add or edit puzzles there.

```bash
cd src/OmbleCavalierPlusPlus/build

# Run all CTest puzzle + unit tests
ctest --output-on-failure

# Or run the engine's built-in puzzle suite interactively
echo "puzzletest" | ./omble_cavalier++
```

### Run (standalone UCI)

```bash
./omble_cavalier++
# Then type UCI commands:
uci
isready
position startpos moves e2e4 e7e5
go wtime 60000 btime 60000
```

---

## 🐍 OmbleCavalier (Python)

<img src="https://i.imgur.com/VpbihwX.jpg" width="400"/>

A Python engine at feature parity with the C++ version. Slower by nature (~10× fewer nodes/sec) but easier to iterate on and experiment with new ideas.

### How it works

Uses [bulletchess](https://github.com/zedeckj/bulletchess) for fast board representation and move generation (Rust-backed). The search is identical in structure to the C++ engine: **iterative deepening negamax** with **alpha-beta pruning**, aspiration windows, null move pruning, and **Late Move Reduction**. Evaluation uses **PESTO tapered evaluation** with precomputed per-square lookup tables (`_W_MG`, `_W_EG`, `_B_MG`, `_B_EG`) that merge material + PST values to minimize per-node arithmetic. A two-tier evaluation strategy uses the full PESTO evaluation (including pawn structure and king safety) at the quiescence entry node, and a lighter material+PST-only path for recursive quiescence nodes.

### Features

| Category | Feature |
|----------|---------|
| **Search** | Negamax with alpha-beta pruning |
| | Iterative deepening |
| | Aspiration windows |
| | Principal Variation Search (PVS) |
| | Null move pruning (R=3, via board copy + turn-swap) |
| | Late Move Reduction (LMR) — depth-aware, up to 3 ply for deep/late moves |
| | Reverse Futility Pruning (RFP) at depth ≤ 5 |
| | Check extension (1 ply) |
| | Futility pruning at depth 1–2 |
| | Delta pruning in quiescence search |
| | Quiescence search |
| **Move ordering** | MVV-LVA capture ordering |
| | Killer move heuristic (2 per ply) |
| | History heuristic |
| **Evaluation** | PESTO tapered evaluation (MG/EG interpolation via game phase) |
| | 12 precomputed per-square lookup tables (6 MG + 6 EG) |
| | Separate MG/EG material values |
| | Pawn structure — phase-weighted (doubled, isolated, rank-scaled passed) |
| | King safety — phase-weighted (pawn shield, open files, pawn storm) |
| | Rook on open / semi-open file bonus |
| | Rook on 7th rank bonus |
| | Bishop pair bonus |
| | Mobility |
| | Two-tier eval (full PESTO at quiescence entry, fast PST-only inside quiescence) |
| **Infrastructure** | Dictionary-based transposition table |
| | Polyglot opening book (`gm2001.bin`) |
| | Adaptive time management |
| | `position fen` + `position startpos` |
| | Puzzle test suite (9 puzzles via pytest) |

### Environment setup

The project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Runtime deps (engine + bot)
uv sync

# Runtime + dev deps (pytest, pyinstaller, snakeviz, cython)
uv sync --group dev
```

The NNUE training pipeline (`src/nnue-training/`) is a separate project with its own venv — PyTorch stays out of the engine runtime. Run all training commands with `uv run` from inside `src/nnue-training/`.

### Run (standalone UCI)

```bash
# From repo root
uv run python src/OmbleCavalierPython/omblecavalier/engines/omble_cavalier.py

# Then type UCI commands:
uci
isready
position startpos moves e2e4
go wtime 60000 btime 60000
```

### Test

Puzzle positions are shared with the C++ engine via [`tests/puzzles.json`](tests/puzzles.json).

```bash
# From repo root
uv run pytest src/OmbleCavalierPython/tests/ -v
```

### Build executable

```bash
uv run pyinstaller --onefile \
  --distpath engines \
  src/OmbleCavalierPython/omblecavalier/engines/omble_cavalier.py
```

---

## 🧠 NNUE Training

Both engines are being extended with a [NNUE](https://www.chessprogramming.org/NNUE) evaluation layer trained on Lichess position evaluations. The training pipeline lives in `src/nnue-training/` as a self-contained project with its own virtual environment — PyTorch is not a runtime dependency of either engine.

### Network architecture

`768 → 256 → 32 → 1` with ClippedReLU activations. Input is a 768-bit binary feature vector (12 piece types × 64 squares, from side-to-move perspective). Output is a win-probability logit; converted to centipawns via `400 × log(p / (1−p))`.

### Pipeline

```
prepare_data.py  →  positions.bin  →  train.py  →  best.pt  →  export.py  →  omblecavalier.nnue
```

**1. Prepare data** — streams `lichess_db_eval.jsonl.zst` ([download from database.lichess.org](https://database.lichess.org/#evals), ~10 GB) and writes binary position records:

```bash
cd src/nnue-training
uv run python prepare_data.py \
    --input  /path/to/lichess_db_eval.jsonl.zst \
    --output data/positions.bin \
    --max-positions 10_000_000 --min-depth 12
```

**2. Train** — 96/2/2% train/val/test split, early stopping (patience 5 epochs by default), MLflow tracking. GPU (CUDA or MPS) is used automatically when available:

```bash
uv run python train.py \
    --data    data/positions.bin \
    --out     checkpoints/ \
    --epochs  20 \
    --batch   16384
```

**3. Export** — converts `best.pt` to a portable `.nnue` binary (magic header + float32 weights):

```bash
uv run python export.py --model checkpoints/best.pt --output omblecavalier.nnue
```

**4. Validate** — sanity-checks win-probabilities on reference positions (starting position ≈ 0.5, clearly winning ≥ 0.65, clearly losing ≤ 0.35):

```bash
uv run python validate.py --model omblecavalier.nnue
```

### Visualise training

```bash
cd src/nnue-training
mlflow ui        # opens http://localhost:5000
```

Shows train loss (per step), val loss + accuracy (per epoch), and final test metrics across all runs.

### Training data

`data/positions.bin` (~7.5 GB for 10 M positions) is tracked via git-lfs. Install git-lfs before pulling it:

```bash
brew install git-lfs   # macOS
git lfs install
git lfs pull
```

---

## Lichess-bot setup

Both engines plug into [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot). Config files are at `config_cpp.yml` and `config_python.yml`.

1. [Create a Lichess OAuth token](https://github.com/lichess-bot-devs/lichess-bot/wiki/How-to-create-a-Lichess-OAuth-token)
2. [Upgrade the account to BOT](https://github.com/lichess-bot-devs/lichess-bot/wiki/Upgrade-to-a-BOT-account)
3. Run with the desired config:

```bash
# C++ engine
uv run python lichess-bot.py -c config_cpp.yml

# Python engine
uv run python lichess-bot.py -c config_python.yml
```

---

## Elo Improvement Roadmap

Ranked by estimated Elo gain per implementation effort. _Both engines_ unless noted.

### Tier 1 — Quick wins (~1–2h each, high return)

- [x] **Late Move Reduction (LMR)** — Depth-aware reductions (1–3 ply) for quiet, non-killer, non-check moves after index 2; re-search on fail-high. _Both engines._
- [x] **Principal Variation Search (PVS)** — After the first move, search with null window `(-alpha-1, -alpha)` and re-search full window only on fail-high. _Both engines._
- [x] **Reverse Futility Pruning (RFP)** — At depth ≤ 5, if `static_eval - 200×depth >= beta`, cut off immediately. _Both engines._
- [x] **Futility Pruning** — At depth 1–2, skip quiet moves where `static_eval + margin <= alpha` (check-giving moves excluded). _Both engines._
- [x] **Delta Pruning in Quiescence** — Skip captures where `stand_pat + piece_value + 200 <= alpha`. _Both engines._
- [ ] **Endgame King PST** — Add a second king table where the king centralizes; swap based on remaining material. Est. +20 Elo. _Both engines._

### Tier 2 — Evaluation improvements (~1–3h each)

- [x] **Tapered evaluation (PESTO)** — Full MG/EG interpolation using a phase score derived from remaining material. 12 piece-square tables (Rofchade PESTO values), separate MG/EG material values. _Both engines._
- [x] **Passed pawn rank scaling** — Bonuses now scale with advancement rank: `MG [0,5,10,20,35,55,80,0]`, `EG [0,15,25,50,80,125,175,0]`. _Both engines._
- [x] **Gate king safety on game phase** — King safety penalties scale by `phase/24`; fade to zero in endgames where the king EG PST takes over. _Both engines._
- [x] **Endgame King PST** — Dedicated EG king table rewards centralization; blended via tapered eval. _Both engines._
- [x] **Rook on open / semi-open file** — +20 (open), +10 (semi-open). _Both engines._
- [x] **Rook on 7th rank** — +20 bonus per rook on rank 7 (rank 2 for Black). _Both engines._
- [ ] **Two-sided mobility** — Currently only the side-to-move's legal move count is used. Differencing both sides gives a more accurate positional bonus. _Both engines._
- [ ] **Backward pawn penalty** — Penalise pawns with advanced neighbours but no rear support on adjacent files; fills the last gap in pawn structure eval. Est. +5–10 Elo. _Both engines._
- [ ] **Connected rooks bonus** — Reward rooks that share a rank/file with no pieces between them (+8 cp each). _Both engines._
- [ ] **Attack-unit king safety** — Replace the current pawn-shield heuristic with a weighted attacker-count scale (0–63 danger units); each piece type attacking the king zone adds a type-specific danger score mapped through a non-linear penalty table. Est. +15–25 Elo. _Both engines._
- [ ] **Texel tuning** — Run gradient-descent tuning on a large self-play or annotated position set to optimise all evaluation weights simultaneously instead of hand-tuning. Est. +30–60 Elo. _Both engines._
- [ ] **Mop-up evaluation** — For elementary K+R/Q vs K positions, add a bonus proportional to how close the losing king is to the corner and how close the winning king is to the losing king; prevents aimless shuffling. _Both engines._

### Tier 2 — Search improvements

- [ ] **SEE (Static Exchange Evaluation)** — Simulate full capture sequences to score exchanges; use for capture ordering in quiescence and to skip losing captures entirely. Est. +20 Elo. _Both engines._
- [ ] **Internal Iterative Deepening (IID)** — When the TT has no hash move at depth ≥ 4, run a shallower search first to find one; improves move ordering cheaply. Est. +10–15 Elo. _Both engines._
- [ ] **Razoring** — At depth 1–3, if `static_eval + margin ≤ alpha`, drop directly into quiescence rather than searching further. Est. +10 Elo. _Both engines._
- [ ] **Adaptive LMR** — Scale reductions by history score and move characteristics (capture vs quiet, killer vs non-killer) instead of the current fixed depth/index formula. Est. +10–20 Elo. _Both engines._
- [ ] **Improved aspiration windows** — Use pre-tuned step sequences (±30 → ±130 → ±530 → ∞) instead of simple doubling on fail; reduces costly re-searches on sharp positions. _Both engines._
- [ ] **TT aging / generation counter** — Maintain a global generation counter incremented each `ucinewgame`; prefer replacing entries from older generations over deeper ones so stale lines do not pollute fresh searches. _C++ engine._
- [ ] **Countermove heuristic** — Index a quiet move that caused a beta-cutoff by the previous opponent move; score it just below killer moves in ordering. Est. +5–10 Elo. _Both engines._
- [ ] **Continuation history tables** — Extend the history heuristic to 2-ply pairs `(prev_move, cur_move)` for finer-grained ordering of quiet moves. _Both engines._
- [ ] **Staged / lazy move generation** — Generate captures first and only produce quiet moves if no early cutoff is found; avoids the full move-gen cost when a capture scores above beta. _C++ engine._
- [ ] **Null move verification search** — After a null-move cutoff, verify with a reduced search in suspected zugzwang positions (pawn-only endgames) to avoid missing key defensive moves. _Both engines._
- [ ] **Repetition detection** — Track Zobrist hashes in a stack through the search; detect 3-fold repetition explicitly. `bulletchess DRAW` may miss mid-search repetitions. _Python only._

### Tier 3 — Larger effort

- [ ] **NNUE evaluation (Python engine)** — load `omblecavalier.nnue`, expose `eval_cp(fen)` via `nnue.py`, replace `evaluateBoard` with NNUE; fall back to HCE when no `.nnue` file is present. Est. +100–200 Elo. _Python only._
- [ ] **NNUE evaluation (C++ engine)** — load `.nnue` binary in `nnue.cpp`, implement forward pass 768→256→32→1 with ClippedReLU, replace `evaluateBoard()` with NNUE; HCE fallback. Add `nnue.cpp` to CMakeLists. Est. +100–200 Elo. _C++ only._
- [ ] **Singular extensions** — Detect when one move is singularly better than all alternatives (re-search with reduced beta); extend that move's search by 1 ply. Est. +20–30 Elo. _C++ engine._
- [ ] **Pondering (think on opponent's time)** — Support `go ponder` / `ponderhit` / `stop`; keep searching the expected reply during the opponent's clock and hit the ground running if the prediction is correct. `ponder: true` is already set in `config.yml` so lichess-bot will send these commands — the engine just doesn't handle them yet. Implementation notes: (1) add a global `std::atomic<bool> g_stop` flag checked in `negamax`/`quiesce` alongside the time check; (2) run `findBestMoveIterative` in a `std::thread` so `main.cpp`'s stdin loop can still read `stop`/`ponderhit` while the search runs; (3) on `stop`, set `g_stop = true` and join the thread; (4) on `ponderhit`, stop the ponder search, restart immediately with real time limits (TT is warm); (5) report `bestmove <m> ponder <pm>` where `<pm>` is `pv[1]` (predicted opponent reply). Hit rate ~50–60 % in practice, effectively doubling thinking time on those moves — especially valuable on slow hardware. Est. +30–60 Elo. _C++ engine (Python engine would need threading too)._
- [ ] **Lazy SMP (multi-threaded search)** — Spin up N threads each running independent iterative-deepening searches on the same position, all sharing the same transposition table; near-linear Elo scaling up to ~8 threads with minimal synchronisation overhead. Implementation notes: (1) make TT entries use `std::atomic` stores/loads (relaxed memory order is sufficient — a torn read at worst wastes one node); (2) each helper thread starts its ID loop at a slightly different depth offset (thread 0 starts at 1, thread 1 at 2, etc.) to reduce redundant work and diversify the search; (3) all threads share killer/history tables — use `std::atomic<int>` for history or accept benign races; (4) the main thread drives time management and calls `g_stop = true` when the clock expires; helper threads exit on the same flag; (5) collect the best move from whichever thread completed the deepest iteration. The `Threads: 4` UCI option is already wired in `config.yml` but currently does nothing for the homemade engine — this makes it real. Est. +50–80 Elo on 4 cores. _C++ engine._
- [ ] **Improved time management** — Replace the current naive formula (`(remaining - 1s) / movesToGo + 0.5 × increment`) with a two-limit model used by all modern engines: a *soft limit* (target time, stop after completing a depth iteration) and a *hard limit* (absolute ceiling, stop mid-search). Additional improvements: (1) extend time on aspiration fail-lows — if the window fails low we may be in trouble and need more time to find the saving move; (2) "easy move" detection — if the same move was best across the last 4+ depth iterations by a large margin, play it instantly without finishing the current depth; (3) better `movesToGo` estimate — use `max(20, 50 - moveNumber)` for the opening/middlegame and tighten to `max(10, 30 - moveNumber)` in the endgame (fewer pieces = fewer moves left); (4) scale allocated time up slightly in complex positions (many legal moves, no TT hit at root). Est. +20–40 Elo, especially in bullet where flagging is common. _Both engines._
- [ ] **Endgame bitbases (KPK / KBNK / KBBK)** — Compile small perfect-play bitbases for common 3-4 piece endings; probe them in the search instead of relying on evaluation heuristics. _Both engines._
- [ ] **Syzygy Tablebase direct integration** — Engine-side probe for ≤7-piece positions for instant WDL+DTZ. Online EGTB already configured in lichess-bot. Est. +50–100 Elo in endgames. _Both engines._
- [ ] **Cython compilation for Python engine** — Rename `omble_cavalier.py` to `.pyx`, add `cdef int` type annotations for hot locals in `evaluate_board_fast` and `negamax`, and add a `setup.py` build step + update the PyInstaller `.spec`. Expected 3–10× speedup on the pure-Python portions (eval arithmetic, TT access, search overhead). _Python only._
- [ ] **Native null move** — Current FEN-string flip works but allocates a new Board on every null move attempt. Investigate bulletchess internals or a workaround. _Python only._
- [ ] **Pawn hash table** — Cache pawn structure scores independently of the main TT. _Both engines._
- [ ] **Multi-PV output** — Report multiple best lines for analysis mode. _Both engines._
- [ ] **Built-in benchmarking** — Port the C++ `bench` command to Python. _Python only._

---

## Known Issues

### Open

_None._

### Fixed

- ~~**Python — Repetition detection incomplete**~~ Fixed: `board.__hash__()` in bulletchess includes the halfmove clock, so identical positions at different move counts had different hashes and `board in DRAW` missed mid-search repetitions. Added `position_key()` (normalises halfmove/fullmove before hashing) and a `rep_counts` dict threaded through the search. Root is counted twice — once from game history, once as the active search anchor — so any branch cycling back scores as a draw.
- ~~**Python — Null move via FEN is slow**~~ Fixed: replaced FEN-string manipulation + `Board.from_fen()` with `board.copy()` followed by direct attribute mutation (`board.turn`, `board.en_passant_square`). ~5× faster per null-move attempt.
- ~~**C++ — PST indexing inverted**~~ Fixed: White pieces now use `mirror(sq)` and Black pieces use `sq` directly to correctly map chess.hpp's a1=0 convention to the PST's a8=0 convention. A White pawn near promotion was previously getting a *penalty* instead of a +50 bonus; a castled king at g1 was scored -40 instead of +30.
- ~~**C++ — `position fen` command not handled**~~ Fixed.
- ~~**C++ — Hash move not used for move ordering**~~ Fixed: TT lookup now always extracts the best move and passes it to move ordering, even when depth is insufficient for a score cutoff.
- ~~**C++ — Check bonus dead code in move ordering**~~ Fixed: moved before the history heuristic branch so it actually fires.
- ~~**C++ — TT used `unordered_map`**~~ Fixed: replaced with a 1M-entry fixed-size array for O(1) cache-friendly access (~24 MB).
- ~~**C++ — `ucinewgame` only cleared TT**~~ Fixed: now also resets killer moves and history heuristic.
- ~~**Python — `ucinewgame` did not clear transposition table**~~ Fixed.
- ~~**Python — Quiescence search returned `beta` instead of `stand_pat` on cutoff**~~ Fixed.
- ~~**Python — Mobility recalculated inside `evaluate_board`**~~ Fixed: legal moves generated once per node.
- ~~**Python — No killer or history heuristics**~~ Fixed.
- ~~**Python — No PST, pawn structure, or king safety**~~ Fixed: all evaluation terms ported from C++.
- ~~**Python — No null move pruning**~~ Fixed: implemented via FEN turn-swap.
- ~~**Python — No aspiration windows**~~ Fixed.
- ~~**Python — Poor time management**~~ Fixed: matches C++ formula (move number, increment, reserve).
- ~~**Both — Passed pawn detection included own pawns**~~ Fixed: the front-span check previously used `allPawns` (own + opponent), so a doubled pawn's rear pawn was always marked as not passed. Now checks only opponent pawns, matching the standard definition.

---

## License

Licensed under the AGPLv3. See [LICENSE](LICENSE).
