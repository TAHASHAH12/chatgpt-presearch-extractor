#!/usr/bin/env bash
# Extract ChatGPT's pre-search / invisible layer at scale, end to end.
#   cp .env.example .env   # fill DFS_AUTH
#   ./run_all.sh [--workers 8] [--prompts prompts.tsv]
set -euo pipefail
cd "$(dirname "$0")/pipeline"
if [ -f ../.env ]; then set -a; . ../.env; set +a; fi
say() { printf '\n\033[1;32m==>\033[0m %s\n' "$1"; }

say "1/3  extract — run prompts through ChatGPT (DataForSEO), keep fan-out + retrieved pool"
python3 -I extract.py "$@"

say "2/3  parse — per prompt: fan-out, retrieved pool, shown citations, invisible set"
python3 parse.py

say "3/3  analyze — invisible-layer metrics + invisible influencers"
python3 analyze.py

say "done. See pipeline/presearch.json (per prompt) and pipeline/analysis.json (rollup)."
