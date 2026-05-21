"""
Sanity-check a .nnue file against a set of known positions.

For each position the script prints:
  FEN | win-prob | eval (cp) | expected direction

A well-trained model should score middlegame positions near 0.5,
clearly winning positions near 1.0, and clearly losing positions near 0.0.

Usage
─────
  python validate.py --model omblecavalier.nnue
  python validate.py --model omblecavalier.nnue --fen "r1bqkb1r/... w KQkq - 0 1"
"""
import argparse

from export import NNUEInference

# Reference positions: (fen, description, expected_direction)
# expected_direction: "win" | "draw" | "loss"  (from side-to-move perspective)
REFERENCE_POSITIONS = [
    (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "Starting position",
        "draw",
    ),
    (
        "8/8/8/8/8/8/PPPPPPPP/R3K2R w KQ - 0 1",
        "White queen-less but full pawn line",
        "draw",
    ),
    (
        "7k/8/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1",
        "White full army vs lone king",
        "win",
    ),
    (
        "rnbqkbnr/pppppppp/8/8/8/8/8/7K w - - 0 1",
        "White lone king vs full army",
        "loss",
    ),
    (
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "Italian game, roughly equal",
        "draw",
    ),
    (
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
        "Italian game, symmetric piece play",
        "draw",
    ),
    (
        "8/5k2/3p4/1p1Pp2p/pP2Pp1P/P4P1K/8/8 b - - 0 46",
        "Locked pawn endgame",
        "draw",
    ),
    (
        "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
        "Pure king+pawns, symmetric",
        "draw",
    ),
    (
        "8/8/8/8/8/8/6K1/Q6k w - - 0 1",
        "White Q+K vs lone K",
        "win",
    ),
    (
        "8/8/8/8/8/8/8/Q3K2k w Q - 0 1",
        "White Q+K vs lone K (back rank)",
        "win",
    ),
]


def _direction(wp: float) -> str:
    if wp >= 0.65:
        return "win"
    if wp <= 0.35:
        return "loss"
    return "draw"


def validate(model_path: str, extra_fens: list[str]) -> None:
    model = NNUEInference(model_path)
    print(f"Loaded: {model_path}\n")

    positions = list(REFERENCE_POSITIONS)
    for fen in extra_fens:
        positions.append((fen, "(user-supplied)", "?"))

    header = f"{'Win-prob':>9}  {'Eval(cp)':>9}  {'Got':>5}  {'Exp':>5}  {'OK':>3}  Description"
    print(header)
    print("─" * len(header))

    n_pass = n_fail = 0
    for fen, desc, expected in positions:
        wp     = model.eval_fen(fen)
        cp     = model.eval_cp(fen)
        got    = _direction(wp)
        ok     = "✓" if (expected == "?" or got == expected) else "✗"
        if expected != "?" and got == expected:
            n_pass += 1
        elif expected != "?":
            n_fail += 1

        print(f"{wp:>9.4f}  {cp:>9}  {got:>5}  {expected:>5}  {ok:>3}  {desc}")

    print()
    if n_pass + n_fail > 0:
        print(f"Reference checks: {n_pass} passed, {n_fail} failed  ({100*n_pass/(n_pass+n_fail):.0f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a .nnue file on reference positions")
    parser.add_argument("--model", required=True,  help="Path to .nnue file")
    parser.add_argument("--fen",   action="append", default=[], metavar="FEN",
                        help="Extra FEN(s) to evaluate (can be repeated)")
    args = parser.parse_args()
    validate(args.model, args.fen)


if __name__ == "__main__":
    main()
