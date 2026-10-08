# X Bot Project: Handoff Summary

Context for any new chat in this project. Last updated 7 Oct 2026.
The bot's code files (`bot.py`, `images.py`, `config.py`, `README.md`, `content/shayari.json`) are uploaded alongside this file and are the source of truth for implementation details.

---

## 1. Who I am

- **X account:** Vashu Vats, about 300 followers. Goal: post consistently without spending daily time on it.
- **Location / audience:** Ghaziabad, India. Hindu, targeting a **North Indian audience**.
- **X bio:** Hacker. Tech | Philosophy | Finance | Bookworm | Armchair philosopher | Finance bro | Conspiracy theorist | Antiquarian | Geostrategist | Har Har Mahadev
- **Tools I have:** a Gemini API key (free tier) and a Claude Pro subscription. Claude Pro does **not** include API access, so the bot uses Gemini.
- **Budget:** wants everything as free as possible.

### My interests (these drive the content)
- **Mind & philosophy:** Jung, Marcus Aurelius, Nietzsche, Alan Watts, Advaita Vedanta, attachment, existentialism, Stoicism, emotional intelligence, neuroplasticity, metacognition, pattern recognition, game theory, "the dangerous art of optimistic delusion", herd mentality, celebrity and sports worship as lack of purpose, "the ultimate reality is the same for all".
- **Ancient mysteries & cycles:** Göbekli Tepe, Egypt, Sumerian and Akkadian texts, Anunnaki, Atlantis, Agartha, Adam & Eve, Manu, Noah, Nephilim, Hopi cycles, Yuga cycles, Mayan calendar, and the repeating civilizational pattern: creation → knowledge → corruption → catastrophe → death and rebirth. Also reptilian and serpent-being legends.
- **Prophecy & surveillance state:** Gog and Magog, Dajjal, the Antichrist, 666, AI, mass data collection, algorithmic persuasion, surveillance tech, centralized infrastructure, the WEF and "NWO" narrative.
- **Geopolitics:** especially the finance side and warfare, current events.
- **History:** big fan of Rome and the barbarian invasions (played a lot of Total War), Indian history and ancient kings, epics from different civilizations.
- **Shayari:** I write shayari and love Jaun Elia and other famous shayars.

---

## 2. What the bot does

Posts to X **twice a day, fully automatically** (no approval step), at a different random time each day:
- once between **9:00–11:00 AM IST**
- once between **7:00–9:30 PM IST**

Each post comes from one of six **content pillars**. The bot rotates through them and never posts the same pillar back to back.

| Pillar | Weight | Image | Notes |
|---|---|---|---|
| mind | 3 | 35% chance, Commons | philosophy and psychology |
| ancient | 3 | 70% chance, Commons | mysteries and cycles |
| prophecy | 2 | 40% chance, Commons | prophecy and surveillance |
| geopolitics | 3 | never | **grounded with Google Search** for the past week's news |
| history | 3 | 70% chance, Commons | Rome, India, epics |
| shayari | 2 | always, designed card | from `content/shayari.json`, not AI-written |

**Language:** English for all AI-written posts. Shayari is in **Hindi (Devanagari) script**, both on the card and in the tweet text.

**Persona rules** (in `config.py`): sharp, contemplative, slightly contrarian, Indian vantage point; at most 260 characters; no hashtags, emojis, links or @mentions; no invented quotes; fringe topics framed as questions, patterns or "what if", never as fact; never blame any ethnic, religious or national group; geopolitics uses only facts from search results, with no investment advice.

---

## 3. Architecture

- **Hosting:** GitHub Actions in a **private** repo, which is free (about 500 of 2,000 free minutes per month).
- **Schedule:** cron checks every 30 minutes around each window (`*/30 3-6 * * *` and `*/30 13-16 * * *` UTC). `bot.py` computes a seeded random target minute per window per day and posts on the first run after it. Duplicate posting is prevented by checking `data/history.json`. Verified in simulation: exactly 60 posts per 30 days.
- **AI:** Gemini via the `google-genai` SDK. Models are tried in order: `gemini-2.5-flash`, then `gemini-2.5-flash-lite`. Geopolitics uses the `google_search` tool, and falls back to a timeless angle if search fails.
- **Quality checks:** X-weighted length ≤ 280; similarity check against the last 40 posts (difflib > 0.6 means regenerate); cleanup strips links, citation markers and markdown; up to 5 retries.
- **Posting:** `tweepy.Client.create_tweet` with OAuth 1.0a user context (API key and secret plus access token and secret, with Read and Write permission).
- **Images:**
  - Shayari cards are drawn with Pillow at 1600×900, with four color palettes and a "Vashu Vats" signature. Fonts are Tiro Devanagari Hindi and Noto Nastaliq Urdu (OFL) in `fonts/`. They need the raqm and fribidi text-shaping libraries; the workflow installs `libfribidi0` if it's missing, and the bot falls back to text-only if shaping is unavailable.
  - Commons images: Gemini suggests a search query, the Wikimedia API keeps **only public-domain or CC0** JPEG/PNG files ≥ 800px, then Gemini (with vision) picks the best candidate or rejects them all. Used images are tracked so they don't repeat.
  - Upload goes through X API v2 `POST https://api.x.com/2/media/upload` (multipart, `media_category=tweet_image`), plus alt text via `POST /2/media/metadata`. If the upload fails, the post goes out as text only.
