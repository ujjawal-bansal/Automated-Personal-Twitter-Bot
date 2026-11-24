#!/bin/bash
set -eu
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH:-}"
case "${1:-dry-run}" in
  dry-run|trending) exec .venv/bin/python bot.py --dry-run ;;
  review|preferences) exec .venv/bin/python bot.py "--$1" ;;
  post-now|trending-now) exec .venv/bin/python bot.py --force ;;
  auto) exec .venv/bin/python bot.py ;;
  *) echo 'Expected dry-run, review, preferences, auto or post-now' >&2; exit 2 ;;
esac
