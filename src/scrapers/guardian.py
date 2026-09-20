import feedparser
from src.config import FEED_URLS


def get_top_story() -> dict:
    feed = feedparser.parse(FEED_URLS["Guardian"])
    entry = feed.entries[0]

    return {
        "fonte": "The Guardian",
        "titolo": entry.get("title"),
        "link": entry.get("links", [{}])[0].get("href"),
        "summary": (entry.get("summary") or entry.get("description") or "").strip(),
        "autore": entry.get("authors", [{}])[0].get("name"),
        "pubblicato": entry.get("published"),
        "link": entry.get("link", "").strip()
    }