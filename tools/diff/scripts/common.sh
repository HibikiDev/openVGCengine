

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUNS="${DIFF_RUNS:-$ROOT/target/diff-runs}"

case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) EXE=.exe ;; *) EXE= ;; esac
DIFFRUN="${DIFFRUN:-$RUNS/diffrun$EXE}"
mkdir -p "$RUNS"
export PATH="$PATH:${USERPROFILE:-$HOME}/.cargo/bin"


if [ -z "${PYO3_PYTHON:-}" ] && [ -x "$ROOT/.venv/bin/python" ]; then export PYO3_PYTHON="$ROOT/.venv/bin/python"; fi
