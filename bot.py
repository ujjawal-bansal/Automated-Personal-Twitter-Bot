#!/usr/bin/env python3
"""
X bot for Vashu Vats.
Each run: checks whether a post is due, picks a pillar, writes a tweet with Gemini
(or picks a shayari from content/shayari.json), posts it, and logs it to data/history.json.

Local test:  python bot.py --dry-run --force
"""
import argparse
import difflib
import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import config

ROOT = Path(__file__).parent
HISTORY_FILE = ROOT / "data" / "history.json"
WEIGHTS_FILE = ROOT / "data" / "weights.json"
SHAYARI_FILE = ROOT / "content" / "shayari.json"
PREVIEW_DIR = ROOT / "preview"
MAX_LEN = 280
TZ = ZoneInfo(config.TIMEZONE)


# ---------------------------------------------------------------- helpers

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_history(history):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def x_length(text):
    """Character count the way X counts it: most scripts (Latin, Devanagari, Urdu) = 1, emoji/CJK = 2."""
    n = 0
    for ch in text:
        cp = ord(ch)
        light = cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247
        n += 1 if light else 2
    return n


def env_flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------- schedule

def at(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


def target_time(day, name, start, end):
    """A random-looking but fixed minute inside the window for this date."""
    seed = f"{day.isoformat()}|{name}|{os.environ.get('SCHEDULE_SEED', '')}"
    rng = random.Random(hashlib.sha256(seed.encode()).hexdigest())
    span = int((end - start).total_seconds() // 60)
    return start + timedelta(minutes=rng.randint(0, span))


def is_trending(post):
    return post.get("pillar") == "trending"


def next_post_day(posts, every_days=None):
    """The date of the next post: 3 or 4 days (config.POST_EVERY_DAYS) after the last one,
    picked at random but fixed for that last post. None if nothing has been posted yet."""
    if not posts:
        return None
    last = datetime.fromisoformat(posts[-1]["time"]).astimezone(TZ).date()
    rng = random.Random(f"{last.isoformat()}|gap|{os.environ.get('SCHEDULE_SEED', '')}")
    lo, hi = every_days or config.POST_EVERY_DAYS
    return last + timedelta(days=rng.randint(lo, hi))


def due_slot(now, history, trending=False):
    """GitHub often runs scheduled jobs late or skips them, so a window's post stays due
    until the next window starts (the last one until midnight): a missed slot is caught
    up on the next run that does happen, instead of being lost.
    Normal posts and trending posts each keep their own window and their own 3-4 day gap."""
    day = now.date()
    if trending:
        posts = [p for p in history["posts"] if is_trending(p)]
        windows = {"trending": config.TRENDING["window"]}
        every_days = config.TRENDING["every_days"]
    else:
        posts = [p for p in history["posts"] if not is_trending(p)]
        windows = config.WINDOWS
        every_days = config.POST_EVERY_DAYS
    windows = sorted(windows.items(), key=lambda w: w[1][0])
    for i, (name, (s, e)) in enumerate(windows):
        start, end = at(day, s), at(day, e)
        if trending:
            until = at(day, config.TRENDING.get("catch_up_until", e))
        elif i + 1 < len(windows):
            until = at(day, windows[i + 1][1][0])
        else:
            until = at(day + timedelta(days=1), "00:00")
        if not (start <= now < until):
            continue
        slot = f"{day.isoformat()}-{name}"
        if any(p.get("slot") == slot for p in history["posts"]):
            print(f"Already posted for {slot}.")
            return None
        wait_until = next_post_day(posts, every_days)
        if wait_until and day < wait_until:
            print(f"{name}: posting every {'-'.join(map(str, sorted(set(every_days))))} days, next post on {wait_until:%d %b}.")
            return None
        target = target_time(day, name, start, end)
        if now < target:
            print(f"{slot}: not yet, today's post time is {target:%H:%M}.")
            return None
        last = max((datetime.fromisoformat(p["time"]) for p in history["posts"]), default=None)
        if last and now - last < timedelta(minutes=config.MIN_GAP_MINUTES):
            print(f"{slot}: last post was at {last:%H:%M}, waiting for a gap of {config.MIN_GAP_MINUTES} minutes.")
            return None
        return slot
    print(f"{now:%H:%M} is outside the {'trending' if trending else 'normal'} posting window.")
    return None


# ---------------------------------------------------------------- content

def pillar_weights():
    """Learned shares from data/weights.json (see learn.py), else the weights in config.py."""
    learned = load_json(WEIGHTS_FILE, {}).get("shares", {})
    return {n: learned.get(n, c["weight"]) for n, c in config.PILLARS.items()}


def choose_pillar(history, exclude=()):
    recent = [p["pillar"] for p in history["posts"][-2:]]
    names = [n for n in config.PILLARS if n not in recent and n not in exclude]
    names = names or [n for n in config.PILLARS if n not in exclude]
    weights = pillar_weights()
    return random.choices(names, [weights[n] for n in names])[0]


def format_shayari(item):
    return f"{item['text'].strip()}\n\n— {item['poet'].strip()}"


def pick_shayari(history):
    """Returns a shayari dict ({'poet', 'text'}) not posted recently, or None."""
    items = [s for s in load_json(SHAYARI_FILE, []) if s.get("text") and s.get("poet")]
    items = [s for s in items if x_length(format_shayari(s)) <= MAX_LEN]
    if not items:
        return None
    used = [p["text"] for p in history["posts"] if p["pillar"] == "shayari"]
    fresh = [s for s in items if format_shayari(s) not in used]
    if not fresh:  # every couplet used once: avoid only the most recent half
        recent = set(used[-(len(items) // 2):]) if len(items) > 1 else set()
        fresh = [s for s in items if format_shayari(s) not in recent] or items
    return random.choice(fresh)


def build_prompt(topic, fmt, recent, search, meant_current, want_image=False):
    parts = [f"Topic: {topic}", f"Format: {fmt}.",
             "Stick to this one topic. No comparisons with other subjects, eras or traditions."]
    if search:
        parts.append("First search for the most significant news on this topic from the past 7 days. "
                     "Build the tweet around one specific, real, recent development, "
                     "using only facts that appear in the search results.")
    elif meant_current:
        parts.append("You have no access to current news, so do not mention specific recent events, "
                     "dates or figures. Take a timeless strategic or historical angle instead.")
    if want_image:
        parts.append("After the tweet, give a 2-5 word Wikimedia Commons search query for a historical "
                     "artwork, artifact, manuscript, sculpture or site photo that would illustrate it, "
                     "inside <image_query></image_query>. Prefer specific, famous subjects.")
    if recent:
        parts.append("Recent tweets on the account (do not repeat their ideas, openings or sentence shapes):\n"
                     + "\n".join(f"- {t}" for t in recent))
    return "\n\n".join(parts)


def generate(topic, fmt, recent, grounded, want_image=False):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models = [m.strip() for m in os.environ.get("GEMINI_MODELS", "").split(",") if m.strip()]
    models = models or config.GEMINI_MODELS
    attempts = [(m, grounded) for m in models] + ([(m, False) for m in models] if grounded else [])

    last_error = None
    for model, search in attempts:
        prompt = build_prompt(topic, fmt, recent, search, meant_current=grounded, want_image=want_image)
        tools = [types.Tool(google_search=types.GoogleSearch())] if search else None
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=config.PERSONA, temperature=1.0, tools=tools),
            )
            if resp.text and resp.text.strip():
                print(f"Generated with {model} (search={search}).")
                return resp.text
            print(f"{model} (search={search}) returned nothing (possibly a safety block).")
        except Exception as e:  # rate limit, unavailable model, etc.
            print(f"{model} (search={search}) failed: {e}")
            last_error = e
    raise RuntimeError(f"Every Gemini attempt failed. Last error: {last_error}")


def clean(raw):
    m = re.search(r"<tweet>(.*?)</tweet>", raw, re.S)
    text = m.group(1) if m else re.sub(r"<image_query>.*?</image_query>", "", raw, flags=re.S)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)       # links cost $0.20 per post on X
    text = re.sub(r"\s*\[\d+(?:[,\s]*\d+)*\]", "", text)       # search citation markers like [1]
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\s*[—–]\s*", ", ", text).replace(";", ".")  # dashes and semicolons read as AI
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip().strip('"“”').strip()


def sounds_like_ai(text):
    """Returns the first banned phrase found (see config.BANNED_PATTERNS), or None."""
    for pattern in config.BANNED_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0)
    return None


def too_similar(text, history):
    for p in history["posts"][-40:]:
        if difflib.SequenceMatcher(None, text.lower(), p["text"].lower()).ratio() > 0.6:
            return True
    return False


def image_query_from(raw):
    m = re.search(r"<image_query>(.*?)</image_query>", raw, re.S)
    return m.group(1).strip() if m else None


def make_post(history):
    skip = set()
    for _ in range(6):
        pillar = choose_pillar(history, exclude=skip)
        cfg = config.PILLARS[pillar]
        if pillar == "shayari":
            item = pick_shayari(history)
            if item:
                return {"pillar": pillar, "topic": None, "text": format_shayari(item), "shayari": item}
            skip.add("shayari")  # file empty
            continue
        topic = random.choice(cfg["topics"])
        fmt = random.choice(config.FORMATS)
        want_image = random.random() < cfg.get("image_chance", 0)
        recent = [p["text"] for p in history["posts"][-8:] if p["pillar"] != "shayari"]
        raw = generate(topic, fmt, recent, cfg.get("grounded", False), want_image)
        text = clean(raw)
        if not text:
            print("Empty tweet after cleaning, retrying.")
        elif x_length(text) > MAX_LEN:
            print(f"Too long ({x_length(text)} chars), retrying.")
        elif sounds_like_ai(text):
            print(f"Sounds AI-written ({sounds_like_ai(text)!r}), retrying.")
        elif too_similar(text, history):
            print("Too similar to a recent post, retrying.")
        else:
            return {"pillar": pillar, "topic": topic, "text": text,
                    "image_query": image_query_from(raw) if want_image else None}
    raise RuntimeError("Could not produce a usable post after 6 tries.")


# ---------------------------------------------------------------- trending posts

TRENDING_PERSONA = config.PERSONA.replace(
    "- No hashtags, no emojis, no links, no @mentions.",
    "- No emojis, no links, no @mentions. Do not put hashtags inside the tweet; give them separately.")
HASHTAG_RE = re.compile(r"^#[^\W_][\w]{1,29}$")


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


def fetch_x_trends():
    """What's trending on X right now, from the places in config.TRENDING["x_trends"].
    Returns [(name, post_count or None)], or [] if X can't be read (the bot then uses search only).
    Each list read costs $0.010 on X."""
    import requests
    places = config.TRENDING.get("x_trends") or []
    if not places or not os.environ.get("X_API_KEY"):
        return []
    try:
        headers = {"Authorization": f"Bearer {x_bearer_token()}"}
    except Exception as e:
        print(f"Could not get an X app token, using search only: {e}")
        return []
    trends, seen = [], set()
    for woeid in places:
        try:
            r = requests.get(f"https://api.x.com/2/trends/by/woeid/{woeid}", headers=headers, timeout=20,
                             params={"max_trends": min(50, config.TRENDING.get("x_trends_count", 30)),
                                     "trend.fields": "trend_name,tweet_count"})
            r.raise_for_status()
            for t in r.json().get("data") or []:
                name = (t.get("trend_name") or "").strip()
                if name and name.lower() not in seen:
                    seen.add(name.lower())
                    trends.append((name, t.get("tweet_count")))
        except Exception as e:
            print(f"Could not read X trends for place {woeid}: {e}")
    print(f"Read {len(trends)} trends from X.")
    return trends


def trending_prompt(recent_topics, recent, x_trends=()):
    T = config.TRENDING
    room = MAX_LEN - 10 - 16 * T["max_hashtags"]
    if x_trends:
        listing = "\n".join(f"- {n}" + (f" ({c:,} posts)" if isinstance(c, int) else "") for n, c in x_trends)
        find = ("These are trending on X right now (India and worldwide):\n" + listing + "\n\n"
                "Pick from this list a trend that is a real news story within these areas, and search Google "
                "for the facts about it:\n" + "\n".join(f"- {c}" for c in T["categories"]))
    else:
        find = ("Search Google for the stories trending on X (Twitter) and in the news in the last 24 hours, "
                "in India and worldwide, within these areas:\n" + "\n".join(f"- {c}" for c in T["categories"]))
    parts = [
        find,
        "Pick the ONE story that is biggest right now and that a sharp, curious guy could have a real "
        "take on. Never pick any of these:\n" + "\n".join(f"- {a}" for a in T["avoid"]),
        f"Write one tweet about it in his voice, at most {room} characters, using only facts that appear "
        "in the search results. Format: a plain observation, an honest question, or a short opinion with "
        "one reason. Protests and politics: describe what is happening and what you wonder about it, do "
        "not take sides against any group of people.",
        f"Then give up to {T['max_hashtags']} hashtags that people on X are actually using for this story "
        "right now, most used first" + (" (use the exact hashtags from the X list above when they fit)" if x_trends else "")
        + ". Only real, relevant tags, no generic ones like #News or #Breaking.",
        "Answer in exactly this shape:\n<topic>short name of the story</topic>\n<tweet>the tweet</tweet>\n"
        "<hashtags>#One #Two</hashtags>",
    ]
    if recent_topics:
        parts.append("Already covered recently, pick something else:\n" + "\n".join(f"- {t}" for t in recent_topics))
    if recent:
        parts.append("Recent tweets on the account (do not repeat their openings or sentence shapes):\n"
                     + "\n".join(f"- {t}" for t in recent))
    return "\n\n".join(parts)


def generate_trending(prompt):
    """Always searches. If search fails there is no trending post (it would only be a guess)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    models = [m.strip() for m in os.environ.get("GEMINI_MODELS", "").split(",") if m.strip()]
    for model in models or config.GEMINI_MODELS:
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=TRENDING_PERSONA, temperature=0.9,
                    tools=[types.Tool(google_search=types.GoogleSearch())]),
            )
            if resp.text and resp.text.strip():
                print(f"Trending post generated with {model}.")
                return resp.text
            print(f"{model} returned nothing (possibly a safety block).")
        except Exception as e:
            print(f"{model} failed: {e}")
    raise RuntimeError("Every Gemini attempt with search failed; no trending post this time.")


def tag(raw, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", raw, re.S)
    return m.group(1).strip() if m else ""


def pick_hashtags(raw, body, x_trends=()):
    """Valid, distinct hashtags from Gemini's answer, as many as fit in the tweet.
    Tags that are on X's live trending list go first."""
    tags, seen = [], {g.lower() for g in config.TRENDING.get("generic_hashtags", [])}
    for t in re.findall(r"#[^\s#]+", tag(raw, "hashtags")):
        t = t.strip(".,;:!?\"'")
        if HASHTAG_RE.match(t) and not t[1:].isdigit() and t[1:].lower() not in seen:
            seen.add(t[1:].lower())
            tags.append(t)
    live = {n.lower() for n, _ in x_trends}
    tags.sort(key=lambda t: t.lower() not in live)  # stable: live trends first, Gemini's order otherwise
    tags = tags[:config.TRENDING["max_hashtags"]]
    while tags and x_length(body + "\n\n" + " ".join(tags)) > MAX_LEN:
        tags.pop()
    return tags


def make_trending_post(history):
    old = [p for p in history["posts"] if is_trending(p)]
    recent_topics = [p["topic"] for p in old[-config.TRENDING["skip_recent_topics"]:] if p.get("topic")]
    recent = [p["text"] for p in history["posts"][-6:] if p["pillar"] != "shayari"]
    x_trends = fetch_x_trends()  # read once per post, not per retry (each read is paid)
    for _ in range(4):
        raw = generate_trending(trending_prompt(recent_topics, recent, x_trends))
        topic = tag(raw, "topic") or None
        body = re.sub(r"(^|\s)#\w+", "", clean(f"<tweet>{tag(raw, 'tweet')}</tweet>")).strip()
        if not body:
            print("Empty tweet after cleaning, retrying.")
            continue
        if sounds_like_ai(body):
            print(f"Sounds AI-written ({sounds_like_ai(body)!r}), retrying.")
            continue
        if too_similar(body, history):
            print("Too similar to a recent post, retrying.")
            continue
        tags = pick_hashtags(raw, body, x_trends)
        text = body + ("\n\n" + " ".join(tags) if tags else "")
        if x_length(text) > MAX_LEN:
            print(f"Too long ({x_length(text)} chars), retrying.")
            continue
        print(f"Trending story: {topic}")
        return {"pillar": "trending", "topic": topic, "text": text}
    raise RuntimeError("Could not produce a usable trending post after 4 tries.")


def attach_image(post, history):
    """Adds post['image'] = {'bytes', 'alt', 'info'} when a good image is available."""
    import images

    if post.get("shayari"):
        chance = config.PILLARS["shayari"].get("card_chance", 0)
        if random.random() < chance:
            if not images.can_render_shayari():
                print("Text shaping (raqm) unavailable; posting shayari without a card.")
                return
            item = post["shayari"]
            post["image"] = {"bytes": images.shayari_card(item["text"], item["poet"]),
                             "alt": post["text"], "info": {"type": "card"}}
        return

    query = post.get("image_query")
    if not query:
        return
    used = {p["image"]["title"] for p in history["posts"] if (p.get("image") or {}).get("title")}
    found = images.find_commons_image(query, post["text"], used)
    if not found:
        print("No fitting public-domain image; posting text only.")
        return
    alt = found["description"] or found["title"].removeprefix("File:").rsplit(".", 1)[0]
    post["image"] = {"bytes": found["bytes"], "alt": alt,
                     "info": {"type": "commons", "title": found["title"], "page": found["page"]}}
    print(f"Image: {found['title']}")


# ---------------------------------------------------------------- posting

def post_to_x(text, image=None):
    import tweepy
    import images

    media_ids = None
    if image:
        try:
            media_ids = [images.upload_to_x(image["bytes"], image.get("alt"))]
        except Exception as e:  # never lose the post because of the image
            print(f"Image upload failed, posting text only: {e}")
            image.clear()

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    return client.create_tweet(text=text, media_ids=media_ids).data["id"]


def maybe_learn(history, force=False):
    """Once a week, piggybacks on a normal run to update the pillar weights.
    Never blocks posting: any error is printed and the post goes ahead."""
    import learn
    try:
        if force or learn.due(datetime.now(TZ)):
            learn.run(history)
            save_history(history)
    except Exception as e:
        print(f"Learning skipped this run: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="generate and print, don't post")
    ap.add_argument("--force", action="store_true", help="ignore the schedule")
    ap.add_argument("--trending", action="store_true", help="with --force: make a trending post")
    args = ap.parse_args()
    dry = args.dry_run or env_flag("DRY_RUN")
    force = args.force or env_flag("FORCE")
    trending_only = args.trending or env_flag("TRENDING")

    history = load_json(HISTORY_FILE, {"posts": []})
    now = datetime.now(TZ)
    if env_flag("LEARN_ONLY"):  # "learn-now" button in GitHub: re-learn, don't post
        maybe_learn(history, force=True)
        return
    if not dry and config.LEARNING.get("enabled") and os.environ.get("X_ACCESS_TOKEN"):
        maybe_learn(history)
    trending = False
    if force:
        slot = f"{now:%Y-%m-%d}-manual-{now:%H%M}"
        trending = trending_only
    else:
        slot = due_slot(now, history)
        if not slot and config.TRENDING.get("enabled"):
            slot = due_slot(now, history, trending=True)
            trending = bool(slot)
    if not slot:
        return

    if trending:
        post = make_trending_post(history)
    else:
        post = make_post(history)
        attach_image(post, history)
    text, image = post["text"], post.get("image")
    print(f"\n----- [{post['pillar']}] {x_length(text)} chars"
          f"{' + image' if image else ''} -----\n{text}\n" + "-" * 40)
    if dry:
        if image:
            PREVIEW_DIR.mkdir(exist_ok=True)
            (PREVIEW_DIR / "image.jpg").write_bytes(image["bytes"])
            (PREVIEW_DIR / "tweet.txt").write_text(text, encoding="utf-8")
            print(f"Image preview saved to {PREVIEW_DIR}/ (in GitHub: download the 'preview' artifact).")
        print("Dry run: nothing posted.")
        return

    tweet_id = post_to_x(text, image)
    print(f"Posted: https://x.com/i/status/{tweet_id}")
    history["posts"].append({
        "slot": slot, "time": now.isoformat(timespec="minutes"),
        "pillar": post["pillar"], "topic": post["topic"], "text": text, "id": tweet_id,
        "image": image["info"] if image else None,
    })
    history["posts"] = history["posts"][-300:]
    save_history(history)


if __name__ == "__main__":
    main()
