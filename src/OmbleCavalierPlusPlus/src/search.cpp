#include "search.hpp"
#include "eval.hpp"
#include "nnue.hpp"
#include "tt.hpp"
#include "utils.hpp"
#include <climits>
using namespace chess;

constexpr int MAX_PLY = 128;

static Move killerMoves[MAX_PLY][2];
static int historyHeuristic[64][64];

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
    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    int stand_pat = evaluateBoard(board, plyFromRoot, legalMoves);

    if (stand_pat >= beta)
        return stand_pat;

    if (stand_pat > alpha)
        alpha = stand_pat;

    for (auto move : legalMoves)
    {
        if (!board.isCapture(move))
            continue;

        // Delta pruning: skip captures that can't improve alpha even with a safety margin
        int capturedVal = getPieceValue(board, move.to());
        if (capturedVal > 0 && stand_pat + capturedVal + 200 <= alpha)
            continue;

        if (nnue_loaded()) nnue_push(board, move);
        board.makeMove(move);
        int score = -quiesce(board, -beta, -alpha, plyFromRoot + 1);
        board.unmakeMove(move);
        if (nnue_loaded()) nnue_pop();

        if (score >= beta)
            return score;
        if (score > stand_pat)
            stand_pat = score;
        if (score > alpha)
            alpha = score;
    }
    return stand_pat;
}

int negamax(Board &board, int depth, int alpha, int beta,
            std::chrono::steady_clock::time_point start, double timeLimit, int plyFromRoot, bool &timedOut)
{
    using namespace std::chrono;
    if (timedOut)
        return 0;
    if (duration<double>(steady_clock::now() - start).count() > timeLimit)
    {
        timedOut = true;
        return 0;
    }

    if (board.isRepetition(1) || board.isInsufficientMaterial())
        return 0;
    if (board.isHalfMoveDraw())
        return 0;

    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    if (legalMoves.empty())
        return board.inCheck() ? -MATE_SCORE + plyFromRoot : 0;

    Move hashMove = Move::NULL_MOVE;
    auto ttVal = ttLookup(board, depth, alpha, beta, plyFromRoot, hashMove);
    if (ttVal.has_value())
        return ttVal.value();

    bool inCheck = board.inCheck();
    int extension = inCheck ? 1 : 0;

    if (depth <= 0)
        return quiesce(board, alpha, beta, plyFromRoot + 1);

    // Compute static eval once; reused by both RFP and futility pruning below.
    int staticEval = INT_MIN;
    if (!inCheck && depth <= 5)
    {
        staticEval = evaluateBoard(board, plyFromRoot, legalMoves);
        if (staticEval - 200 * depth >= beta)
            return staticEval;
    }

    // Null move pruning
    if (depth >= 3 && !inCheck)
    {
        int nonPawnMaterial = 0;
        for (PieceType pt : {PieceType::KNIGHT, PieceType::BISHOP, PieceType::ROOK, PieceType::QUEEN})
            nonPawnMaterial += MG_VALUES[(int)pt] * board.pieces(pt, board.sideToMove()).count();
        if (nonPawnMaterial >= 2 * MG_VALUES[(int)PieceType::ROOK])
        {
            board.makeNullMove();
            int nullScore = -negamax(board, depth - 3, -beta, -beta + 1, start, timeLimit, plyFromRoot + 1, timedOut);
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

    // Futility pruning: at depth 1-2, skip quiet moves that can't raise alpha.
    // staticEval was already computed above for depth ≤ 5, so no extra eval call here.
    static const int FUTILITY_MARGINS[3] = { 0, 300, 600 };
    bool canFutilityPrune = depth <= 2 && !inCheck;

    int moveIdx = 0;
    for (auto move : legalMoves)
    {
        bool isCapture = board.isCapture(move);
        bool isKiller = plyFromRoot < MAX_PLY &&
                        (move == killerMoves[plyFromRoot][0] || move == killerMoves[plyFromRoot][1]);
        bool isGivingCheck = canFutilityPrune && board.givesCheck(move) != chess::CheckType::NO_CHECK;

        if (canFutilityPrune && !isCapture && !isKiller && !isGivingCheck && staticEval + FUTILITY_MARGINS[depth] < alpha)
        {
            moveIdx++;
            continue;
        }

        if (nnue_loaded()) nnue_push(board, move);
        board.makeMove(move);
        bool givesCheck = board.inCheck();

        int score;
        // Late Move Reduction: reduce quiet, non-killer, non-check moves after the first few
        if (!inCheck && depth >= 3 && moveIdx >= 2 && !isCapture && !isKiller && !givesCheck)
        {
            int reduction = 1 + (depth > 5 ? 1 : 0) + (moveIdx >= 6 ? 1 : 0);
            score = -negamax(board, depth - 1 + extension - reduction, -alpha - 1, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
            if (!timedOut && score > alpha)
                score = -negamax(board, depth - 1 + extension, -beta, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
        }
        else if (moveIdx > 0)
        {
            // PVS: null window for non-first non-LMR moves, re-search only on fail-high
            score = -negamax(board, depth - 1 + extension, -alpha - 1, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
            if (!timedOut && score > alpha)
                score = -negamax(board, depth - 1 + extension, -beta, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
        }
        else
        {
            score = -negamax(board, depth - 1 + extension, -beta, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
        }

        board.unmakeMove(move);
        if (nnue_loaded()) nnue_pop();
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

SearchResult negamaxRoot(Board &board, int depth, int alpha, int beta,
                         std::chrono::steady_clock::time_point start, double timeLimit, int plyFromRoot, bool &timedOut)
{
    using namespace std::chrono;
    if (timedOut)
        return {0, Move::NULL_MOVE};
    if (duration<double>(steady_clock::now() - start).count() > timeLimit)
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
        if (nnue_loaded()) nnue_push(board, move);
        board.makeMove(move);
        int score = -negamax(board, depth - 1, -beta, -alpha, start, timeLimit, plyFromRoot + 1, timedOut);
        board.unmakeMove(move);
        if (nnue_loaded()) nnue_pop();

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

Move findBestMoveIterative(Board &board, int maxDepth, double totalTimeRemaining, double increment)
{
    resetSearchState();
    if (nnue_loaded()) nnue_refresh(board);

    int moveNumber = board.fullMoveNumber();
    chess::Movelist legalMoves;
    movegen::legalmoves(legalMoves, board);

    int movesToGo = std::max(1, std::min(40, 60 - moveNumber));
    double reserve = 1.0;
    double timeForMove = std::max(0.05, std::min(
                                            (totalTimeRemaining - reserve) / movesToGo + 0.5 * increment,
                                            0.5 * totalTimeRemaining));

    auto start = std::chrono::steady_clock::now();

    if (legalMoves.empty())
    {
        std::cout << "info string No legal moves available\n";
        return Move::NULL_MOVE;
    }

    Move bestMove = legalMoves[0];
    int prevScore = 0;

    for (int depth = 1; depth <= maxDepth; ++depth)
    {
        std::cout << "info string Searching at depth " << depth << "\n";
        bool timedOut = false;

        int window = 50;
        int alpha = std::max(-MATE_SCORE, prevScore - window);
        int beta = std::min(MATE_SCORE, prevScore + window);
        SearchResult result;
        Move move;

        while (true)
        {
            result = negamaxRoot(board, depth, alpha, beta, start, timeForMove, 0, timedOut);
            move = result.bestMove;

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

        double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        if (elapsed > 0.9 * timeForMove)
        {
            std::cout << "info string Stopping iterative deepening due to time\n";
            break;
        }
    }

    return bestMove;
}
