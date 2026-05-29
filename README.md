# OmbleCavalier Chess Engines

[![Engine CI](https://github.com/hu64/OmbleCavalier/actions/workflows/engine-ci.yml/badge.svg)](https://github.com/hu64/OmbleCavalier/actions/workflows/engine-ci.yml)

Two UCI-compatible chess engines — one in C++, one in Python — built to run as bots on [Lichess](https://lichess.org) via [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot).

> **Challenge them on Lichess:**
> [OmbleCavalier (Python)](https://lichess.org/@/OmbleCavalier) · [OmbleCavalierPP (C++)](https://lichess.org/@/OmbleCavalierPP)

---

## Lichess Rating History

| Date | Engine | Format | Rating | Games |
|------|--------|--------|--------|-------|
| 2026-05-28 | OmbleCavalier (Python) | Bullet | 1860 | 628 |
| 2026-05-28 | OmbleCavalier (Python) | Blitz | 1883 | 728 |
| 2026-05-28 | OmbleCavalier (Python) | Rapid | 1764 | 19 |
| 2026-05-28 | OmbleCavalierPP (C++) | Bullet | 2079 | 7,772 |
| 2026-05-28 | OmbleCavalierPP (C++) | Blitz | 2070 | 8,065 |
| 2026-05-28 | OmbleCavalierPP (C++) | Rapid | 1858 | 979 |

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
| | Null move pruning (R=3) |
| | Late Move Reduction (LMR) |
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
| | Null move pruning (R=3, via FEN turn-swap) |
| | Late Move Reduction (LMR) |
| | Quiescence search |
| **Move ordering** | MVV-LVA capture ordering |
| | Killer move heuristic (2 per ply) |
| | History heuristic |
| **Evaluation** | PESTO tapered evaluation (MG/EG interpolation via game phase) |
| | 12 precomputed per-square lookup tables (6 MG + 6 EG) |
| | Separate MG/EG material values |
| | Pawn structure — phase-weighted (doubled, isolated, rank-scaled passed) |
| | King safety — phase-weighted (pawn shield, open files, pawn storm) |
| | Bishop pair bonus |
| | Mobility |
| | Two-tier eval (full PESTO at quiescence entry, fast PST-only inside quiescence) |
| **Infrastructure** | Dictionary-based transposition table |
| | Polyglot opening book (`gm2001.bin`) |
| | Adaptive time management |
| | `position fen` + `position startpos` |
| | Puzzle test suite (9 puzzles via pytest) |

### Environment setup

The project uses [uv](https://github.com/astral-sh/uv) for dependency management from the repo root.

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (from repo root)
uv sync
```

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

### Tier 1 — Highest priority (biggest Elo gains)

- [ ] **SEE (Static Exchange Evaluation)** — Simulate full capture sequences to determine if a trade is winning or losing. Replaces MVV-LVA in ordering, prunes bad captures in QS, enables SEE-based pruning in main search. Est. +50–100 Elo. _Both engines._
- [ ] **Fix two-sided mobility** — Currently only the side-to-move's legal move count contributes to eval; this creates a bias that cancels incorrectly across plies. Eval both sides and difference them (or use attack maps). Bug fix + est. +20–40 Elo. _Both engines._
- [ ] **LMR log table** — Current LMR uses only two reduction levels (1 or 2). Replace with a standard log-based table: `R = 0.75 + log(depth) * log(moveIndex) / 2`. Meaningful improvement past depth 8. Est. +20 Elo. _Both engines._
- [ ] **Late Move Pruning (LMP)** — At low depths (≤ 3) with no capture/check, drop moves after N quiet moves entirely rather than just reducing. Cheap to implement alongside LMR. Est. +15 Elo. _Both engines._
- [ ] **Delta Pruning in Quiescence** — Skip captures where `stand_pat + captured_value + margin <= alpha`. Avoids searching captures that cannot raise alpha. Est. +10 Elo. _Both engines._
- [ ] **Countermove Heuristic** — Store the quiet move causing a beta cutoff indexed by `[prev_from][prev_to]`; score it just below killers in ordering. ~10 lines. Est. +15 Elo. _Both engines._
- [ ] **Principal Variation Search (PVS)** — After the first move, search subsequent moves with a null window `(-alpha-1, -alpha)` and re-search full window only on fail-high. Pairs naturally with LMR. Est. +20 Elo. _Both engines._
- [x] **Late Move Reduction (LMR)** — Quiet, non-killer, non-check moves after index 2 get depth-1 or depth-2 reduction with re-search on fail-high. _Both engines._
- [x] **Futility Pruning** — At depth 1, if `static_eval + 300 <= alpha`, skip quiet non-killer moves. _Both engines._

### Tier 2 — Evaluation improvements (~1–3h each)

- [x] **Tapered evaluation (PESTO)** — Full MG/EG interpolation using a phase score derived from remaining material. 12 piece-square tables (Rofchade PESTO values), separate MG/EG material values. _Both engines._
- [x] **Passed pawn rank scaling** — Bonuses now scale with advancement rank: `MG [0,5,10,20,35,55,80,0]`, `EG [0,15,25,50,80,125,175,0]`. _Both engines._
- [x] **Gate king safety on game phase** — King safety penalties scale by `phase/24`; fade to zero in endgames where the king EG PST takes over. _Both engines._
- [x] **Endgame King PST** — Dedicated EG king table rewards centralization; blended via tapered eval. _Both engines._
- [x] **Rook on open / semi-open file** — Rook with no friendly pawns on its file: +20 (open), +10 (semi-open). _Both engines._
- [ ] **Rook on 7th rank** — +20 bonus per rook on rank 7 (rank 2 for Black). Est. +10 Elo. _Both engines._
- [ ] **Knight / bishop outposts** — Bonus for minor pieces on outpost squares (advanced, protected by a pawn, cannot be chased by opponent pawns). Est. +15 Elo. _Both engines._
- [ ] **Backward pawns** — Penalty for pawns that cannot advance and sit on a semi-open file (can't be defended by other pawns). Est. +10 Elo. _Both engines._

### Tier 2 — Search improvements

- [ ] **Repetition detection** — Track Zobrist hashes in a stack through the search; detect 3-fold repetition explicitly. `bulletchess DRAW` may miss mid-search repetitions. _Python only._

### Tier 3 — Larger effort

- [ ] **Pawn hash table** — Cache pawn structure scores independently of the main TT; pawn structure is expensive to recompute at every node. _Both engines._
- [ ] **Syzygy Tablebase direct integration** — Engine-side probe for ≤7-piece positions for instant WDL+DTZ. Online EGTB already configured in lichess-bot. Est. +50–100 Elo in endgames. _Both engines._
- [ ] **Native null move** — Current FEN-string flip works but allocates a new Board on every null move attempt. Investigate bulletchess internals or a workaround. _Python only._
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
