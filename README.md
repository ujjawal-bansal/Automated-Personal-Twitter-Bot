# Vashu's X Bot

Posts three times a day at random times (once between 9:00–11:00 AM IST, once between 1:00–3:00 PM IST, once between 7:00–9:30 PM IST).
Each post is either an AI-written tweet from one of five themes (mind, ancient mysteries, prophecy and surveillance, geopolitics, history) or a classic shayari from `content/shayari.json`.

**Images (no AI images, nothing to label):**
- Every shayari goes out with a designed card: the couplet in Devanagari (or Urdu Nastaliq) on a dark background, with the poet's name.
- History, ancient mysteries, philosophy and prophecy posts *sometimes* get a real **public-domain** image from Wikimedia Commons (a sculpture, manuscript, painting, or site photo). Gemini suggests a search, the bot keeps only public-domain/CC0 results, then Gemini looks at the candidates and picks the best one, or none. If nothing fits, the post goes out as text.
- Geopolitics posts stay text-only.

Runs on GitHub Actions. No server, no laptop needs to stay on.

## What it costs

| Piece | Cost |
|---|---|
| GitHub Actions | Free. About 750 of the 2,000 free minutes per month, even for a private repo |
| Gemini API | Free tier, including Google Search for the geopolitics posts |
| X API | Pay-per-use, about $0.015 per post. Image posts may cost a little more (the upload may be billed separately, plus $0.005 for alt text). Expect roughly **$1.50–2.50/month** at 3 posts a day. Posts with links cost $0.20 each, so the bot strips links |
| Images | Free. Cards are drawn by the code; Commons images are public domain |

## Setup (about 20 minutes)

### 1. Create the repo
1. Make a **private** repository on GitHub, for example `x-bot`.
2. Upload every file from this folder, keeping the structure. The `.github/workflows/post.yml` file is the important one. Some computers hide folders that start with a dot, so if it doesn't upload, use **Add file → Create new file**, type `.github/workflows/post.yml` as the name, and paste the contents.

### 2. Get a Gemini API key
Go to https://aistudio.google.com, click **Get API key**, and copy it.

### 3. Get X API keys
1. Go to https://developer.x.com and sign in **as your Vashu Vats account**.
2. Create a Project and an App.
3. In the app, open **User authentication settings → Set up**:
   - App permissions: **Read and write**
   - Type of App: **Web App, Automated App or Bot**
   - Callback URL / Website: any valid URL, for example your X profile URL. It isn't used.
4. Open **Keys and tokens** and copy:
   - API Key and API Key Secret
   - Access Token and Access Token Secret. Generate these *after* step 3, otherwise they are read-only. If you generated them earlier, click **Regenerate**.
5. In the developer console's billing section, add a small credit balance (a few dollars lasts months).

### 4. Add the secrets to GitHub
Repo → **Settings → Secrets and variables → Actions → New repository secret**. Add these six:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | from step 2 |
| `X_API_KEY` | API Key |
| `X_API_SECRET` | API Key Secret |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |
| `SCHEDULE_SEED` | any random word. It makes your posting times unpredictable |

Then check **Settings → Actions → General → Workflow permissions** and choose **Read and write permissions**, so the bot can save its post history.

### 5. Test it
1. Open the **Actions** tab → **Post to X** → **Run workflow** → mode **dry-run**.
2. Open the run and read the log. You'll see the tweet it *would* have posted. If it chose an image, scroll to the bottom of the run page and download the **preview** artifact to see it. Run it a few times to get a feel for the voice.
3. When you're happy, run it once with **post-now** to confirm posting works.

After that, it runs by itself. If a run ever fails, GitHub emails you.

## Making it yours

- **Voice, topics, schedule:** everything lives in `config.py`. Add or remove topics, change how often each theme appears (`weight`), or edit the persona rules.
- **Shayari:** add entries to `content/shayari.json` in this format:
  ```json
  {"poet": "मिर्ज़ा ग़ालिब", "text": "first line\nsecond line"}
  ```
  The bot posts each one once before repeating, always with the poet's name and a card. Urdu-script couplets work too.
- **Images:** in `config.py`, each pillar's `image_chance` (0 to 1) controls how often it tries to attach an image. Set it to 0 to turn images off for that pillar. `card_chance` does the same for shayari cards, and `CARD_SIGNATURE` is the name in the card's footer.
- **Change posting times:** edit `WINDOWS` in `config.py` *and* the three `cron` lines in `post.yml`. Cron uses UTC, which is IST minus 5:30.
- **Pause the bot:** Actions tab → Post to X → **⋯ → Disable workflow**.
- **See what was posted:** `data/history.json`.

## Running it on your own computer (optional)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...          # on Windows PowerShell: $env:GEMINI_API_KEY="..."
python bot.py --dry-run --force    # generates a tweet without posting
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `401` / `403` from X | Tokens were made before Read and write was enabled. Regenerate the Access Token and Secret and update the secrets |
| `402` from X | Out of X credits. Top up in the developer console |
| `429` from Gemini | Free-tier rate limit. The next 30-minute run retries automatically |
| Gemini model not found | Google retired a model. Update `GEMINI_MODELS` in `config.py` with a current Flash model name from AI Studio |
| Shayari posted without a card | The log says text shaping is unavailable. The workflow installs it automatically; if it still fails, the post just goes out as text |
| `Image upload failed` in the log | The post still went out, text only. If it keeps happening, check that your X app has Read and write permission |
| Scheduled runs stopped | GitHub pauses schedules in repos with no activity for 60 days. The bot's history commits normally prevent this; if it happens, re-enable the workflow in the Actions tab |

## Credits

Fonts in `fonts/`: Tiro Devanagari Hindi and Noto Nastaliq Urdu, both under the SIL Open Font License (license files included).
