#include "chess.hpp"
#include <sstream>
#include <thread>
#include <limits>
#include "puzzles.hpp"
#include "tt.hpp"
#include "book.hpp"
#include "search.hpp"
#include "eval.hpp"
using namespace chess;

// ── Ponder thread state ───────────────────────────────────────────────────────
static std::thread  g_ponder_thread;
static double       g_ponder_total_time = 60.0;
static double       g_ponder_increment  = 0.0;
static int          g_ponder_fullmove   = 1;

static void stopPonderThread()
{
    if (g_ponder_thread.joinable())
    {
        g_stop.store(true, std::memory_order_relaxed);
        g_ponder_thread.join();
        g_stop.store(false, std::memory_order_relaxed);
    }
}

static Move getPonderMove(Board board, Move bestMove)
{
    board.makeMove(bestMove);
    Move pm = ttProbeMove(board);
    if (pm == Move::NULL_MOVE)
    {
        Movelist ml;
        movegen::legalmoves(ml, board);
        if (!ml.empty())
            pm = ml[0];
    }
    return pm;
}

// ─────────────────────────────────────────────────────────────────────────────

void benchmarking()
{
    auto overall_start = std::chrono::steady_clock::now();
    const int evalNum = 10000000;
    Board board;
    board.setFen(chess::constants::STARTPOS);

    Movelist moves;
    movegen::legalmoves(moves, board);
    for (size_t i = 0; i < evalNum; ++i)
    {
        evaluateBoard(board, 0, moves);
    }

    auto end = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(end - overall_start).count();

    std::cout << "Benchmarking complete: evaluated " << evalNum << " positions in " << elapsed << " seconds." << std::endl;
    findBestMoveIterative(board, 14, 1000.0);
    ttClear();
}

