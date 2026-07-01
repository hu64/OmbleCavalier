#include "search.hpp"
#include "eval.hpp"
#include "tt.hpp"
#include "utils.hpp"
#include <climits>
#include <cstdint>
#include <limits>
using namespace chess;
using namespace std::chrono;

constexpr int MAX_PLY = 128;

static Move killerMoves[MAX_PLY][2];
static int historyHeuristic[64][64];

// Pondering control
std::atomic<bool>    g_stop{false};
std::atomic<int64_t> g_deadline_ns{std::numeric_limits<int64_t>::max()};

static inline bool shouldStop()
{
    if (g_stop.load(std::memory_order_relaxed))
        return true;
    auto now = steady_clock::now().time_since_epoch().count();
    return now > g_deadline_ns.load(std::memory_order_relaxed);
}

void resetSearchState()
{
    for (int i = 0; i < MAX_PLY; ++i)
    {
        killerMoves[i][0] = Move::NULL_MOVE;
        killerMoves[i][1] = Move::NULL_MOVE;
    }
    for (int i = 0; i < 64; ++i)
        for (int j = 0; j < 64; ++j)
            historyHeuristic[i][j] = 0;
}

int quiesce(Board &board, int alpha, int beta, int plyFromRoot)
{
    if (board.isHalfMoveDraw() || board.isInsufficientMaterial())
        return 0;

    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    if (legalMoves.empty())
        return board.inCheck() ? -MATE_SCORE + plyFromRoot : 0;

    int stand_pat = evaluateBoard(board, plyFromRoot, legalMoves);

    if (stand_pat >= beta)
        return stand_pat;

    if (stand_pat > alpha)
        alpha = stand_pat;

    for (auto move : legalMoves)
    {
        if (!board.isCapture(move))
            continue;

        board.makeMove(move);
        int score = -quiesce(board, -beta, -alpha, plyFromRoot + 1);
        board.unmakeMove(move);

        if (score >= beta)
            return score;
        if (score > stand_pat)
            stand_pat = score;
        if (score > alpha)
            alpha = score;
    }
    return stand_pat;
}

int negamax(Board &board, int depth, int alpha, int beta, int plyFromRoot, bool &timedOut)
{
    if (timedOut || shouldStop())
    {
        timedOut = true;
        return 0;
    }

    if (board.isRepetition(1) || board.isInsufficientMaterial())
        return 0;
    if (board.isHalfMoveDraw())
        return 0;

    Move hashMove = Move::NULL_MOVE;
    auto ttVal = ttLookup(board, depth, alpha, beta, plyFromRoot, hashMove);
    if (ttVal.has_value())
        return ttVal.value();

    // Drop into quiescence at the horizon before generating a full movelist here;
    // quiesce() handles its own draw/mate/stalemate detection.
    if (depth <= 0)
        return quiesce(board, alpha, beta, plyFromRoot);

    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    if (legalMoves.empty())
        return board.inCheck() ? -MATE_SCORE + plyFromRoot : 0;

    bool inCheck = board.inCheck();
    int extension = inCheck ? 1 : 0;

    // Null move pruning
    if (depth >= 3 && !inCheck)
    {
        int nonPawnMaterial = 0;
        for (PieceType pt : {PieceType::KNIGHT, PieceType::BISHOP, PieceType::ROOK, PieceType::QUEEN})
            nonPawnMaterial += MG_VALUES[(int)pt] * board.pieces(pt, board.sideToMove()).count();
        if (nonPawnMaterial >= 2 * MG_VALUES[(int)PieceType::ROOK])
        {
            board.makeNullMove();
            int nullScore = -negamax(board, depth - 3, -beta, -beta + 1, plyFromRoot + 1, timedOut);
            board.unmakeNullMove();
            if (timedOut)
                return 0;
            if (nullScore >= beta)
                return beta;
        }
    }

    int bestScore = INT_MIN;
    Move bestMove = Move::NULL_MOVE;
    int originalAlpha = alpha;

    orderMovesInPlace(
        board, legalMoves, plyFromRoot,
        hashMove != Move::NULL_MOVE ? std::optional<Move>(hashMove) : std::nullopt,
        std::vector<Move>{killerMoves[plyFromRoot][0], killerMoves[plyFromRoot][1]},
        historyHeuristic);

    static const int FUTILITY_MARGIN = 300;
    bool canFutilityPrune = depth == 1 && !inCheck;
    int staticEval = canFutilityPrune ? evaluateBoard(board, plyFromRoot, legalMoves) : INT_MIN;

    int moveIdx = 0;
    for (auto move : legalMoves)
    {
        bool isCapture = board.isCapture(move);
        bool isKiller = plyFromRoot < MAX_PLY &&
                        (move == killerMoves[plyFromRoot][0] || move == killerMoves[plyFromRoot][1]);

        if (canFutilityPrune && !isCapture && !isKiller && staticEval + FUTILITY_MARGIN < alpha)
        {
            moveIdx++;
            continue;
        }

        board.makeMove(move);
        bool givesCheck = board.inCheck();

        int score;
        if (!inCheck && depth >= 3 && moveIdx >= 2 && !isCapture && !isKiller && !givesCheck)
        {
            int reduction = 1 + (moveIdx >= 6 ? 1 : 0);
            score = -negamax(board, depth - 1 + extension - reduction, -alpha - 1, -alpha, plyFromRoot + 1, timedOut);
            if (!timedOut && score > alpha)
                score = -negamax(board, depth - 1 + extension, -beta, -alpha, plyFromRoot + 1, timedOut);
        }
        else
        {
            score = -negamax(board, depth - 1 + extension, -beta, -alpha, plyFromRoot + 1, timedOut);
        }

        board.unmakeMove(move);
        moveIdx++;

        if (timedOut)
            break;

        if (score > bestScore)
        {
            bestScore = score;
            bestMove = move;
        }
        if (score > alpha)
            alpha = score;
        if (alpha >= beta)
        {
            if (!isCapture)
            {
                if (plyFromRoot < MAX_PLY)
                {
                    if (killerMoves[plyFromRoot][0] != move)
                    {
                        killerMoves[plyFromRoot][1] = killerMoves[plyFromRoot][0];
                        killerMoves[plyFromRoot][0] = move;
                    }
                }
                historyHeuristic[move.from().index()][move.to().index()] += depth * depth;
            }
            break;
        }
    }

    if (!timedOut)
        ttStore(board, depth, bestMove, bestScore, originalAlpha, beta, plyFromRoot);

    return bestScore;
}

