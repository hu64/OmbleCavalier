# Run Puzzle Tests

Build (if needed) and run the full CTest suite — puzzle correctness tests and pawn-structure unit tests.

## Steps

1. Check that `src/OmbleCavalierPlusPlus/build/omble_cavalier++` exists.
   - If not, build first using the `/build` skill.
2. Run the test suite from the build directory:
   ```
   cd src/OmbleCavalierPlusPlus/build && ctest --output-on-failure
   ```
3. Collect:
   - Total tests run, how many passed, how many failed.
   - For each failure: test name, and any output printed (expected move vs. actual move if available).

## Reporting

- Start with a one-line summary: `X / Y tests passed`.
- **All pass:** state clearly, nothing more needed.
- **Failures:** list each failed test with:
  - Test name
  - Expected move / actual move (if the output shows it)
  - The FEN position (if shown in the failure output)
- Suggest a likely cause only if the pattern of failures points to something specific (e.g., all failures are endgame positions → evaluation issue, all are captures → move ordering issue).

## Notes

- The puzzle JSON lives at `tests/puzzles.json`; individual test cases are generated from it at cmake time via `tests/gen_cmake_tests.py`.
- Pawn-structure tests (`testDoubledPawns*`, `testIsolated*`, `testPassed*`, `testRook*`) are compiled from `src/OmbleCavalierPlusPlus/src/test_pawnstructure.cpp`.
- If cmake needs to re-generate the test list (e.g., after adding puzzles to `puzzles.json`), re-run `cmake ..` from the build directory before `ctest`.
