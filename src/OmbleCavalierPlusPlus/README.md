# ♞ OmbleCavalierPlusPlus
*A modern C++ Chess Engine*

<p align="center">
  <img src="https://i.imgur.com/zhaKbyY.png" alt="OmbleCavalierPlusPlus anime fish chess" width="250"/>
</p>

---
## Play me on Lichess.org

https://lichess.org/@/OmbleCavalierPP

## ✨ Features
- ♟️ **UCI protocol** support (compatible with most chess GUIs)
- 📖 **Polyglot opening book** support
- 🔍 **Iterative deepening** with **aspiration windows**
- ✂️ **Alpha-beta pruning** with **null move pruning** (R=3)
- ⏩ **Late Move Reduction (LMR)** for quiet moves
- 🛡️ **Check extension** — extends search by 1 ply when in check
- 🔪 **Futility pruning** at depth 1 to skip losing quiet moves
- 🗂️ **Transposition table** with move-score flags
- ⚔️ **Killer move & history heuristics** for move ordering
- 🎯 **MVV-LVA** and check bonuses for tactical move ordering
- ⚡ **Tapered PESTO evaluation** (middlegame/endgame piece-square tables)
- 👑 **King safety** (pawn shield, open files, pawn storm)
- 🏰 **Pawn structure** (doubled, isolated, passed pawns with rank-scaled bonuses)
- 🏛️ **Rook on open/semi-open file** bonuses
- 💡 **Bishop pair** bonus
- 🧩 Built-in **puzzle test suite**
- 📊 **Benchmarking utility**

---

## 🛠️ Build Instructions

### ✅ Prerequisites
- C++20 compiler (GCC, Clang, or MSVC)
- CMake 3.10+
- [Disservin’s chess.hpp library](https://github.com/Disservin/chess.hpp) (included as submodule or vendored)

### ⚙️ Build
If using submodules, initialize them first:
```bash
git clone https://github.com/yourusername/OmbleCavalierPlusPlus.git
cd OmbleCavalierPlusPlus
git submodule update --init --recursive
mkdir build && cd build
cmake ..
make
```

---

## 🚀 Usage

### Run as a UCI Engine
Use with any UCI-compatible GUI (e.g., Arena, CuteChess, Banksia):
```bash
./omble_cavalier++
```

### Run Puzzle Tests
```bash
./omble_cavalier++ 
puzzletest
```

### Benchmarking
```bash
./omble_cavalier++ 
benchmarking
```

---

## 📂 Project Structure
```
src/
 ├─ main.cpp        # UCI loop and entry point
 ├─ search.cpp/hpp  # Search algorithms (negamax, quiesce, iterative deepening)
 ├─ eval.cpp/hpp    # Evaluation functions and piece-square tables
 ├─ tt.cpp/hpp      # Transposition table (hash table)
 ├─ book.cpp/hpp    # Polyglot opening book support
 ├─ puzzles.cpp/hpp # Puzzle test suite
 └─ utils.cpp/hpp   # Bitboard and move ordering utilities

include/
 └─ chess.hpp       # Disservin's chess library
```

---

## ♟️ Lichess Integration
You can run **OmbleCavalierPlusPlus** as a Lichess bot.  
See the [Lichess Bot API](https://lichess.org/api#operation/botAccountUpgrade) for details.

---

## 📜 License
[MIT License](LICENSE)

---

## 🙏 Acknowledgements
- [Disservin/chess.hpp](https://github.com/Disservin/chess.hpp) — Chess library  
- [Polyglot book format](https://www.chessprogramming.org/Polyglot)  
- [Lichess.org](https://lichess.org/) — Platform & API
