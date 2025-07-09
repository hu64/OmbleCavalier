#!/usr/bin/env python3
import logging
import sys
import time

import bulletchess as chess
from bulletchess import (
    BLACK,
    CHECK,
    CHECKMATE,
    DRAW,
    INSUFFICIENT_MATERIAL,
    PIECE_TYPES,
    STALEMATE,
    WHITE,
    Board,
    Move,
)

logging.basicConfig(level=logging.DEBUG)

# Material values
MATERIAL_VALUES = {
    PIECE_TYPES[0]: 100,
    PIECE_TYPES[1]: 320,
    PIECE_TYPES[2]: 330,
    PIECE_TYPES[3]: 500,
    PIECE_TYPES[4]: 900,
    PIECE_TYPES[5]: 60000,
}
# Transform the piece-square tables into 2D arrays (8x8)
pst_2d = {
    chess.PAWN: [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [78, 83, 86, 73, 102, 82, 85, 90],
        [7, 29, 21, 44, 40, 31, 44, 7],
        [-17, 16, -2, 15, 14, 0, 15, -13],
        [-26, 3, 10, 9, 6, 1, 0, -23],
        [-22, 9, 5, -11, -10, -2, 3, -19],
        [-31, 8, -7, -37, -36, -14, 3, -31],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ],
    chess.KNIGHT: [
        [-66, -53, -75, -75, -10, -55, -58, -70],
        [-3, -6, 100, -36, 4, 62, -4, -14],
        [10, 67, 1, 74, 73, 27, 62, -2],
        [24, 24, 45, 37, 33, 41, 25, 17],
        [-1, 5, 31, 21, 22, 35, 2, 0],
        [-18, 10, 13, 22, 18, 15, 11, -14],
        [-23, -15, 2, 0, 2, 0, -23, -20],
        [-74, -23, -26, -24, -19, -35, -22, -69],
    ],
    chess.BISHOP: [
        [-59, -78, -82, -76, -23, -107, -37, -50],
        [-11, 20, 35, -42, -39, 31, 2, -22],
        [-9, 39, -32, 41, 52, -10, 28, -14],
        [25, 17, 20, 34, 26, 25, 15, 10],
        [13, 10, 17, 23, 17, 16, 0, 7],
        [14, 25, 24, 15, 8, 25, 20, 15],
        [19, 20, 11, 6, 7, 6, 20, 16],
        [-7, 2, -15, -12, -14, -15, -10, -10],
    ],
    chess.ROOK: [
        [35, 29, 33, 4, 37, 33, 56, 50],
        [55, 29, 56, 67, 55, 62, 34, 60],
        [19, 35, 28, 33, 45, 27, 25, 15],
        [0, 5, 16, 13, 18, -4, -9, -6],
        [-28, -35, -16, -21, -13, -29, -46, -30],
        [-42, -28, -42, -25, -25, -35, -26, -46],
        [-53, -38, -31, -26, -29, -43, -44, -53],
        [-30, -24, -18, 5, -2, -18, -31, -32],
    ],
    chess.QUEEN: [
        [6, 1, -8, -104, 69, 24, 88, 26],
        [14, 32, 60, -10, 20, 76, 57, 24],
        [-2, 43, 32, 60, 72, 63, 43, 2],
        [1, -16, 22, 17, 25, 20, -13, -6],
        [-14, -15, -2, -5, -1, -10, -20, -22],
        [-30, -6, -13, -11, -16, -11, -16, -27],
        [-36, -18, 0, -19, -15, -15, -21, -38],
        [-39, -30, -31, -13, -31, -36, -34, -42],
    ],
    chess.KING: [
        [4, 54, 47, -99, -99, 60, 83, -62],
        [-32, 10, 55, 56, 56, 55, 10, 3],
        [-62, 12, -57, 44, -67, 28, 37, -31],
        [-55, 50, 11, -4, -19, 13, 0, -49],
        [-55, -43, -52, -28, -51, -47, -8, -50],
        [-47, -42, -43, -79, -64, -32, -29, -32],
        [-4, 3, -14, -50, -57, -18, 13, 4],
        [17, 30, -3, -14, 6, -1, 40, 18],
    ],
}

