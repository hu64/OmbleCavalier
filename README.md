# OmbleCavalier Chess Engines

Two UCI-compatible chess engines — one in C++, one in Python — built to run as bots on [Lichess](https://lichess.org) via [lichess-bot](https://github.com/lichess-bot-devs/lichess-bot).

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
| **Evaluation** | Material values |
| | Piece-square tables (6 tables) |
| | Pawn structure (doubled, isolated, passed) |
| | King safety (pawn shield, open files) |
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

Uses [bulletchess](https://github.com/zedeckj/bulletchess) for fast board representation and move generation (Rust-backed). The search is identical in structure to the C++ engine: **iterative deepening negamax** with **alpha-beta pruning**, aspiration windows, null move pruning, and **Late Move Reduction**. Evaluation uses precomputed per-square lookup tables (`_W_TABLES`, `_B_TABLES`) that merge material + PST values to minimize per-node arithmetic. Quiescence search uses a fast evaluation path (material + PST + bishop pair only) to avoid calling expensive pawn structure code on every tactical node.

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
| **Evaluation** | Precomputed material + PST lookup tables |
| | Pawn structure (doubled, isolated, passed) |
| | King safety (pawn shield, open files) |
| | Bishop pair bonus |
| | Mobility |
| | Two-tier eval (fast in quiescence, full in main search) |
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

```bash
# From repo root
uv run pytest src/OmbleCavalierPython/tests/ -v
```

### Build executable

```bash
uv run pyinstaller --onefile \
  --distpath src/OmbleCavalierPlusPlus/engines \
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

### Tier 1 — Quick wins (~1–2h each, high return)

- [x] **Late Move Reduction (LMR)** — Quiet, non-killer, non-check moves after index 2 get depth-1 or depth-2 reduction with re-search on fail-high. _Both engines._
- [ ] **Futility Pruning** — At depth 1, if `static_eval + 200 <= alpha`, skip the move entirely. ~5 lines, est. +25 Elo. _Both engines._
- [ ] **Principal Variation Search (PVS)** — After the first move, search with null window `(-alpha-1, -alpha)` and re-search full window only on fail-high. Pairs naturally with LMR. Est. +25 Elo. _Both engines._
- [ ] **Delta Pruning in Quiescence** — Skip captures where `stand_pat + piece_value + margin <= alpha`. Prunes useless captures cheaply. Est. +10 Elo. _Both engines._
- [ ] **Endgame King PST** — Add a second king table where the king centralizes; swap based on remaining material. Est. +20 Elo. _Both engines._

### Tier 2 — Evaluation improvements (~1–3h each)

- [ ] **Rook on open / semi-open file** — Rook with no friendly pawns on its file: +15 (open), +10 (semi-open). Est. +25 Elo. _Both engines._
- [ ] **Passed pawn rank scaling** — Current flat +20 bonus should scale with advancement rank (e.g. `[0,10,15,20,30,50,80,0]`). Est. +15 Elo. _Both engines._
- [ ] **Gate king safety on game phase** — Suppress pawn shield penalty when little material remains (king should be active in endgame). Est. +10 Elo. _Both engines._
- [ ] **Rook on 7th rank** — +20 bonus per rook on rank 7 (rank 2 for Black). Est. +10 Elo. _Both engines._
- [ ] **Two-sided mobility** — Currently only the side-to-move's legal move count is used. Differencing both sides gives a more accurate positional bonus. _Both engines._
- [ ] **Tapered evaluation** — Blend all PSTs and king safety between midgame/endgame sets using a material phase score. Est. +25 Elo. _Both engines._

### Tier 2 — Search improvements

- [ ] **SEE (Static Exchange Evaluation)** — Replace MVV-LVA with a full capture-sequence simulation to determine if a trade is winning or losing. Est. +20 Elo. _Both engines._
- [ ] **Repetition detection** — Track Zobrist hashes in a stack through the search; detect 3-fold repetition explicitly. `bulletchess DRAW` may miss mid-search repetitions. _Python only._
- [ ] **Countermove Heuristic** — Store the move causing a beta cutoff indexed by the previous move; give it a bonus in ordering just below killers. Est. +5 Elo. _Both engines._

### Tier 3 — Larger effort

- [ ] **Syzygy Tablebase direct integration** — Engine-side probe for ≤7-piece positions for instant WDL+DTZ. Online EGTB already configured in lichess-bot. Est. +50–100 Elo in endgames. _Both engines._
- [ ] **Native null move** — Current FEN-string flip works but allocates a new Board on every null move attempt. Investigate bulletchess internals or a workaround. _Python only._
- [ ] **Pawn hash table** — Cache pawn structure scores independently of the main TT. _Both engines._
- [ ] **Multi-PV output** — Report multiple best lines for analysis mode. _Both engines._
- [ ] **Built-in benchmarking** — Port the C++ `bench` command to Python. _Python only._

---

## Known Issues

### Open

1. **Python — Repetition detection incomplete**
   - `board in DRAW` from bulletchess may not catch all repetitions mid-search.
   - **Fix**: Track board hashes in a stack and detect three-fold repetition explicitly.

2. **Python — Null move via FEN is slow**
   - Null move is implemented by flipping the turn in the FEN string and creating a new `Board`. Functionally correct but slower than a native make/unmake null move.
   - **Fix**: Investigate bulletchess internals or implement a workaround.

### Fixed

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

---

## License

Licensed under the AGPLv3. See [LICENSE](LICENSE).
