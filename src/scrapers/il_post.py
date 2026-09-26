import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    HEADERS,
    IL_POST_FIRST_LINK_SELECTOR,
    IL_POST_SECTION_URL,
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


def _nodo_articolo_jsonld(soup):
    """Trova il nodo JSON-LD di tipo Article/NewsArticle/BlogPosting,
    appiattendo anche eventuali blocchi organizzati con '@graph'."""

    tipi_validi = {"Article", "NewsArticle", "BlogPosting", "ReportageNewsArticle"}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, json.JSONDecodeError):
            continue

        nodi = data if isinstance(data, list) else [data]
        appiattiti = []
        for nodo in nodi:
            if isinstance(nodo, dict) and isinstance(nodo.get("@graph"), list):
                appiattiti.extend(n for n in nodo["@graph"] if isinstance(n, dict))
            elif isinstance(nodo, dict):
                appiattiti.append(nodo)

        for nodo in appiattiti:
            tipo = nodo.get("@type")
            tipi = tipo if isinstance(tipo, list) else [tipo]
            if any(t in tipi_validi for t in tipi):
                return nodo

    return None


def _autore_da_testo(soup):
    """Su ilpost.it l'autore non è quasi mai in un meta tag o nel JSON-LD:
    compare come testo 'di Nome Cognome' sotto il sottotitolo dell'articolo."""

    pattern = re.compile(
        r"^di\s+([A-ZÀ-Ý][\wÀ-ÿ'’.\-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'’.\-]+){0,3})$"
    )

    for tag in soup.find_all(["h3", "h4", "p", "span", "a", "div"]):
        testo = tag.get_text(" ", strip=True)
        match = pattern.match(testo)
        if match:
            return match.group(1).strip()

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


def _estrai_data(soup, nodo_ld=None):
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
    if nodo_ld and nodo_ld.get("datePublished"):
        return str(nodo_ld["datePublished"])

    # 3. Tag <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return time_tag["datetime"].strip()

    return ""


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_top_story():
    """Restituisce il primo articolo della sezione Tecnologia de Il Post."""

    soup_sezione = _get_soup(IL_POST_SECTION_URL)

    primo_link = soup_sezione.select_one(IL_POST_FIRST_LINK_SELECTOR)
    if not primo_link or not primo_link.get("href"):
        logger.warning("Il Post: nessun link a un articolo trovato in sezione")
        return None

    article_url = urljoin(IL_POST_SECTION_URL, primo_link["href"])

    try:
        soup_articolo = _get_soup(article_url)
    except requests.RequestException as e:
        logger.warning(f"Il Post: impossibile aprire {article_url} - {e}")
        return None

    nodo_ld = _nodo_articolo_jsonld(soup_articolo)

    titolo = _meta(soup_articolo, "og:title", "twitter:title")
    if not titolo and soup_articolo.title and soup_articolo.title.string:
        titolo = soup_articolo.title.string.strip()

    if not titolo:
        logger.warning(f"Il Post: articolo senza titolo, scartato ({article_url})")
        return None

    sommario = _meta(soup_articolo, "og:description", "description") or (
        nodo_ld.get("description") if nodo_ld else ""
    )

    autore = _meta(soup_articolo, "author", "article:author")
    if not autore and nodo_ld:
        autore_ld = nodo_ld.get("author")
        if autore_ld:
            autore_ld = autore_ld[0] if isinstance(autore_ld, list) else autore_ld
            autore = (
                autore_ld.get("name") if isinstance(autore_ld, dict) else autore_ld
            ) or ""
    if not autore:
        autore = _autore_da_testo(soup_articolo)

    data_parsata = _parse_iso(_estrai_data(soup_articolo, nodo_ld))
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