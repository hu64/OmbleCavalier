#pragma once
#include "chess.hpp"

static const int TT_BITS = 20;
static const int TT_SIZE = 1 << TT_BITS; // ~1M entries, ~24 MB

struct TTEntry
{
    uint64_t key;
    int value;
    int depth;
    chess::Move move;
    uint8_t flag;

    static constexpr uint8_t EMPTY = 0;
    static constexpr uint8_t EXACT = 1;
    static constexpr uint8_t LOWERBOUND = 2;
    static constexpr uint8_t UPPERBOUND = 3;
};

extern TTEntry TT[TT_SIZE];

// Returns the score if TT entry is usable for a cutoff. Always sets hashMove if an entry exists.
std::optional<int> ttLookup(const chess::Board &board, int depth, int alpha, int beta, int plyFromRoot, chess::Move &hashMove);
void ttStore(const chess::Board &board, int depth, chess::Move move, int value, int originalAlpha, int beta, int plyFromRoot);
void ttClear();
