#include "puzzles.hpp"
#include "search.hpp"
#include "tt.hpp"
#include <fstream>
using namespace chess;

static std::string jsonStr(const std::string &obj, const std::string &key)
{
    auto kpos = obj.find("\"" + key + "\"");
    if (kpos == std::string::npos) return "";
    auto colon = obj.find(':', kpos);
    auto q1 = obj.find('"', colon + 1);
    if (q1 == std::string::npos) return "";
    auto q2 = obj.find('"', q1 + 1);
    if (q2 == std::string::npos) return "";
    return obj.substr(q1 + 1, q2 - q1 - 1);
}

static int jsonInt(const std::string &obj, const std::string &key)
{
    auto kpos = obj.find("\"" + key + "\"");
    if (kpos == std::string::npos) return 0;
    auto colon = obj.find(':', kpos);
    size_t i = colon + 1;
    while (i < obj.size() && !std::isdigit((unsigned char)obj[i])) ++i;
    size_t j = i;
    while (j < obj.size() && std::isdigit((unsigned char)obj[j])) ++j;
    if (i == j) return 0;
    return std::stoi(obj.substr(i, j - i));
}

static std::vector<Puzzle> loadPuzzles(const std::string &path)
{
    std::ifstream file(path);
    if (!file.is_open())
    {
        std::cerr << "Could not open puzzles file: " << path << std::endl;
        return {};
    }
    std::string content((std::istreambuf_iterator<char>(file)), {});

    std::vector<Puzzle> puzzles;
    size_t pos = 0;
    while ((pos = content.find('{', pos)) != std::string::npos)
    {
        size_t end = content.find('}', pos);
        if (end == std::string::npos) break;
        std::string obj = content.substr(pos, end - pos + 1);
        std::string fen = jsonStr(obj, "fen");
        if (!fen.empty())
            puzzles.push_back({fen, jsonStr(obj, "description"), jsonStr(obj, "best_move"), jsonInt(obj, "depth")});
        pos = end + 1;
    }
    return puzzles;
}

void runPuzzleTests(const std::string &puzzlesPath)
{
    auto puzzles = loadPuzzles(puzzlesPath);
    if (puzzles.empty())
    {
        std::cout << "No puzzles loaded from: " << puzzlesPath << std::endl;
        return;
    }

    int passCount = 0;
    int total = (int)puzzles.size();

    auto overall_start = std::chrono::steady_clock::now();

    for (const auto &puzzle : puzzles)
    {
        auto start = std::chrono::steady_clock::now();

        Board board;
        board.setFen(puzzle.fen);
        Move bestMove = findBestMoveIterative(board, puzzle.requiredDepth, 1000);
        std::string bestMoveUci = uci::moveToUci(bestMove);

        auto end = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(end - start).count();

        bool passed = (bestMoveUci == puzzle.expected_best_move);
        if (passed)
        {
            std::cout << "[PASS] ";
            ++passCount;
        }
        else
        {
            std::cout << "[FAIL] ";
        }
        std::cout << "FEN: " << puzzle.fen;
        if (!puzzle.description.empty())
            std::cout << " (" << puzzle.description << ")";
        std::cout << " - Expected: " << puzzle.expected_best_move << ", Got: " << bestMoveUci;
        std::cout << " | Time: " << elapsed << "s" << std::endl;
        ttClear();
    }

    auto overall_end = std::chrono::steady_clock::now();
    double overall_elapsed = std::chrono::duration<double>(overall_end - overall_start).count();

    std::cout << "Puzzle tests passed: " << passCount << " / " << total << std::endl;
    std::cout << "Total time for all puzzles: " << overall_elapsed << "s" << std::endl;
}

bool runSingleTest(const std::string &fen, const std::string &expectedMove, int depth)
{
    Board board;
    board.setFen(fen);
    ttClear();

    Move bestMove = findBestMoveIterative(board, depth, 60.0);
    std::string bestMoveUci = uci::moveToUci(bestMove);

    bool passed = (bestMoveUci == expectedMove);

    if (passed)
        std::cout << "[PASS] Found best move: " << bestMoveUci << std::endl;
    else
        std::cout << "[FAIL] Expected: " << expectedMove << ", Got: " << bestMoveUci << std::endl;

    return passed;
}
