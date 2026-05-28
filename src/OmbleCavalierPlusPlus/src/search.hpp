#pragma once
#include "chess.hpp"
#include <atomic>
#include <chrono>
#include <cstdint>
#include <limits>

static const int MAX_DEPTH = 69;

// Pondering control — written by main thread, read by search thread.
extern std::atomic<bool>    g_stop;
extern std::atomic<int64_t> g_deadline_ns; // steady_clock nanoseconds

struct SearchResult
{
    int score;
    chess::Move bestMove;
};

SearchResult negamaxRoot(chess::Board &board, int depth, int alpha, int beta, int plyFromRoot, bool &timedOut);

int negamax(chess::Board &board, int depth, int alpha, int beta, int plyFromRoot, bool &timedOut);

int quiesce(chess::Board &board, int alpha, int beta, int plyFromRoot);

chess::Move findBestMoveIterative(chess::Board &board, int maxDepth, double totalTimeRemaining,
                                  double increment = 0.0, bool isPonder = false);
void resetSearchState();
