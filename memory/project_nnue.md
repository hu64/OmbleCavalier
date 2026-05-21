---
name: project-nnue
description: NNUE training pipeline status and key design decisions for OmbleCavalier
metadata:
  type: project
---

Started NNUE training pipeline in `src/nnue-training/`. Goal: train a shared eval model usable by both the C++ and Python engines.

**Why:** Replace/augment the current hand-crafted eval (PESTO tapered + pawn structure + king safety) with a learned NNUE that can capture patterns the HCE misses.

**Architecture:**
- Features: 768-input (6 piece types × 2 sides × 64 squares, side-to-move perspective)
- Network: 768 → 256 → 32 → 1, ClippedReLU hidden layers
- Output: raw logit; sigmoid gives win-probability

**Data source:** Lichess eval database (`lichess_db_eval.jsonl.zst` from database.lichess.org)
- Target: `sigmoid(cp_stm / 400)` where cp_stm is Stockfish centipawn eval from side-to-move perspective

**Binary formats:**
- Training data: `positions.bin` — 12-byte header (magic `OCDT`) + 772-byte records (768 uint8 features + 4 float32 target)
- Weights: `.nnue` — header (magic `NNUE`, version, layer descriptors) + float32 weights row-major

**Current state:** Pipeline code written, not yet trained. Next step: download Lichess eval DB, run `prepare_data.py`, then `train.py`.

**How to apply:** When user asks about NNUE progress or integration into engines, the pipeline is in `src/nnue-training/`. C++ and Python engine integration (nnue.cpp / nnue.py) is the next phase after a trained `.nnue` file exists.
