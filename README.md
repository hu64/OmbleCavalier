<div align="center">

  ![lichess-bot](https://github.com/lichess-bot-devs/lichess-bot-images/blob/main/lichess-bot-icon-400.png)

  <h1>lichess-bot</h1>

  A bridge between [lichess.org](https://lichess.org) and bots.
  <br>
  <strong>[Explore lichess-bot docs »](https://github.com/lichess-bot-devs/lichess-bot/wiki)</strong>
  <br>
  <br>
  [![Python Build](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/python-build.yml/badge.svg)](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/python-build.yml)
  [![Python Test](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/python-test.yml/badge.svg)](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/python-test.yml)
  [![Mypy](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/mypy.yml/badge.svg)](https://github.com/lichess-bot-devs/lichess-bot/actions/workflows/mypy.yml)

</div>

## Overview

[lichess-bot](https://github.com/lichess-bot-devs/lichess-bot) is a free bridge
between the [Lichess Bot API](https://lichess.org/api#tag/Bot) and chess engines.

With lichess-bot, you can create and operate a bot on lichess. Your bot will be able to play against humans and bots alike, and you will be able to view these games live on lichess.

See also the lichess-bot [documentation](https://github.com/lichess-bot-devs/lichess-bot/wiki) for further usage help.

## Features
Supports:
- Every variant and time control
- UCI, XBoard, and Homemade engines
- Matchmaking (challenging other bots)
- Offering Draws and Resigning
- Participating in tournaments
- Accepting move takeback requests from opponents
- Saving games as PGN
- Local & Online Opening Books
- Local & Online Endgame Tablebases

Can run on:
- Python 3.10 and later
- Windows, Linux and MacOS
- Docker

## Included Engines

This repository includes two chess engines built for this bot:

### ♞ OmbleCavalierPlusPlus (C++)
A modern C++ chess engine with UCI protocol support.

**Features:**
- UCI protocol compatibility
- Polyglot opening book support
- Iterative deepening with alpha-beta pruning
- Aspiration windows
- Transposition table (hash table)
- Killer move & history heuristics
- MVV-LVA capture ordering
- Piece-square tables (PST)
- Pawn structure analysis (doubled, isolated, passed pawns)
- King safety (pawn shield, open files)
- Bishop pair bonus
- Null move pruning
- Bitboard-based fast evaluation
- Built-in puzzle test suite
- Benchmarking utility

**Build Requirements:**
- C++20 compiler (GCC, Clang, or MSVC)
- CMake 3.10+
- Disservin's chess.hpp library (included)

**Build & Run:**
```bash
cd src/OmbleCavalierPlusPlus
mkdir build && cd build
cmake ..
make
./omble_cavalier++
```

### ♞ OmbleCavalier (Python)
A UCI-compatible chess engine written in Python with negamax search, now at feature parity with the C++ engine.

**Features:**
- UCI protocol support (`position fen`, `wtime`/`btime`/`winc`/`binc`)
- Negamax search with alpha-beta pruning
- Iterative deepening with aspiration windows
- Quiescence search
- Null move pruning (via FEN turn-swap)
- Killer move & history heuristics
- MVV-LVA capture ordering
- Piece-square tables (PST) — same tables as C++
- Pawn structure analysis (doubled, isolated, passed pawns)
- King safety (pawn shield, open files)
- Bishop pair bonus
- Adaptive time management (move number, increment, reserve)
- Transposition table
- Polyglot opening book support
- Random-move engine for testing
- Puzzle-based testing with pytest

**Setup & Run:**
```bash
cd src/OmbleCavalierPython
poetry install
poetry run python omblecavalier/engines/omble_cavalier.py
```

**Build Executable:**
```bash
poetry shell
pyinstaller --onefile --distpath engines omblecavalier/engines/omble_cavalier.py
```

## Elo Improvement Roadmap

Both engines are at feature parity. Future improvements apply to both unless noted.

### High Priority

- [x] **Late Move Reduction (LMR)** — Quiet, non-killer, non-check moves after index 2 get depth-1 or depth-2 reduction with re-search on fail-high. _Both engines._
- [ ] **Principal Variation Search (PVS)** — Zero-window search after first move. Est. +20–40 Elo. _Both engines._
- [ ] **Futility / Razoring Pruning** — Prune clearly bad nodes near leaf. Est. +30–50 Elo. _Both engines._
- [ ] **SEE (Static Exchange Evaluation)** — Replace MVV-LVA with accurate capture ordering. Est. +15–30 Elo. _Both engines._
- [ ] **Endgame-specific PSTs (King activity)** — King should centralize in endgame. Est. +15–25 Elo. _Both engines._

### Medium Priority

- [ ] **Repetition detection in Python** — `bulletchess` `DRAW` may not catch all repetitions; add explicit repetition tracking. _Python only._
- [ ] **Native null move in Python** — Current FEN-based approach works but is slower than a native null move; consider patching bulletchess or using a workaround. _Python only._
- [ ] **Endgame Tablebase (Syzygy) direct integration** — Online EGTB already configured in lichess-bot; add direct engine-side probe for faster response. Est. +50–100 Elo in endgames. _Both engines._
- [ ] **Tapered evaluation (midgame/endgame blend)** — PSTs and king safety should shift as material comes off the board. Est. +20–40 Elo. _Both engines._
- [ ] **Pawn hash table** — Cache pawn structure scores independently. _Both engines._

### Lower Priority / Polish

- [ ] **Built-in benchmarking for Python** — Port the C++ `bench` command. _Python only._
- [ ] **Puzzle test suite for C++** — Expand puzzle coverage and CI integration. _C++ only._
- [ ] **Multi-PV output** — Report multiple best lines for analysis mode. _Both engines._

## Known Issues

### Remaining (Open)

1. **Python — Repetition detection incomplete**
   - `board in DRAW` from bulletchess may not catch all repetitions mid-search.
   - The 50-move rule is now handled via `board.halfmove_clock >= 100`.
   - **Fix**: Track board hashes in a stack and detect three-fold repetition explicitly.

2. **Python — Null move via FEN is slow**
   - The null move is implemented by flipping the turn in the FEN string and creating a new `Board`. This works but is slower than a native make/unmake null move.
   - **Fix**: Contribute null-move support to bulletchess, or implement a workaround at the engine level.

### Fixed

- ~~**C++ — PST indexing inverted**~~ Fixed: White pieces now use `mirror(sq)` and Black pieces use `sq` directly to correctly map chess.hpp's a1=0 convention to the PST's a8=0 convention. A White pawn near promotion was previously getting a *penalty* (rank-2 PST value) instead of a +50 bonus.
- ~~**C++ — `position fen` command not handled**~~ Fixed: engine can now accept arbitrary FEN positions with or without a moves list.
- ~~**C++ — Hash move not used for move ordering**~~ Fixed: TT lookup now always extracts the best move and passes it to `orderMovesInPlace`, even when depth is insufficient for a score cutoff.
- ~~**C++ — Check bonus dead code in move ordering**~~ Fixed: moved before the history heuristic branch so it actually fires.
- ~~**C++ — TT used `unordered_map`**~~ Fixed: replaced with a 1M-entry fixed-size array for O(1) cache-friendly access (~24 MB).
- ~~**C++ — `ucinewgame` only cleared TT**~~ Fixed: now also resets killer moves and history heuristic via `resetSearchState()`.
- ~~**Python — `ucinewgame` did not clear transposition table**~~ Fixed: `reset_search_state()` clears TT, killers, and history on every new game and search.
- ~~**Python — Quiescence search returned `beta` instead of `stand_pat` on cutoff**~~ Fixed: now returns the correct `stand_pat` / `score` value.
- ~~**Python — Mobility recalculated inside `evaluate_board`**~~ Fixed: legal moves are generated once per node and the count is passed to `evaluate_board`.
- ~~**Python — No killer or history heuristics**~~ Fixed: both implemented matching C++.
- ~~**Python — No PST, pawn structure, or king safety**~~ Fixed: all evaluation terms ported from C++.
- ~~**Python — No null move pruning**~~ Fixed: implemented via FEN turn-swap.
- ~~**Python — No aspiration windows**~~ Fixed: implemented in iterative deepening loop.
- ~~**Python — Poor time management (no increment, no move number)**~~ Fixed: matches C++ formula.
- ~~**Python — `position fen` command not handled**~~ Fixed.
- ~~**Python — `winc`/`binc` not parsed**~~ Fixed.

## Steps
1. [Install lichess-bot](https://github.com/lichess-bot-devs/lichess-bot/wiki/How-to-Install)
2. [Create a lichess OAuth token](https://github.com/lichess-bot-devs/lichess-bot/wiki/How-to-create-a-Lichess-OAuth-token)
3. [Setup the engine](https://github.com/lichess-bot-devs/lichess-bot/wiki/Setup-the-engine)
4. [Configure lichess-bot](https://github.com/lichess-bot-devs/lichess-bot/wiki/Configure-lichess-bot)
5. [Upgrade to a BOT account](https://github.com/lichess-bot-devs/lichess-bot/wiki/Upgrade-to-a-BOT-account)
6. [Run lichess-bot](https://github.com/lichess-bot-devs/lichess-bot/wiki/How-to-Run-lichess%E2%80%90bot)

## Advanced options
- [Create a homemade engine](https://github.com/lichess-bot-devs/lichess-bot/wiki/Create-a-homemade-engine)
- [Add extra customizations](https://github.com/lichess-bot-devs/lichess-bot/wiki/Extra-customizations)

<br />

## Acknowledgements
Thanks to the Lichess team, especially T. Alexander Lystad and Thibault Duplessis for working with the LeelaChessZero team to get this API up. Thanks to [Niklas Fiekas](https://github.com/niklasf) and his [python-chess](https://github.com/niklasf/python-chess) code which allows engine communication seamlessly.

## License
lichess-bot is licensed under the AGPLv3 (or any later version at your option). Check out the [LICENSE file](https://github.com/lichess-bot-devs/lichess-bot/blob/master/LICENSE) for the full text.

## Citation
If this software has been used for research purposes, please cite it using the "Cite this repository" menu on the right sidebar. For more information, check the [CITATION file](https://github.com/lichess-bot-devs/lichess-bot/blob/master/CITATION.cff).
