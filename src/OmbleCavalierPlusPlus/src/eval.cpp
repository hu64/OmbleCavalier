#include "eval.hpp"
#include "utils.hpp"
using namespace chess;

// Compute game phase: 24 = full middlegame, 0 = pure endgame
int gamePhase(const Board &board)
{
    int phase = 0;
    for (int i = 0; i < 6; ++i)
    {
        int w = PHASE_WEIGHTS[i];
        if (w == 0) continue;
        phase += w * (board.pieces(ptArray[i], Color::WHITE).count()
                    + board.pieces(ptArray[i], Color::BLACK).count());
    }
    return (phase > TOTAL_PHASE) ? TOTAL_PHASE : phase;
}

// King safety: pawn shield + open files + pawn storm, phase-weighted
int kingSafety(const Board &board, Color color, int phase)
{
    if (phase == 0) return 0; // king safety irrelevant in pure endgame

    Square kingSq = board.kingSq(color);
    int kfile = kingSq.file();
    int krank = kingSq.rank();

    int penalty = 0;

    // Pawn shield: 3 squares directly in front of king
    int shieldRank = (color == Color::WHITE) ? krank + 1 : krank - 1;
    if (shieldRank >= 0 && shieldRank <= 7)
    {
        for (int df = -1; df <= 1; ++df)
        {
            int f = kfile + df;
            if (f < 0 || f > 7) continue;
            Square sq = Square(f + shieldRank * 8);
            Piece p = board.at(sq);
            if (p.type() != PieceType::PAWN || p.color() != color)
                penalty += 15;
        }
    }

    // Open / semi-open files near king
    for (int df = -1; df <= 1; ++df)
    {
        int f = kfile + df;
        if (f < 0 || f > 7) continue;
        chess::Bitboard myPawns  = board.pieces(PieceType::PAWN,  color) & chess::Bitboard(File(f));
        chess::Bitboard oppPawns = board.pieces(PieceType::PAWN, ~color) & chess::Bitboard(File(f));
        if (!myPawns)
            penalty += oppPawns ? 10 : 25; // semi-open: 10, fully open: 25
    }

    // Pawn storm: opponent pawns advancing toward the king
    chess::Bitboard storming = board.pieces(PieceType::PAWN, ~color);
    while (storming)
    {
        int sq = storming.lsb();
        storming.clear(sq);
        int f = sq % 8;
        int r = sq / 8;
        if (f < kfile - 1 || f > kfile + 1) continue;
        int dist = (color == Color::WHITE) ? r - krank : krank - r;
        if (dist > 0 && dist <= 3)
            penalty += (4 - dist) * 8; // dist 1→24, dist 2→16, dist 3→8
    }

    // Scale by game phase (full penalty in MG, zero in EG)
    return penalty * phase / TOTAL_PHASE;
}

// Doubled and isolated pawn helpers (kept public for tests)
int countDoubledPawns(const Board &board, Color color)
{
    int doubled = 0;
    chess::Bitboard pawns = board.pieces(PieceType::PAWN, color);
    for (int f = 0; f < 8; ++f)
    {
        int cnt = countBits(pawns & chess::Bitboard(File(f)));
        if (cnt > 1) doubled += cnt - 1;
    }
    return doubled;
}

int countIsolatedPawns(const Board &board, Color color)
{
    int isolated = 0;
    chess::Bitboard pawns = board.pieces(PieceType::PAWN, color);
    for (int f = 0; f < 8; ++f)
    {
        chess::Bitboard filePawns = pawns & chess::Bitboard(File(f));
        if (!filePawns) continue;
        bool hasLeft  = (f > 0) && (pawns & chess::Bitboard(File(f - 1)));
        bool hasRight = (f < 7) && (pawns & chess::Bitboard(File(f + 1)));
        if (!hasLeft && !hasRight)
            isolated += countBits(filePawns);
    }
    return isolated;
}

// Passed pawn count (public for tests). Only opponent pawns block passage.
int countPassedPawns(const Board &board, Color color)
{
    int passed = 0;
    chess::Bitboard pawns    = board.pieces(PieceType::PAWN,  color);
    chess::Bitboard oppPawns = board.pieces(PieceType::PAWN, ~color);

    while (pawns)
    {
        int sq   = pawns.lsb();
        pawns.clear(sq);
        int file = sq % 8;
        int rank = sq / 8;
        bool isPassed = true;

        for (int df = -1; df <= 1 && isPassed; ++df)
        {
            int f = file + df;
            if (f < 0 || f > 7) continue;
            if (color == Color::WHITE)
            {
                for (int r = rank + 1; r < 8; ++r)
                    if (oppPawns.check(f + r * 8)) { isPassed = false; break; }
            }
            else
            {
                for (int r = rank - 1; r >= 0; --r)
                    if (oppPawns.check(f + r * 8)) { isPassed = false; break; }
            }
        }
        if (isPassed) ++passed;
    }
    return passed;
}

