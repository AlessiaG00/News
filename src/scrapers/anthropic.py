
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    ANTHROPIC_ARTICLE_PATTERN,
    ANTHROPIC_CATEGORY_FILTER,
    ANTHROPIC_DATE_PATTERN,
    ANTHROPIC_KNOWN_CATEGORIES,
    ANTHROPIC_URL,
    HEADERS,
    MESI_EN,
    REQUEST_TIMEOUT,
)

logger = get_logger(__name__)

DATE_PATTERN = re.compile(ANTHROPIC_DATE_PATTERN)
ARTICLE_PATTERN = re.compile(ANTHROPIC_ARTICLE_PATTERN)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def clean_text(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _parse_data_en(data_str):
    """'Sep 1, 2026' -> datetime (indipendente dal locale del sistema)."""
    try:
        mese, giorno, anno = data_str.replace(",", "").split()
        return datetime(int(anno), MESI_EN[mese.lower()[:3]], int(giorno))
    except (ValueError, KeyError):
        return None


def _parse_voce_lista(raw_text):
    """
    Divide il testo di un link della lista "News" in (data, categoria, titolo).
    Esempi di testo grezzo:
      "Sep 1, 2026Announcements Developing Enterprise Frontier Safeguards..."
      "Aug 31, 2026 Improving our alignment and security efforts"  (senza categoria)
    """

    match = DATE_PATTERN.match(raw_text)
    if not match:
        return None

    data_str = match.group(0)
    resto = raw_text[len(data_str):].strip()

    categoria = None
    for cat in ANTHROPIC_KNOWN_CATEGORIES:
        if resto == cat or resto.startswith(cat + " "):
            categoria = cat
            resto = resto[len(cat):].strip()
            break

    return {
        "data_str": data_str,
        "data": _parse_data_en(data_str),
        "categoria": categoria,
        "titolo": resto.strip(),
    }


# ------------------------------------------------------------
# LISTA ARTICOLI
# ------------------------------------------------------------

def _lista_articoli():
    """
    Legge la pagina News. Restituisce (tutti, candidati):
    tutti = ogni articolo trovato; candidati = solo quelli che passano
    il filtro per categoria. Entrambe senza duplicati.
    """

    response = requests.get(ANTHROPIC_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    tutti = []
    candidati = []
    visti = set()

    for link in soup.find_all("a", href=True):

        full_url = urljoin(ANTHROPIC_URL, link["href"].strip())
        full_url = full_url.split("?")[0].split("#")[0]

        if not ARTICLE_PATTERN.match(full_url) or full_url in visti:
            continue

        voce = _parse_voce_lista(clean_text(link.get_text(" ", strip=True)))

        if not voce or not voce["titolo"]:
            continue

        visti.add(full_url)
        voce["link"] = full_url
        tutti.append(voce)

        if ANTHROPIC_CATEGORY_FILTER and voce["categoria"] != ANTHROPIC_CATEGORY_FILTER:
            continue

        candidati.append(voce)

    return tutti, candidati


# ------------------------------------------------------------
# ARTICOLO
# ------------------------------------------------------------

def _leggi_articolo(voce):
    """
    Apre l'articolo per il titolo pulito (og:title) e il sommario.
    Il meta description di Anthropic è generico per tutto il sito, quindi
    il sommario è il primo paragrafo vero dopo l'<h1>.
    Se la pagina non si apre, ripiega sui dati della lista.
    """

    titolo = voce["titolo"]
    sommario = ""

    try:
        response = requests.get(voce["link"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Anthropic: impossibile aprire {voce['link']} - {e}")
        return titolo, sommario

    soup = BeautifulSoup(response.text, "html.parser")

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        titolo = og_title["content"].strip()

    h1 = soup.find("h1")
    if h1:
        for p in h1.find_all_next("p"):
            testo = clean_text(p.get_text(" ", strip=True))
            if len(testo) > 40:
                sommario = testo
                break

    return titolo, sommario


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_anthropic_latest():
    """Restituisce l'articolo più recente della pagina News di Anthropic."""

    tutti, candidati = _lista_articoli()

    if not candidati:
        if not tutti:
            logger.warning(
                "Anthropic: nessun link corrisponde al pattern degli articoli "
                "(probabile HTML diverso da quello del browser: anti-bot o "
                "rendering lato client)"
            )
        else:
            dettaglio = "; ".join(
                f"{v['categoria']!r}: {v['titolo']} ({v['data_str']})"
                for v in tutti[:10]
            )
            logger.warning(
                f"Anthropic: nessun articolo nella categoria "
                f"'{ANTHROPIC_CATEGORY_FILTER}'. Trovati {len(tutti)} articoli "
                f"in altre categorie: {dettaglio}"
            )
        return None

    # Il più recente per data reale (a parità, vale l'ordine della pagina)
    candidati.sort(key=lambda v: v["data"] or datetime.min, reverse=True)
    ultimo = candidati[0]

    titolo, sommario = _leggi_articolo(ultimo)

    return {
        "titolo": titolo,
        "sommario": sommario,
        "pubblicato": (
            ultimo["data"].strftime("%d/%m/%Y") if ultimo["data"] else ultimo["data_str"]
        ),
        "link": ultimo["link"],
    }


if __name__ == "__main__":
    # Esegui dalla root della repo:  python -m src.scrapers.anthropic_news
    articolo = get_anthropic_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")