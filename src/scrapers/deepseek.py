import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    DEEPSEEK_DATE_SUFFIX_PATTERN,
    DEEPSEEK_ENTRY_URL,
    DEEPSEEK_NEWS_LINK_PATTERN,
    HEADERS,
    REQUEST_TIMEOUT,
)

logger = get_logger(__name__)

NEWS_LINK_PATTERN = re.compile(DEEPSEEK_NEWS_LINK_PATTERN)
DATE_SUFFIX_PATTERN = re.compile(DEEPSEEK_DATE_SUFFIX_PATTERN)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def clean_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


# ------------------------------------------------------------
# LISTA NEWS
# ------------------------------------------------------------

def _lista_candidati():
    """Legge la sidebar News e restituisce le voci senza duplicati."""

    response = requests.get(DEEPSEEK_ENTRY_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    candidati = []
    visti = set()

    for link in soup.find_all("a", href=True):

        full_url = urljoin(DEEPSEEK_ENTRY_URL, link["href"].strip())
        full_url = full_url.split("?")[0].split("#")[0]

        # Lo stesso URL può comparire più volte nella sidebar
        if not NEWS_LINK_PATTERN.match(full_url) or full_url in visti:
            continue

        raw_text = clean_text(link.get_text(" ", strip=True))
        match = DATE_SUFFIX_PATTERN.search(raw_text)

        if not match:
            continue

        anno, mese, giorno = match.groups()

        try:
            data = datetime(int(anno), int(mese), int(giorno))
        except ValueError:
            continue

        visti.add(full_url)
        candidati.append({
            "titolo": raw_text[: match.start()].strip(),
            "link": full_url,
            "data": data,
        })

    return candidati


# ------------------------------------------------------------
# ARTICOLO
# ------------------------------------------------------------

def _leggi_articolo(voce):
    """
    Apre la pagina per titolo e sommario puliti. Se non si apre,
    ripiega sui dati della sidebar.
    """

    titolo = voce["titolo"]
    sommario = ""

    try:
        response = requests.get(voce["link"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"DeepSeek: impossibile aprire {voce['link']} - {e}")
        return titolo, sommario

    soup = BeautifulSoup(response.text, "html.parser")

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        # Il sito aggiunge " | DeepSeek API Docs" al titolo della pagina
        titolo = og_title["content"].split("|")[0].strip() or titolo

    meta_description = soup.find("meta", attrs={"name": "description"})
    if meta_description and meta_description.get("content"):
        sommario = meta_description["content"].strip()

    return titolo, sommario


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_deepseek_latest():
    """Restituisce la news più recente di DeepSeek."""

    candidati = _lista_candidati()

    if not candidati:
        logger.warning("DeepSeek: nessuna news trovata nella pagina")
        return None

    # Non ci si fida dell'ordine nella sidebar: si sceglie la data più recente
    candidati.sort(key=lambda c: c["data"], reverse=True)
    ultima = candidati[0]

    titolo, sommario = _leggi_articolo(ultima)

    return {
        "titolo": titolo,
        "sommario": sommario,
        "pubblicato": ultima["data"].strftime("%d/%m/%Y"),
        "link": ultima["link"],
    }


if __name__ == "__main__":
    # Esegui dalla root della repo:  python -m src.scrapers.deepseek_news
    articolo = get_deepseek_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")