- **Secrets (GitHub Actions):** `GEMINI_API_KEY`, `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `SCHEDULE_SEED`.
- **Manual runs:** Actions → Post to X → Run workflow, with mode `dry-run` (shows the tweet and saves the image as a downloadable "preview" artifact) or `post-now`.

---

## 4. Costs (checked Oct 2026)

- **X API:** no free tier since 6 Feb 2026; pay-per-use with prepaid credits. About $0.015 per post and $0.20 if the post contains a URL (the bot strips links). Image uploads may add a small charge, and alt text costs $0.005. Expected total: **about $1–1.50/month**.
- **Gemini:** free tier for text and search grounding. Gemini **image generation has no free API tier**, which is one reason we don't use AI images.
- **GitHub Actions:** free.

---

## 5. Decisions made, and why

- **No AI-generated images.** They cost about $2/month, X has a "Made with AI" label (the API has a field for it), and realistic AI war imagery risks manipulated-media enforcement. We chose public-domain Commons images plus shayari cards instead, and not every post has an image.
- **Shayari comes from a curated file, not scraping.** Scraping poetry sites breaks their terms and is fragile.
- **The seeded shayari is public domain only:** Ghalib, Mir, Momin, Dagh, Iqbal ("Saare Jahan Se Achha", 1904) and Kabir, 17 couplets. Jaun Elia, Faiz and other modern poets are still under copyright, so Claude doesn't add their couplets. I can add my own choices to the file myself.
- **Fully automatic posting**, by my choice.
- **No automation that risks the account:** no auto-follow, auto-like, auto-reply to strangers or trending-hashtag posting.

---

## 6. Current status

- Code is built and tested with mocked services (scheduling, cards, license filtering, upload fallback). **Not yet tested live**, since Claude's sandbox couldn't reach Wikimedia or X. The first dry runs on GitHub are the real test.
- A detailed 9-step setup guide was given: unzip → private GitHub repo → upload files (check that `.github/workflows/post.yml` exists) → Gemini key (no billing) → X developer app (Read and write, then generate tokens, then add credits; Indian cards need international transactions enabled) → 6 secrets plus workflow Read and write permission → dry runs → one post-now test → automatic from then on.
- **Open question:** shayari tweet text in Roman Hinglish (with the card staying Devanagari) vs. all Devanagari. Currently all Devanagari.

---

## 7. Improvement roadmap (agreed order)

1. **My voice examples:** I paste 15–20 of my own tweets, and they get added to the persona as examples. Biggest quality boost.
2. **Idea inbox** (`ideas.json`, where I jot rough thoughts and the bot polishes them first) **plus Telegram notifications** for each post.
3. **Self-learning loop:** a weekly read of my own posts' metrics (about $0.001 each), auto-adjusting pillar weights, plus a weekly report.
4. **Polls** (same cost as a post) and a **weekly Sunday thread** (about $0.08–0.10).

Other ideas: a critic/quality pass before posting, calendar-aware posts (Mahashivratri, Navratri, Ghalib's birthday on 27 Dec, Panipat on 14 Jan, solstices), Telegram commands (`/skip`, `/pause`, `/post`), Roman shayari captions.

Note: quote-posting requires X's Enterprise plan and isn't available on pay-per-use.

---

## 8. For Claude in future chats

- Treat the uploaded code files as the current version. When changing them, give back complete updated files plus a zip of the whole repo.
- Keep it cheap: prefer free options and state any added X API cost per post.
- I'm not deeply technical. Give step-by-step instructions with exact button names, and casual English or Hinglish is fine.
- Next likely task: roadmap item 1 (I'll paste my tweets).
