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

This repository includes two example chess engines that can be used with lichess-bot:

### ♞ OmbleCavalierPlusPlus (C++)
A modern C++ chess engine with UCI protocol support.

**Features:**
- UCI protocol compatibility
- Polyglot opening book support
- Iterative deepening with alpha-beta pruning
- Transposition table (hash table)
- Killer move & history heuristics
- MVV-LVA and check bonuses for move ordering
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
A UCI-compatible chess engine written in Python with negamax search.

**Features:**
- UCI protocol support
- Negamax search with alpha-beta pruning
- Quiescence search
- Move ordering heuristics
- Transposition table
- Polyglot opening book support
- Lightweight evaluation (material, mobility)
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

### Feature Parity First (Highest Priority)

To keep both engines aligned, these features should be implemented across both:

**Python engine needs to catch up:**
1. **Iterative Deepening** — C++ has it; Python uses fixed depth. Estimated +30-40 Elo and enables time management
2. **Killer Move Heuristics** — C++ has it; improves move ordering. Estimated +20-30 Elo
3. **History Heuristics** — C++ has it; refines move ordering. Estimated +15-25 Elo
4. **MVV-LVA Move Ordering** — C++ has it; prioritizes captures. Estimated +10-20 Elo
5. **Check Detection in Move Ordering** — C++ has bonus for checks; add to Python. Estimated +10-15 Elo
6. **Null Move Pruning** — C++ has it; Python doesn't. Estimated +25-35 Elo
7. **Built-in Benchmarking Utility** — C++ has it; add to Python for testing parity


### Additional Elo Improvements (After Parity)

Once both engines have feature parity, these optimizations apply to both:

1. **Late Move Reduction (LMR)** — Reduce search depth for late quiet moves. Estimated +50-80 Elo
2. **Aspiration Windows** — Use tight alpha-beta windows based on previous iteration. Estimated +20-40 Elo
3. **Razoring/Futility Pruning** — Prune obviously bad positions. Estimated +30-50 Elo (C++ only for now; Python needs iterative deepening first)
4. **Advanced Evaluation** — Pawn structure analysis, king safety, tropism. Estimated +40-60 Elo

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
