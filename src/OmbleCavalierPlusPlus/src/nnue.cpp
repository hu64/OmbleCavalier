#include "nnue.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <immintrin.h>

// ── Network dimensions (768 → 512 → N_BUCKETS) ───────────────────────────────
static constexpr int N0        = 768;
static constexpr int N1        = 512;
static constexpr int N_BUCKETS = 8;

// g_w1_T is stored transposed [N0][N1] for cache-friendly acc updates.
alignas(32) static float g_w1_T[N0][N1];
alignas(32) static float g_b1[N1];
alignas(32) static float g_w_out[N_BUCKETS][N1];
static float g_b_out[N_BUCKETS];
static bool  g_loaded = false;

// ── Lazy accumulator delta ────────────────────────────────────────────────────
// Each nnue_push records up to 6 piece-move ops without touching the float
// arrays.  The arrays are only computed (materialized) if nnue_eval is called
// for that position, saving the 4 KB memcpy + delta work for every branch
// that gets alpha-beta cut before evaluation.
struct AccDelta {
    struct Op {
        uint8_t color;   // chess::Color cast to uint8_t (WHITE=0, BLACK=1)
        int8_t  pt_idx;
        int8_t  sq;
        int8_t  sign;    // +1 = add, -1 = sub
    };
    Op     ops[6];
    int8_t n = 0;

    void push(chess::Color c, int pt, int s, int sg) {
        ops[n++] = { static_cast<uint8_t>(c), static_cast<int8_t>(pt),
                     static_cast<int8_t>(s),  static_cast<int8_t>(sg) };
    }
};

// alignas(32) on the float arrays guarantees 32-byte alignment for AVX2 loads.
// The compiler rounds sizeof(Accumulator) up to a multiple of alignof (32),
// so every element of g_acc_stack is also 32-byte aligned.
struct Accumulator {
    alignas(32) float white[N1];
    alignas(32) float black[N1];
    bool     valid;      // false → must materialize from parent before use
    int      parent_sp;  // stack index of the parent frame
    AccDelta delta;      // ops to apply on top of the parent to get this frame
};

static constexpr int ACC_STACK_SIZE = 256;   // MAX_PLY(128) + quiescence + margin
static Accumulator   g_acc_stack[ACC_STACK_SIZE];
static int           g_acc_sp = 0;

// Piece-type ordering must match features.py: P N B R Q K
static constexpr chess::PieceType PT_ORDER[6] = {
    chess::PieceType::PAWN,
    chess::PieceType::KNIGHT,
    chess::PieceType::BISHOP,
    chess::PieceType::ROOK,
    chess::PieceType::QUEEN,
    chess::PieceType::KING,
};

// ── File loading ──────────────────────────────────────────────────────────────

bool nnue_load(const std::string &path)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;

    char magic[4];
    f.read(magic, 4);
    if (std::strncmp(magic, "NNUE", 4) != 0) return false;

    uint8_t version, n_buckets;
    f.read(reinterpret_cast<char *>(&version),   1);
    f.read(reinterpret_cast<char *>(&n_buckets), 1);
    if (version != 2 || n_buckets != N_BUCKETS) return false;

    uint32_t n0, n1;
    f.read(reinterpret_cast<char *>(&n0), 4);
    f.read(reinterpret_cast<char *>(&n1), 4);
    if (n0 != N0 || n1 != N1) return false;

    auto read_floats = [&](float *dst, int n) {
        return static_cast<bool>(f.read(reinterpret_cast<char *>(dst), n * sizeof(float)));
    };

    {
        float tmp[N1 * N0];
        if (!read_floats(tmp, N1 * N0)) return false;
        for (int i = 0; i < N1; ++i)
            for (int j = 0; j < N0; ++j)
                g_w1_T[j][i] = tmp[i * N0 + j];
    }
    if (!read_floats(g_b1,            N1))             return false;
    if (!read_floats(&g_w_out[0][0],  N_BUCKETS * N1)) return false;
    if (!read_floats(g_b_out,         N_BUCKETS))      return false;

    g_loaded = true;
    return true;
}

bool nnue_loaded() { return g_loaded; }

// ── Feature index helpers ─────────────────────────────────────────────────────

