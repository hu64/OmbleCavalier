# ♞ OmbleCavalier

<img src="https://i.imgur.com/IITkYpY.png" alt="OmbleCavalier Profile" width="120" style="border-radius:8px; margin-bottom:8px;" />

Challenge me on lichess.org: https://lichess.org/@/OmbleCavalier

**OmbleCavalier** is a UCI-compatible chess engine written in Python. It features a classic **Negamax** search with quiescence pruning and evaluation heuristics, along with a basic **random-move UCI engine** for testing. The engine is designed to run in standard UCI-compatible interfaces and supports PyInstaller for creating executables.

## 🚀 Features

- Supports the UCI protocol
- **Iterative deepening** with **aspiration windows**
- **Negamax** search with:
  - Alpha-beta pruning
  - Null move pruning (R=3)
  - Late Move Reduction (LMR) for quiet moves
  - Check extension — extends search by 1 ply when in check
  - Futility pruning at depth 1 to skip losing quiet moves
  - Quiescence search
  - Killer move & history heuristics for move ordering
  - MVV-LVA capture ordering
  - Transposition table
  - Repetition detection
- [Opening book (Polyglot, The Baron)](https://www.chessprogramming.net/new-version-of-the-baron-v3-43-plus-the-barons-polyglot-opening-book/)
- **Tapered PESTO evaluation** (middlegame/endgame piece-square tables) with:
  - King safety (pawn shield, open files, pawn storm)
  - Pawn structure (doubled, isolated, passed pawns with rank-scaled bonuses)
  - Rook on open/semi-open file bonuses
  - Bishop pair bonus
  - Mobility
- Random-move UCI engine for benchmarking
- Puzzle-based testing with Pytest
- Project managed with `pyproject.toml`
- Build executable with PyInstaller

## 🗂️ Project Structure

```
omblecavalier/
├── omblecavalier/
│   └── engines/
│       ├── omble_cavalier.py       # Main negamax engine
│       └── uci_random_moves.py     # Random move engine (UCI-compatible)
├── tests/
│   ├── test_puzzles.py             # Pytest unit tests with tactical positions
│   └── test_eval.py                # Pytest unit tests for evaluation functions
├── pyproject.toml                  # Dependency and package config
├── README.md                       # Project documentation
└── dist/                           # Built executable (via PyInstaller)
```

## ⚙️ Setup Instructions

### 1. Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Install the project and dependencies

```bash
git clone https://github.com/yourusername/omblecavalier.git
cd omblecavalier
poetry install
```

## 🧪 Run Tests (Tactical Puzzles)

Unit tests using Pytest and FEN puzzle positions:

```bash
poetry run pytest -s
```

Each test prints:

- A FEN position
- Expected best move (mate, material win, etc.)
- The engine’s evaluation and response

Sample from `tests/test_puzzles.py`:

```python
("kbK5/pp6/1P6/8/8/8/R7/8 w - - 0 2", "Mate in 2", "a2a6"),
```

## 🔨 Build Executable (with PyInstaller)

Enter Poetry's virtualenv:

```bash
poetry shell
```

Then build:

```bash
pyinstaller --onefile --distpath engines omblecavalier/engines/omble_cavalier.py --collect-all bulletchess
```

The resulting binary is located in `engines/omblecavalier`.

## ♟️ UCI Compatibility

OmbleCavalier supports the Universal Chess Interface (UCI), and can be run using tools such as:

- CuteChess-cli
- Banksia GUI
- Lichess Bot API

Example match (engine vs engine):

```bash
cutechess-cli \
-engine cmd="engines/omble_cavalier" \
-engine cmd="engines/uci_random_moves" \
-each proto=uci tc=40/60 \
-rounds 100
```

## 🛠️ Future Enhancements

- [ ] Endgame tablebase integration
- [ ] Piece tropism (king proximity bonuses)
- [ ] Syzygy endgame tablebases

## 📜 License

This project is licensed under the MIT License.  
Use, modify, and share freely.

## 👤 Author

**Hughes Perreault**  
GitHub: https://github.com/hu64
