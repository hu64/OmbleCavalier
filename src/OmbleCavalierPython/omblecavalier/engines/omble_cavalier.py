#!/usr/bin/env python3
import logging
import sys
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

MATERIAL_VALUES = {
    PIECE_TYPES[0]: 100,    # PAWN
    PIECE_TYPES[1]: 320,    # KNIGHT
    PIECE_TYPES[2]: 330,    # BISHOP
    PIECE_TYPES[3]: 500,    # ROOK
    PIECE_TYPES[4]: 900,    # QUEEN
    PIECE_TYPES[5]: 60000,  # KING
}

MATE_SCORE = 100000
MAX_PLY = 128

# PST tables from White's perspective (a1=0, h8=63).
# For Black pieces, index with MIRROR[sq_int] to flip vertically.
PAWN_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,  # rank 1
     5, 10, 10,-20,-20, 10, 10,  5,  # rank 2
     5, -5,-10,  0,  0,-10, -5,  5,  # rank 3
     0,  0,  0, 20, 20,  0,  0,  0,  # rank 4
     5,  5, 10, 25, 25, 10,  5,  5,  # rank 5
    10, 10, 20, 30, 30, 20, 10, 10,  # rank 6
    50, 50, 50, 50, 50, 50, 50, 50,  # rank 7
     0,  0,  0,  0,  0,  0,  0,  0,  # rank 8
]

KNIGHT_PST = [
    -50,-40,-30,-30,-30,-30,-40,-50,  # rank 1
    -40,-20,  0,  5,  5,  0,-20,-40,  # rank 2
    -30,  5, 10, 15, 15, 10,  5,-30,  # rank 3
    -30,  0, 15, 20, 20, 15,  0,-30,  # rank 4
    -30,  5, 15, 20, 20, 15,  5,-30,  # rank 5
    -30,  0, 10, 15, 15, 10,  0,-30,  # rank 6
    -40,-20,  0,  0,  0,  0,-20,-40,  # rank 7
    -50,-40,-30,-30,-30,-30,-40,-50,  # rank 8
]

BISHOP_PST = [
    -20,-10,-10,-10,-10,-10,-10,-20,  # rank 1
    -10,  5,  0,  0,  0,  0,  5,-10,  # rank 2
    -10, 10, 10, 10, 10, 10, 10,-10,  # rank 3
    -10,  0, 10, 10, 10, 10,  0,-10,  # rank 4
    -10,  5,  5, 10, 10,  5,  5,-10,  # rank 5
    -10,  0,  5, 10, 10,  5,  0,-10,  # rank 6
    -10,  0,  0,  0,  0,  0,  0,-10,  # rank 7
    -20,-10,-10,-10,-10,-10,-10,-20,  # rank 8
]

ROOK_PST = [
     0,  0,  0,  5,  5,  0,  0,  0,  # rank 1
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 2
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 3
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 4
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 5
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 6
     5, 10, 10, 10, 10, 10, 10,  5,  # rank 7
     0,  0,  0,  0,  0,  0,  0,  0,  # rank 8
]

QUEEN_PST = [
    -20,-10,-10, -5, -5,-10,-10,-20,  # rank 1
    -10,  0,  5,  0,  0,  0,  0,-10,  # rank 2
    -10,  5,  5,  5,  5,  5,  0,-10,  # rank 3
      0,  0,  5,  5,  5,  5,  0, -5,  # rank 4
     -5,  0,  5,  5,  5,  5,  0, -5,  # rank 5
    -10,  0,  5,  5,  5,  5,  0,-10,  # rank 6
    -10,  0,  0,  0,  0,  0,  0,-10,  # rank 7
    -20,-10,-10, -5, -5,-10,-10,-20,  # rank 8
]

KING_PST = [
     20, 30, 10,  0,  0, 10, 30, 20,  # rank 1
     20, 20,  0,  0,  0,  0, 20, 20,  # rank 2
    -10,-20,-20,-20,-20,-20,-20,-10,  # rank 3
    -20,-30,-30,-40,-40,-30,-30,-20,  # rank 4
    -30,-40,-40,-50,-50,-40,-40,-30,  # rank 5
    -30,-40,-40,-50,-50,-40,-40,-30,  # rank 6
    -30,-40,-40,-50,-50,-40,-40,-30,  # rank 7
    -30,-40,-40,-50,-50,-40,-40,-30,  # rank 8
]

PST_TABLES = [PAWN_PST, KNIGHT_PST, BISHOP_PST, ROOK_PST, QUEEN_PST, KING_PST]

