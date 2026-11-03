#!/usr/bin/env bash
# Run the Simplify ETF checker with one command (no need to activate the venv).
#
# Usage:
#   ./run.sh              # check all ETFs
#   ./run.sh --limit 5    # check only the first 5 ETFs
#   ./run.sh test         # run the unit tests
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

PYTHON=".venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "Virtual environment not found (.venv). Create it first:" >&2
    echo "  uv venv --python 3.13 && uv pip install -r requirements.txt" >&2
    exit 1
fi

if [[ "${1:-}" == "test" ]]; then
    exec "$PYTHON" -m unittest discover -s tests -t . -v
fi

exec "$PYTHON" etf_checker.py "$@"
