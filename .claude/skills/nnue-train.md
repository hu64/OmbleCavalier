# NNUE Training Pipeline

Manage the full NNUE training workflow for OmbleCavalier: data prep → training → export → validation → engine integration.

All training code lives in `src/nnue-training/`. The shared weight file format is `.nnue` (see `export.py` for the binary layout).

---

## Determine current phase

Check which phase the project is in before doing anything:

1. Does `src/nnue-training/data/positions.bin` exist?  
   → If no: **Phase 1 – need to prepare data.**
2. Does `src/nnue-training/checkpoints/best.pt` exist?  
   → If no: **Phase 2 – need to train.**
3. Does a `.nnue` file exist in `src/nnue-training/` (or project root)?  
   → If no: **Phase 3 – need to export.**
4. Do the engines have NNUE inference integrated?  
   - Python: does `src/OmbleCavalierPython/omblecavalier/nnue.py` exist?  
   - C++: does `src/OmbleCavalierPlusPlus/src/nnue.cpp` exist?  
   → If no: **Phase 4 – need to integrate.**

Report the current phase clearly before taking any action.

---

## Phase 1 – Prepare training data

Requires: `lichess_db_eval.jsonl.zst` (downloaded from database.lichess.org/#evals).

If the user hasn't downloaded the file yet, tell them:
> Download `lichess_db_eval.jsonl.zst` from https://database.lichess.org/#evals  
> (the full file is ~10 GB compressed; any size works since prepare_data.py streams it)

Once the file path is known:

```bash
cd src/nnue-training
uv run python prepare_data.py \
    --input  /path/to/lichess_db_eval.jsonl.zst \
    --output data/positions.bin \
    --max-positions 10_000_000 \
    --min-depth 12
```

Expected output: `data/positions.bin` (~7.5 GB for 10M positions).  
Report how many positions were written and how many were skipped.

---

## Phase 2 – Train

```bash
cd src/nnue-training
uv run python train.py \
    --data  data/positions.bin \
    --out   checkpoints/ \
    --epochs 3 \
    --batch  16384
```

- GPU is used automatically if available (`nvidia-smi` to check).
- Logs train loss every ~5% of each epoch and val loss at epoch end.
- Best checkpoint (lowest val loss) saved to `checkpoints/best.pt`.
- Report final val loss and the checkpoint path when done.

---

## Phase 3 – Export to `.nnue`

```bash
cd src/nnue-training
uv run python export.py \
    --model  checkpoints/best.pt \
    --output omblecavalier.nnue
```

Then run the validation suite:

```bash
uv run python validate.py --model omblecavalier.nnue
```

A healthy model should score:
- Starting position: win-prob near 0.5
- Clearly winning positions (e.g., queen vs lone king): win-prob ≥ 0.65
- Clearly losing positions: win-prob ≤ 0.35

Report pass/fail counts. If more than 2 reference positions fail, flag it — the model may need more training data or epochs.

---

## Phase 4 – Integrate into engines

### Python engine

Create `src/OmbleCavalierPython/omblecavalier/nnue.py` that:
- Copies `NNUEInference` from `src/nnue-training/export.py` (or imports it)
- Exposes `eval_cp(fen: str) -> int` as a drop-in replacement for the current eval

In `omble_cavalier.py`, replace the `evaluateBoard` function body with a call to `NNUEInference.eval_cp()`, keeping the HCE as a fallback if no `.nnue` file is found.

### C++ engine

Create `src/OmbleCavalierPlusPlus/src/nnue.hpp` and `nnue.cpp` that:
- Load the `.nnue` binary (same format as `export.py`)
- Implement forward pass: 768→256→32→1 with ClippedReLU (clamp to [0,1])
- Expose `int nnue_eval(const chess::Board& board)` returning centipawn score

In `eval.cpp`, replace `evaluateBoard()` with NNUE eval when weights are loaded; fall back to HCE otherwise.

Add `nnue.cpp` to `CMakeLists.txt` source list.

---

## Notes

- Feature encoding is always from side-to-move perspective (defined in `features.py`).
- The output logit maps to win-probability via sigmoid; to centipawns via `400 × log(wp / (1-wp))`.
- The `.nnue` binary format: magic `NNUE` + version byte + layer descriptors + float32 weights row-major. See `export.py` for exact layout.
- HCE fallback should remain in both engines so they can run without a `.nnue` file.