int main(int argc, char *argv[])
{
    if (argc > 1 && std::string(argv[1]) == "--test")
    {
        if (argc < 5)
        {
            std::cerr << "Usage: " << argv[0] << " --test [FEN] [expected_move] [depth]" << std::endl;
            return 1;
        }
        std::string fen = argv[2];
        std::string expectedMove = argv[3];
        int depth = std::stoi(argv[4]);

        bool result = runSingleTest(fen, expectedMove, depth);
        return result ? 0 : 1;
    }

    Board board;
    std::string line;

    while (std::getline(std::cin, line))
    {
        if (line == "uci")
        {
            std::cout << "id name OmbleCavalierCPP\n";
            std::cout << "id author Hughes Perreault\n";
            std::cout << "option name Ponder type check default true\n";
            std::cout << "uciok\n";
            std::cout.flush();
        }
        else if (line == "isready")
        {
            std::cout << "readyok\n";
            std::cout.flush();
        }
        else if (line == "ucinewgame")
        {
            stopPonderThread();
            board.setFen(chess::constants::STARTPOS);
            ttClear();
            resetSearchState();
        }
        else if (line.rfind("position", 0) == 0)
        {
            if (line.find("startpos") != std::string::npos)
            {
                board.setFen(chess::constants::STARTPOS);
                auto movesPos = line.find("moves");
                if (movesPos != std::string::npos)
                {
                    std::istringstream ss(line.substr(movesPos + 6));
                    std::string moveStr;
                    while (ss >> moveStr)
                    {
                        Move m = uci::uciToMove(board, moveStr);
                        board.makeMove(m);
                    }
                }
            }
            else if (line.find("fen") != std::string::npos)
            {
                auto fenPos = line.find("fen") + 4;
                auto movesPos = line.find(" moves ");
                std::string fen = line.substr(fenPos, movesPos == std::string::npos ? std::string::npos : movesPos - fenPos);
                board.setFen(fen);
                if (movesPos != std::string::npos)
                {
                    std::istringstream ss(line.substr(movesPos + 7));
                    std::string moveStr;
                    while (ss >> moveStr)
                    {
                        Move m = uci::uciToMove(board, moveStr);
                        board.makeMove(m);
                    }
                }
            }
        }
        else if (line.rfind("go", 0) == 0)
        {
            double total_time_remaining = 5.0;
            double increment = 0.0;
            bool isPonder = false;

            stopPonderThread();

            std::istringstream ss(line);
            std::string token;
            while (ss >> token)
            {
                if (token == "ponder")
                {
                    isPonder = true;
                }
                else if (token == "movetime")
                {
                    int ms; ss >> ms;
                    total_time_remaining = ms / 1000.0;
                }
                else if (token == "wtime" && board.sideToMove() == chess::Color::WHITE)
                {
                    int ms; ss >> ms;
                    total_time_remaining = ms / 1000.0;
                }
                else if (token == "btime" && board.sideToMove() == chess::Color::BLACK)
                {
                    int ms; ss >> ms;
                    total_time_remaining = ms / 1000.0;
                }
                else if (token == "winc" && board.sideToMove() == chess::Color::WHITE)
                {
                    int ms; ss >> ms;
                    increment = ms / 1000.0;
                }
                else if (token == "binc" && board.sideToMove() == chess::Color::BLACK)
                {
                    int ms; ss >> ms;
                    increment = ms / 1000.0;
                }
            }

            if (isPonder)
            {
                // Save params for ponderhit
                g_ponder_total_time = total_time_remaining;
                g_ponder_increment  = increment;
                g_ponder_fullmove   = board.fullMoveNumber();

                g_stop.store(false, std::memory_order_relaxed);
                g_deadline_ns.store(std::numeric_limits<int64_t>::max(), std::memory_order_relaxed);

                Board board_copy = board;
                g_ponder_thread = std::thread([board_copy]() mutable {
                    Move best = findBestMoveIterative(board_copy, MAX_DEPTH, 9999.0, 0.0, true);
                    if (best == Move::NULL_MOVE)
                    {
                        std::cout << "bestmove 0000\n";
                        std::cout.flush();
                        return;
                    }
                    Move ponder = getPonderMove(board_copy, best);
                    std::string ponderStr = (ponder != Move::NULL_MOVE && !g_stop.load())
                                           ? " ponder " + uci::moveToUci(ponder)
                                           : "";
                    std::cout << "bestmove " << uci::moveToUci(best) << ponderStr << "\n";
                    std::cout.flush();
                });
            }
            else
            {
                // Try Polyglot book first
                if (BOOK_LOADED || loadPolyglotBook(BOOK_PATH))
                {
                    if (auto bm = getBookMove(board))
                    {
                        std::cout << "info string book move found\n";
                        std::cout << "bestmove " << uci::moveToUci(*bm) << "\n";
                        std::cout.flush();
                        continue;
                    }
                }

                g_stop.store(false, std::memory_order_relaxed);
                g_deadline_ns.store(std::numeric_limits<int64_t>::max(), std::memory_order_relaxed);

                Move best = findBestMoveIterative(board, MAX_DEPTH, total_time_remaining, increment);
                Move ponder = (best != Move::NULL_MOVE) ? getPonderMove(board, best) : Move::NULL_MOVE;
                std::string ponderStr = (ponder != Move::NULL_MOVE)
                                        ? " ponder " + uci::moveToUci(ponder)
                                        : "";
                std::cout << "bestmove " << uci::moveToUci(best) << ponderStr << "\n";
                std::cout.flush();
            }
        }
        else if (line == "ponderhit")
        {
            // Opponent played the ponder move — switch to timed search.
            int movesToGo = std::max(1, std::min(40, 60 - g_ponder_fullmove));
            double reserve = 1.0;
            double timeForMove = std::max(0.05, std::min(
                (g_ponder_total_time - reserve) / movesToGo + 0.5 * g_ponder_increment,
                0.5 * g_ponder_total_time));
            auto now = std::chrono::steady_clock::now();
            int64_t deadline = now.time_since_epoch().count()
                               + static_cast<int64_t>(timeForMove * 1'000'000'000LL);
            g_deadline_ns.store(deadline, std::memory_order_relaxed);
        }
        else if (line == "stop")
        {
            stopPonderThread();
        }
        else if (line == "quit")
        {
            stopPonderThread();
            break;
        }
        else if (line.rfind("puzzletest", 0) == 0)
        {
            std::string path = (line.size() > 11) ? line.substr(11) : PUZZLES_JSON_PATH;
            runPuzzleTests(path);
            std::cout << "info string Puzzle tests complete\n";
        }
        else if (line == "benchmarking")
        {
            benchmarking();
            std::cout << "info string benchmarking complete\n";
        }
    }
}
