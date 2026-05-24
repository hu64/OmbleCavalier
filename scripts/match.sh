#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# match.sh — Build/stage both engine implementations and run head-to-head matches.
#
# Usage:
#   scripts/match.sh [options]
#
# Options:
#   --games   N     Total games to play, must be even (default: 100)
#   --tc      TC    Time control in cutechess format (default: 10+0.1)
#   --branch  B     Base branch to compare against (default: master)
#   --no-cache      Force rebuild even if binary already cached
#   --cpp-only      Skip the Python engine match
#   --py-only       Skip the C++ engine match
#
# Prerequisites:
#   cmake, make, cutechess-cli
#   macOS: brew install cutechess
#
# The current branch is the "challenger". The base branch is the "baseline".
# C++ binaries are cached in tests/engines/ by commit hash.
# Python source snapshots are also cached in tests/engines/ by commit hash.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
ENGINE_CACHE="$REPO_ROOT/tests/engines"
MATCH_DIR="$REPO_ROOT/matches"
CPP_SRC="$REPO_ROOT/src/OmbleCavalierPlusPlus"
PY_SRC="$REPO_ROOT/src/OmbleCavalierPython"
OPENINGS="$REPO_ROOT/tests/openings.epd"
NNUE_FILE="$REPO_ROOT/src/nnue-training/omblecavalier.nnue"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python3"

# ── Defaults ──────────────────────────────────────────────────────────────────
GAMES=100
TC="10+0.1"
BASE_BRANCH="master"
NO_CACHE=0
RUN_CPP=1
RUN_PY=1

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --games)    GAMES="$2";       shift 2 ;;
        --tc)       TC="$2";          shift 2 ;;
        --branch)   BASE_BRANCH="$2"; shift 2 ;;
        --no-cache) NO_CACHE=1;       shift   ;;
        --cpp-only) RUN_PY=0;         shift   ;;
        --py-only)  RUN_CPP=0;        shift   ;;
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown argument: $1  (use --help)"; exit 1 ;;
    esac
done

if (( GAMES % 2 != 0 )); then
    echo "ERROR: --games must be even (each opening is played from both sides)"; exit 1
fi

# ── Prerequisite check ────────────────────────────────────────────────────────
missing=()
for cmd in git cmake make cutechess-cli; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
done
if [[ ! -x "$VENV_PYTHON" ]]; then
    missing+=("$VENV_PYTHON (run: uv sync)")
