#include "tt.hpp"
#include "eval.hpp"
#include <cstring>
using namespace chess;

TTEntry TT[TT_SIZE];

void ttClear()
{
    std::memset(TT, 0, sizeof(TT));
}

std::optional<int> ttLookup(const Board &board, int depth, int alpha, int beta, int plyFromRoot, Move &hashMove)
{
    uint64_t key = board.hash();
    TTEntry &e = TT[key & (TT_SIZE - 1)];

    hashMove = Move::NULL_MOVE;
    if (e.flag == TTEntry::EMPTY || e.key != key)
        return std::nullopt;

    hashMove = e.move;

    if (e.depth < depth)
        return std::nullopt;

    int val = e.value;
    if (val > MATE_SCORE - 1000)
        val -= plyFromRoot;
    else if (val < -MATE_SCORE + 1000)
        val += plyFromRoot;

    if (e.flag == TTEntry::EXACT)
        return val;
    if (e.flag == TTEntry::LOWERBOUND && val >= beta)
        return val;
    if (e.flag == TTEntry::UPPERBOUND && val <= alpha)
        return val;

    return std::nullopt;
}

void ttStore(const Board &board, int depth, Move move, int value, int originalAlpha, int beta, int plyFromRoot)
{
    uint64_t key = board.hash();
    TTEntry &e = TT[key & (TT_SIZE - 1)];

    // Always replace if same key, or replace lower-depth entries
    if (e.key == key || e.depth <= depth)
    {
        e.key = key;
        e.depth = depth;
        e.move = move;

        if (value > MATE_SCORE - 1000)
            e.value = value + plyFromRoot;
        else if (value < -MATE_SCORE + 1000)
            e.value = value - plyFromRoot;
        else
            e.value = value;

        if (value <= originalAlpha)
            e.flag = TTEntry::UPPERBOUND;
        else if (value >= beta)
            e.flag = TTEntry::LOWERBOUND;
        else
            e.flag = TTEntry::EXACT;
    }
}