# Precomputed per-square values (material + PST) indexed by sq_int (0-63).
# Eliminates per-node dict and addition overhead inside the hot eval loop.
_W_TABLES: list[list[int]] = []  # White: W_TABLES[piece_idx][sq_int]
_B_TABLES: list[list[int]] = []  # Black: B_TABLES[piece_idx][sq_int]
for _i, _pt in enumerate(PIECE_TYPES):
    _mv = MATERIAL_VALUES[_pt]
    _pst = PST_TABLES[_i]
    _W_TABLES.append([_mv + _pst[sq] for sq in range(64)])
    _B_TABLES.append([_mv + _pst[MIRROR[sq]] for sq in range(64)])

TRANSPOSITION_TABLE = {}
killer_moves = [[None, None] for _ in range(MAX_PLY)]
history_heuristic = [[0] * 64 for _ in range(64)]


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
    return MATERIAL_VALUES.get(piece.piece_type, 0)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_board_fast(board, legal_moves_count):
    """Material + PST + bishop pair + mobility. Used in quiescence search."""
    score = 0
    sq_map = SQ_TO_INT
    wt = _W_TABLES
    bt = _B_TABLES
    for i, piece_type in enumerate(PIECE_TYPES):
        w = wt[i]
        b = bt[i]
        for sq in board[WHITE, piece_type]:
            score += w[sq_map[sq]]
        for sq in board[BLACK, piece_type]:
            score -= b[sq_map[sq]]

    if len(board[WHITE, PIECE_TYPES[2]]) >= 2:
        score += 30
    if len(board[BLACK, PIECE_TYPES[2]]) >= 2:
        score -= 30

    if board.turn == WHITE:
        score += legal_moves_count * 5
    else:
        score -= legal_moves_count * 5

    return score if board.turn == WHITE else -score


