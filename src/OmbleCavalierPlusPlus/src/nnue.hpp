#pragma once
#include <string>
#include <vector>
#include "chess.hpp"

// Attempt to load a v2 .nnue weight file.  Returns true on success.
bool nnue_load(const std::string &path);

// Returns true after a successful nnue_load().
bool nnue_loaded();

// Full accumulator recompute from the given board state.
// Must be called once before the search begins (e.g. at the top of findBestMoveIterative).
void nnue_refresh(const chess::Board &board);

// Incremental accumulator update for a move.
// Call BEFORE board.makeMove(move).  Always pair with nnue_pop() after unmakeMove().
void nnue_push(const chess::Board &board, chess::Move move);

// Restore accumulator to the state before the last nnue_push().
void nnue_pop();

// Evaluate the current position.
// Returns centipawns from side-to-move's perspective.
// Only meaningful when nnue_loaded() is true.
int nnue_eval(const chess::Board &board);

// Return sorted active feature indices (0-767) for the given position.
// Used by unit tests and cross-engine verification; independent of network weights.
std::vector<int> nnue_active_features(const chess::Board &board);
