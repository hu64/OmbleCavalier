#pragma once
#include "chess.hpp"

// Tapered evaluation: separate middlegame and endgame material values (centipawns)
static const int MG_VALUES[6] = { 82, 337, 365, 477, 1025, 0 };
static const int EG_VALUES[6] = { 94, 281, 297, 512,  936, 0 };

// Phase weights: Knight=1, Bishop=1, Rook=2, Queen=4. Max phase = 24.
static const int PHASE_WEIGHTS[6] = { 0, 1, 1, 2, 4, 0 };
static const int TOTAL_PHASE = 24;

static const int MATE_SCORE = 69000;

static const chess::PieceType ptArray[6] = {
    chess::PieceType::PAWN,
    chess::PieceType::KNIGHT,
    chess::PieceType::BISHOP,
    chess::PieceType::ROOK,
    chess::PieceType::QUEEN,
    chess::PieceType::KING};

int evaluateBoard(const chess::Board &board, int plyFromRoot, chess::Movelist &moves);
int pawnStructure(const chess::Board &board, chess::Color color, int phase);
int kingSafety(const chess::Board &board, chess::Color color, int phase);
int gamePhase(const chess::Board &board);
int countDoubledPawns(const chess::Board &board, chess::Color color);
int countIsolatedPawns(const chess::Board &board, chess::Color color);
int countPassedPawns(const chess::Board &board, chess::Color color);
