"""
Weekly self-learning.

Once a week the bot reads how its own posts did on X (views, likes, replies, reposts,
bookmarks) and nudges how often each pillar gets picked. Pillars that land well get a
little more airtime, weaker ones a little less, but the guardrails in config.LEARNING
keep the feed a real mix: every pillar keeps a minimum share, none can pass a maximum,
and shares only move part of the way each week.

Results go to data/weights.json (used by bot.py) and data/report.md (for you to read).

Cost: own-post reads are "Owned Reads" on X pay-per-use, $0.001 per post, and each post
is read once, a few days after it went out. About $0.10 a month at 3 posts a day.

Local test:  python learn.py --dry-run   (reads metrics, prints the report, saves nothing)
"""
import argparse
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import config

ROOT = Path(__file__).parent
WEIGHTS_FILE = ROOT / "data" / "weights.json"
REPORT_FILE = ROOT / "data" / "report.md"
SETTLE = timedelta(hours=48)   # measure a post once it is this old; most reach comes early
LOOKBACK = timedelta(days=29)  # older posts no longer steer the weights


# ---------------------------------------------------------------- reading metrics

def _time(p):
    return datetime.fromisoformat(p["time"]).astimezone(timezone.utc)


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_metrics(history, now):
    """Adds p['metrics'] to bot posts that are old enough and not measured yet.
    Returns how many posts were measured."""
    todo = [p for p in history["posts"] if p.get("id") and "metrics" not in p
            and now - LOOKBACK <= _time(p) <= now - SETTLE]
    if not todo:
        print("Learning: no new posts old enough to measure.")
        return 0

    import images  # reuses the OAuth 1.0a signer used for media upload
    user_id = os.environ["X_ACCESS_TOKEN"].split("-")[0]  # X access tokens start with the account id
    params = {
        "start_time": _iso(min(_time(p) for p in todo) - timedelta(minutes=1)),
        "end_time": _iso(now - SETTLE),
        "max_results": 100,
        "tweet.fields": "public_metrics,created_at",
        "exclude": "retweets,replies",
    }
    found = {}
    while True:
        r = requests.get(f"https://api.x.com/2/users/{user_id}/tweets", params=params,
                         auth=images._oauth(), timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"metrics read failed {r.status_code}: {r.text[:300]}")
        body = r.json()
        for t in body.get("data", []):
            found[t["id"]] = t["public_metrics"]
        token = body.get("meta", {}).get("next_token")
        if not token:
            break
        params["pagination_token"] = token

    measured = 0
    for p in todo:
        m = found.get(str(p["id"]))
        if m:
            p["metrics"] = {k: m.get(k, 0) for k in
                            ("impression_count", "like_count", "reply_count",
                             "retweet_count", "quote_count", "bookmark_count")}
            measured += 1
    print(f"Learning: read {len(found)} posts from X, measured {measured} bot posts.")
    return measured


# ---------------------------------------------------------------- scoring

def points(m):
    """One number per post. Conversations and shares count most, then likes and bookmarks;
    50 views are worth about one like, so reach still matters on a small account."""
    return (m["like_count"] + m["bookmark_count"]
            + 2 * (m["reply_count"] + m["retweet_count"] + m["quote_count"])
            + m["impression_count"] / 50)


def pillar_scores(history, now):
    """Per pillar: (recency-weighted post count, how it compares to the account average).
    Uses log(points) so one viral post can't drag a whole pillar up on its own."""
    rows = []
    for p in history["posts"]:
        if "metrics" in p and p["pillar"] in config.PILLARS and _time(p) >= now - LOOKBACK:
            age_days = (now - _time(p)).total_seconds() / 86400
            w = 0.5 ** (age_days / config.LEARNING["half_life_days"])  # newer posts count more
            rows.append((p["pillar"], w, math.log1p(points(p["metrics"]))))
    if not rows:
        return {}
    overall = sum(w * s for _, w, s in rows) / sum(w for _, w, _ in rows)
    out = {}
    for name in config.PILLARS:
        mine = [(w, s) for n, w, s in rows if n == name]
        n = len(mine)
        wsum = sum(w for w, _ in mine)
        if n < config.LEARNING["min_posts"]:
            out[name] = (n, 0.0)  # not enough data yet: stay neutral
            continue
        mean = sum(w * s for w, s in mine) / wsum
        # shrink toward "average" when there are few posts, so luck doesn't steer
        out[name] = (n, (mean - overall) * wsum / (wsum + config.LEARNING["prior_posts"]))
    return out


# ---------------------------------------------------------------- weights with guardrails

