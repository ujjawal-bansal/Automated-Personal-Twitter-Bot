# Automated Personal Twitter Bot

A self-running X (Twitter) bot that writes and posts tweets in one person's voice. It uses Google Gemini to write the tweets, makes its own Hindi/Urdu shayari cards, picks public-domain images from Wikimedia Commons and reacts to trending stories. Once a week it looks at how its posts did and shifts what it posts toward what works.

It runs entirely on **GitHub Actions**. There is no server, and no laptop has to stay on.

---

## Features

- **Tweets in a persona's voice.** Gemini writes one tweet at a time from a detailed persona and a set of content pillars: *mind & philosophy*, *ancient mysteries*, *prophecy & surveillance*, *geopolitics* and *history*. Geopolitics posts are checked against Google Search results first.
- **Anti-"AI voice" filter.** Every draft is checked against a list of phrases that make writing sound machine-made (`BANNED_PATTERNS`). A draft that trips the filter is thrown away and rewritten, and so is one too similar to a recent post.
- **Shayari cards.** Classic couplets from `content/shayari.json` are posted with a designed image card, drawn in Devanagari or Urdu Nastaliq with Pillow, with the poet's name.
- **Real images, never AI images.** Some posts get a **public-domain** image from Wikimedia Commons. Gemini suggests a search, the bot keeps only public-domain/CC0 results, and Gemini then picks the best match or none.
- **Trending posts.** Once a day the bot reads X's live trending lists (India and Worldwide). Gemini picks a real story, checks the facts with Google Search and writes a tweet with up to 3 relevant hashtags. Deaths, disasters, communal violence and rumours are skipped.
- **Human-like schedule.** It posts every 3–4 days at a random time inside an evening window, plus one trending post a day in an afternoon window. If GitHub skips a scheduled run, the missed post goes out on the next run, and the bot never posts twice for the same slot.
- **Weekly self-learning.** The bot reads its own posts' metrics (views, likes, replies, reposts, bookmarks) and adjusts how often each pillar is picked, within limits so the feed stays a mix.
- **Cheap to run.** GitHub Actions and the Gemini free tier cover almost everything. X's pay-per-use API costs about a dollar a month.

## How it works

```
GitHub Actions (cron / cron-job.org / manual)
        │
        ▼
     bot.py ── is a post due? (config.WINDOWS, POST_EVERY_DAYS, TRENDING) ── no ──▶ exit
        │ yes
        ├─▶ choose a pillar (weights from data/weights.json, learned weekly)
        ├─▶ Gemini writes the tweet  ──▶ AI-phrase + similarity checks (rewrite if needed)
        ├─▶ images.py: shayari card or Wikimedia Commons image (optional)
        ├─▶ post to X (tweepy)
        └─▶ save to data/history.json ── committed back to the repo by the workflow

learn.py (weekly) ── reads post metrics from X ──▶ data/weights.json + data/report.md
```

## Tech stack

| Area | Tools |
|---|---|
| Language | Python 3.12 |
| Text generation | Google Gemini (`google-genai`), with Google Search grounding |
| X / Twitter | `tweepy`, `requests-oauthlib` (X API v2 + media upload) |
| Images | `Pillow` with `libraqm` / `libfribidi` for Hindi & Urdu text shaping |
| Image source | Wikimedia Commons API (public-domain / CC0 only) |
| Scheduling & hosting | GitHub Actions, optionally triggered by cron-job.org |

## Project structure

```
.
├── bot.py                    # Main entry: scheduling, generation, checks, posting
├── config.py                 # Persona, pillars, topics, schedule, models, trending + learning settings
├── images.py                 # Shayari cards, Wikimedia Commons search, X media upload
├── learn.py                  # Weekly self-learning: metrics → pillar weights + report
├── content/shayari.json      # Couplets the bot posts with cards
├── data/
│   ├── history.json          # Everything the bot has posted (written by the bot)
│   ├── weights.json          # Learned pillar weights
│   └── report.md             # Latest weekly performance report
├── fonts/                    # Tiro Devanagari Hindi, Noto Nastaliq Urdu (SIL OFL)
├── .github/workflows/post.yml# Scheduled + manual GitHub Actions workflow
├── run_local.sh              # Helper to run the bot on your own machine
├── .env.example              # Template for local environment variables
└── requirements.txt
```

## Setup

### 1. Get API keys

