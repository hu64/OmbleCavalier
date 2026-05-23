#include "nnue.hpp"
#include "chess.hpp"
#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

using namespace chess;

struct TestCase {
    const char *label;
    const char *fen;
    std::vector<int> expected; // sorted active feature indices from features.py
};

static const TestCase CASES[] = {
    {
        "startpos (White to move)",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        {8,9,10,11,12,13,14,15,65,70,130,133,192,199,259,324,
         432,433,434,435,436,437,438,439,505,510,570,573,632,639,699,764}
    },
    {
        "e4 e5 Nf3 (Black to move)",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        {8,9,10,11,13,14,15,28,65,70,130,133,192,199,259,324,
         420,432,433,434,435,437,438,439,493,505,570,573,632,639,699,764}
    },
    {
        "lone kings (White to move)",
        "8/8/8/8/8/8/4K3/4k3 w - - 0 1",
        {332, 708}
    },
    {
        "complex middlegame (White to move)",
        "r3k2r/pppq1ppp/2npbn2/2b1p3/2B1P3/2NPBN2/PPPQ1PPP/R3K2R w KQkq - 4 9",
        {8,9,10,13,14,15,19,28,82,85,148,154,192,199,267,324,
         420,427,432,433,434,437,438,439,490,493,546,556,632,639,691,764}
    },
};

int main()
{
    int passed = 0, failed = 0;

    for (const auto &tc : CASES) {
        Board board;
        board.setFen(tc.fen);

        std::vector<int> got = nnue_active_features(board);

        if (got == tc.expected) {
            std::cout << "PASS  " << tc.label << "\n";
            ++passed;
        } else {
            std::cout << "FAIL  " << tc.label << "\n";
            std::cout << "  expected (" << tc.expected.size() << "): ";
            for (int x : tc.expected) std::cout << x << " ";
            std::cout << "\n  got     (" << got.size() << "): ";
            for (int x : got) std::cout << x << " ";
            std::cout << "\n";
            // Diff
            std::vector<int> missing, extra;
            for (int x : tc.expected) if (!std::binary_search(got.begin(), got.end(), x)) missing.push_back(x);
            for (int x : got) if (!std::binary_search(tc.expected.begin(), tc.expected.end(), x)) extra.push_back(x);
            if (!missing.empty()) { std::cout << "  missing: "; for (int x : missing) std::cout << x << " "; std::cout << "\n"; }
            if (!extra.empty())   { std::cout << "  extra:   "; for (int x : extra)   std::cout << x << " "; std::cout << "\n"; }
            ++failed;
        }
    }

    std::cout << "\n" << passed << "/" << (passed + failed) << " tests passed\n";
    return failed == 0 ? 0 : 1;
}
