#!/usr/bin/env python3
import logging
import sys
import time

import bulletchess as chess
import chess.polyglot
import numpy as np
from bulletchess import (
    BLACK,
    CHECK,
    CHECKMATE,
    DRAW,
    PIECE_TYPES,
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
        return -(100000 - ply_from_root)

    if board in DRAW:
        return 0

    score = 0
    material_score = 0

    for index, piece_type in enumerate(MATERIAL_VALUES):
        material_score += (
            len(board[WHITE, piece_type]) * MATERIAL_VALUES[piece_type]
            - len(board[BLACK, piece_type]) * MATERIAL_VALUES[piece_type]
        )

    score += material_score if board.turn == WHITE else -material_score

    # Mobility
    mobility_score = 10 * len(list(board.legal_moves()))
    score += mobility_score

    return score


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
            return 200

        if move.is_capture(board):
            captured_value = get_piece_value(board, move.destination)
            capturing_value = get_piece_value(board, move.origin)

            return 100 + ((captured_value - capturing_value) / 100)
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

    if board in DRAW:
        return 0

    tt_value = tt_lookup(board, depth, alpha, beta)
    if tt_value is not None:
        return tt_value

    if depth <= 0:
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


def find_best_move(board, depth, start_time, time_limit):
    best_move = None
    best_score = -88888
    alpha = -88888
    beta = 88888
    timed_out = False

    for move in order_moves(board):
        if time.time() - start_time > time_limit:
            print("info string Time limit reached in find best move, stopping search")
            timed_out = True
            break
        board.apply(move)
        score = negamax(
            board, depth - 1, -beta, -alpha, start_time, time_limit, ply_from_root=1
        )
        board.undo()
        if score is None:
            timed_out = True
            break
        else:
            score = -score

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, score)
        print(f"info score cp {score} pv {move.uci()}")

    return best_move, timed_out


def find_best_move_iterative(board, max_depth, total_time_remaining):
    time_limit = total_time_remaining / max(10, (40 - (len(board.history) / 2)))
    start_time = time.time()

    legal_moves_list = list(board.legal_moves())
    if not legal_moves_list:
        print("info string No legal moves available")
        return None

    best_move = legal_moves_list[0]
    for depth in range(1, max_depth + 1):
        print(f"info string Searching at depth {depth}")
        move, timed_out = find_best_move(board, depth, start_time, time_limit)
        if not timed_out and move in legal_moves_list:
            best_move = move
            print(f"info string Best move at depth {depth}: {best_move.uci()}")
        elif timed_out:
            print("info string Search interrupted by time, keeping previous best move")
            break
        else:
            print("info string No legal moves found")
            break

    return best_move

def main():
    board = Board()
    depth = 30

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
                print("uciok")
                sys.stdout.flush()

            elif line == "isready":
                print("readyok")
                sys.stdout.flush()

            elif line == "ucinewgame":
                board = Board.from_fen(
                    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                )
                TRANSPOSITION_TABLE = {}

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

                if "depth" in tokens:
                    depth_index = tokens.index("depth") + 1
                    depth = int(tokens[depth_index])
                if "movetime" in tokens:
                    time_index = tokens.index("movetime") + 1
                    total_time_remaining = int(tokens[time_index]) / 1000
                if "wtime" in tokens and board.turn == WHITE:
                    time_index = tokens.index("wtime") + 1
                    total_time_remaining = int(tokens[time_index]) / 1000
                if "btime" in tokens and not board.turn == WHITE:
                    time_index = tokens.index("btime") + 1
                    total_time_remaining = int(tokens[time_index]) / 1000

                # Try Polyglot book move first
                book_move = None
                if book is not None:
                    try:
                        # Convert bulletchess Board to python-chess Board
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
                        board, depth, total_time_remaining
                    )
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
