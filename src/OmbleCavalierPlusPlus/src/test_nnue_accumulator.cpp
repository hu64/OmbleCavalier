#include "nnue.hpp"
#include "chess.hpp"
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using namespace chess;

// Returns true if both evals agree (within floating-point rounding).
static bool check_consistency(Board &board, const std::string &label)
{
    int incremental = nnue_eval(board);

    // Full recompute
    nnue_refresh(board);
    int fresh = nnue_eval(board);

    if (incremental != fresh) {
        std::cout << "FAIL  " << label
                  << "  incremental=" << incremental
                  << "  fresh=" << fresh
                  << "  delta=" << (incremental - fresh) << "\n";
        return false;
    }
    std::cout << "PASS  " << label << "  eval=" << incremental << "\n";
    return true;
}

// Play through a sequence of UCI moves and check consistency after each one.
static bool play_sequence(const std::string &start_fen,
                          const std::vector<std::string> &moves,
                          const std::string &suite_label)
{
    Board board;
    board.setFen(start_fen);
    nnue_refresh(board);

    bool all_pass = true;
    int idx = 0;
    for (const auto &uci : moves) {
        Move m = chess::uci::uciToMove(board, uci);
        nnue_push(board, m);
        board.makeMove(m);
        ++idx;
        bool ok = check_consistency(board, suite_label + " move " + std::to_string(idx) + " (" + uci + ")");
        if (!ok) {
            all_pass = false;
            // Re-sync so subsequent moves start from a known-good state
            nnue_refresh(board);
        }
    }
    return all_pass;
}

int main(int argc, char *argv[])
{
    const char *nnue_path = (argc > 1) ? argv[1] : "omblecavalier.nnue";
    if (!nnue_load(nnue_path)) {
        std::cerr << "Could not load NNUE weights from: " << nnue_path << "\n";
        return 1;
    }
    std::cout << "NNUE loaded from: " << nnue_path << "\n\n";

    int passed = 0, failed = 0;
    auto run = [&](const std::string &fen, const std::vector<std::string> &moves, const std::string &label) {
        if (play_sequence(fen, moves, label)) ++passed;
        else                                 ++failed;
    };

    // ── Normal moves & captures ───────────────────────────────────────────────
    run("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        {"e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5c6", "d7c6"},
        "Opening+capture");

    // ── En passant ────────────────────────────────────────────────────────────
    // White plays e5, Black plays d5, White captures en passant e5xd6
    run("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        {"e2e4", "d7d5", "e4e5", "d5d4", "e5e6",   // white advances past ep
         "c7c5", "e6e7"},                            // normal push to 7th
        "En-passant setup (no capture)");

    run("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2",
        {"e5d6"},    // white captures en passant
        "En-passant white captures");

    run("rnbqkbnr/pppp1ppp/8/8/3Pp3/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 2",
        {"e4d3"},    // black captures en passant
        "En-passant black captures");

    // ── Castling ──────────────────────────────────────────────────────────────
    run("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
        {"e1g1"},   // white kingside castle
        "White kingside castle");

    run("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
        {"e1c1"},   // white queenside castle
        "White queenside castle");

    run("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R b kq - 0 1",
        {"e8g8"},   // black kingside castle
        "Black kingside castle");

    run("r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R b kq - 0 1",
        {"e8c8"},   // black queenside castle
        "Black queenside castle");

    // ── Promotions ────────────────────────────────────────────────────────────
    run("8/P7/8/8/8/8/8/4K2k w - - 0 1",
        {"a7a8q"},  // queen promotion
        "White queen promotion");

    run("8/P7/8/8/8/8/8/4K2k w - - 0 1",
        {"a7a8n"},  // knight promotion
        "White knight promotion");

    run("4k2K/8/8/8/8/8/p7/8 b - - 0 1",
        {"a2a1q"},  // black queen promotion
        "Black queen promotion");

    // ── Promotion capture ─────────────────────────────────────────────────────
    run("1r6/P7/8/8/8/8/8/4K2k w - - 0 1",
        {"a7b8q"},  // capture + promote
        "White promotion capture");

    // ── Deep sequence: mix of all special moves ───────────────────────────────
    run("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        {"e1g1", "e6d5", "d2h6", "b4b3", "f3f6", "g7f6", "e5g6"},
        "Kiwipete mix");

    // ── Push-pop roundtrip: make a move then unmake, check we're back ─────────
    {
        Board board;
        board.setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
        nnue_refresh(board);
        int before = nnue_eval(board);

        Move m = uci::uciToMove(board, "e2e4");
        nnue_push(board, m);
        board.makeMove(m);
        board.unmakeMove(m);
        nnue_pop();

        int after = nnue_eval(board);
        if (before == after) {
            std::cout << "PASS  Push-pop roundtrip  eval=" << before << "\n";
            ++passed;
        } else {
            std::cout << "FAIL  Push-pop roundtrip  before=" << before << " after=" << after << "\n";
            ++failed;
        }
    }

    std::cout << "\n" << passed << "/" << (passed + failed) << " suites passed\n";
    return failed == 0 ? 0 : 1;
}
