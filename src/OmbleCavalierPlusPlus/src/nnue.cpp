#include "nnue.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>

// ── Network dimensions (768 → 512 → N_BUCKETS) ───────────────────────────────
static constexpr int N0        = 768;
static constexpr int N1        = 512;
static constexpr int N_BUCKETS = 8;

// Weight storage
static float g_w1[N1][N0];               // L1 weights  (N1 × N0)
static float g_b1[N1];                   // L1 biases   (N1)
static float g_w_out[N_BUCKETS][N1];     // output weights  (N_BUCKETS × N1)
static float g_b_out[N_BUCKETS];         // output biases   (N_BUCKETS)
static bool  g_loaded = false;

// ── Dual accumulator ─────────────────────────────────────────────────────────
// Two perspectives (White / Black) maintained side-by-side so both are always
// up-to-date.  At eval time we select the accumulator for the side to move.
struct Accumulator {
    float white[N1];
    float black[N1];
};

static constexpr int ACC_STACK_SIZE = 256;   // MAX_PLY(128) + quiescence + margin
static Accumulator   g_acc_stack[ACC_STACK_SIZE];
static int           g_acc_sp = 0;           // index of the current frame

// Piece-type ordering must match features.py: P N B R Q K (same as chess.hpp 0-5)
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

    if (!read_floats(&g_w1[0][0],     N1 * N0))      return false;
    if (!read_floats(g_b1,            N1))            return false;
    if (!read_floats(&g_w_out[0][0],  N_BUCKETS * N1)) return false;
    if (!read_floats(g_b_out,         N_BUCKETS))     return false;

    g_loaded = true;
    return true;
}

bool nnue_loaded() { return g_loaded; }

// ── Feature index helpers ─────────────────────────────────────────────────────

// Feature index for a piece of `piece_color` and type index `pt_idx` on square
// `sq` (0-63, a1=0), from `perspective`'s point of view.
//   - perspective == WHITE: no rank mirroring; own pieces in [0,384), opp in [384,768)
//   - perspective == BLACK: rank-mirror sq^56; own pieces in [0,384), opp in [384,768)
static inline int feat_idx(chess::Color piece_color, int pt_idx, int sq,
                            chess::Color perspective)
{
    int eff = (perspective == chess::Color::BLACK) ? (sq ^ 56) : sq;
    return (piece_color == perspective ? 0 : 384) + pt_idx * 64 + eff;
}

// Add a piece to both accumulators in the current stack frame.
static inline void acc_add(chess::Color piece_color, int pt_idx, int sq)
{
    int fw = feat_idx(piece_color, pt_idx, sq, chess::Color::WHITE);
    int fb = feat_idx(piece_color, pt_idx, sq, chess::Color::BLACK);
    Accumulator &acc = g_acc_stack[g_acc_sp];
    for (int i = 0; i < N1; ++i) {
        acc.white[i] += g_w1[i][fw];
        acc.black[i] += g_w1[i][fb];
    }
}

// Remove a piece from both accumulators in the current stack frame.
static inline void acc_sub(chess::Color piece_color, int pt_idx, int sq)
{
    int fw = feat_idx(piece_color, pt_idx, sq, chess::Color::WHITE);
    int fb = feat_idx(piece_color, pt_idx, sq, chess::Color::BLACK);
    Accumulator &acc = g_acc_stack[g_acc_sp];
    for (int i = 0; i < N1; ++i) {
        acc.white[i] -= g_w1[i][fw];
        acc.black[i] -= g_w1[i][fb];
    }
}

// ── Public accumulator API ────────────────────────────────────────────────────

void nnue_refresh(const chess::Board &board)
{
    g_acc_sp = 0;
    Accumulator &acc = g_acc_stack[0];
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
                acc_add(c, i, sq);
            }
        }
    }
}

void nnue_push(const chess::Board &board, chess::Move move)
{
    // Push a copy of the current frame onto the stack.
    int next = g_acc_sp + 1;
    g_acc_stack[next] = g_acc_stack[g_acc_sp];
    g_acc_sp = next;

    chess::Color stm = board.sideToMove();
    auto mt = move.typeOf();

    // ── Castling ────────────────────────────────────────────────────────────
    // In chess.hpp the move is encoded as king→rook; we resolve the real
    // destinations via the library helpers.
    if (mt == chess::Move::CASTLING) {
        bool kingside = move.to() > move.from();
        int king_from = move.from().index();
        int rook_from = move.to().index();
        int king_to   = chess::Square::castling_king_square(kingside, stm).index();
        int rook_to   = chess::Square::castling_rook_square(kingside, stm).index();

        acc_sub(stm, 5 /* KING */, king_from);
        acc_sub(stm, 3 /* ROOK */, rook_from);
        acc_add(stm, 5,            king_to);
        acc_add(stm, 3,            rook_to);
        return;
    }

    chess::Piece piece = board.at(move.from());
    int pt_idx  = static_cast<int>(piece.type().internal());
    int from_sq = move.from().index();
    int to_sq   = move.to().index();

    // ── En passant capture ──────────────────────────────────────────────────
    // The captured pawn is NOT on move.to() but one rank behind it.
    if (mt == chess::Move::ENPASSANT) {
        int ep_sq = move.to().ep_square().index();
        acc_sub(~stm, 0 /* PAWN */, ep_sq);
    } else if (board.isCapture(move)) {
        chess::Piece cap = board.at(move.to());
        acc_sub(cap.color(), static_cast<int>(cap.type().internal()), to_sq);
    }

    // ── Move the piece (handle promotion) ───────────────────────────────────
    acc_sub(stm, pt_idx, from_sq);
    if (mt == chess::Move::PROMOTION) {
        acc_add(stm, static_cast<int>(move.promotionType().internal()), to_sq);
    } else {
        acc_add(stm, pt_idx, to_sq);
    }
}

void nnue_pop()
{
    --g_acc_sp;
}

// ── Inference ────────────────────────────────────────────────────────────────

int nnue_eval(const chess::Board &board)
{
    const Accumulator &acc = g_acc_stack[g_acc_sp];
    const float *stm_acc   = (board.sideToMove() == chess::Color::WHITE)
                             ? acc.white : acc.black;

    // Bucket: fewer pieces → higher bucket index (more endgame-specialised head)
    int n_pieces = board.occ().count();
    int bucket   = std::min(N_BUCKETS - 1, (32 - n_pieces) * N_BUCKETS / 32);

    // SCReLU: clamp(x, 0, 1)^2
    float out = g_b_out[bucket];
    for (int i = 0; i < N1; ++i) {
        float c = stm_acc[i] < 0.0f ? 0.0f : (stm_acc[i] > 1.0f ? 1.0f : stm_acc[i]);
        out += g_w_out[bucket][i] * (c * c);
    }

    // logit → win-probability → centipawns
    float wp = 1.0f / (1.0f + std::exp(-out));
    wp = std::max(1e-7f, std::min(1.0f - 1e-7f, wp));
    return static_cast<int>(400.0f * std::log(wp / (1.0f - wp)));
}

// ── Feature-index utility (used by tests) ────────────────────────────────────

static int collect_features(const chess::Board &board, int *out)
{
    int n = 0;
    chess::Color us     = board.sideToMove();
    chess::Color them   = ~us;
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
