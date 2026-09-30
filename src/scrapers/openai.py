import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    HEADERS,
    MESI_IT,
    OPENAI_ARTICLE_PATTERN,
    OPENAI_CANDIDATES_TO_CHECK,
    OPENAI_CATEGORY_LABELS,
    OPENAI_URL,
    REQUEST_TIMEOUT,
)

logger = get_logger(__name__)

ARTICLE_PATTERN = re.compile(OPENAI_ARTICLE_PATTERN)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def clean_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _meta(soup, **attrs):
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content", "").strip() if tag else ""


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


def _trova_categoria(raw_text):
    """Restituisce la prima etichetta di OPENAI_CATEGORY_LABELS presente nel
    testo, oppure None se nessuna combacia."""
    for etichetta in OPENAI_CATEGORY_LABELS:
        if etichetta in raw_text:
            return etichetta
    return None


def _parse_card_date(text):
    """Legge una data tipo '18 set 2026' dal testo della card."""
    match = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ù]{3,})\.?\s+(\d{4})", text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MESI_IT.get(month_name[:3].lower())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day), tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_date(soup):
    """Cerca la data di pubblicazione dentro l'articolo con più strategie."""

    # 1. Meta tag
    for attrs in (
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"property": "og:published_time"},
        {"itemprop": "datePublished"},
        {"name": "date"},
    ):
        value = _meta(soup, **attrs)
        if value:
            return value

    # 2. JSON-LD (datePublished)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue

        items = data if isinstance(data, list) else [data]
        for item in list(items):
            if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                items.extend(item["@graph"])

        for item in items:
            if isinstance(item, dict) and item.get("datePublished"):
                return str(item["datePublished"])

    # 3. <time datetime="...">
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return time_tag["datetime"].strip()

    return ""


# ------------------------------------------------------------
# LISTA CARD
# ------------------------------------------------------------

def _lista_candidati():
    """
    Legge la pagina elenco e restituisce (candidati, altre_categorie):
    candidati = card che hanno una delle etichette in OPENAI_CATEGORY_LABELS
    (es. "Ricerca", "Prodotto"); altre_categorie = testo grezzo dei link
    articolo che non hanno nessuna di queste etichette, utile in diagnostica
    per capire cosa si è trovato davvero.
    """

    response = requests.get(OPENAI_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    candidati = []
    altre_categorie = []
    visti = set()

    for link in soup.find_all("a", href=True):

        full_url = urljoin(OPENAI_URL, link["href"].strip())
        full_url = full_url.split("?")[0].split("#")[0]

        if not ARTICLE_PATTERN.match(full_url) or full_url in visti:
            continue

        # Testo del link = titolo + categoria + data attaccati, es:
        # "Introducing the Australian Youth Safety BlueprintAzienda18 set 2026"
        raw_text = clean_text(link.get_text(" ", strip=True))

        if not raw_text:
            continue

        categoria = _trova_categoria(raw_text)

        if categoria is None:
            visti.add(full_url)
            altre_categorie.append(raw_text)
            continue

        titolo, _, resto = raw_text.partition(categoria)
        titolo = titolo.strip()

        if len(titolo) < 5:
            continue

        visti.add(full_url)
        candidati.append({
            "titolo": titolo,
            "link": full_url,
            "data_card": _parse_card_date(resto),
        })

    return candidati, altre_categorie


# ------------------------------------------------------------
# ARTICOLO
# ------------------------------------------------------------

def _leggi_articolo(candidato):
    """Apre l'articolo. Restituisce (articolo, data_parsata) oppure None."""

    try:
        response = requests.get(
            candidato["link"], headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"OpenAI: impossibile aprire {candidato['link']} - {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    titolo = _meta(soup, property="og:title")
    if not titolo:
        title_tag = soup.find("title")
        titolo = clean_text(title_tag.get_text()) if title_tag else ""

    sommario = _meta(soup, name="description") or _meta(
        soup, property="og:description"
    )

    # Data: prima dall'articolo, poi (fallback) dalla card nell'elenco
    data_parsata = _parse_iso(_extract_date(soup)) or candidato["data_card"]

    articolo = {
        "titolo": titolo or candidato["titolo"],
        "sommario": sommario,
        "pubblicato": data_parsata.strftime("%d/%m/%Y") if data_parsata else "",
        "link": candidato["link"],
    }

    return articolo, data_parsata


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_openai_latest():
    """Restituisce l'articolo più recente tra le categorie OpenAI configurate."""

    candidati, altre_categorie = _lista_candidati()

    if not candidati:
        if not altre_categorie:
            logger.warning(
                "OpenAI: nessun link corrisponde al pattern degli articoli "
                "(probabile HTML diverso da quello del browser: anti-bot o "
                "pagina cambiata)"
            )
        else:
            dettaglio = "; ".join(altre_categorie[:10])
            logger.warning(
                f"OpenAI: nessuna card tra {OPENAI_CATEGORY_LABELS} trovata. "
                f"Trovati {len(altre_categorie)} link articolo con altro testo: {dettaglio}"
            )
        return None

    migliore = None
    migliore_data = None

    for candidato in candidati[:OPENAI_CANDIDATES_TO_CHECK]:

        letto = _leggi_articolo(candidato)
        if letto is None:
            continue

        articolo, data = letto

        # Il primo risultato valido fa da fallback se le date mancano
        if migliore is None or (data and (migliore_data is None or data > migliore_data)):
            migliore, migliore_data = articolo, data

    return migliore


if __name__ == "__main__":
    # Esegui dalla root della repo:  python -m src.scrapers.openai_news
    articolo = get_openai_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")