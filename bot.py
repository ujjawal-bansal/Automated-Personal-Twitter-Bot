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


def due_slot(now, history):
    day = now.date()
    for name, (s, e) in config.WINDOWS.items():
        start, end = at(day, s), at(day, e)
        if not (start <= now <= end + timedelta(minutes=config.GRACE_MINUTES)):
            continue
        slot = f"{day.isoformat()}-{name}"
        if any(p.get("slot") == slot for p in history["posts"]):
            print(f"Already posted for {slot}.")
            return None
        target = target_time(day, name, start, end)
        if now < target:
            print(f"{slot}: not yet, today's post time is {target:%H:%M}.")
            return None
        return slot
    print(f"{now:%H:%M} is outside every posting window.")
    return None


# ---------------------------------------------------------------- content

def choose_pillar(history, exclude=()):
    recent = [p["pillar"] for p in history["posts"][-2:]]
    names = [n for n in config.PILLARS if n not in recent and n not in exclude]
    names = names or [n for n in config.PILLARS if n not in exclude]
    return random.choices(names, [config.PILLARS[n]["weight"] for n in names])[0]


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
    parts = [f"Topic: {topic}", f"Format: {fmt}."]
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
        parts.append("Recent tweets on the account (do not repeat their ideas or openings):\n"
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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip().strip('"“”').strip()


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
    for _ in range(5):
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
        elif too_similar(text, history):
            print("Too similar to a recent post, retrying.")
        else:
            return {"pillar": pillar, "topic": topic, "text": text,
                    "image_query": image_query_from(raw) if want_image else None}
    raise RuntimeError("Could not produce a usable post after 5 tries.")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="generate and print, don't post")
    ap.add_argument("--force", action="store_true", help="ignore the schedule")
    args = ap.parse_args()
    dry = args.dry_run or env_flag("DRY_RUN")
    force = args.force or env_flag("FORCE")

    history = load_json(HISTORY_FILE, {"posts": []})
    now = datetime.now(TZ)
    slot = f"{now:%Y-%m-%d}-manual-{now:%H%M}" if force else due_slot(now, history)
    if not slot:
        return

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
