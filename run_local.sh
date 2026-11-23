#!/bin/bash
# Run XBot on this Mac with keys from .env (never committed: .env is in .gitignore).
#   ./run_local.sh                  test: write a normal tweet, DON'T post
#   ./run_local.sh trending         test: write a trending tweet, DON'T post
#   ./run_local.sh post-now         REALLY post a normal tweet now (costs X credit)
#   ./run_local.sh trending-now     REALLY post a trending tweet now
#   ./run_local.sh auto             same as a scheduled GitHub run (posts only if due)
cd "$(dirname "$0")"
if [ ! -f .env ]; then echo "No .env file. Copy .env.example to .env and fill in your keys."; exit 1; fi
set -a; source .env; set +a
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib   # Hindi/Urdu text shaping (Homebrew libraqm)
case "${1:-dry-run}" in
  dry-run)      exec .venv/bin/python bot.py --dry-run --force ;;
  trending)     exec .venv/bin/python bot.py --dry-run --force --trending ;;
  post-now)     exec .venv/bin/python bot.py --force ;;
  trending-now) exec .venv/bin/python bot.py --force --trending ;;
  auto)         exec .venv/bin/python bot.py ;;
  *) echo "Unknown mode: $1"; exit 1 ;;
esac
