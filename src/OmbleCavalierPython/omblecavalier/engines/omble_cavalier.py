#!/usr/bin/env python3
import logging
import sys
import threading
import time
from operator import itemgetter

import bulletchess as chess
import chess.polyglot
from bulletchess import (
    BLACK,
    CHECK,
    DRAW,
    PIECE_TYPES,
    SQUARES,
    WHITE,
    Board,
    Move,
)

logging.basicConfig(level=logging.DEBUG)

# Square index mapping: Square object -> int (a1=0, h8=63)
SQ_TO_INT = {sq: i for i, sq in enumerate(SQUARES)}

# Vertical mirror for Black PST lookup: sq -> mirrored_sq
MIRROR = [(7 - sq // 8) * 8 + sq % 8 for sq in range(64)]

# Tapered evaluation material values (centipawns)
MG_VALUES = [82, 337, 365, 477, 1025, 0]   # pawn … king
EG_VALUES = [94, 281, 297, 512,  936, 0]

# For MVV-LVA move ordering (use MG values; king=0 is fine for legal moves)
_MV_ORDER = {pt: MG_VALUES[i] for i, pt in enumerate(PIECE_TYPES)}

MATE_SCORE = 100000
MAX_PLY = 128

# Phase weights: N=1, B=1, R=2, Q=4.  Max total phase = 24.
_PHASE_WEIGHTS = [0, 1, 1, 2, 4, 0]

# -----------------------------------------------------------------------
# PESTO piece-square tables (a1=0 format: rank 1 first, rank 8 last).
# White pieces use sq_int directly.
# Black pieces use MIRROR[sq_int] to flip vertically.
# Values are positional bonuses only; material is added separately.
# -----------------------------------------------------------------------

MG_PAWN_PST = [
      0,   0,   0,   0,   0,   0,   0,   0,  # rank 1
    -35,  -1, -20, -23, -15,  24,  38, -22,  # rank 2
    -26,  -4,  -4, -10,   3,   3,  33, -12,  # rank 3
    -27,  -2,  -5,  12,  17,   6,  10, -25,  # rank 4
    -14,  13,   6,  21,  23,  12,  17, -23,  # rank 5
     -6,   7,  26,  31,  65,  56,  25, -20,  # rank 6
     98, 134,  61,  95,  68, 126,  34, -11,  # rank 7
      0,   0,   0,   0,   0,   0,   0,   0,  # rank 8
]
EG_PAWN_PST = [
      0,   0,   0,   0,   0,   0,   0,   0,  # rank 1
     13,   8,   8,  10,  13,   0,   2,  -7,  # rank 2
      4,   7,  -6,   1,   0,  -5,  -1,  -8,  # rank 3
     13,   9,  -3,  -7,  -7,  -8,   3,  -1,  # rank 4
     32,  24,  13,   5,  -2,   4,  17,  17,  # rank 5
     94, 100,  85,  67,  56,  53,  82,  84,  # rank 6
    178, 173, 158, 134, 147, 132, 165, 187,  # rank 7
      0,   0,   0,   0,   0,   0,   0,   0,  # rank 8
]
MG_KNIGHT_PST = [
    -105, -21, -58, -33, -17, -28, -19,  -23,  # rank 1
     -29, -53, -12,  -3,  -1,  18, -14,  -19,  # rank 2
     -23,  -9,  12,  10,  19,  17,  25,  -16,  # rank 3
     -13,   4,  16,  13,  28,  19,  21,   -8,  # rank 4
      -9,  17,  19,  53,  37,  69,  18,   22,  # rank 5
     -47,  60,  37,  65,  84, 129,  73,   44,  # rank 6
     -73, -41,  72,  36,  23,  62,   7,  -17,  # rank 7
    -167, -89, -34, -49,  61, -97, -15, -107,  # rank 8
]
EG_KNIGHT_PST = [
     -29, -51, -23, -15, -22, -18, -50, -64,  # rank 1
     -42, -20, -10,  -5,  -2, -20, -23, -44,  # rank 2
     -23,  -3,  -1,  15,  10,  -3, -20, -22,  # rank 3
     -18,  -6,  16,  25,  16,  17,   4, -18,  # rank 4
     -17,   3,  22,  22,  22,  11,   8, -18,  # rank 5
     -24, -20,  10,   9,  -1,  -9, -19, -41,  # rank 6
     -25,  -8, -25,  -2,  -9, -25, -24, -52,  # rank 7
     -58, -38, -13, -28, -31, -27, -63, -99,  # rank 8
]
MG_BISHOP_PST = [
     -33,  -3, -14, -21, -13, -12, -39, -21,  # rank 1
       4,  15,  16,   0,   7,  21,  33,   1,  # rank 2
       0,  15,  15,  15,  14,  27,  18,  10,  # rank 3
      -6,  13,  13,  26,  34,  12,  10,   4,  # rank 4
      -4,   5,  19,  50,  37,  37,   7,  -2,  # rank 5
     -16,  37,  43,  40,  35,  50,  37,  -2,  # rank 6
     -26,  16, -18, -13,  30,  59,  18, -47,  # rank 7
     -29,   4, -82, -37, -25, -42,   7,  -8,  # rank 8
]
EG_BISHOP_PST = [
     -23,  -9, -23,  -5,  -9, -16,  -5, -17,  # rank 1
     -14, -18,  -7,  -1,   4,  -9, -15, -27,  # rank 2
     -12,  -3,   8,  10,  13,   3,  -7, -15,  # rank 3
      -6,   3,  13,  19,   7,  10,  -3,  -9,  # rank 4
      -3,   9,  12,   9,  14,  10,   3,   2,  # rank 5
       2,  -8,   0,  -1,  -2,   6,   0,   4,  # rank 6
      -8,  -4,   7, -12,  -3, -13,  -4, -14,  # rank 7
     -14, -21, -11,  -8,  -7,  -9, -17, -24,  # rank 8
]
MG_ROOK_PST = [
     -19, -13,   1,  17,  16,   7, -37, -26,  # rank 1
     -44, -16, -20,  -9,  -1,  11,  -6, -71,  # rank 2
     -45, -25, -16, -17,   3,   0,  -5, -33,  # rank 3
     -36, -26, -12,  -1,   9,  -7,   6, -23,  # rank 4
     -24, -11,   7,  26,  24,  35,  -8, -20,  # rank 5
      -5,  19,  26,  36,  17,  45,  61,  16,  # rank 6
      27,  32,  58,  62,  80,  67,  26,  44,  # rank 7
      32,  42,  32,  51,  63,   9,  31,  43,  # rank 8
]
EG_ROOK_PST = [
      -9,   2,   3,  -1,  -5, -13,   4, -20,  # rank 1
      -6,  -6,   0,   2,  -9,  -9, -11,  -3,  # rank 2
      -4,   0,  -5,  -1,  -7, -12,  -8, -16,  # rank 3
       3,   5,   8,   4,  -5,  -6,  -8, -11,  # rank 4
       4,   3,  13,   1,   2,   1,  -1,   2,  # rank 5
       7,   7,   7,   5,   4,  -3,  -5,  -3,  # rank 6
      11,  13,  13,  11,  -3,   3,   8,   3,  # rank 7
      13,  10,  18,  15,  12,  12,   8,   5,  # rank 8
]
MG_QUEEN_PST = [
      -1, -18,  -9,  10, -15, -25, -31, -50,  # rank 1
     -35,  -8,  11,   2,   8,  15,  -3,   1,  # rank 2
     -14,   2, -11,  -2,  -5,   2,  14,   5,  # rank 3
      -9, -26,  -9, -10,  -2,  -4,   3,  -3,  # rank 4
     -27, -27, -16, -16,  -1,  17,  -2,   1,  # rank 5
     -13, -17,   7,   8,  29,  56,  47,  57,  # rank 6
     -24, -39,  -5,   1, -16,  57,  28,  54,  # rank 7
     -28,   0,  29,  12,  59,  44,  43,  45,  # rank 8
]
EG_QUEEN_PST = [
     -33, -28, -22, -43,  -5, -32, -20, -41,  # rank 1
     -22, -23, -30, -16, -16, -23, -36, -32,  # rank 2
     -16, -27,  15,   6,   9,  17,  10,   5,  # rank 3
     -18,  28,  19,  47,  31,  34,  39,  23,  # rank 4
       3,  22,  24,  45,  57,  40,  57,  36,  # rank 5
     -20,   6,   9,  49,  47,  35,  19,   9,  # rank 6
     -17,  20,  32,  41,  58,  25,  30,   0,  # rank 7
      -9,  22,  22,  27,  27,  19,  10,  20,  # rank 8
]
MG_KING_PST = [
     -15,  36,  12, -54,   8, -28,  24,  14,  # rank 1
       1,   7,  -8, -64, -43, -16,   9,   8,  # rank 2
     -14, -14, -22, -46, -44, -30, -15, -27,  # rank 3
     -49,  -1, -27, -39, -46, -44, -33, -51,  # rank 4
     -17, -20, -12, -27, -30, -25, -14, -36,  # rank 5
      -9,  24,   2, -16, -20,   6,  22, -22,  # rank 6
      29,  -1, -20,  -7,  -8,  -4, -38, -29,  # rank 7
     -65,  23,  16, -15, -56, -34,   2,  13,  # rank 8
]
EG_KING_PST = [
     -53, -34, -21, -11, -28, -14, -24, -43,  # rank 1
     -27, -11,   4,  13,  14,   4,  -5, -17,  # rank 2
     -19,  -3,  11,  21,  23,  16,   7,  -9,  # rank 3
     -18,  -4,  21,  24,  27,  23,   9, -11,  # rank 4
      -8,  22,  24,  27,  26,  33,  26,   3,  # rank 5
      10,  17,  23,  15,  20,  45,  44,  13,  # rank 6
     -12,  17,  14,  17,  17,  38,  23,  11,  # rank 7
     -74, -35, -18, -18, -11,  15,   4, -17,  # rank 8
]

_MG_PSTS = [MG_PAWN_PST, MG_KNIGHT_PST, MG_BISHOP_PST, MG_ROOK_PST, MG_QUEEN_PST, MG_KING_PST]
_EG_PSTS = [EG_PAWN_PST, EG_KNIGHT_PST, EG_BISHOP_PST, EG_ROOK_PST, EG_QUEEN_PST, EG_KING_PST]

# Precomputed per-square (material + PST) tables for hot eval loop.
# [piece_idx][sq_int]
_W_MG: list[list[int]] = []
_W_EG: list[list[int]] = []
_B_MG: list[list[int]] = []
_B_EG: list[list[int]] = []
for _i in range(6):
    _mgv, _egv = MG_VALUES[_i], EG_VALUES[_i]
    _mg_pst, _eg_pst = _MG_PSTS[_i], _EG_PSTS[_i]
    _W_MG.append([_mgv + _mg_pst[sq] for sq in range(64)])
    _W_EG.append([_egv + _eg_pst[sq] for sq in range(64)])
    _B_MG.append([_mgv + _mg_pst[MIRROR[sq]] for sq in range(64)])
    _B_EG.append([_egv + _eg_pst[MIRROR[sq]] for sq in range(64)])

TRANSPOSITION_TABLE = {}
killer_moves = [[None, None] for _ in range(MAX_PLY)]
history_heuristic = [[0] * 64 for _ in range(64)]
game_position_keys: list[int] = []

# ── Pondering control (GIL-safe booleans + one deadline timestamp) ─────────────
_g_stop: bool = False            # set True to abort search immediately
_g_deadline: float = float("inf")  # absolute time.time() deadline
_g_search_thread: threading.Thread | None = None
_g_ponder_params: dict = {}      # saved from "go ponder": total_time, increment, fullmove


def position_key(board: Board) -> int:
    """Position hash excluding halfmove clock and fullmove number, for repetition detection."""
    c = board.copy()
    c.halfmove_clock = 0
    c.fullmove_number = 1
    return c.__hash__()


def reset_search_state():
    global killer_moves, history_heuristic
    killer_moves = [[None, None] for _ in range(MAX_PLY)]
    history_heuristic = [[0] * 64 for _ in range(64)]
    TRANSPOSITION_TABLE.clear()


def tt_lookup(board, depth, alpha, beta):
    key = board.__hash__()
    if key in TRANSPOSITION_TABLE:
        stored_depth, value, flag = TRANSPOSITION_TABLE[key]
        if stored_depth >= depth:
            if flag == "EXACT":
                return value
            elif flag == "LOWERBOUND" and value > alpha:
                alpha = value
            elif flag == "UPPERBOUND" and value < beta:
                beta = value
            if alpha >= beta:
                return value
    return None


def tt_store(board, depth, value, alpha, beta):
    key = board.__hash__()
    if value <= alpha:
        flag = "UPPERBOUND"
    elif value >= beta:
        flag = "LOWERBOUND"
    else:
        flag = "EXACT"
    TRANSPOSITION_TABLE[key] = (depth, value, flag)


def get_piece_value(board, square):
    piece = board[square]
    if piece is None:
        return 0
    return _MV_ORDER.get(piece.piece_type, 0)


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _compute_phase(board) -> int:
    """Game phase: 24 = full middlegame, 0 = pure endgame."""
    phase = 0
    for i, pt in enumerate(PIECE_TYPES):
        w = _PHASE_WEIGHTS[i]
        if w:
            phase += w * (len(board[WHITE, pt]) + len(board[BLACK, pt]))
    return min(24, phase)


def pawn_structure(board, color, phase: int) -> int:
    """Tapered pawn structure score: doubled/isolated penalties + rank-scaled passed bonuses."""
    sq_map = SQ_TO_INT
    opp = BLACK if color == WHITE else WHITE

    pawn_sqs = [(sq_map[sq] // 8, sq_map[sq] % 8) for sq in board[color, PIECE_TYPES[0]]]
    if not pawn_sqs:
        return 0
    opp_sqs  = [(sq_map[sq] // 8, sq_map[sq] % 8) for sq in board[opp,   PIECE_TYPES[0]]]

    my_files = [f for _, f in pawn_sqs]
    file_set = set(my_files)
    file_counts: dict[int, int] = {}
    for f in my_files:
        file_counts[f] = file_counts.get(f, 0) + 1

    doubled  = sum(c - 1 for c in file_counts.values() if c > 1)
    isolated = sum(1 for _, f in pawn_sqs if (f - 1) not in file_set and (f + 1) not in file_set)

    mg = -12 * doubled - 15 * isolated
    eg = -20 * doubled - 25 * isolated

    # Passed pawns: only opponent pawns can block passage, rank-scaled bonuses
    PASSED_MG = (0,  5, 10, 20,  35,  55,  80, 0)
    PASSED_EG = (0, 15, 25, 50,  80, 125, 175, 0)
    is_white = color == WHITE
    for rank, file in pawn_sqs:
        is_passed = True
        for opp_rank, opp_file in opp_sqs:  # opponent pawns only
            d = opp_file - file
            if -1 <= d <= 1:
                if is_white and opp_rank > rank:
                    is_passed = False
                    break
                if not is_white and opp_rank < rank:
                    is_passed = False
                    break
        if is_passed:
            eff = rank if is_white else 7 - rank
            mg += PASSED_MG[eff]
            eg += PASSED_EG[eff]

    return (mg * phase + eg * (24 - phase)) // 24


def king_safety(board, color, phase: int) -> int:
    """Phase-weighted king safety penalty: pawn shield + open files + pawn storm."""
    if phase == 0:
        return 0
    sq_map = SQ_TO_INT
    king_sqs = list(board[color, PIECE_TYPES[5]])
    if not king_sqs:
        return 0
    king_idx = sq_map[king_sqs[0]]
    kfile = king_idx % 8
    krank = king_idx // 8

    opp = BLACK if color == WHITE else WHITE
    friendly_pawns = set(board[color, PIECE_TYPES[0]])
    opp_pawns      = list(board[opp,   PIECE_TYPES[0]])

    penalty = 0

    # Pawn shield
    shield_rank = krank + 1 if color == WHITE else krank - 1
    if 0 <= shield_rank <= 7:
        for df in (-1, 0, 1):
            f = kfile + df
            if 0 <= f <= 7 and SQUARES[shield_rank * 8 + f] not in friendly_pawns:
                penalty += 15

    # Open / semi-open files near king
    my_pawn_files  = {sq_map[sq] % 8 for sq in friendly_pawns}
    opp_pawn_files = {sq_map[sq] % 8 for sq in opp_pawns}
    for df in (-1, 0, 1):
        f = kfile + df
        if 0 <= f <= 7 and f not in my_pawn_files:
            penalty += 20 if f not in opp_pawn_files else 10

    # Pawn storm: opponent pawns advancing toward king
    for opp_sq in opp_pawns:
        idx = sq_map[opp_sq]
        f = idx % 8
        r = idx // 8
        if abs(f - kfile) > 1:
            continue
        dist = r - krank if color == WHITE else krank - r
        if 1 <= dist <= 3:
            penalty += (4 - dist) * 8  # dist 1→24, dist 2→16, dist 3→8

    return penalty * phase // 24


def rook_open_file_bonus(board, color) -> int:
    """Bonus for rooks on open (+20) or semi-open (+10) files."""
    opp = BLACK if color == WHITE else WHITE
    sq_map = SQ_TO_INT
    my_pawn_files = {sq_map[sq] % 8 for sq in board[color, PIECE_TYPES[0]]}
    opp_pawn_files = {sq_map[sq] % 8 for sq in board[opp, PIECE_TYPES[0]]}
    bonus = 0
    for sq in board[color, PIECE_TYPES[3]]:
        f = sq_map[sq] % 8
        if f not in my_pawn_files:
            bonus += 20 if f not in opp_pawn_files else 10
    return bonus


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_board_fast(board, legal_moves_count):
    """PESTO tapered material + PST + bishop pair + mobility (used in quiescence)."""
    sq_map = SQ_TO_INT
    phase = _compute_phase(board)
    mg, eg = 0, 0
    for i in range(6):
        wm, we = _W_MG[i], _W_EG[i]
        bm, be = _B_MG[i], _B_EG[i]
        for sq in board[WHITE, PIECE_TYPES[i]]:
            s = sq_map[sq]; mg += wm[s]; eg += we[s]
        for sq in board[BLACK, PIECE_TYPES[i]]:
            s = sq_map[sq]; mg -= bm[s]; eg -= be[s]

    score = (mg * phase + eg * (24 - phase)) // 24

    if len(board[WHITE, PIECE_TYPES[2]]) >= 2:
        score += 30
    if len(board[BLACK, PIECE_TYPES[2]]) >= 2:
        score -= 30

    score += legal_moves_count * 5 if board.turn == WHITE else -legal_moves_count * 5
    return score if board.turn == WHITE else -score


def evaluate_board_full(board, legal_moves_count):
    """Full PESTO evaluation: tapered material/PST + pawn structure + king safety."""
    sq_map = SQ_TO_INT
    phase = _compute_phase(board)
    mg, eg = 0, 0
    for i in range(6):
        wm, we = _W_MG[i], _W_EG[i]
        bm, be = _B_MG[i], _B_EG[i]
        for sq in board[WHITE, PIECE_TYPES[i]]:
            s = sq_map[sq]; mg += wm[s]; eg += we[s]
        for sq in board[BLACK, PIECE_TYPES[i]]:
            s = sq_map[sq]; mg -= bm[s]; eg -= be[s]

    score = (mg * phase + eg * (24 - phase)) // 24

    if len(board[WHITE, PIECE_TYPES[2]]) >= 2:
        score += 30
    if len(board[BLACK, PIECE_TYPES[2]]) >= 2:
        score -= 30

    score += pawn_structure(board, WHITE, phase)
    score -= pawn_structure(board, BLACK, phase)
    score -= king_safety(board, WHITE, phase)
    score += king_safety(board, BLACK, phase)
    score += rook_open_file_bonus(board, WHITE)
    score -= rook_open_file_bonus(board, BLACK)

    score += legal_moves_count * 5 if board.turn == WHITE else -legal_moves_count * 5
    return score if board.turn == WHITE else -score


# ---------------------------------------------------------------------------
# Move ordering
# ---------------------------------------------------------------------------

def order_moves(board, legal_moves, ply_from_root):
    k = killer_moves[ply_from_root] if ply_from_root < MAX_PLY else (None, None)
    k0, k1 = k[0], k[1]
    sq_map = SQ_TO_INT
    hist = history_heuristic

    scored = []
    for move in legal_moves:
        if move.is_capture(board):
            captured = get_piece_value(board, move.destination)
            capturing = get_piece_value(board, move.origin)
            score = 900000 + 10 * captured - capturing
        elif move == k0 or move == k1:
            score = 800000
        else:
            score = 1000 + hist[sq_map[move.origin]][sq_map[move.destination]]
        scored.append((score, move))

    scored.sort(key=itemgetter(0), reverse=True)
    return list(map(itemgetter(1), scored))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def quiesce(board, alpha, beta, ply_from_root, legal_moves=None, stand_pat=None):
    """Quiescence search using fast evaluation (material + PST + bishop pair).

    If legal_moves and stand_pat are provided (passed from negamax at depth=0),
    we skip regenerating legal moves and recomputing stand_pat for this first call.
    Recursive calls always regenerate their own state.
    """
    if legal_moves is None:
        legal_moves = list(board.legal_moves())
        if not legal_moves:
            return -(MATE_SCORE - ply_from_root) if board in CHECK else 0
        if board.halfmove_clock >= 100 or board in DRAW:
            return 0
        stand_pat = evaluate_board_fast(board, len(legal_moves))

    if stand_pat >= beta:
        return stand_pat
    alpha = max(alpha, stand_pat)
    best = stand_pat

    for move in legal_moves:
        if not move.is_capture(board):
            continue
        board.apply(move)
        score = -quiesce(board, -beta, -alpha, ply_from_root + 1)
        board.undo()

        if score >= beta:
            return score
        if score > best:
            best = score
        if score > alpha:
            alpha = score

    return best


def negamax(board, depth, alpha, beta, start_time, time_limit, ply_from_root=0, rep_counts=None):
    if _g_stop or time.time() > _g_deadline:
        return None

    legal_moves = list(board.legal_moves())

    if not legal_moves:
        return -(MATE_SCORE - ply_from_root) if board in CHECK else 0
    if board.halfmove_clock >= 100 or board in DRAW:
        return 0

    # Repetition detection: position_key excludes halfmove/fullmove so positions
    # that repeat at different move counts are correctly identified as draws.
    current_key = position_key(board)
    if rep_counts is not None and rep_counts.get(current_key, 0) >= 1:
        return 0

    tt_value = tt_lookup(board, depth, alpha, beta)
    if tt_value is not None:
        return tt_value

    if depth <= 0:
        stand_pat = evaluate_board_full(board, len(legal_moves))
        return quiesce(board, alpha, beta, ply_from_root, legal_moves, stand_pat)

    in_check = board in CHECK
    extension = 1 if in_check else 0

    # Null move pruning (copy + attribute mutation avoids slow FEN roundtrip)
    if depth >= 3 and not in_check:
        non_pawn_material = (
            len(board[board.turn, PIECE_TYPES[1]]) * 320
            + len(board[board.turn, PIECE_TYPES[2]]) * 330
            + len(board[board.turn, PIECE_TYPES[3]]) * 500
            + len(board[board.turn, PIECE_TYPES[4]]) * 900
        )
        if non_pawn_material >= 1000:
            null_board = board.copy()
            null_board.turn = BLACK if board.turn == WHITE else WHITE
            null_board.en_passant_square = None
            null_score = negamax(null_board, depth - 3, -beta, -beta + 1, start_time, time_limit, ply_from_root + 1, rep_counts)
            if null_score is not None and -null_score >= beta:
                return beta

    original_alpha = alpha
    best_score = float("-inf")
    move_idx = 0

    # Futility pruning: at depth 1, skip quiet moves that can't raise alpha
    FUTILITY_MARGIN = 300
    can_futility_prune = depth == 1 and not in_check
    static_eval = evaluate_board_full(board, len(legal_moves)) if can_futility_prune else None

    if rep_counts is not None:
        rep_counts[current_key] = rep_counts.get(current_key, 0) + 1

    try:
        for move in order_moves(board, legal_moves, ply_from_root):
            is_capture = move.is_capture(board)
            is_killer = ply_from_root < MAX_PLY and (
                move == killer_moves[ply_from_root][0] or move == killer_moves[ply_from_root][1]
            )

            if can_futility_prune and not is_capture and not is_killer and static_eval + FUTILITY_MARGIN < alpha:
                move_idx += 1
                continue

            board.apply(move)
            gives_check = board in CHECK

            # Late Move Reduction: quiet, non-killer, non-check moves after the first few
            if not in_check and depth >= 3 and move_idx >= 2 and not is_capture and not is_killer and not gives_check:
                reduction = 1 + (1 if move_idx >= 6 else 0)
                score = negamax(board, depth - 1 + extension - reduction, -alpha - 1, -alpha, start_time, time_limit, ply_from_root + 1, rep_counts)
                if score is not None:
                    score = -score
                    if score > alpha:
                        # Fail-high on reduced search: re-search at full depth
                        score = negamax(board, depth - 1 + extension, -beta, -alpha, start_time, time_limit, ply_from_root + 1, rep_counts)
                        if score is not None:
                            score = -score
            else:
                score = negamax(board, depth - 1 + extension, -beta, -alpha, start_time, time_limit, ply_from_root + 1, rep_counts)
                if score is not None:
                    score = -score

            board.undo()
            move_idx += 1

            if score is None:
                return None

            if score > best_score:
                best_score = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if not is_capture:
                    from_idx = SQ_TO_INT[move.origin]
                    to_idx = SQ_TO_INT[move.destination]
                    if ply_from_root < MAX_PLY:
                        if killer_moves[ply_from_root][0] != move:
                            killer_moves[ply_from_root][1] = killer_moves[ply_from_root][0]
                            killer_moves[ply_from_root][0] = move
                    history_heuristic[from_idx][to_idx] += depth * depth
                break

        tt_store(board, depth, best_score, original_alpha, beta)
        return best_score
    finally:
        if rep_counts is not None:
            rep_counts[current_key] -= 1
            if rep_counts[current_key] == 0:
                del rep_counts[current_key]


def find_best_move(board, depth, start_time, time_limit, legal_moves, alpha, beta, rep_counts=None):
    best_move = None
    best_score = float("-inf")
    timed_out = False

    for move in order_moves(board, legal_moves, 0):
        if _g_stop or time.time() > _g_deadline:
            timed_out = True
            break
        board.apply(move)
        score = negamax(board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root=1, rep_counts=rep_counts)
        board.undo()
        if score is None:
            timed_out = True
            break
        score = -score

        if score > best_score:
            best_score = score
            best_move = move
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

        print(f"info score cp {score} pv {move.uci()}")

    return best_move, best_score, timed_out


def _calc_time_for_move(total_time_remaining, move_number, increment):
    """Adaptive time allocation matching the C++ formula with low-time safety."""
    if total_time_remaining < 3.0:
        return max(0.05, total_time_remaining * 0.1)
    moves_to_go = max(1, min(40, 60 - move_number))
    reserve = min(1.0, total_time_remaining * 0.05)
    return max(
        0.1,
        min(
            (total_time_remaining - reserve) / moves_to_go + 0.5 * increment,
            total_time_remaining * 0.4,
        ),
    )


def _get_ponder_move(board: Board, best_move: Move) -> Move | None:
    """Return the top-ordered reply after best_move as a ponder hint."""
    board.apply(best_move)
    legal = list(board.legal_moves())
    result = order_moves(board, legal, 0)[0] if legal else None
    board.undo()
    return result


def _stop_pondering() -> None:
    global _g_stop, _g_search_thread
    if _g_search_thread and _g_search_thread.is_alive():
        _g_stop = True
        _g_search_thread.join()
        _g_stop = False
    _g_search_thread = None


def find_best_move_iterative(board, max_depth, total_time_remaining, increment=0.0, ponder: bool = False):
    global _g_deadline
    time_for_move = _calc_time_for_move(total_time_remaining, board.fullmove_number, increment)
    start_time = time.time()
    if not ponder:
        _g_deadline = start_time + time_for_move
    reset_search_state()

    legal_moves = list(board.legal_moves())
    if not legal_moves:
        print("info string No legal moves available")
        return None, None

    # Build repetition counter from game history (includes root position).
    # Root is counted twice: once from game history, once for the active search,
    # so any branch cycling back to root is correctly detected as a 2-fold draw.
    rep_counts: dict[int, int] = {}
    for key in game_position_keys:
        rep_counts[key] = rep_counts.get(key, 0) + 1
    if game_position_keys:
        root_key = game_position_keys[-1]
        rep_counts[root_key] = rep_counts.get(root_key, 0) + 1

    best_move = legal_moves[0]
    prev_score = 0

    for depth in range(1, max_depth + 1):
        print(f"info string Searching at depth {depth}")

        if depth <= 1:
            alpha, beta = -MATE_SCORE, MATE_SCORE
            window = MATE_SCORE
        else:
            window = 50
            alpha = max(-MATE_SCORE, prev_score - window)
            beta = min(MATE_SCORE, prev_score + window)

        timed_out = False

        while True:
            move, score, timed_out = find_best_move(
                board, depth, start_time, time_for_move, legal_moves, alpha, beta, rep_counts
            )

            if timed_out:
                print("info string Search interrupted by time, keeping previous best move")
                break

            if move is None:
                break

            if score <= alpha:
                alpha = max(-MATE_SCORE, alpha - window)
                window *= 2
                print("info string Aspiration window fail-low, widening")
                continue
            elif score >= beta:
                beta = min(MATE_SCORE, beta + window)
                window *= 2
                print("info string Aspiration window fail-high, widening")
                continue
            else:
                prev_score = score
                best_move = move
                print(f"info string Best move at depth {depth}: {best_move.uci()}")
                break

        if timed_out:
            break

        elapsed = time.time() - start_time
        if not ponder and elapsed > 0.9 * time_for_move:
            print("info string Stopping iterative deepening due to time")
            break

    ponder_move = _get_ponder_move(board, best_move) if best_move else None
    return best_move, ponder_move


def main():
    # When launched as a subprocess (pipe), stdout is block-buffered.
    # Force line buffering so every print() reaches the GUI immediately.
    sys.stdout.reconfigure(line_buffering=True)

    # Declare all module-level search-control globals we write to in this function.
    global _g_stop, _g_deadline, _g_search_thread, _g_ponder_params

    board = Board()
    depth = 30
    total_time_remaining = 60.0
    increment = 0.0

    try:
        book = chess.polyglot.open_reader("books/gm2001.bin")
    except Exception as e:
        book = None
        logging.warning(f"Could not open Polyglot book: {e}")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()

            if line == "uci":
                print("id name OmbleCavalier")
                print("id author Hughes Perreault")
                print("option name Ponder type check default true")
                print("uciok")
                sys.stdout.flush()

            elif line == "isready":
                print("readyok")
                sys.stdout.flush()

            elif line == "ucinewgame":
                _stop_pondering()
                board = Board.from_fen(
                    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                )
                reset_search_state()

            elif line.startswith("position"):
                tokens = line.split()
                if "startpos" in tokens:
                    board = Board.from_fen(
                        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                    )
                    game_position_keys.clear()
                    game_position_keys.append(position_key(board))
                    if "moves" in tokens:
                        for move_str in tokens[tokens.index("moves") + 1 :]:
                            board.apply(Move.from_uci(move_str))
                            game_position_keys.append(position_key(board))
                elif "fen" in tokens:
                    fen_idx = tokens.index("fen") + 1
                    if "moves" in tokens:
                        moves_idx = tokens.index("moves")
                        board = Board.from_fen(" ".join(tokens[fen_idx:moves_idx]))
                        game_position_keys.clear()
                        game_position_keys.append(position_key(board))
                        for move_str in tokens[moves_idx + 1 :]:
                            board.apply(Move.from_uci(move_str))
                            game_position_keys.append(position_key(board))
                    else:
                        board = Board.from_fen(" ".join(tokens[fen_idx:]))
                        game_position_keys.clear()
                        game_position_keys.append(position_key(board))

            elif line.startswith("go"):
                tokens = line.split()
                is_ponder = "ponder" in tokens
                increment = 0.0

                _stop_pondering()

                if "depth" in tokens:
                    depth = int(tokens[tokens.index("depth") + 1])
                if "movetime" in tokens:
                    total_time_remaining = int(tokens[tokens.index("movetime") + 1]) / 1000
                if "wtime" in tokens and board.turn == WHITE:
                    total_time_remaining = int(tokens[tokens.index("wtime") + 1]) / 1000
                if "btime" in tokens and board.turn != WHITE:
                    total_time_remaining = int(tokens[tokens.index("btime") + 1]) / 1000
                if "winc" in tokens and board.turn == WHITE:
                    increment = int(tokens[tokens.index("winc") + 1]) / 1000
                if "binc" in tokens and board.turn != WHITE:
                    increment = int(tokens[tokens.index("binc") + 1]) / 1000

                if is_ponder:
                    _g_ponder_params.clear()
                    _g_ponder_params.update({
                        "total_time": total_time_remaining,
                        "increment": increment,
                        "fullmove": board.fullmove_number,
                    })
                    _g_deadline = float("inf")
                    board_copy = board.copy()
                    search_depth = depth

                    def _ponder_fn(b=board_copy, d=search_depth):
                        global _g_search_thread
                        best_move, ponder_move = find_best_move_iterative(
                            b, d, 9999.0, 0.0, ponder=True
                        )
                        bm = best_move.uci() if best_move else "0000"
                        ponder_str = (
                            f" ponder {ponder_move.uci()}"
                            if ponder_move and not _g_stop
                            else ""
                        )
                        print(f"bestmove {bm}{ponder_str}")
                        sys.stdout.flush()

                    _g_search_thread = threading.Thread(target=_ponder_fn, daemon=True)
                    _g_search_thread.start()
                else:
                    book_move = None
                    if book is not None:
                        try:
                            import chess as pychess

                            py_board = pychess.Board(board.fen())
                            entry = book.find(py_board)
                            book_move = entry.move.uci()
                        except Exception:
                            book_move = None

                    if book_move:
                        print(f"bestmove {book_move}")
                    else:
                        best_move, ponder_move = find_best_move_iterative(
                            board, depth, total_time_remaining, increment
                        )
                        if best_move:
                            ponder_str = f" ponder {ponder_move.uci()}" if ponder_move else ""
                            print(f"bestmove {best_move.uci()}{ponder_str}")
                        else:
                            print("bestmove 0000")
                    sys.stdout.flush()

            elif line == "ponderhit":
                p = _g_ponder_params
                if p:
                    time_for_move = _calc_time_for_move(
                        p["total_time"], p["fullmove"], p["increment"]
                    )
                    _g_deadline = time.time() + time_for_move

            elif line == "stop":
                _stop_pondering()

            elif line == "quit":
                _stop_pondering()
                break

            else:
                print(f"info string Unknown command: {line}")
                sys.stdout.flush()

        except Exception as e:
            print(f"info string Exception: {e}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
