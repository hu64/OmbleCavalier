# ♞ OmbleCavalier

**OmbleCavalier** is a UCI-compatible chess engine written in Python. It features a classic **Negamax** search with quiescence pruning and evaluation heuristics, along with a basic **random-move UCI engine** for testing. The engine is designed to run in standard UCI-compatible interfaces and supports PyInstaller for creating executables.

## 🚀 Features

- Supports the UCI protocol
- Negamax search with:
  - Alpha-beta pruning
  - Quiescence search
  - Move ordering heuristics
  - (Optional) Transposition table
- Lightweight evaluation function (material, optional PSTs)
- Bonus: Random-move UCI engine for benchmarking
- Puzzle-based testing with Pytest
- Project managed with Poetry and `pyproject.toml`
- Build executable with PyInstaller

## 🗂️ Project Structure

```
omblecavalier/
├── omblecavalier/
│   └── engines/
│       ├── omble_cavalier.py       # Main negamax engine
│       └── random_engine.py        # Random move engine (UCI-compatible)
├── tests/
│   └── test_puzzles.py             # Pytest unit tests with tactical positions
├── pyproject.toml                  # Poetry dependency and package config
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

- [ ] Iterative deepening + time-aware search
- [ ] Endgame tablebase integration
- [ ] Opening book (Polyglot)
- [ ] GUI interface or web viewer
- [ ] More advanced evaluation (tropism, king safety, etc.)
- [ ] Integration with Lichess as a playing bot

## 📜 License

This project is licensed under the MIT License.  
Use, modify, and share freely.

## 👤 Author

**Hughes Perreault**  
GitHub: https://github.com/hu64