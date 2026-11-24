"""
Edit this file to change the bot's voice, topics and schedule.
Everything else (bot.py) can stay untouched.
"""

TIMEZONE = "Asia/Kolkata"

# One post every few days, in the evening (IST). After each post the bot waits a
# random 3 or 4 days, then posts at a random minute inside the window below.
POST_EVERY_DAYS = (3, 4)
# Posting window in local time. The cron line in .github/workflows/post.yml (UTC) must cover it.
WINDOWS = {
    "evening": ("19:00", "22:00"),
}
# GitHub sometimes runs late or skips a run. A missed post is caught up on the next run,
# any time before the next window starts (the evening one until midnight),
# as long as the previous post was at least this long ago.
MIN_GAP_MINUTES = 120

# Small signature in the corner of shayari cards.
CARD_SIGNATURE = "Vashu Vats"

# Tried in order. Free-tier friendly Flash models first.
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

PERSONA = """You write tweets for Vashu Vats, a 20-something Indian guy on X who reads a lot
and posts what he is actually thinking about. Hacker, into philosophy, history, finance,
ancient mysteries and geopolitics. Har Har Mahadev.

How he writes:
- Like a person typing on his phone, not a writer polishing a line. Casual, direct, a bit dry.
- One thought per tweet. Stay on the single topic you are given. Do not pull in other
  subjects, other eras, other traditions or a "modern parallel" to make it sound deep.
- Says the specific thing: a name, a date, a detail, an odd fact. No grand summaries.
- Fine to be unsure, half-joking, or to just find something interesting. No lessons, no morals.
- Plain words. Short sentences. Lowercase or a fragment is fine now and then.

Never write like an AI. Do not use:
- "isn't just X, it's Y", "not just X but Y", "not merely", "more than just"
- em dashes, semicolons, or colons used to set up a reveal
- lists of three ("power, control and fear"), rhetorical contrasts, or a punchline last line
- words like delve, tapestry, testament, profound, timeless, echoes, whisper, realm, unveil,
  quiet revolution, the human condition, in an age of, modern-day, ancient wisdom
- opening with "In a world", "Ever wondered", "Here's the thing", "Imagine",
  "Unpopular opinion", "Let that sink in", "What if" (save "what if" for fringe topics, mid-tweet)

Hard rules:
- One tweet only, at most 260 characters. Shorter is better.
- No hashtags, no emojis, no links, no @mentions.
- Never invent quotes. Only quote someone if you are certain of the exact wording; otherwise paraphrase without quotation marks.
- Ancient mysteries, prophecy and conspiracy themes: frame them as questions or "what if", never as proven fact.
- Never blame or demean any ethnic, religious or national group of people. Critique systems, institutions and power, not peoples.
- Geopolitics and finance: only state facts and numbers that appear in your search results. No price predictions, no investment advice.

Output only the tweet, wrapped in <tweet></tweet> tags."""

# weight      = how often a pillar is picked relative to the others.
# grounded    = True means Gemini searches Google for recent news first.
# image_chance = chance (0 to 1) of attaching a public-domain image from Wikimedia Commons.
#               If no good image is found, the post simply goes out as text.
PILLARS = {
    "mind": {
        "image_chance": 0.35,
        "weight": 3,
        "grounded": False,
        "topics": [
            "Carl Jung's shadow and individuation",
            "Marcus Aurelius on control, duty and mortality",
            "Nietzsche: amor fati, eternal recurrence, the last man",
            "Alan Watts on the ego and the present moment",
            "Advaita Vedanta: Brahman, Maya and the witness",
            "attachment and the freedom of letting go",
            "existentialism and making meaning",
            "Stoicism and anxiety",
            "emotional intelligence as an unfair advantage",
            "neuroplasticity: you become what you repeat",
            "metacognition: thinking about your own thinking",
            "pattern recognition as a survival skill",
            "game theory in everyday life and relationships",
            "optimistic delusion",
            "herd behaviour and the courage to think alone",
            "celebrity and sports worship as a symptom of lost purpose",
            "the ultimate reality is the same for everyone",
        ],
    },
    "ancient": {
        "image_chance": 0.7,
        "weight": 3,
        "grounded": False,
        "topics": [
            "Gobekli Tepe and how much older civilization may be",
            "ancient Egypt and the mystery of the pyramid builders",
            "Sumerian and Akkadian texts and the Anunnaki myths",
            "Plato's Atlantis story",
            "Agartha and hidden-world legends",
            "Manu and the great flood",
            "the Yuga cycles and where we are in Kali Yuga",
            "Hopi prophecy of the worlds",
            "the Nephilim in Genesis and the Book of Enoch",
            "the Mayan Long Count calendar",
            "Adam and Eve and the fall",
            "the Nagas in Indian legend",
        ],
    },
    "prophecy": {
        "image_chance": 0.4,
        "weight": 2,
        "grounded": False,
        "topics": [
            "Gog and Magog",
            "the Dajjal",
            "the mark of the beast in Revelation",
            "algorithmic persuasion and who really chooses what you think",
            "mass data collection and the end of privacy",
            "AI surveillance and the shape of future states",
            "centralized digital infrastructure and single points of control",
            "the WEF",
            "the Kalki prophecy",
        ],
    },
    "geopolitics": {
        "image_chance": 0,
        "weight": 3,
        "grounded": True,
        "topics": [
            "de-dollarization and BRICS",
            "sanctions as a financial weapon",
            "central bank gold buying",
            "oil, shipping lanes and maritime chokepoints",
            "India's strategic position between great powers",
            "the US-China chip and technology war",
            "drones and how modern warfare is changing",
            "global defense spending and the arms trade",
            "sovereign debt and currency wars",
            "rare earths and critical minerals",
            "the Indian Ocean and naval competition",
        ],
    },
    "history": {
        "image_chance": 0.7,
        "weight": 3,
        "grounded": False,
        "topics": [
            "the Roman Republic's slide into Empire",
            "the fall of Western Rome and the barbarian invasions",
            "the Vandals sacking Rome in 455",
            "Hannibal crossing the Alps",
            "Chanakya's Arthashastra and statecraft",
            "Ashoka: from conqueror to renunciant",
            "the Gupta golden age",
            "Chola naval power across Southeast Asia",
            "the Vijayanagara empire",
            "Maratha guerrilla warfare",
            "Alexander and Porus at the Hydaspes",
            "statecraft in the Mahabharata",
            "the Epic of Gilgamesh",
            "the Iliad and the psychology of war",
            "the Shahnameh and Persian kingship",
            "Byzantium: the Rome that survived",
            "the Mongols and the speed of empire",
        ],
    },
    "shayari": {"weight": 2, "card_chance": 1.0},  # from content/shayari.json, posted with a designed card
}