- **Gemini:** create a key at [Google AI Studio](https://aistudio.google.com).
- **X:** on [developer.x.com](https://developer.x.com), create a Project and an App and set its permissions to **Read and write**. Then generate the API Key/Secret and an Access Token/Secret. Generate the access token *after* turning on Read and write, or it will be read-only. Add a small credit balance for pay-per-use.

### 2. Add GitHub secrets

In the repo, go to **Settings → Secrets and variables → Actions** and add:

| Secret | What it is |
|---|---|
| `GEMINI_API_KEY` | Gemini API key |
| `X_API_KEY` | X API Key |
| `X_API_SECRET` | X API Key Secret |
| `X_ACCESS_TOKEN` | X Access Token |
| `X_ACCESS_TOKEN_SECRET` | X Access Token Secret |
| `SCHEDULE_SEED` | Any random word. It makes the posting times unpredictable |

Then set **Settings → Actions → General → Workflow permissions** to **Read and write**, so the bot can commit its post history.

### 3. Run it from GitHub

Go to **Actions → Post to X → Run workflow** and pick a mode:

| Mode | What it does |
|---|---|
| `dry-run` | Writes a normal tweet and shows it in the log without posting. Any image is saved as the `preview` artifact |
| `post-now` | Posts a normal tweet right away |
| `trending-dry-run` | Writes a trending tweet without posting |
| `trending-now` | Posts a trending tweet right away |
| `learn-now` | Re-runs the weekly learning step and updates the report and weights |
| `auto` | Same as a scheduled run: posts only if a slot is due |

After that the workflow runs by itself on its cron schedule.

### 4. Run it locally (optional)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in your keys; .env is gitignored
./run_local.sh              # dry run: write a normal tweet, don't post
./run_local.sh trending     # dry run: write a trending tweet
./run_local.sh post-now     # really post a normal tweet
./run_local.sh trending-now # really post a trending tweet
./run_local.sh auto         # behave like a scheduled run
```

Hindi/Urdu cards need the system libraries `libraqm` and `libfribidi`. On macOS, install them with Homebrew (`brew install libraqm`). The script points Python to `/opt/homebrew/lib`.

You can also call the bot directly: `python bot.py --dry-run --force [--trending]`.

## Configuration

All tuning happens in `config.py`. You don't need to edit `bot.py`.

| Setting | Controls |
|---|---|
| `PERSONA` | The voice and hard rules for every tweet |
| `PILLARS` | Themes, topics, relative `weight`, Google Search grounding and `image_chance` |
| `POST_EVERY_DAYS`, `WINDOWS`, `MIN_GAP_MINUTES` | How often and when normal posts go out (IST) |
| `TRENDING` | Trending posts: on/off, X trend locations, blocked story types, hashtag rules |
| `LEARNING` | Weekly learning: on/off, floor/ceiling share per pillar, minimum posts before judging |
| `BANNED_PATTERNS` | Regexes for phrases that sound AI-written |
| `GEMINI_MODELS` | Gemini models, tried in order |
| `CARD_SIGNATURE` | Name shown on shayari cards |

To add shayari, add entries to `content/shayari.json`:

```json
{"poet": "मिर्ज़ा ग़ालिब", "text": "first line\nsecond line"}
```

## Reliable timing with cron-job.org

GitHub's free scheduler often skips runs. To make the timing dependable, a free [cron-job.org](https://cron-job.org) job can start the workflow every 30 minutes with mode `auto`. Extra runs never cause double posts.

- **URL:** `https://api.github.com/repos/<owner>/<repo>/actions/workflows/post.yml/dispatches` (method `POST`)
- **Headers:** `Authorization: Bearer <fine-grained token with Actions read/write on this repo>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
- **Body:** `{"ref":"main","inputs":{"mode":"auto"}}`

## Weekly self-learning

`learn.py` reads each post's metrics once, about two days after it goes out. It scores each pillar and moves the posting shares **halfway** toward the new target. Every pillar keeps between 8% and 30% of posts, a pillar needs at least 3 measured posts before it is judged, and one viral post can't carry a whole pillar. The results go to `data/report.md`.

## Running costs (approx.)

| Piece | Cost |
|---|---|
| GitHub Actions | Free tier |
| Gemini API | Free tier (including Google Search) |
| X API, normal posts | About $0.015 per post, roughly $0.15–0.25/month |
| X API, trending posts | About $1/month (one post plus two trend-list reads a day) |
| Weekly learning | About $0.10/month |

## Troubleshooting

| Problem | Fix |
|---|---|
| `401` / `403` from X | Access token was created before Read and write was on. Regenerate it and update the secrets |
| `402` from X | Out of X API credits. Top up in the developer console |
| `429` from Gemini | Free-tier rate limit. The next run retries |
| Gemini "model not found" | Google retired a model. Update `GEMINI_MODELS` in `config.py` |
| Shayari posted without a card | Text-shaping libraries are missing. The post still goes out as text |
| Scheduled runs stopped | GitHub pauses schedules after 60 days without activity. Re-enable the workflow |

## Credits

Fonts: [Tiro Devanagari Hindi](fonts/OFL-TiroDevanagariHindi.txt) and [Noto Nastaliq Urdu](fonts/OFL-NotoNastaliqUrdu.txt), both under the SIL Open Font License.
