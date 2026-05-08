#pragma once
#include <string>

struct Puzzle
{
    std::string fen;
    std::string description;
    std::string expected_best_move;
    int requiredDepth;
};

void runPuzzleTests(const std::string &puzzlesPath);
bool runSingleTest(const std::string &fen, const std::string &expectedMove, int depth);
