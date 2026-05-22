#pragma once
#include <string>
#include "chess.hpp"

// Attempt to load a .nnue weight file. Returns true on success.
bool nnue_load(const std::string &path);

// Returns true after a successful nnue_load().
bool nnue_loaded();

// Evaluate position using the loaded NNUE network.
// Returns centipawns from side-to-move's perspective.
// Only call when nnue_loaded() is true.
int nnue_eval(const chess::Board &board);
