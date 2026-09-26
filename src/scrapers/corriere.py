import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    CORRIERE_FIRST_LINK_SELECTOR,
    CORRIERE_SECTION_URL,
    HEADERS,
    REQUEST_TIMEOUT,
)

logger = get_logger(__name__)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def _get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _meta(soup, *names):
    """Legge il primo meta tag trovato tra property e name."""
    for nome in names:
        tag = soup.find("meta", attrs={"property": nome}) or soup.find(
            "meta", attrs={"name": nome}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _autore_da_jsonld(soup):
    """Fallback: cerca l'autore nei blocchi JSON-LD della pagina."""

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue

        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            autore = item.get("author")
            if not autore:
                continue
            autore = autore[0] if isinstance(autore, list) else autore
            nome = autore.get("name") if isinstance(autore, dict) else autore
            if nome:
                return str(nome).strip()

    return ""


def _parse_iso(value):
    """Data ISO -> datetime timezone-aware, oppure None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _estrai_data(soup):
    """Cerca la data di pubblicazione con più strategie, in ordine."""

    # 1. Meta tag
    data_str = _meta(
        soup,
        "article:published_time",
        "article:modified_time",
        "og:article:published_time",
        "datePublished",
    )
    if data_str:
        return data_str

    # 2. JSON-LD (datePublished)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in list(items):
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                items.extend(item["@graph"])

        for item in items:
            if isinstance(item, dict) and item.get("datePublished"):
                return str(item["datePublished"])

    # 3. Tag <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return time_tag["datetime"].strip()

    return ""


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_top_story():
    """Restituisce il primo articolo della sezione Tecnologia del Corriere."""

    soup_sezione = _get_soup(CORRIERE_SECTION_URL)

    primo_link = soup_sezione.select_one(CORRIERE_FIRST_LINK_SELECTOR)
    if not primo_link or not primo_link.get("href"):
        logger.warning("Corriere: nessun link a un articolo trovato in sezione")
        return None

    article_url = urljoin(CORRIERE_SECTION_URL, primo_link["href"])

    try:
        soup_articolo = _get_soup(article_url)
    except requests.RequestException as e:
        logger.warning(f"Corriere: impossibile aprire {article_url} - {e}")
        return None

    titolo = _meta(soup_articolo, "og:title", "twitter:title")
    if not titolo and soup_articolo.title and soup_articolo.title.string:
        titolo = soup_articolo.title.string.strip()

    if not titolo:
        logger.warning(f"Corriere: articolo senza titolo, scartato ({article_url})")
        return None

    sommario = _meta(soup_articolo, "og:description", "description")
    autore = _meta(soup_articolo, "author", "article:author") or _autore_da_jsonld(
        soup_articolo
    )

    data_parsata = _parse_iso(_estrai_data(soup_articolo))
    pubblicato = data_parsata.strftime("%d/%m/%Y") if data_parsata else ""

    return {
        "titolo": titolo,
        "sommario": sommario,
        "autore": autore,
        "pubblicato": pubblicato,
        "link": article_url,
    }


if __name__ == "__main__":
    articolo = get_top_story()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("AUTORE:", articolo["autore"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")