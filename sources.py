"""Fetch Telugu headlines + trend signals and group them into stories.

Feeds are Google News (Telugu edition) topic feeds plus Google Trends India.
Add or remove URLs in FEEDS freely, e.g. direct RSS feeds of Telugu outlets.
"""
import hashlib
import re
import time
from dataclasses import dataclass, field

import feedparser
import requests

from config import MAX_STORY_AGE_HOURS

UA = "TeluguNewsBot/1.0 (+personal news summarizer)"
GN = "https://news.google.com/rss"
TAIL = "hl=te&gl=IN&ceid=IN:te"

FEEDS = {
    "top": f"{GN}?{TAIL}",
    "nation": f"{GN}/headlines/section/topic/NATION?{TAIL}",
    "world": f"{GN}/headlines/section/topic/WORLD?{TAIL}",
    "business": f"{GN}/headlines/section/topic/BUSINESS?{TAIL}",
    "tech": f"{GN}/headlines/section/topic/TECHNOLOGY?{TAIL}",
    "entertainment": f"{GN}/headlines/section/topic/ENTERTAINMENT?{TAIL}",
    "sports": f"{GN}/headlines/section/topic/SPORTS?{TAIL}",
    "science": f"{GN}/headlines/section/topic/SCIENCE?{TAIL}",
}
TRENDS_URL = "https://trends.google.com/trending/rss?geo=IN"


@dataclass
class Item:
    title: str
    source: str
    link: str
    published: float
    feed: str
    rank: int


@dataclass
class Cluster:
    items: list = field(default_factory=list)
    stems: set = field(default_factory=set)
    score: float = 0.0

    @property
    def sources(self):
        seen, out = set(), []
        for it in self.items:
            if it.source and it.source not in seen:
                seen.add(it.source)
                out.append(it.source)
        return out

    @property
    def n_sources(self):
        return len(self.sources)

    @property
    def rep(self):
        return self.items[0]

    @property
    def fingerprint(self):
        return hashlib.sha1(" ".join(sorted(self.stems)[:10]).encode()).hexdigest()[:16]


def stems_of(text: str) -> set:
    toks = re.findall(r"[ఀ-౿]+|[A-Za-z0-9]+", text.lower())
    return {t[:5] for t in toks if len(t) > 2}


def _get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return feedparser.parse(r.content)


def fetch_items() -> list:
    items = []
    for name, url in FEEDS.items():
        try:
            feed = _get(url)
        except Exception as e:  # one bad feed must not stop the run
            print(f"[sources] {name} failed: {e}")
            continue
        for rank, e in enumerate(feed.entries):
            title = e.get("title", "").strip()
            src = (e.get("source") or {}).get("title", "")
            if not src and " - " in title:
                title, src = title.rsplit(" - ", 1)
            elif src and title.endswith(f" - {src}"):
                title = title[: -len(src) - 3]
            ts = time.mktime(e.published_parsed) if e.get("published_parsed") else time.time()
            items.append(Item(title, src.strip(), e.get("link", ""), ts, name, rank))
    return items


def fetch_trends() -> list:
    try:
        feed = _get(TRENDS_URL)
        return [e.get("title", "").lower() for e in feed.entries]
    except Exception as e:
        print(f"[sources] trends failed: {e}")
        return []


def build_clusters() -> list:
    items = fetch_items()
    trends = fetch_trends()
    now = time.time()
    items = [i for i in items if now - i.published < MAX_STORY_AGE_HOURS * 3600 and i.title]
    items.sort(key=lambda i: i.rank)

    clusters = []
    for it in items:
        s = stems_of(it.title)
        if len(s) < 2:
            continue
        for c in clusters:
            inter = len(s & c.stems)
            if inter >= 3 or inter / len(s | c.stems) >= 0.35:
                c.items.append(it)
                c.stems |= s
                break
        else:
            clusters.append(Cluster(items=[it], stems=set(s)))

    for c in clusters:
        text = " ".join(i.title for i in c.items).lower()
        trend_hit = any(t and t in text for t in trends)
        freshest = max(i.published for i in c.items)
        fresh_bonus = 2 if now - freshest < 6 * 3600 else 0
        best_rank = min(i.rank for i in c.items)
        c.score = c.n_sources * 3 + max(0, 5 - best_rank / 4) + fresh_bonus + (3 if trend_hit else 0)
    clusters.sort(key=lambda c: c.score, reverse=True)
    return clusters
