#!/usr/bin/env python3
import sys
import random
import bulletchess as chess
from bulletchess import Board, Move
import logging

logging.basicConfig(filename="engine_debug.log", level=logging.DEBUG)

logging.debug("Engine started")

def main():
    board = Board()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()

        if line == "uci":
            print("id name RandomMoves")
            print("id author Hughes Perreault")
            print("uciok")
            sys.stdout.flush()

        elif line == "isready":
            print("readyok")
            sys.stdout.flush()

        elif line.startswith("position"):
            tokens = line.split()
            if "startpos" in tokens:
                board = Board.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                if "moves" in tokens:
                    moves_index = tokens.index("moves") + 1
                    for move_str in tokens[moves_index:]:
                        move = Move.from_uci(move_str)
                        board.apply(move)

        elif line == "ucinewgame":
            board = Board.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

        elif line.startswith("go"):
            legal_moves = list(board.legal_moves())
            if legal_moves:
                move = random.choice(legal_moves)
                print(f"bestmove {move.uci()}")
                sys.stdout.flush()

        elif line == "quit":
            break

        else:
            print(f"info string Unknown command: {line}")
            sys.stdout.flush()

if __name__ == "__main__":
    main()