static inline int feat_idx(chess::Color piece_color, int pt_idx, int sq,
                            chess::Color perspective)
{
    int eff = (perspective == chess::Color::BLACK) ? (sq ^ 56) : sq;
    return (piece_color == perspective ? 0 : 384) + pt_idx * 64 + eff;
}

// Apply one piece add/sub to a specific accumulator frame.
static inline void acc_apply(Accumulator &acc, chess::Color color, int pt_idx,
                              int sq, int sign)
{
    int fw = feat_idx(color, pt_idx, sq, chess::Color::WHITE);
    int fb = feat_idx(color, pt_idx, sq, chess::Color::BLACK);
    const float *cw = g_w1_T[fw];
    const float *cb = g_w1_T[fb];
    if (sign > 0) {
        for (int i = 0; i < N1; ++i) acc.white[i] += cw[i];
        for (int i = 0; i < N1; ++i) acc.black[i] += cb[i];
    } else {
        for (int i = 0; i < N1; ++i) acc.white[i] -= cw[i];
        for (int i = 0; i < N1; ++i) acc.black[i] -= cb[i];
    }
}

// Ensure g_acc_stack[sp] has valid float arrays.
// Recursively materializes the parent first if needed (chain is at most a few
// frames deep because RFP / futility / quiesce always call nnue_eval before
// pushing grandchildren).
static void materialize(int sp)
{
    Accumulator &acc = g_acc_stack[sp];
    if (acc.valid) return;

    int psp = acc.parent_sp;
    if (!g_acc_stack[psp].valid) materialize(psp);

    const Accumulator &par = g_acc_stack[psp];
    std::memcpy(acc.white, par.white, N1 * sizeof(float));
    std::memcpy(acc.black, par.black, N1 * sizeof(float));

    for (int i = 0; i < acc.delta.n; ++i) {
        const AccDelta::Op &op = acc.delta.ops[i];
        acc_apply(acc, static_cast<chess::Color>(op.color),
                  op.pt_idx, op.sq, op.sign);
    }
    acc.valid = true;
}

// ── Public accumulator API ────────────────────────────────────────────────────

void nnue_refresh(const chess::Board &board)
{
    g_acc_sp = 0;
    Accumulator &acc = g_acc_stack[0];
    acc.valid     = true;
    acc.parent_sp = -1;
    acc.delta.n   = 0;

    for (int i = 0; i < N1; ++i) {
        acc.white[i] = g_b1[i];
        acc.black[i] = g_b1[i];
    }
    for (int i = 0; i < 6; ++i) {
        for (chess::Color c : {chess::Color::WHITE, chess::Color::BLACK}) {
            chess::Bitboard bb = board.pieces(PT_ORDER[i], c);
            while (bb) {
                int sq = bb.lsb();
                bb.clear(sq);
                acc_apply(acc, c, i, sq, +1);
            }
        }
    }
}

// Record the move as a pending delta — no float work done here.
// The actual accumulator update is deferred to the first nnue_eval call.
void nnue_push(const chess::Board &board, chess::Move move)
{
    int next = g_acc_sp + 1;
    Accumulator &frame = g_acc_stack[next];
    frame.valid     = false;
    frame.parent_sp = g_acc_sp;
    frame.delta.n   = 0;
    g_acc_sp = next;

    chess::Color stm = board.sideToMove();
    auto mt = move.typeOf();

    if (mt == chess::Move::CASTLING) {
        bool kingside = move.to() > move.from();
        int king_from = move.from().index();
        int rook_from = move.to().index();
        int king_to   = chess::Square::castling_king_square(kingside, stm).index();
        int rook_to   = chess::Square::castling_rook_square(kingside, stm).index();
        frame.delta.push(stm, 5 /* KING */, king_from, -1);
        frame.delta.push(stm, 3 /* ROOK */, rook_from, -1);
        frame.delta.push(stm, 5,            king_to,   +1);
        frame.delta.push(stm, 3,            rook_to,   +1);
        return;
    }

    chess::Piece piece = board.at(move.from());
    int pt_idx  = static_cast<int>(piece.type().internal());
    int from_sq = move.from().index();
    int to_sq   = move.to().index();

    if (mt == chess::Move::ENPASSANT) {
        int ep_sq = move.to().ep_square().index();
        frame.delta.push(~stm, 0 /* PAWN */, ep_sq, -1);
    } else if (board.isCapture(move)) {
        chess::Piece cap = board.at(move.to());
        frame.delta.push(cap.color(), static_cast<int>(cap.type().internal()), to_sq, -1);
    }

    frame.delta.push(stm, pt_idx, from_sq, -1);
    if (mt == chess::Move::PROMOTION) {
        frame.delta.push(stm, static_cast<int>(move.promotionType().internal()), to_sq, +1);
    } else {
        frame.delta.push(stm, pt_idx, to_sq, +1);
    }
}

