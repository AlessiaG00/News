import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import DEEPMIND_RSS_URL, HEADERS, REQUEST_TIMEOUT

logger = get_logger(__name__)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def clean_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _campo(item, tag):
    """Testo completo dell'elemento (anche se contiene tag figli)."""
    el = item.find(tag)
    return "".join(el.itertext()).strip() if el is not None else ""


def _formatta_data(pub_date):
    """'Wed, 16 Sep 2026 10:00:00 +0000' -> '16/09/2026'.
    Se il formato non è leggibile restituisce il testo originale."""
    if not pub_date:
        return ""
    try:
        return parsedate_to_datetime(pub_date).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return pub_date


def _sommario_da_pagina(link):
    """Legge og:description dalla pagina dell'articolo.
    Nota: deepmind.google/blog/<slug> a volte reindirizza a blog.google;
    requests segue i redirect normalmente.
    Se la pagina non si apre restituisce stringa vuota."""

    try:
        response = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Google DeepMind: impossibile aprire {link} - {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    tag = soup.find("meta", attrs={"property": "og:description"})
    if tag and tag.get("content"):
        return tag["content"].strip()

    return ""


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_deepmind_latest():
    """Restituisce l'ultimo post del blog di Google DeepMind."""

    response = requests.get(DEEPMIND_RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = root.findall("./channel/item")

    if not items:
        logger.warning("Google DeepMind: nessun articolo nel feed RSS")
        return None

    # Il feed è già ordinato dal più recente al più vecchio
    ultimo = items[0]

    titolo = clean_text(_campo(ultimo, "title"))
    link = _campo(ultimo, "link")
    sommario = clean_text(_campo(ultimo, "description"))

    # Se il feed non ha la descrizione (capita per alcuni post) la si cerca
    # nella pagina dell'articolo
    if not sommario and link:
        sommario = _sommario_da_pagina(link)

    return {
        "titolo": titolo,
        "sommario": sommario,
        "pubblicato": _formatta_data(_campo(ultimo, "pubDate")),
        "link": link,
    }


if __name__ == "__main__":
    # Esegui dalla root della repo:  python -m src.scrapers.google_deepmind
    articolo = get_deepmind_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")