// Pawn structure with MG/EG split and rank-scaled passed pawn bonuses
int pawnStructure(const Board &board, Color color, int phase)
{
    // MG/EG penalties
    int doubled  = countDoubledPawns(board, color);
    int isolated = countIsolatedPawns(board, color);
    int mg = -12 * doubled - 15 * isolated;
    int eg = -20 * doubled - 25 * isolated;

    // Passed pawns: rank-scaled bonuses (rank index 0=rank1 … 7=rank8)
    static const int PASSED_MG[8] = { 0,  5, 10, 20, 35,  55,  80, 0 };
    static const int PASSED_EG[8] = { 0, 15, 25, 50, 80, 125, 175, 0 };

    chess::Bitboard pawns    = board.pieces(PieceType::PAWN,  color);
    chess::Bitboard oppPawns = board.pieces(PieceType::PAWN, ~color);

    while (pawns)
    {
        int sq   = pawns.lsb();
        pawns.clear(sq);
        int file = sq % 8;
        int rank = sq / 8;
        bool isPassed = true;

        for (int df = -1; df <= 1 && isPassed; ++df)
        {
            int f = file + df;
            if (f < 0 || f > 7) continue;
            if (color == Color::WHITE)
            {
                for (int r = rank + 1; r < 8; ++r)
                    if (oppPawns.check(f + r * 8)) { isPassed = false; break; }
            }
            else
            {
                for (int r = rank - 1; r >= 0; --r)
                    if (oppPawns.check(f + r * 8)) { isPassed = false; break; }
            }
        }
        if (isPassed)
        {
            int effectiveRank = (color == Color::WHITE) ? rank : 7 - rank;
            mg += PASSED_MG[effectiveRank];
            eg += PASSED_EG[effectiveRank];
        }
    }

    return (mg * phase + eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;
}

// Rook on open/semi-open file bonus (phase-independent structural bonus)
int rookOpenFileBonus(const Board &board, Color color)
{
    int bonus = 0;
    chess::Bitboard rooks = board.pieces(PieceType::ROOK, color);
    chess::Bitboard myPawns = board.pieces(PieceType::PAWN, color);
    chess::Bitboard oppPawns = board.pieces(PieceType::PAWN, ~color);

    while (rooks)
    {
        int sq = rooks.lsb();
        rooks.clear(sq);
        int file = sq % 8;
        chess::Bitboard fileMask = chess::Bitboard(File(file));
        bool hasMyPawn = static_cast<bool>(myPawns & fileMask);
        bool hasOppPawn = static_cast<bool>(oppPawns & fileMask);
        if (!hasMyPawn && !hasOppPawn)
            bonus += 20; // open file
        else if (!hasMyPawn)
            bonus += 10; // semi-open file
    }
    return bonus;
}

// Main evaluation (always returns score from side-to-move's perspective)
int evaluateBoard(const Board &board, int plyFromRoot, Movelist &moves)
{
    if (moves.empty())
        return board.inCheck() ? (-MATE_SCORE + plyFromRoot) : 0;

    int phase = gamePhase(board);

    int mg = 0, eg = 0;

    // Material + PST (tapered)
    for (int i = 0; i < 6; ++i)
    {
        PieceType pt = ptArray[i];
        int mgVal = MG_VALUES[i];
        int egVal = EG_VALUES[i];
        const int *mgPst = MG_PST[i];
        const int *egPst = EG_PST[i];

        chess::Bitboard wbb = board.pieces(pt, Color::WHITE);
        while (wbb)
        {
            int sq = wbb.lsb();
            wbb.clear(sq);
            int idx = mirror(sq); // a1=0 → a8=0
            mg += mgVal + mgPst[idx];
            eg += egVal + egPst[idx];
        }

        chess::Bitboard bbb = board.pieces(pt, Color::BLACK);
        while (bbb)
        {
            int sq = bbb.lsb();
            bbb.clear(sq);
            // Black uses sq directly (a1=0 naturally mirrors for Black)
            mg -= mgVal + mgPst[sq];
            eg -= egVal + egPst[sq];
        }
    }

    // Taper between MG and EG
    int score = (mg * phase + eg * (TOTAL_PHASE - phase)) / TOTAL_PHASE;

    // Bishop pair bonus
    if (board.pieces(PieceType::BISHOP, Color::WHITE).count() >= 2) score += 30;
    if (board.pieces(PieceType::BISHOP, Color::BLACK).count() >= 2) score -= 30;

    // Pawn structure (phase-aware)
    score += pawnStructure(board, Color::WHITE, phase);
    score -= pawnStructure(board, Color::BLACK, phase);

    // King safety (phase-weighted, fades to zero in endgame)
    score -= kingSafety(board, Color::WHITE, phase);
    score += kingSafety(board, Color::BLACK, phase);

    // Rook on open/semi-open file
    score += rookOpenFileBonus(board, Color::WHITE);
    score -= rookOpenFileBonus(board, Color::BLACK);

    // Rooks on 7th rank (strong attacking position)
    {
        chess::Bitboard wr7 = board.pieces(PieceType::ROOK, Color::WHITE);
        while (wr7) { int sq = wr7.lsb(); wr7.clear(sq); if (sq / 8 == 6) score += 20; }
        chess::Bitboard br2 = board.pieces(PieceType::ROOK, Color::BLACK);
        while (br2) { int sq = br2.lsb(); br2.clear(sq); if (sq / 8 == 1) score -= 20; }
    }

    // Mobility (side to move only)
    score += (board.sideToMove() == Color::WHITE ? 1 : -1) * (int(moves.size()) * 5);

    // Return from side-to-move's perspective
    if (board.sideToMove() == Color::BLACK)
        score = -score;

    return score;
}
