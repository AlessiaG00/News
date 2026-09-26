
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    GOOGLE_RESEARCH_CATEGORY_FILTER,
    GOOGLE_RESEARCH_RSS_URL,
    HEADERS,
    REQUEST_TIMEOUT,
)

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


def _leggi_item(item):
    return {
        "titolo": clean_text(_campo(item, "title")),
        "link": _campo(item, "link"),
        "pubblicato": _formatta_data(_campo(item, "pubDate")),
        "categorie": [
            c.text.strip() for c in item.findall("category") if c.text
        ],
    }


def _sommario_da_pagina(link):
    """Legge og:description (o meta description) dalla pagina dell'articolo.
    Se la pagina non si apre restituisce stringa vuota."""

    try:
        response = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Google Research: impossibile aprire {link} - {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    for attrs in ({"property": "og:description"}, {"name": "description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"].strip()

    return ""


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_research_latest():
    """Restituisce l'ultimo post del blog di Google Research."""

    response = requests.get(
        GOOGLE_RESEARCH_RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = root.findall("./channel/item")

    if not items:
        logger.warning("Google Research: nessun articolo nel feed RSS")
        return None

    articoli = [_leggi_item(item) for item in items]

    if GOOGLE_RESEARCH_CATEGORY_FILTER:
        articoli = [
            a for a in articoli
            if GOOGLE_RESEARCH_CATEGORY_FILTER in a["categorie"]
        ]

    if not articoli:
        logger.warning(
            f"Google Research: nessun articolo per la categoria "
            f"'{GOOGLE_RESEARCH_CATEGORY_FILTER}'"
        )
        return None

    # Il feed è già ordinato dal più recente al più vecchio
    ultimo = articoli[0]

    return {
        "titolo": ultimo["titolo"],
        "sommario": _sommario_da_pagina(ultimo["link"]) if ultimo["link"] else "",
        "pubblicato": ultimo["pubblicato"],
        "link": ultimo["link"],
    }


if __name__ == "__main__":
    articolo = get_research_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")