fi
if (( ${#missing[@]} > 0 )); then
    echo "ERROR: Missing prerequisites: ${missing[*]}"
    echo "  cutechess-cli: brew install cutechess"
    exit 1
fi

mkdir -p "$ENGINE_CACHE" "$MATCH_DIR"

# ── Resolve branches and hashes ───────────────────────────────────────────────
CURRENT_BRANCH=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)
CURRENT_HASH=$(git  -C "$REPO_ROOT" rev-parse --short HEAD)

BASE_HASH=$(git -C "$REPO_ROOT" rev-parse --short "${BASE_BRANCH}" 2>/dev/null \
         || git -C "$REPO_ROOT" rev-parse --short "origin/${BASE_BRANCH}")

CURRENT_SLUG="${CURRENT_BRANCH//\//-}"
BASE_SLUG="${BASE_BRANCH//\//-}"

echo "╔══════════════════════════════════════════════════════╗"
echo "║             OmbleCavalier Engine Match               ║"
echo "╠══════════════════════════════════════════════════════╣"
printf "║  Challenger : %-38s║\n" "${CURRENT_BRANCH} (${CURRENT_HASH})"
printf "║  Baseline   : %-38s║\n" "${BASE_BRANCH} (${BASE_HASH})"
printf "║  Games      : %-5s   TC: %-26s   ║\n" "$GAMES" "$TC"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── C++ build helper ──────────────────────────────────────────────────────────
build_cpp() {
    local src_dir="$1"
    local out_bin="$2"
    local label="$3"

    echo "  ▶ Building C++ ${label}…"
    local build_dir
    build_dir=$(mktemp -d)

    cmake -S "$src_dir" -B "$build_dir" \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_CXX_FLAGS="-march=native" \
          --log-level=ERROR > /dev/null 2>&1

    local cpus
    cpus=$(sysctl -n hw.logicalcpu 2>/dev/null || nproc)
    make -C "$build_dir" -j"$cpus" omble_cavalier++ > /dev/null 2>&1

    cp "$build_dir/omble_cavalier++" "$out_bin"
    chmod +x "$out_bin"
    rm -rf "$build_dir"

    echo "  ✓ ${label} → $(basename "$out_bin")"
}

# ── Python launcher helper ────────────────────────────────────────────────────
# Writes a small shell script that sets PYTHONPATH to the given source dir
# and runs the Python engine using the shared root venv.
make_py_launcher() {
    local src_dir="$1"
    local launcher="$2"
    cat > "$launcher" << LAEOF
#!/usr/bin/env bash
export PYTHONPATH="$src_dir"
exec "$VENV_PYTHON" -m omblecavalier.engines.omble_cavalier
LAEOF
    chmod +x "$launcher"
}

# ── Stage NNUE weights ────────────────────────────────────────────────────────
if [[ -f "$NNUE_FILE" ]]; then
    cp "$NNUE_FILE" "$ENGINE_CACHE/omblecavalier.nnue"
    echo "  ✓ NNUE weights staged → tests/engines/"
fi

# ── C++ engine setup ──────────────────────────────────────────────────────────
if (( RUN_CPP )); then
    echo ""
    echo "── C++ engines ──────────────────────────────────────────"
    CURRENT_CPP_BIN="$ENGINE_CACHE/ocpp-${CURRENT_SLUG}-${CURRENT_HASH}"
    BASE_CPP_BIN="$ENGINE_CACHE/ocpp-${BASE_SLUG}-${BASE_HASH}"

    if [[ $NO_CACHE -eq 1 || ! -f "$CURRENT_CPP_BIN" ]]; then
        build_cpp "$CPP_SRC" "$CURRENT_CPP_BIN" "$CURRENT_BRANCH"
    else
        echo "  ✓ Cached: $(basename "$CURRENT_CPP_BIN")"
    fi

    if [[ $NO_CACHE -eq 1 || ! -f "$BASE_CPP_BIN" ]]; then
        WORKTREE=$(mktemp -d)
        trap 'git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null; rm -rf "$WORKTREE"' EXIT
        git -C "$REPO_ROOT" worktree add --detach "$WORKTREE" "$BASE_HASH" 2>/dev/null
        build_cpp "$WORKTREE/src/OmbleCavalierPlusPlus" "$BASE_CPP_BIN" "$BASE_BRANCH"
        git -C "$REPO_ROOT" worktree remove --force "$WORKTREE" 2>/dev/null; rm -rf "$WORKTREE"
        trap - EXIT
    else
        echo "  ✓ Cached: $(basename "$BASE_CPP_BIN")"
    fi
fi

# ── Python engine setup ───────────────────────────────────────────────────────
if (( RUN_PY )); then
    echo ""
    echo "── Python engines ───────────────────────────────────────"
    CURRENT_PY_LAUNCHER="$ENGINE_CACHE/ocpy-${CURRENT_SLUG}-${CURRENT_HASH}.sh"
    BASE_PY_DIR="$ENGINE_CACHE/py-src-${BASE_SLUG}-${BASE_HASH}"
    BASE_PY_LAUNCHER="$ENGINE_CACHE/ocpy-${BASE_SLUG}-${BASE_HASH}.sh"

    # Current branch: always regenerate launcher (points to live source)
    make_py_launcher "$PY_SRC" "$CURRENT_PY_LAUNCHER"
    echo "  ✓ Python challenger launcher → $(basename "$CURRENT_PY_LAUNCHER")"

    # Base branch: cache a source snapshot so we don't keep a live worktree
    if [[ $NO_CACHE -eq 1 || ! -d "$BASE_PY_DIR" ]]; then
        echo "  ▶ Snapshotting Python ${BASE_BRANCH}…"
        WORKTREE_PY=$(mktemp -d)
        trap 'git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_PY" 2>/dev/null; rm -rf "$WORKTREE_PY"' EXIT
        git -C "$REPO_ROOT" worktree add --detach "$WORKTREE_PY" "$BASE_HASH" 2>/dev/null
        rm -rf "$BASE_PY_DIR"
        cp -r "$WORKTREE_PY/src/OmbleCavalierPython" "$BASE_PY_DIR"
        git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_PY" 2>/dev/null; rm -rf "$WORKTREE_PY"
        trap - EXIT
        echo "  ✓ ${BASE_BRANCH} → $(basename "$BASE_PY_DIR")"
    else
        echo "  ✓ Cached: $(basename "$BASE_PY_DIR")"
    fi
    make_py_launcher "$BASE_PY_DIR" "$BASE_PY_LAUNCHER"
fi

echo ""

# ── Shared cutechess args ─────────────────────────────────────────────────────
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ROUNDS=$(( GAMES / 2 ))
OPENINGS_ARGS=()
[[ -f "$OPENINGS" ]] && OPENINGS_ARGS=(-openings "file=$OPENINGS" format=epd order=random)

# ── Result parser (reused for both matches) ───────────────────────────────────
parse_results() {
    local pgn="$1" e1="$2" e2="$3"
    "$VENV_PYTHON" - "$pgn" "$e1" "$e2" << 'PYEOF'
import sys, re, math as _m

pgn_path = sys.argv[1]
engine1  = sys.argv[2]
engine2  = sys.argv[3]

w1 = w2 = draws = 0
white = black = result = None

with open(pgn_path) as f:
    for line in f:
        line = line.strip()
        m = re.match(r'\[White "(.+)"\]', line)
        if m: white = m.group(1); continue
        m = re.match(r'\[Black "(.+)"\]', line)
        if m: black = m.group(1); continue
        m = re.match(r'\[Result "(.+)"\]', line)
        if m:
            result = m.group(1)
            if result == "1-0":
                if engine1 in white: w1 += 1
                else: w2 += 1
            elif result == "0-1":
                if engine1 in black: w1 += 1
                else: w2 += 1
            elif result == "1/2-1/2":
                draws += 1
            white = black = result = None

total = w1 + w2 + draws
if total == 0:
    print("No completed games found in PGN.")
    sys.exit(0)

pts1 = w1 + draws * 0.5
pts2 = w2 + draws * 0.5

los = 0.5
if (w1 + w2) > 0:
    z = (w1 - w2) / _m.sqrt(w1 + w2)
    los = 0.5 * (1 + _m.erf(z / _m.sqrt(2)))

elo_diff = 0
if 0 < pts1 < total:
    elo_diff = round(-400 * _m.log10(total / pts1 - 1))

print()
print("╔══════════════════════════════════════════════════════╗")
print("║                    MATCH RESULTS                    ║")
print("╠══════════════════════════════════════════════════════╣")
print(f"║  {'Engine':<28}  {'Score':>6}  {'W':>4} {'L':>4} {'D':>4} ║")
print("╠══════════════════════════════════════════════════════╣")
print(f"║  {engine1:<28}  {pts1:>5.1f}   {w1:>4} {w2:>4} {draws:>4} ║")
print(f"║  {engine2:<28}  {pts2:>5.1f}   {w2:>4} {w1:>4} {draws:>4} ║")
print("╠══════════════════════════════════════════════════════╣")
print(f"║  Total games : {total:<4}                                 ║")
print(f"║  Elo diff    : {elo_diff:+d} (challenger perspective)          ║")
print(f"║  LOS         : {los*100:.1f}%                                  ║")
print("╠══════════════════════════════════════════════════════╣")
verdict = "PASS ✓" if elo_diff > 0 and los >= 0.95 else \
          "LIKELY +" if elo_diff > 0 and los >= 0.70 else \
          "INCONCLUSIVE" if abs(elo_diff) < 10 else "FAIL ✗"
print(f"║  Verdict     : {verdict:<38}║")
print("╚══════════════════════════════════════════════════════╝")
print()
print(f"  PGN log: {pgn_path}")
PYEOF
}

# ── C++ match ─────────────────────────────────────────────────────────────────
if (( RUN_CPP )); then
    CPP_PGN="$MATCH_DIR/${TIMESTAMP}-cpp-${CURRENT_SLUG}-vs-${BASE_SLUG}.pgn"
    CPP_E1_NAME="cpp-${CURRENT_SLUG}"
    CPP_E2_NAME="cpp-${BASE_SLUG}-${BASE_HASH}"

    echo "▶ C++ match: ${GAMES} games (${ROUNDS} opening pairs)…"
    echo ""

    cutechess-cli \
        -engine "cmd=$CURRENT_CPP_BIN" "name=$CPP_E1_NAME" "dir=$ENGINE_CACHE" proto=uci \
        -engine "cmd=$BASE_CPP_BIN"    "name=$CPP_E2_NAME" "dir=$ENGINE_CACHE" proto=uci \
        -each "tc=$TC" \
        -rounds "$ROUNDS" \
        -games 2 \
        -repeat \
        -pgnout "$CPP_PGN" \
        -resign movecount=5 score=1000 \
        -draw movenumber=40 movecount=8 score=10 \
        "${OPENINGS_ARGS[@]}"

    parse_results "$CPP_PGN" "$CPP_E1_NAME" "$CPP_E2_NAME"
fi

# ── Python match ──────────────────────────────────────────────────────────────
if (( RUN_PY )); then
    PY_PGN="$MATCH_DIR/${TIMESTAMP}-py-${CURRENT_SLUG}-vs-${BASE_SLUG}.pgn"
    PY_E1_NAME="py-${CURRENT_SLUG}"
    PY_E2_NAME="py-${BASE_SLUG}-${BASE_HASH}"

    echo "▶ Python match: ${GAMES} games (${ROUNDS} opening pairs)…"
    echo ""

    cutechess-cli \
        -engine "cmd=$CURRENT_PY_LAUNCHER" "name=$PY_E1_NAME" "dir=$ENGINE_CACHE" proto=uci \
        -engine "cmd=$BASE_PY_LAUNCHER"    "name=$PY_E2_NAME" "dir=$ENGINE_CACHE" proto=uci \
        -each "tc=$TC" \
        -rounds "$ROUNDS" \
        -games 2 \
        -repeat \
        -pgnout "$PY_PGN" \
        -resign movecount=5 score=1000 \
        -draw movenumber=40 movecount=8 score=10 \
        "${OPENINGS_ARGS[@]}"

    parse_results "$PY_PGN" "$PY_E1_NAME" "$PY_E2_NAME"
fi
