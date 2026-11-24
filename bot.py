"""CLI and shared X text helpers for the daily personal agent."""
import json
import os
import re
from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent
HISTORY_FILE = ROOT / "data" / "history.json"

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def x_length(text):
    """Character count the way X counts it: most scripts (Latin, Devanagari, Urdu) = 1, emoji/CJK = 2."""
    n = 0
    for ch in text:
        cp = ord(ch)
        light = cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247
        n += 1 if light else 2
    return n


def sounds_like_ai(text):
    """Returns the first banned phrase found (see config.BANNED_PATTERNS), or None."""
    for pattern in config.BANNED_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0)
    return None


def x_bearer_token():
    """App-only token for reading public X data, made from the same API key and secret
    the bot already has (an X_BEARER_TOKEN secret is used instead if you add one)."""
    import requests
    if os.environ.get("X_BEARER_TOKEN"):
        return os.environ["X_BEARER_TOKEN"]
    r = requests.post("https://api.x.com/oauth2/token",
                      auth=(os.environ["X_API_KEY"], os.environ["X_API_SECRET"]),
                      data={"grant_type": "client_credentials"}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    from agent.daily import main as daily_main
    daily_main()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Public Actions logs must never disclose drafts, credentials or response bodies.
        import sys
        cause = type(exc).__name__
        if isinstance(exc, ValueError) and exc.args == ('quality_threshold',):
            cause = 'quality_threshold'
        print(f"Daily agent failed: {cause}", file=sys.stderr)
        sys.exit(1)
