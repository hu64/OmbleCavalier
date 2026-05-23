#pragma once
#include <string>
#include <vector>
#include "chess.hpp"

// Attempt to load a .nnue weight file. Returns true on success.
bool nnue_load(const std::string &path);

// Returns true after a successful nnue_load().
bool nnue_loaded();

// Evaluate position using the loaded NNUE network.
// Returns centipawns from side-to-move's perspective.
// Only call when nnue_loaded() is true.
int nnue_eval(const chess::Board &board);

// Return sorted active feature indices (0–767) for the given position.
// Used for unit tests and cross-engine verification.
std::vector<int> nnue_active_features(const chess::Board &board);
