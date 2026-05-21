# Build C++ Engine

Build the OmbleCavalierPlusPlus C++ engine and copy the binary to `engines/`.

## Steps

1. Check whether `src/OmbleCavalierPlusPlus/build/CMakeCache.txt` exists.
   - If not, run `cmake ..` from `src/OmbleCavalierPlusPlus/build/` first (creates the build system).
2. Run the build from the project root:
   ```
   cd src/OmbleCavalierPlusPlus/build && make -j$(nproc)
   ```
3. If the build succeeds, copy the binary:
   ```
   cp src/OmbleCavalierPlusPlus/build/omble_cavalier++ engines/omble_cavalier++
   ```
4. Report the outcome.

## Reporting

- **Success:** state that the build succeeded, mention the binary is at `engines/omble_cavalier++`.
- **Failure:** show only the error lines (file, line number, message). Do not dump the full build log. Identify which source file contains the error and suggest the likely cause.

## Notes

- The build script at `scripts/build_cpp_engine.sh` does the same thing if you need a reference.
- Use `make -j$(nproc)` to parallelize; do not use plain `make`.
- If `CMakeCache.txt` exists but cmake seems stale (e.g., new source files were added), re-run `cmake ..` before `make`.
