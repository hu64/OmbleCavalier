#include <cassert>
#include <iostream>
#include "chess.hpp"
#include "eval.hpp"
using namespace chess;

bool testDoubledPawnsWhite()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    int doubledPawns = countDoubledPawns(board, Color::WHITE);
    int expected = 0;
    std::cout << "Doubled pawns (White): " << doubledPawns << ", Expected: " << expected << std::endl;
    return countDoubledPawns(board, Color::WHITE) == 0;
}

bool testDoubledPawnsBlack()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    return countDoubledPawns(board, Color::BLACK) == 1;
}

bool testIsolatedPawnsWhite()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    return countIsolatedPawns(board, Color::WHITE) == 2;
}

bool testIsolatedPawnsBlack()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    return countIsolatedPawns(board, Color::BLACK) == 3;
}

bool testPassedPawnsWhite()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    return countPassedPawns(board, Color::WHITE) == 2;
}

bool testPassedPawnsBlack()
{
    Board board;
    board.setFen("k7/5p2/5p2/8/7p/8/P1P5/K7 w - - 0 1");
    // f7, f6, h4 are all passed (only opponent pawns block passage; own doubled pawn doesn't)
    return countPassedPawns(board, Color::BLACK) == 3;
}

bool testPassedPawnsBlackBlockedbyKnight()
{
    Board board;
    board.setFen("k7/5p2/5p2/5n2/7p/8/P1P5/K7 w - - 0 1");
    // Knight is not a pawn — same 3 passed pawns as without the knight
    return countPassedPawns(board, Color::BLACK) == 3;
}

bool testRookOpenFile()
{
    Board board;
    // White rook on d4, no pawns on d-file at all → open file (+20)
    board.setFen("k7/8/8/8/3R4/8/PP3PPP/K7 w - - 0 1");
    return rookOpenFileBonus(board, Color::WHITE) == 20;
}

bool testRookSemiOpenFile()
{
    Board board;
    // White rook on d4, black pawn on d7, no white pawn on d → semi-open (+10)
    board.setFen("k7/3p4/8/8/3R4/8/PP3PPP/K7 w - - 0 1");
    return rookOpenFileBonus(board, Color::WHITE) == 10;
}

bool testRookBlockedByOwnPawn()
{
    Board board;
    // White rook on d4, white pawn on d3 → no bonus
    board.setFen("k7/8/8/8/3R4/3P4/PP3PPP/K7 w - - 0 1");
    return rookOpenFileBonus(board, Color::WHITE) == 0;
}

bool testTwoRooksOpenFiles()
{
    Board board;
    // White rooks on d4 and e4, no pawns on d or e files → 2 open files (+40)
    board.setFen("k7/8/8/8/3RR3/8/PP3PPP/K7 w - - 0 1");
    return rookOpenFileBonus(board, Color::WHITE) == 40;
}

int main(int argc, char *argv[])
{
    int passed = 0, total = 10;

    if (argc == 2)
    {
        std::string test = argv[1];
        if (test == "testDoubledPawnsWhite")
            return testDoubledPawnsWhite() ? 0 : 1;
        if (test == "testDoubledPawnsBlack")
            return testDoubledPawnsBlack() ? 0 : 1;
        if (test == "testIsolatedPawnsWhite")
            return testIsolatedPawnsWhite() ? 0 : 1;
        if (test == "testIsolatedPawnsBlack")
            return testIsolatedPawnsBlack() ? 0 : 1;
        if (test == "testPassedPawnsWhite")
            return testPassedPawnsWhite() ? 0 : 1;
        if (test == "testPassedPawnsBlack")
            return testPassedPawnsBlack() ? 0 : 1;
        if (test == "testPassedPawnsBlackBlockedbyKnight")
            return testPassedPawnsBlackBlockedbyKnight() ? 0 : 1;
        if (test == "testRookOpenFile")
            return testRookOpenFile() ? 0 : 1;
        if (test == "testRookSemiOpenFile")
            return testRookSemiOpenFile() ? 0 : 1;
        if (test == "testRookBlockedByOwnPawn")
            return testRookBlockedByOwnPawn() ? 0 : 1;
        if (test == "testTwoRooksOpenFiles")
            return testTwoRooksOpenFiles() ? 0 : 1;
        std::cout << "Unknown test: " << test << std::endl;
        return 2;
    }

    // Run all tests if no argument is given
    if (testDoubledPawnsWhite())
    {
        std::cout << "testDoubledPawnsWhite passed\n";
        ++passed;
    }
    else
        std::cout << "testDoubledPawnsWhite FAILED\n";

    if (testDoubledPawnsBlack())
    {
        std::cout << "testDoubledPawnsBlack passed\n";
        ++passed;
    }
    else
        std::cout << "testDoubledPawnsBlack FAILED\n";

    if (testIsolatedPawnsWhite())
    {
        std::cout << "testIsolatedPawnsWhite passed\n";
        ++passed;
    }
    else
        std::cout << "testIsolatedPawnsWhite FAILED\n";

    if (testIsolatedPawnsBlack())
    {
        std::cout << "testIsolatedPawnsBlack passed\n";
        ++passed;
    }
    else
        std::cout << "testIsolatedPawnsBlack FAILED\n";

    if (testPassedPawnsWhite())
    {
        std::cout << "testPassedPawnsWhite passed\n";
        ++passed;
    }
    else
        std::cout << "testPassedPawnsWhite FAILED\n";

    if (testPassedPawnsBlack())
    {
        std::cout << "testPassedPawnsBlack passed\n";
        ++passed;
    }
    else
        std::cout << "testPassedPawnsBlack FAILED\n";

    if (testRookOpenFile())
    {
        std::cout << "testRookOpenFile passed\n";
        ++passed;
    }
    else
        std::cout << "testRookOpenFile FAILED\n";

    if (testRookSemiOpenFile())
    {
        std::cout << "testRookSemiOpenFile passed\n";
        ++passed;
    }
    else
        std::cout << "testRookSemiOpenFile FAILED\n";

    if (testRookBlockedByOwnPawn())
    {
        std::cout << "testRookBlockedByOwnPawn passed\n";
        ++passed;
    }
    else
        std::cout << "testRookBlockedByOwnPawn FAILED\n";

    if (testTwoRooksOpenFiles())
    {
        std::cout << "testTwoRooksOpenFiles passed\n";
        ++passed;
    }
    else
        std::cout << "testTwoRooksOpenFiles FAILED\n";

    std::cout << passed << "/" << total << " tests passed.\n";
    return (passed == total) ? 0 : 1;
}