TRANSPOSITION_TABLE = {}


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


def evaluate_board(board, ply_from_root=0):
    if board in CHECKMATE:
        return -100000 + ply_from_root

    if board in STALEMATE or board in INSUFFICIENT_MATERIAL:
        return 0

    score = 0
    material_score = 0

    for piece_type in MATERIAL_VALUES:
        material_score += (
            board[WHITE, piece_type].__len__() * MATERIAL_VALUES[piece_type]
        ) - (board[BLACK, piece_type].__len__() * MATERIAL_VALUES[piece_type])

        # for square in board.pieces(piece_type, chess.WHITE):
        #     rank = 7 - chess.square_rank(square)
        #     file = chess.square_file(square)

        #     material_score += MATERIAL_VALUES[piece_type] + pst_2d[piece_type][rank][file]

        # for square in board.pieces(piece_type, chess.BLACK):
        #     rank = chess.square_rank(square)
        #     file = chess.square_file(square)
        #     material_score -= MATERIAL_VALUES[piece_type] + pst_2d[piece_type][rank][file]

    # if board.is_repetition(3) or board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
    #     return -200 if material_score >= 200 else 0

    score += material_score if board.turn == WHITE else -material_score

    # nbr_doubled_pawns = count_doubled_pawns(board, board.turn) - count_doubled_pawns(board, not board.turn)
    # nbr_isolated_pawns = count_isolated_pawns(board, board.turn) - count_isolated_pawns(board, not board.turn)
    # nbr_blocked_pawns = count_blocked_pawns(board, board.turn) - count_blocked_pawns(board, not board.turn)
    # DSI = 50 * (nbr_doubled_pawns + nbr_isolated_pawns + nbr_blocked_pawns)
    # score += DSI

    mobility_score = 10 * len(list(board.legal_moves()))
    score += mobility_score if board.turn == WHITE else -mobility_score

    return score


def count_doubled_pawns(board, color):
    """Count doubled pawns for a given color."""
    pawns = board.pieces(chess.PAWN, color)
    files = set()
    doubled_count = 0
    for square in pawns:
        file_index = chess.square_file(square)
        if file_index in files:
            doubled_count += 1
        else:
            files.add(file_index)
    return doubled_count


def count_isolated_pawns(board, color):
    """Count isolated pawns for a given color."""
    pawns = board.pieces(chess.PAWN, color)
    isolated_count = 0
    for square in pawns:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)

        # Check if there are no pawns on adjacent files
        left_file = file_index - 1
        right_file = file_index + 1

        has_left_pawn = left_file >= 0 and any(
            chess.square(left_file, rank) in pawns for rank in range(8)
        )
        has_right_pawn = right_file <= 7 and any(
            chess.square(right_file, rank) in pawns for rank in range(8)
        )

        if not (has_left_pawn or has_right_pawn):
            isolated_count += 1

    return isolated_count


def count_blocked_pawns(board, color):
    """Count blocked pawns for a given color."""
    pawns = board.pieces(chess.PAWN, color)
    blocked_count = 0
    for square in pawns:
        # Check if the pawn is blocked by a piece in front of it
        if color == chess.WHITE and board.piece_at(square + 8) is not None:
            blocked_count += 1
        elif color == chess.BLACK and board.piece_at(square - 8) is not None:
            blocked_count += 1
    return blocked_count


def get_piece_value(board, square):
    pt = board[square].piece_type
    return MATERIAL_VALUES[pt] if pt else 0


# Order moves based on a heuristic
def order_moves(board):
    """Order moves to improve Alpha-Beta Pruning efficiency."""

    def move_score(move):
        board.apply(move)
        is_check = board in CHECK
        board.undo()
        if is_check:
            return 70
        if move.is_capture(board):
            captured_value = get_piece_value(board, move.destination)
            capturing_value = get_piece_value(board, move.origin)

            return 100 + ((captured_value - capturing_value) / 100)
        if move.is_castling(board):
            return 90
        if move.promotion:
            return 60
        return 0

    return sorted(board.legal_moves(), key=move_score, reverse=True)


