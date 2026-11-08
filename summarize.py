"""Turn a cluster of headlines into a Telugu card + caption using Claude.

Claude only sees headlines (not article bodies), and is told to add nothing
that is not in them. It also flags stories that should not be auto-posted.
"""
import json
import re
import time

import requests

from config import (ANTHROPIC_API_KEY, CLAUDE_MODEL, GEMINI_API_KEY, GEMINI_MODEL,
                    LLM_PROVIDER)

CATEGORIES = ["politics", "india", "world", "business", "tech", "sports",
              "entertainment", "science", "local", "general"]

SYSTEM = """You are the night-desk editor of a Telugu news channel on Instagram.
You receive several headlines (from different outlets) about ONE event.

Rules:
- Use ONLY facts present in the headlines. Never invent numbers, names, quotes,
  causes, locations or outcomes. If the headlines disagree, keep to what they agree on.
- Write natural, neutral Telugu in a news tone. Do not copy any outlet's wording;
  rewrite in your own words. Do not mention outlet names in the text.
- Use "రూ." instead of the rupee symbol. Use only plain punctuation (. , : ? ! - ).
- Set "sensitive": true if the story involves any of: deaths or violence, accidents
  with casualties, crimes against women or children, communal/religious tension,
  active elections or party-political attacks, unverified allegations against a named
  person, health scares, or anything where a mistake could cause real harm.
- Set "skip": true if the headlines are too vague, clickbait, a rumour, an advert,
  or you cannot summarise them faithfully.

Return ONLY a JSON object, no prose, with keys:
skip (bool), skip_reason (string),
sensitive (bool),
category (one of: %s),
headline_te (max 14 words),
summary_te (25 to 40 words, 2 short sentences),
caption_te (2-3 sentences for the Instagram caption, ending with a line inviting people to follow),
hashtags (list of 6-8 strings without '#', mix of Telugu and English).
""" % ", ".join(CATEGORIES)


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def telugu_ratio(s: str) -> float:
    letters = [c for c in s if not c.isspace() and c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if 0x0C00 <= ord(c) <= 0x0C7F) / len(letters)


def _generate(prompt: str) -> str:
    """Call the configured LLM and return its raw text reply."""
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
        }
        for attempt in range(3):  # free tier rate-limits (429); wait and retry
            r = requests.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=90)
            if r.status_code == 429 and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            break
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini API {r.status_code}: {r.text[:300]}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    import anthropic

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1200, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def make_card(cluster) -> dict:
    lines = [f"- {i.title}  [{i.source}]" for i in cluster.items[:8]]
    raw = _generate("Headlines:\n" + "\n".join(lines))
    card = _extract_json(raw)

    if card.get("skip"):
        return card
    for key in ("headline_te", "summary_te", "caption_te"):
        if not card.get(key):
            raise ValueError(f"missing {key}")
    if telugu_ratio(card["headline_te"]) < 0.6 or telugu_ratio(card["summary_te"]) < 0.6:
        raise ValueError("output is not predominantly Telugu")
    if card.get("category") not in CATEGORIES:
        card["category"] = "general"
    card["hashtags"] = [h.lstrip("#").replace(" ", "") for h in card.get("hashtags", [])][:8]
    return card