def clamp_shares(shares, floor, ceiling):
    """Scales shares to sum to 1 while keeping each between floor and ceiling."""
    shares = dict(shares)
    fixed = {}
    for _ in range(len(shares) + 1):
        free = {k: v for k, v in shares.items() if k not in fixed}
        room = 1 - sum(fixed.values())
        total = sum(free.values()) or 1
        scaled = {k: v / total * room for k, v in free.items()}
        # pin the single worst offender, then rescale the rest and look again
        worst = max(scaled, key=lambda k: max(floor - scaled[k], scaled[k] - ceiling))
        if floor - 1e-12 <= scaled[worst] <= ceiling + 1e-12:
            return {**fixed, **scaled}
        fixed[worst] = floor if scaled[worst] < floor else ceiling
    return {**fixed, **scaled}


def base_shares():
    total = sum(c["weight"] for c in config.PILLARS.values())
    return {n: c["weight"] / total for n, c in config.PILLARS.items()}


def current_shares():
    saved = json.loads(WEIGHTS_FILE.read_text()) if WEIGHTS_FILE.exists() else {}
    base = base_shares()
    return {n: saved.get("shares", {}).get(n, base[n]) for n in config.PILLARS}


def new_shares(scores):
    L = config.LEARNING
    base = base_shares()
    target = {}
    for n in config.PILLARS:
        _, rel = scores.get(n, (0, 0.0))
        boost = min(max(math.exp(rel * L["strength"]), 1 / L["max_boost"]), L["max_boost"])
        target[n] = base[n] * boost
    target = clamp_shares(target, L["floor"], L["ceiling"])
    old = current_shares()
    moved = {n: old[n] + L["step"] * (target[n] - old[n]) for n in config.PILLARS}
    return clamp_shares(moved, L["floor"], L["ceiling"])


# ---------------------------------------------------------------- report

def report(history, scores, before, after, now):
    lines = [f"# Weekly report, {now:%d %b %Y}", "",
             "How each kind of post did over the last 4 weeks, and how often the bot will "
             "pick it from now on.", "",
             "| Pillar | Posts measured | Avg views | Avg likes | Share before | Share now |",
             "|---|---|---|---|---|---|"]
    for n in config.PILLARS:
        ms = [p["metrics"] for p in history["posts"] if p["pillar"] == n and "metrics" in p
              and _time(p) >= now - LOOKBACK]
        views = sum(m["impression_count"] for m in ms) / len(ms) if ms else 0
        likes = sum(m["like_count"] for m in ms) / len(ms) if ms else 0
        lines.append(f"| {n} | {len(ms)} | {views:.0f} | {likes:.1f} | "
                     f"{before[n]:.0%} | {after[n]:.0%} |")
    week = [p for p in history["posts"] if "metrics" in p and _time(p) >= now - timedelta(days=9)]
    week.sort(key=lambda p: points(p["metrics"]), reverse=True)
    if week:
        lines += ["", "## Best posts this week", ""]
        for p in week[:3]:
            m = p["metrics"]
            first = p["text"].split("\n")[0][:90]
            lines.append(f"- [{p['pillar']}] {first} ({m['impression_count']} views, "
                         f"{m['like_count']} likes) https://x.com/i/status/{p['id']}")
    L = config.LEARNING
    lines += ["", f"Guardrails: every pillar stays between {L['floor']:.0%} and {L['ceiling']:.0%}, "
              f"shares move {L['step']:.0%} of the way per week, and a pillar never "
              "repeats within 3 posts."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- entry points

def due(now):
    if not WEIGHTS_FILE.exists():
        return True
    updated = datetime.fromisoformat(json.loads(WEIGHTS_FILE.read_text())["updated"])
    return now - updated >= timedelta(days=config.LEARNING["every_days"])


def run(history, now=None, save=True):
    """Measures new posts, updates weights and writes the report. Changes history in place."""
    now = now or datetime.now(timezone.utc)
    fetch_metrics(history, now)
    scores = pillar_scores(history, now)
    before = current_shares()
    after = new_shares(scores) if scores else before
    text = report(history, scores, before, after, now)
    print(text)
    if save:
        WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        WEIGHTS_FILE.write_text(json.dumps(
            {"updated": now.isoformat(timespec="minutes"),
             "shares": {n: round(v, 4) for n, v in after.items()}}, indent=2))
        REPORT_FILE.write_text(text, encoding="utf-8")


def main():
    import bot
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the report, save nothing")
    args = ap.parse_args()
    history = bot.load_json(bot.HISTORY_FILE, {"posts": []})
    run(history, save=not args.dry_run)
    if not args.dry_run:
        bot.save_history(history)


if __name__ == "__main__":
    main()