def pawn_structure(board, color):
    """Doubled, isolated, passed pawn evaluation. Single-pass per color."""
    pawn_sqs = [(SQ_TO_INT[sq] // 8, SQ_TO_INT[sq] % 8) for sq in board[color, PIECE_TYPES[0]]]
    if not pawn_sqs:
        return 0

    opp = BLACK if color == WHITE else WHITE
    opp_sqs = [(SQ_TO_INT[sq] // 8, SQ_TO_INT[sq] % 8) for sq in board[opp, PIECE_TYPES[0]]]
    all_sqs = pawn_sqs + opp_sqs

    my_files = [f for _, f in pawn_sqs]
    file_set = set(my_files)

    file_counts: dict[int, int] = {}
    for f in my_files:
        file_counts[f] = file_counts.get(f, 0) + 1

    doubled = sum(c - 1 for c in file_counts.values() if c > 1)
    isolated = sum(1 for _, f in pawn_sqs if (f - 1) not in file_set and (f + 1) not in file_set)

    passed = 0
    is_white = color == WHITE
    for rank, file in pawn_sqs:
        is_passed = True
        for other_rank, other_file in all_sqs:
            d = other_file - file
            if -1 <= d <= 1:
                if is_white and other_rank > rank:
                    is_passed = False
                    break
                if not is_white and other_rank < rank:
                    is_passed = False
                    break
        if is_passed:
            passed += 1

    return 20 * passed - 12 * doubled - 15 * isolated


def king_safety(board, color):
    king_sqs = list(board[color, PIECE_TYPES[5]])
    if not king_sqs:
        return 0
    king_idx = SQ_TO_INT[king_sqs[0]]
    kfile = king_idx % 8
    krank = king_idx // 8

    opp = BLACK if color == WHITE else WHITE
    friendly_pawns = set(board[color, PIECE_TYPES[0]])
    opp_pawns = set(board[opp, PIECE_TYPES[0]])

    penalty = 0
    shield_rank = krank + 1 if color == WHITE else krank - 1
    if 0 <= shield_rank <= 7:
        for df in (-1, 0, 1):
            f = kfile + df
            if 0 <= f <= 7 and SQUARES[shield_rank * 8 + f] not in friendly_pawns:
                penalty += 15

    my_pawn_files = {SQ_TO_INT[sq] % 8 for sq in friendly_pawns}
    opp_pawn_files = {SQ_TO_INT[sq] % 8 for sq in opp_pawns}
    for df in (-1, 0, 1):
        f = kfile + df
        if 0 <= f <= 7 and f not in my_pawn_files:
            penalty += 20 if f not in opp_pawn_files else 10

    return penalty


def evaluate_board_full(board, legal_moves_count):
    """Full positional evaluation (pawn structure + king safety).
    Not called in the main search path — reserved for futility pruning
    or analysis once that feature is implemented."""
    score = 0
    sq_map = SQ_TO_INT
    wt = _W_TABLES
    bt = _B_TABLES
    for i, piece_type in enumerate(PIECE_TYPES):
        w = wt[i]
        b = bt[i]
        for sq in board[WHITE, piece_type]:
            score += w[sq_map[sq]]
        for sq in board[BLACK, piece_type]:
            score -= b[sq_map[sq]]

    if len(board[WHITE, PIECE_TYPES[2]]) >= 2:
        score += 30
    if len(board[BLACK, PIECE_TYPES[2]]) >= 2:
        score -= 30

    score += pawn_structure(board, WHITE)
    score -= pawn_structure(board, BLACK)
    score -= king_safety(board, WHITE)
    score += king_safety(board, BLACK)

    if board.turn == WHITE:
        score += legal_moves_count * 5
    else:
        score -= legal_moves_count * 5

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


def negamax(board, depth, alpha, beta, start_time, time_limit, ply_from_root=0):
    if time.time() - start_time > time_limit:
        return None

    legal_moves = list(board.legal_moves())

    if not legal_moves:
        return -(MATE_SCORE - ply_from_root) if board in CHECK else 0
    if board.halfmove_clock >= 100 or board in DRAW:
        return 0

    tt_value = tt_lookup(board, depth, alpha, beta)
    if tt_value is not None:
        return tt_value

    if depth <= 0:
        # Pass legal_moves and stand_pat into quiesce to avoid recomputing them.
        stand_pat = evaluate_board_fast(board, len(legal_moves))
        return quiesce(board, alpha, beta, ply_from_root, legal_moves, stand_pat)

    # Null move pruning
    if depth >= 3 and board not in CHECK:
        non_pawn_material = (
            len(board[board.turn, PIECE_TYPES[1]]) * 320
            + len(board[board.turn, PIECE_TYPES[2]]) * 330
            + len(board[board.turn, PIECE_TYPES[3]]) * 500
            + len(board[board.turn, PIECE_TYPES[4]]) * 900
        )
        if non_pawn_material >= 1000:
            fen_parts = board.fen().split()
            fen_parts[1] = "b" if fen_parts[1] == "w" else "w"
            fen_parts[3] = "-"
            null_board = Board.from_fen(" ".join(fen_parts))
            null_score = negamax(null_board, depth - 3, -beta, -beta + 1, start_time, time_limit, ply_from_root + 1)
            if null_score is not None and -null_score >= beta:
                return beta

    original_alpha = alpha
    best_score = float("-inf")

    for move in order_moves(board, legal_moves, ply_from_root):
        board.apply(move)
        score = negamax(board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root + 1)
        board.undo()

        if score is None:
            return None
        score = -score

        if score > best_score:
            best_score = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            if not move.is_capture(board):
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


def find_best_move(board, depth, start_time, time_limit, legal_moves, alpha, beta):
    best_move = None
    best_score = float("-inf")
    timed_out = False

    for move in order_moves(board, legal_moves, 0):
        if time.time() - start_time > time_limit:
            timed_out = True
            break
        board.apply(move)
        score = negamax(board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root=1)
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


def find_best_move_iterative(board, max_depth, total_time_remaining, increment=0.0):
    time_for_move = _calc_time_for_move(total_time_remaining, board.fullmove_number, increment)
    start_time = time.time()
    reset_search_state()

    legal_moves = list(board.legal_moves())
    if not legal_moves:
        print("info string No legal moves available")
        return None

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
                board, depth, start_time, time_for_move, legal_moves, alpha, beta
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
        if elapsed > 0.9 * time_for_move:
            print("info string Stopping iterative deepening due to time")
            break

    return best_move


def main():
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
                print("id name OmbleCavalierNew")
                print("id author Hughes Perreault")
                print("uciok")
                sys.stdout.flush()

            elif line == "isready":
                print("readyok")
                sys.stdout.flush()

            elif line == "ucinewgame":
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
                    if "moves" in tokens:
                        for move_str in tokens[tokens.index("moves") + 1 :]:
                            board.apply(Move.from_uci(move_str))
                elif "fen" in tokens:
                    fen_idx = tokens.index("fen") + 1
                    if "moves" in tokens:
                        moves_idx = tokens.index("moves")
                        board = Board.from_fen(" ".join(tokens[fen_idx:moves_idx]))
                        for move_str in tokens[moves_idx + 1 :]:
                            board.apply(Move.from_uci(move_str))
                    else:
                        board = Board.from_fen(" ".join(tokens[fen_idx:]))

            elif line.startswith("go"):
                tokens = line.split()
                increment = 0.0

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
                    best_move = find_best_move_iterative(
                        board, depth, total_time_remaining, increment
                    )
                    print(f"bestmove {best_move.uci()}" if best_move else "bestmove 0000")
                sys.stdout.flush()

            elif line == "quit":
                break

            else:
                print(f"info string Unknown command: {line}")
                sys.stdout.flush()

        except Exception as e:
            print(f"info string Exception: {e}")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
