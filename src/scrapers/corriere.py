import feedparser
from src.config import FEED_URLS

def get_top_story() -> dict:
    feed = feedparser.parse(FEED_URLS["Corriere"])
    entry = feed.entries[0]

    return {
        "fonte": "Corriere Della Sera",
        "titolo": entry.get("title"),
        "link": entry.get("links", [{}])[0].get("href"),
        "summary": entry.get("summary"),
        "autore": entry.get("authors", [{}])[0].get("name"),
        "pubblicato": entry.get("published"),
    }