def quiesce(board, alpha, beta, ply_from_root=0):
    stand_pat = evaluate_board(board, ply_from_root)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    for move in board.legal_moves():
        if move.is_capture(board):
            board.apply(move)
            score = -quiesce(board, -beta, -alpha, ply_from_root + 1)
            board.undo()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
    return alpha


def negamax(board, depth, alpha, beta, start_time, time_limit, ply_from_root=0):
    if time.time() - start_time > time_limit:
        return None

    if board in CHECKMATE:
        return -100000 + ply_from_root

    tt_value = tt_lookup(board, depth, alpha, beta)
    if tt_value is not None:
        return tt_value

    if depth <= 0 or board in (CHECKMATE, DRAW):
        return quiesce(board, alpha, beta, ply_from_root)

    original_alpha = alpha
    best_score = float("-inf")
    for move in order_moves(board):
        board.apply(move)
        score = negamax(
            board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root + 1
        )
        board.undo()
        if score is None:
            return None
        else:
            score = -score

        if score > best_score:
            best_score = score

        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    tt_store(board, depth, best_score, original_alpha, beta)
    return best_score


def find_best_move(board, depth, total_time_remaining):
    print(
        f"info string Finding best move for {'White' if board.turn == WHITE else 'Black'} at depth {depth} with total time remaining {total_time_remaining:.2f} seconds"
    )

    best_move = None
    best_score = -float("inf")
    alpha = -float("inf")
    beta = float("inf")

    time_limit = min(max(0.05 * total_time_remaining, 0.5), total_time_remaining / 10)
    start_time = time.time()

    for move in order_moves(board):
        board.apply(move)
        score = negamax(
            board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root=1
        )
        board.undo()
        if score is None:
            return None
        else:
            score = -score

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, score)

        if abs(score) > 99900:
            # Mate score: convert distance-to-mate from score
            mate_in = 100000 - abs(score)
            sign = 1 if score > 0 else -1
            print(f"info score mate {sign * (mate_in + 1)} pv {move.uci()}")
        else:
            print(f"info score cp {score} pv {move.uci()}")

        # Early cutoff on mate found
        if best_score > 99900:
            break

        if time.time() - start_time > time_limit:
            break

    return best_move


def find_best_move_iterative(board, max_depth, total_time_remaining):
    legal_moves_list = list(board.legal_moves())
    if not legal_moves_list:
        print("info string No legal moves available")
        return None

    best_move = legal_moves_list[0]
    for depth in range(1, max_depth + 1):
        print(f"info string Searching at depth {depth}")
        move = find_best_move(board, depth, total_time_remaining)
        if move in legal_moves_list:
            best_move = move
        else:
            print("info string No legal moves found")
            break

        # Stop early if mate found
        if best_move is not None:
            board.apply(best_move)
            if board in CHECKMATE:
                board.undo()
                break
            board.undo()

    return best_move


def main():
    board = Board()
    depth = 6

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()

            if line == "uci":
                print("id name OmbleCavalier")
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

            elif line.startswith("position"):
                tokens = line.split()
                if "startpos" in tokens:
                    board = Board.from_fen(
                        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                    )
                    if "moves" in tokens:
                        moves_index = tokens.index("moves") + 1
                        for move_str in tokens[moves_index:]:
                            move = Move.from_uci(move_str)
                            board.apply(move)

            elif line.startswith("go"):
                tokens = line.split()
                total_time_remaining = 50  # default in seconds

                if "depth" in tokens:
                    depth_index = tokens.index("depth") + 1
                    depth = int(tokens[depth_index])
                if "wtime" in tokens and board.turn == WHITE:
                    time_index = tokens.index("wtime") + 1
                    total_time_remaining = int(tokens[time_index]) / 1000
                if "btime" in tokens and not board.turn == WHITE:
                    time_index = tokens.index("btime") + 1
                    total_time_remaining = int(tokens[time_index]) / 1000

                best_move = find_best_move_iterative(board, depth, total_time_remaining)
                if best_move is not None:
                    print(f"bestmove {best_move.uci()}")
                else:
                    print("bestmove 0000")
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
