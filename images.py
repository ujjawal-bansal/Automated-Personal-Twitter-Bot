"""
Images for posts:
  - shayari_card(): draws a couplet on a designed card (free, no AI)
  - find_commons_image(): finds a matching public-domain image on Wikimedia Commons
  - upload_to_x(): uploads an image to X and returns its media id
"""
import html
import io
import os
import random
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

import config

FONTS = Path(__file__).parent / "fonts"
DEVANAGARI_FONT = FONTS / "TiroDevanagariHindi-Regular.ttf"
URDU_FONT = FONTS / "NotoNastaliqUrdu.ttf"
UA = {"User-Agent": "VashuVatsXBot/1.0 (personal X bot; github.com)"}
MAX_UPLOAD = 5 * 1024 * 1024

PALETTES = [  # (background top, background bottom, text, accent)
    ((14, 14, 22), (30, 24, 44), (238, 226, 200), (201, 162, 90)),     # midnight + gold
    ((40, 10, 16), (16, 6, 8), (245, 230, 215), (214, 150, 110)),      # maroon
    ((8, 24, 28), (4, 12, 14), (225, 236, 230), (150, 196, 170)),      # deep teal
    ((22, 22, 22), (6, 6, 6), (240, 240, 235), (190, 190, 180)),       # charcoal
]


# ------------------------------------------------------------- shayari card

def can_render_shayari():
    """Devanagari/Urdu need the raqm text-shaping library, or the letters render broken."""
    return features.check("raqm") and DEVANAGARI_FONT.exists()


def _font_for(text, size):
    is_urdu = bool(re.search(r"[\u0600-\u06FF]", text))
    path = URDU_FONT if is_urdu and URDU_FONT.exists() else DEVANAGARI_FONT
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


def shayari_card(text, poet, size=(1600, 900)):
    """Returns JPEG bytes of a card showing the couplet and the poet's name."""
    W, H = size
    top, bottom, ink, accent = random.choice(PALETTES)

    # vertical gradient + soft vignette
    bg = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        bg.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img = bg.resize((W, H))
    vignette = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vignette).ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(160))
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), vignette)
    d = ImageDraw.Draw(img)

    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    max_w = W * 0.82
    fsize = 76
    while fsize > 30:
        font = _font_for(text, fsize)
        if all(d.textlength(l, font=font) <= max_w for l in lines):
            break
        fsize -= 2
    is_urdu = bool(re.search(r"[\u0600-\u06FF]", text))
    line_h = int(fsize * (2.5 if is_urdu else 1.9))
    poet_font = _font_for(poet, int(fsize * 0.55))
    sig_font = _font_for(config.CARD_SIGNATURE, 26)

    block_h = line_h * len(lines) + int(fsize * 1.6)
    y = (H - block_h) // 2 + int(fsize * 0.3)
    for l in lines:
        d.text((W / 2, y + line_h / 2), l, font=font, fill=ink, anchor="mm")
        y += line_h

    # divider + poet
    y += int(fsize * (0.6 if is_urdu else 0.35))
    d.line((W / 2 - 60, y, W / 2 + 60, y), fill=accent, width=2)
    d.text((W / 2, y + int(fsize * 0.75)), poet, font=poet_font, fill=accent, anchor="mm")

    # corner ornaments + signature
    for x0, y0, sx, sy in ((40, 40, 1, 1), (W - 40, 40, -1, 1), (40, H - 40, 1, -1), (W - 40, H - 40, -1, -1)):
        d.line((x0, y0, x0 + 70 * sx, y0), fill=accent, width=2)
        d.line((x0, y0, x0, y0 + 70 * sy), fill=accent, width=2)
    d.text((W / 2, H - 58), config.CARD_SIGNATURE, font=sig_font, fill=accent, anchor="mm")

    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


# ------------------------------------------------------------- Wikimedia Commons

def _plain(s):
    text = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([,.;:!?])", r"\1", text).strip()


def _is_public_domain(meta):
    lic = meta.get("License", {}).get("value", "").lower()
    short = meta.get("LicenseShortName", {}).get("value", "").lower()
    return lic.startswith("pd") or lic == "cc0" or "public domain" in short or short.startswith("cc0")


def commons_candidates(query, used_titles=(), limit=6):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 1600,
    }
    r = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=UA, timeout=20)
    r.raise_for_status()
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))

    out = []
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        if p["title"] in used_titles or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if info.get("width", 0) < 800 or not _is_public_domain(meta):
            continue
        desc = _plain(meta.get("ImageDescription", {}).get("value", ""))[:300]
        out.append({"title": p["title"], "url": info.get("thumburl") or info["url"],
                    "page": info.get("descriptionurl"), "description": desc})
        if len(out) >= limit:
            break
    return out


def download_jpeg(url, max_side=1600):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


def pick_best(tweet, candidates):
    """Shows Gemini the candidate images and the tweet; returns the best match or None."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts = [f"Tweet: {tweet}\n\nBelow are candidate images. Pick the one that best fits the tweet "
             "as an illustration. Reject scanned text pages, maps with tiny labels, blurry images, "
             "modern snapshots of unrelated things, and anything that would look out of place. "
             "Answer only <choice>N</choice> with the image number, or <choice>NONE</choice>."]
    shown = []
    for c in candidates:
        try:
            c["bytes"] = download_jpeg(c["url"])
        except Exception as e:
            print(f"  skip {c['title']}: {e}")
            continue
        small = Image.open(io.BytesIO(c["bytes"]))
        small.thumbnail((512, 512))
        buf = io.BytesIO()
        small.save(buf, "JPEG", quality=80)
        shown.append(c)
        parts += [f"Image {len(shown)}: {c['title']} — {c['description']}",
                  types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")]
    if not shown:
        return None

    for model in config.GEMINI_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=parts)
            m = re.search(r"<choice>\s*(\d+|NONE)\s*</choice>", resp.text or "", re.I)
            if not m or m.group(1).upper() == "NONE":
                return None
            i = int(m.group(1)) - 1
            return shown[i] if 0 <= i < len(shown) else None
        except Exception as e:
            print(f"  image pick with {model} failed: {e}")
    return None


def find_commons_image(query, tweet, used_titles=()):
    try:
        candidates = commons_candidates(query, used_titles)
        print(f"Commons: {len(candidates)} public-domain candidates for '{query}'.")
        return pick_best(tweet, candidates) if candidates else None
    except Exception as e:
        print(f"Commons search failed: {e}")
        return None


# ------------------------------------------------------------- X upload

def _oauth():
    from requests_oauthlib import OAuth1
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_TOKEN_SECRET"])


def upload_to_x(jpeg_bytes, alt_text=None):
    if len(jpeg_bytes) > MAX_UPLOAD:
        raise ValueError("image larger than 5 MB")
    auth = _oauth()
    r = requests.post("https://api.x.com/2/media/upload", auth=auth, timeout=60,
                      files={"media": ("image.jpg", jpeg_bytes, "image/jpeg")},
                      data={"media_category": "tweet_image"})
    if r.status_code >= 300:
        raise RuntimeError(f"media upload failed {r.status_code}: {r.text[:300]}")
    media_id = r.json()["data"]["id"]
    if alt_text:  # accessibility; costs a fraction of a cent, so failures are ignored
        try:
            requests.post("https://api.x.com/2/media/metadata", auth=auth, timeout=30,
                          json={"id": media_id, "metadata": {"alt_text": {"text": alt_text[:1000]}}})
        except Exception as e:
            print(f"alt text failed (ignored): {e}")
    return media_id