SearchResult negamaxRoot(Board &board, int depth, int alpha, int beta, int plyFromRoot, bool &timedOut)
{
    if (timedOut || shouldStop())
    {
        timedOut = true;
        return {0, Move::NULL_MOVE};
    }

    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    if (board.isRepetition(1) || board.isInsufficientMaterial())
        return {0, Move::NULL_MOVE};
    if (board.isHalfMoveDraw())
        return {0, Move::NULL_MOVE};
    if (legalMoves.empty())
        return {board.inCheck() ? -MATE_SCORE + plyFromRoot : 0, Move::NULL_MOVE};

    int bestScore = INT_MIN;
    Move bestMove = Move::NULL_MOVE;
    int originalAlpha = alpha;

    Move hashMove = Move::NULL_MOVE;
    ttLookup(board, depth, alpha, beta, plyFromRoot, hashMove);

    orderMovesInPlace(
        board, legalMoves, plyFromRoot,
        hashMove != Move::NULL_MOVE ? std::optional<Move>(hashMove) : std::nullopt,
        std::vector<Move>{killerMoves[plyFromRoot][0], killerMoves[plyFromRoot][1]},
        historyHeuristic);

    for (auto move : legalMoves)
    {
        board.makeMove(move);
        int score = -negamax(board, depth - 1, -beta, -alpha, plyFromRoot + 1, timedOut);
        board.unmakeMove(move);

        if (timedOut)
            break;

        if (score > bestScore)
        {
            bestScore = score;
            bestMove = move;
            std::cout << "info string Best move so far: " << uci::moveToUci(bestMove) << " with score " << bestScore << "\n";
        }
        if (score > alpha)
            alpha = score;
        if (alpha >= beta)
            break;
    }

    if (!timedOut)
        ttStore(board, depth, bestMove, bestScore, originalAlpha, beta, plyFromRoot);

    return {bestScore, bestMove};
}

Move findBestMoveIterative(Board &board, int maxDepth, double totalTimeRemaining, double increment, bool isPonder)
{
    resetSearchState();
    ttClear();

    int moveNumber = board.fullMoveNumber();
    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    if (legalMoves.empty())
    {
        std::cout << "info string No legal moves available\n";
        return Move::NULL_MOVE;
    }

    int movesToGo = std::max(1, std::min(40, 60 - moveNumber));
    double reserve = 1.0;
    double timeForMove = std::max(0.05, std::min(
        (totalTimeRemaining - reserve) / movesToGo + 0.5 * increment,
        0.5 * totalTimeRemaining));

    auto start = steady_clock::now();

    if (!isPonder)
    {
        // Set absolute deadline for normal searches
        int64_t deadline = start.time_since_epoch().count()
                           + static_cast<int64_t>(timeForMove * 1'000'000'000LL);
        g_deadline_ns.store(deadline, std::memory_order_relaxed);
    }
    // For ponder: g_deadline_ns is already INT64_MAX; main thread updates it on ponderhit.

    Move bestMove = legalMoves[0];
    int prevScore = 0;

    for (int depth = 1; depth <= maxDepth; ++depth)
    {
        std::cout << "info string Searching at depth " << depth << "\n";
        bool timedOut = false;

        // Full window at depth 1 (no reliable prevScore yet); aspiration thereafter.
        int window = depth <= 1 ? MATE_SCORE : 50;
        int alpha = std::max(-MATE_SCORE, prevScore - window);
        int beta  = std::min(MATE_SCORE,  prevScore + window);
        SearchResult result;
        Move move;

        while (true)
        {
            result = negamaxRoot(board, depth, alpha, beta, 0, timedOut);
            move   = result.bestMove;

            if (timedOut)
            {
                std::cout << "info string Search interrupted by time, keeping previous best move\n";
                break;
            }

            if (result.score <= alpha)
            {
                alpha = std::max(-MATE_SCORE, alpha - window);
                window *= 2;
                std::cout << "info string Aspiration window fail-low, widening window\n";
                continue;
            }
            else if (result.score >= beta)
            {
                beta = std::min(MATE_SCORE, beta + window);
                window *= 2;
                std::cout << "info string Aspiration window fail-high, widening window\n";
                continue;
            }
            else
            {
                break;
            }
        }

        prevScore = result.score;

        if (!timedOut && std::find(legalMoves.begin(), legalMoves.end(), move) != legalMoves.end())
        {
            bestMove = move;
            std::cout << "info string Best move at depth " << depth << ": " << uci::moveToUci(bestMove) << "\n";
        }
        else if (timedOut)
        {
            std::cout << "info string Search interrupted by time, keeping previous best move\n";
            break;
        }
        else
        {
            std::cout << "info string No legal moves found\n";
            break;
        }

        if (!isPonder)
        {
            double elapsed = duration<double>(steady_clock::now() - start).count();
            if (elapsed > 0.9 * timeForMove)
            {
                std::cout << "info string Stopping iterative deepening due to time\n";
                break;
            }
        }
    }

    return bestMove;
}
