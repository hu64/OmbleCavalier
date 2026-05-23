#include "nnue.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>

// ── Network dimensions (768 → 256 → 32 → 1) ─────────────────────────────────
static constexpr int N0 = 768, N1 = 256, N2 = 32;

// Weight storage — laid out row-major (out, in) matching export.py
static float g_w1[N1][N0], g_b1[N1];
static float g_w2[N2][N1], g_b2[N2];
static float g_w3[N2],     g_b3;      // L3 is (1, 32) — store as flat array + scalar
static bool  g_loaded = false;

// Piece-type ordering: P N B R Q K — matches features.py PIECE_ORDER
static constexpr chess::PieceType PT_ORDER[6] = {
    chess::PieceType::PAWN,
    chess::PieceType::KNIGHT,
    chess::PieceType::BISHOP,
    chess::PieceType::ROOK,
    chess::PieceType::QUEEN,
    chess::PieceType::KING,
};

// ── File loading ─────────────────────────────────────────────────────────────

bool nnue_load(const std::string &path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;

    // Magic + version + layer count
    char magic[4];
    f.read(magic, 4);
    if (std::strncmp(magic, "NNUE", 4) != 0) return false;

    uint8_t version, n_layers;
    f.read(reinterpret_cast<char *>(&version),  1);
    f.read(reinterpret_cast<char *>(&n_layers), 1);
    if (version != 1 || n_layers != 3) return false;

    // Skip layer descriptors (sizes are compile-time constants)
    f.seekg(n_layers * 8, std::ios::cur);

    auto read_floats = [&](float *dst, int n) {
        return (bool)f.read(reinterpret_cast<char *>(dst), n * sizeof(float));
    };

    if (!read_floats(&g_w1[0][0], N1 * N0)) return false;
    if (!read_floats(g_b1,        N1))      return false;
    if (!read_floats(&g_w2[0][0], N2 * N1)) return false;
    if (!read_floats(g_b2,        N2))      return false;
    if (!read_floats(g_w3,        N2))      return false;  // L3 weights (1×32)
    if (!read_floats(&g_b3,       1))       return false;  // L3 bias

    g_loaded = true;
    return true;
}

bool nnue_loaded() { return g_loaded; }

// ── Inference ────────────────────────────────────────────────────────────────

// Collect active feature indices (max 32: 2 sides × 6 piece types × ≤16 pieces)
static int collect_features(const chess::Board &board, int *out)
{
    int n = 0;
    chess::Color us     = board.sideToMove();
    chess::Color them   = (us == chess::Color::WHITE) ? chess::Color::BLACK
                                                       : chess::Color::WHITE;
    bool mirror = (us == chess::Color::BLACK);

    for (int i = 0; i < 6; ++i)
    {
        chess::Bitboard our_bb  = board.pieces(PT_ORDER[i], us);
        chess::Bitboard their_bb = board.pieces(PT_ORDER[i], them);

        while (our_bb)
        {
            int sq = our_bb.lsb(); our_bb.clear(sq);
            out[n++] = i * 64 + (mirror ? (sq ^ 56) : sq);
        }
        while (their_bb)
        {
            int sq = their_bb.lsb(); their_bb.clear(sq);
            out[n++] = 384 + i * 64 + (mirror ? (sq ^ 56) : sq);
        }
    }
    return n;
}

std::vector<int> nnue_active_features(const chess::Board &board)
{
    int raw[32];
    int n = collect_features(board, raw);
    std::vector<int> v(raw, raw + n);
    std::sort(v.begin(), v.end());
    return v;
}

int nnue_eval(const chess::Board &board)
{
    int active[32];
    int n = collect_features(board, active);

    // L1: sparse input (only active features contribute) → ClippedReLU
    float x1[N1];
    for (int o = 0; o < N1; ++o)
    {
        float v = g_b1[o];
        for (int k = 0; k < n; ++k)
            v += g_w1[o][active[k]];
        x1[o] = v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
    }

    // L2: dense → ClippedReLU
    float x2[N2];
    for (int o = 0; o < N2; ++o)
    {
        float v = g_b2[o];
        for (int i = 0; i < N1; ++i)
            v += g_w2[o][i] * x1[i];
        x2[o] = v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v);
    }

    // L3: dense → logit
    float logit = g_b3;
    for (int i = 0; i < N2; ++i)
        logit += g_w3[i] * x2[i];

    // logit → win-probability → centipawns
    float wp = 1.0f / (1.0f + std::exp(-logit));
    wp = std::max(1e-7f, std::min(1.0f - 1e-7f, wp));
    return static_cast<int>(400.0f * std::log(wp / (1.0f - wp)));
}
