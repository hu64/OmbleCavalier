import chess
from omblecavalier.engines.omble_cavalier import evaluate_board, find_best_move  # Import the evaluate_board function from your engine

def test_evaluation():
    # Create a new board
    board = chess.Board()

    # Print the starting position
    print("Starting Position:")
    print(board)
    print(f"Evaluation: {evaluate_board(board)}\n")
    print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    # Set up a custom position (e.g., White is winning)
    board.set_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")  # After 1. e4
    print("Custom Position 1 (After 1. e4):")
    print(board)
    print(f"Evaluation: {evaluate_board(board)}\n")
    print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    # # Set up another custom position (e.g., Black is winning)
    # board.set_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")  # After 1... e5
    # print("Custom Position 2 (After 1... e5):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")

    # # Set up another custom position (e.g., Black is winning)
    # board.set_fen("rnbqk1nr/ppp1p1bp/6p1/5p2/4p3/1PN5/PBPPNPPP/R2QKB1R w KQkq - 2 6")  # After 1... e5
    # print("Custom Position 2 (After 1... e5):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")


    # # Set up a checkmate position
    # board.set_fen("r1bqkb1r/ppp1pppp/n4n2/3P4/2P5/1P6/P2P1PPP/RNBQKBNR b KQkq - 0 4")  # Black is in checkmate
    # print("Custom Position 3 (Checkmate):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")

    # # Set up a checkmate position
    # board.set_fen("rnbqkbnr/2pp1Qpp/pp6/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")  # Black is in checkmate
    # print("Custom Position 3 (Checkmate):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")

    # # Set up a stalemate position
    # board.set_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")  # Black is in stalemate
    # print("Custom Position 4 (Stalemate):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")


    # board.set_fen("4r3/1pp2rbk/6pn/4n3/P3B3/1PB2bqP/6N1/2Q1RRK1 b - - 1 32")  # Black is in stalemate
    # print("mate in 1 (g3g2):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")
    # print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    # board.set_fen("4r3/1pp2rbk/6pn/4n3/P3BN1q/1PB2bPP/8/2Q1RRK1 b - - 0 31")  # Black is in stalemate
    # print("mate in 2 (h4g3):")
    # print(board)
    # print(f"Evaluation: {evaluate_board(board)}\n")
    # print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    
    board.set_fen("kbK5/pp6/1P6/8/8/8/R7/8 w - - 0 2") 
    print("mate in 2 (a2a6):")
    print(board)
    print(f"Evaluation: {evaluate_board(board)}\n")
    print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    board.set_fen("rnbqkbnr/ppp2ppp/3p4/4p3/4P1Q1/8/PPPP1PPP/RNB1KBNR b KQkq - 1 3") 
    print("black wins a queen (c8g4) :")
    print(board)
    print(f"Evaluation: {evaluate_board(board)}\n")
    print(f"Best Move: {find_best_move(board, 3, 10000)}\n")


    board.set_fen("rnbqkbnr/1pp2ppp/p2p4/4p1B1/4P3/3P4/PPP2PPP/RN1QKBNR w KQkq - 0 4") 
    print("white wins a queen (g5d8) :")
    print(board)
    print(f"Evaluation: {evaluate_board(board)}\n")
    print(f"Best Move: {find_best_move(board, 3, 10000)}\n")

    # if chess.WHITE:
    #     print("White to play")
    # if chess.BLACK:
    #     print("Black to play")

if __name__ == "__main__":

    test_evaluation()