void nnue_pop()
{
    --g_acc_sp;
}

// ── Inference ─────────────────────────────────────────────────────────────────

int nnue_eval(const chess::Board &board)
{
    materialize(g_acc_sp);
    const Accumulator &acc = g_acc_stack[g_acc_sp];
    const float *stm_acc   = (board.sideToMove() == chess::Color::WHITE)
                             ? acc.white : acc.black;

    int n_pieces = board.occ().count();
    int bucket   = std::min(N_BUCKETS - 1, (32 - n_pieces) * N_BUCKETS / 32);

    // SCReLU clamp(x,0,1)² + weighted dot product, unrolled 4× with AVX2 FMA.
    // stm_acc and g_w_out[bucket] are both 32-byte aligned (see struct layout).
    const float *w    = g_w_out[bucket];
    const __m256 zero = _mm256_setzero_ps();
    const __m256 one  = _mm256_set1_ps(1.0f);
    __m256 sum0 = _mm256_setzero_ps();
    __m256 sum1 = _mm256_setzero_ps();
    __m256 sum2 = _mm256_setzero_ps();
    __m256 sum3 = _mm256_setzero_ps();

    for (int i = 0; i < N1; i += 32) {
        __m256 x0 = _mm256_load_ps(stm_acc + i);
        __m256 x1 = _mm256_load_ps(stm_acc + i +  8);
        __m256 x2 = _mm256_load_ps(stm_acc + i + 16);
        __m256 x3 = _mm256_load_ps(stm_acc + i + 24);

        __m256 c0 = _mm256_min_ps(_mm256_max_ps(x0, zero), one);
        __m256 c1 = _mm256_min_ps(_mm256_max_ps(x1, zero), one);
        __m256 c2 = _mm256_min_ps(_mm256_max_ps(x2, zero), one);
        __m256 c3 = _mm256_min_ps(_mm256_max_ps(x3, zero), one);

        sum0 = _mm256_fmadd_ps(_mm256_load_ps(w + i),      _mm256_mul_ps(c0, c0), sum0);
        sum1 = _mm256_fmadd_ps(_mm256_load_ps(w + i +  8), _mm256_mul_ps(c1, c1), sum1);
        sum2 = _mm256_fmadd_ps(_mm256_load_ps(w + i + 16), _mm256_mul_ps(c2, c2), sum2);
        sum3 = _mm256_fmadd_ps(_mm256_load_ps(w + i + 24), _mm256_mul_ps(c3, c3), sum3);
    }

    __m256 s  = _mm256_add_ps(_mm256_add_ps(sum0, sum1), _mm256_add_ps(sum2, sum3));
    __m128 lo = _mm256_castps256_ps128(s);
    __m128 hi = _mm256_extractf128_ps(s, 1);
    lo = _mm_add_ps(lo, hi);
    lo = _mm_hadd_ps(lo, lo);
    lo = _mm_hadd_ps(lo, lo);
    float out = g_b_out[bucket] + _mm_cvtss_f32(lo);

    float wp = 1.0f / (1.0f + std::exp(-out));
    wp = std::max(1e-7f, std::min(1.0f - 1e-7f, wp));
    return static_cast<int>(400.0f * std::log(wp / (1.0f - wp)));
}

// ── Feature-index utility (used by tests) ────────────────────────────────────

static int collect_features(const chess::Board &board, int *out)
{
    int n = 0;
    chess::Color us   = board.sideToMove();
    chess::Color them = ~us;
    bool mirror = (us == chess::Color::BLACK);

    for (int i = 0; i < 6; ++i) {
        chess::Bitboard our_bb   = board.pieces(PT_ORDER[i], us);
        chess::Bitboard their_bb = board.pieces(PT_ORDER[i], them);
        while (our_bb) {
            int sq = our_bb.lsb(); our_bb.clear(sq);
            out[n++] = i * 64 + (mirror ? (sq ^ 56) : sq);
        }
        while (their_bb) {
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
