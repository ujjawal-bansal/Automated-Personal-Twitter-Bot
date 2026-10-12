"""
Edit this file to change the bot's voice, topics and schedule.
Everything else (bot.py) can stay untouched.
"""

TIMEZONE = "Asia/Kolkata"

# Posting windows in local time. Every day the bot picks a random minute inside
# each window, so posts never land at the same time twice.
# If you change these, also update the cron lines in .github/workflows/post.yml (UTC).
WINDOWS = {
    "morning": ("09:00", "11:00"),
    "afternoon": ("13:00", "15:00"),
    "evening": ("19:00", "21:30"),
}
GRACE_MINUTES = 100  # a delayed GitHub run may still post this long after a window ends

# Small signature in the corner of shayari cards.
CARD_SIGNATURE = "Vashu Vats"

# Tried in order. Free-tier friendly Flash models first.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

PERSONA = """You write tweets for Vashu Vats, an Indian thinker on X.
His bio: Hacker. Tech | Philosophy | Finance. Bookworm, armchair philosopher, finance bro,
conspiracy theorist, antiquarian, geostrategist. Har Har Mahadev.

Voice:
- Sharp, contemplative, a little contrarian. A well-read person thinking out loud, not a brand or a motivational page.
- Connects ideas across fields: Stoicism with game theory, Yuga cycles with the fall of Rome, prophecy with mass surveillance.
- Indian vantage point: draws on Advaita Vedanta, the epics and Indian history alongside Western thought.
- Plain modern English. Short sentences. Concrete images over abstractions.

Hard rules:
- One tweet only, at most 260 characters.
- No hashtags, no emojis, no links, no @mentions.
- Never open with "In a world", "Ever wondered", "Here's the thing", "Imagine", "Unpopular opinion" or "Let that sink in".
- Never invent quotes. Only quote someone if you are certain of the exact wording; otherwise paraphrase without quotation marks.
- Ancient mysteries, prophecy and conspiracy themes: present them as patterns, questions or "what if" observations, never as proven fact.
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
            "Stoicism applied to modern anxiety",
            "emotional intelligence as an unfair advantage",
            "neuroplasticity: you become what you repeat",
            "metacognition: thinking about your own thinking",
            "pattern recognition as a survival skill",
            "game theory in everyday life and relationships",
            "the dangerous art of optimistic delusion",
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
            "flood myths: Manu, Noah, Utnapishtim",
            "the Yuga cycles and where we are in Kali Yuga",
            "Hopi world cycles and the Mayan calendar",
            "the Nephilim in Genesis and the Book of Enoch",
            "the repeating pattern: creation, knowledge, corruption, catastrophe, rebirth",
            "first-human myths: Adam and Eve, Manu, and others compared",
            "serpent beings across cultures: Nagas, reptilian legends, the Garden serpent",
        ],
    },
    "prophecy": {
        "image_chance": 0.4,
        "weight": 2,
        "grounded": False,
        "topics": [
            "Gog and Magog across Biblical and Islamic tradition",
            "the Dajjal and the Antichrist as archetypes of deception",
            "666 and the mark of the beast versus digital ID",
            "algorithmic persuasion and who really chooses what you think",
            "mass data collection and the end of privacy",
            "AI surveillance and the shape of future states",
            "centralized digital infrastructure and single points of control",
            "the WEF and the 'NWO' narrative: why it resonates",
            "signs of Kali Yuga in modern technology",
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
            "Goths, Huns and Vandals: the outsiders who toppled an empire",
            "grand strategy lessons from the Total War era of history",
            "Chanakya's Arthashastra and statecraft",
            "Ashoka: from conqueror to renunciant",
            "the Gupta golden age",
            "Chola naval power across Southeast Asia",
            "the Vijayanagara empire",
            "Maratha guerrilla warfare",
            "Alexander and Porus at the Hydaspes",
            "the Mahabharata and Ramayana as political texts",
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
    "half_life_days": 14, # a post from 2 weeks ago counts half as much as one from today
}

FORMATS = [
    "a single sharp one-liner",
    "a question that makes people stop scrolling",
    "a short observation connecting two seemingly unrelated ideas",
    "a contrarian take with one line of reasoning",
    "a lesson from the past applied to today",
    "a two-line then-versus-now contrast",
]
