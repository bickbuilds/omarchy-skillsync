#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$root/tests/test_skillkit.py"
node --test "$root/tests/test_model.js"