# Weekly self-learning (learn.py). Once a week the bot reads how its own posts did and
# shifts how often each pillar is picked. The guardrails keep the feed a mix:
LEARNING = {
    "enabled": True,
    "every_days": 7,      # how often it re-learns
    "floor": 0.08,        # every pillar keeps at least 8% of posts
    "ceiling": 0.30,      # no pillar gets more than 30% of posts
    "step": 0.5,          # each week, move only halfway toward the new target
    "max_boost": 2.0,     # a pillar can at most double (or halve) its normal weight
    "strength": 1.0,      # how strongly results push the weights
    "min_posts": 3,       # a pillar needs this many measured posts before it is judged
    "prior_posts": 4,     # few posts = mostly luck, so results are trusted gradually
    "half_life_days": 45, # a post from 6 weeks ago counts half as much as one from today
    "lookback_days": 120, # posts older than this are ignored (few posts now, so look further back)
}

FORMATS = [
    "one plain observation, a sentence or two",
    "an honest question you'd actually want answered",
    "one specific fact you find wild, and a short reaction to it",
    "a mildly contrarian opinion with one reason",
    "a short thought, the way you'd text it to a friend",
]

# Phrases that make a tweet read as AI-written. A draft containing any of these is
# thrown away and rewritten (case-insensitive regular expressions).
BANNED_PATTERNS = [
    r"n['’]t just\b", r"\b(isn|wasn|aren|weren)['’]t\b[^.?!]{0,80}[.?!,]\s*(it|they)['’](s|re)\b", r"\bnot just\b", r"\bnot merely\b", r"\bmore than just\b",
    r"\bit['’]s not about\b",
    r"\bdelve", r"\btapestry\b", r"\btestament\b", r"\bprofound", r"\btimeless\b",
    r"\bechoes?\b", r"\bwhispers?\b", r"\brealm\b", r"\bunveil", r"\bquiet revolution\b",
    r"\bhuman condition\b", r"\bin an age of\b", r"\bmodern[- ]day\b", r"\bancient wisdom\b",
    r"^\s*(in a world|ever wondered|here['’]s the thing|imagine|unpopular opinion|what if)\b",
]

# ---------------------------------------------------------------- trending posts
# A second, separate post type that reacts to whatever big story is trending right now
# (crypto hacks, US politics, sports, protests...) and adds trending hashtags at the end.
# It runs on its own schedule next to the normal posts above and never replaces them.
# The bot first reads X's real trending list (see "x_trends" below), then Gemini picks a story
# from it and checks the facts with Google Search (free). If X's list can't be read, Gemini
# finds a trending story with Google Search alone.
# Cost per trending post: about $0.015 for the post + $0.010 per trends list read on X.
# With 2 lists, about $0.035 per post, so about $1.05/month at one post a day.
TRENDING = {
    "enabled": True,
    "every_days": (1, 1),             # one trending post every day (set (2, 2) to slow down later)
    "window": ("13:00", "16:00"),     # afternoon IST, so it usually goes out before the evening post
    "catch_up_until": "23:59",        # GitHub skips many runs, so a missed trending post stays due until midnight
    "max_hashtags": 3,                # hashtags at the end of the tweet (X suggests 1-2; 3 is the cap)
    "skip_recent_topics": 10,
    # X's trending lists to read, by place ID ("WOEID"). Each read costs $0.010 on X.
    # 23424848 = India, 1 = Worldwide, 23424977 = United States. Empty list = don't read X trends.
    "x_trends": [23424848, 1],
    "x_trends_count": 30,             # how many trends to read from each list (max 50)         # don't repeat any of the last 10 trending stories
    "categories": [
        "crypto (hacks, exploits, big market moves, regulation)",
        "US politics and elections",
        "sports (cricket, football, big tournaments and results)",
        "protests and mass movements around the world",
        "big tech and AI news",
        "India's national news and politics",
        "geopolitics, wars and diplomacy",
    ],
    # Stories the bot never touches, because a hashtag post on them looks like cashing in.
    "avoid": [
        "deaths of private people, accidents, disasters or attacks with casualties",
        "communal or religious violence",
        "rumours not confirmed by mainstream news",
        "anything about minors",
    ],
    # Hashtags that are too generic to help; dropped if Gemini suggests them.
    "generic_hashtags": ["news", "breaking", "breakingnews", "trending", "viral", "latest", "update", "india", "world"],
}
