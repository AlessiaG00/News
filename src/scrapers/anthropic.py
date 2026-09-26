import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logger import get_logger
from src.config import (
    ANTHROPIC_CATEGORY_FILTER,
    ANTHROPIC_DATE_PATTERN,
    ANTHROPIC_GENERIC_DESC,
    ANTHROPIC_SITE,
    ANTHROPIC_URL,
    HEADERS,
    MESI_EN,
    REQUEST_TIMEOUT,
)

logger = get_logger(__name__)

DATE_PATTERN = re.compile(ANTHROPIC_DATE_PATTERN)


# ------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------

def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


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
            return _clean(tag["content"])
    return ""


def _parse_data_en(mese, giorno, anno):
    """'Sep', '22', '2026' -> datetime (indipendente dal locale del sistema)."""
    try:
        return datetime(int(anno), MESI_EN[mese.lower()[:3]], int(giorno))
    except (ValueError, KeyError):
        return None


# ------------------------------------------------------------
# LISTA ARTICOLI
# ------------------------------------------------------------

def _trova_voci(soup, category_filter=None):
    """
    Restituisce {url: {data, data_str, testo}} per ogni link della pagina il
    cui testo contiene una data. Copre sia la lista "News" (/news/slug) sia
    le card in evidenza in cima (URL diversi, es. /features/...): in queste
    ultime categoria e data sono spesso attaccate al testo del link
    """

    voci = {}

    for link in soup.find_all("a", href=True):
        url = urljoin(ANTHROPIC_URL, link["href"].strip())
        url = url.split("?")[0].split("#")[0].rstrip("/")

        if not url.startswith(ANTHROPIC_SITE) or url == ANTHROPIC_URL:
            continue

        testo = _clean(link.get_text(" ", strip=True))
        match = DATE_PATTERN.search(testo)
        if not match:
            continue

        if category_filter and category_filter.lower() not in testo.lower():
            continue

        if url not in voci:
            voci[url] = {
                "data": _parse_data_en(match.group(1), match.group(2), match.group(3)),
                "data_str": match.group(0),
                "testo": testo,
            }

    return voci


# ------------------------------------------------------------
# ARTICOLO
# ------------------------------------------------------------

def _leggi_articolo(soup):
    """
    Estrae titolo e sommario dall'articolo.
    La meta description di Anthropic è generica per tutto il sito, quindi
    va scartata e sostituita dal primo paragrafo vero dopo l'<h1>.
    """

    h1 = soup.find("h1")
    titolo = _clean(h1.get_text(" ", strip=True)) if h1 else ""
    titolo = titolo or _meta(soup, "og:title")

    sommario = _meta(soup, "og:description", "description")
    if ANTHROPIC_GENERIC_DESC in sommario:
        sommario = ""

    if not sommario and h1:
        for p in h1.find_all_next("p"):
            testo = _clean(p.get_text(" ", strip=True))
            if len(testo) > 40:
                sommario = testo[:300]
                break

    return titolo, sommario


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_anthropic_latest(category_filter=ANTHROPIC_CATEGORY_FILTER):
    """Restituisce l'articolo più recente della pagina News di Anthropic."""

    voci = _trova_voci(_get_soup(ANTHROPIC_URL), category_filter)

    if not voci:
        logger.warning(
            "Anthropic: nessun link con data trovato (probabile HTML diverso "
            "da quello del browser: anti-bot o rendering lato client)"
        )
        return None

    # Il più recente per data reale; a parità vince il primo in ordine di pagina
    link, info = max(voci.items(), key=lambda kv: kv[1]["data"] or datetime.min)

    try:
        soup_articolo = _get_soup(link)
    except requests.RequestException as e:
        logger.warning(f"Anthropic: impossibile aprire {link} - {e}")
        return {
            "titolo": info["testo"],
            "sommario": "",
            "pubblicato": info["data_str"],
            "link": link,
        }

    titolo, sommario = _leggi_articolo(soup_articolo)

    return {
        "titolo": titolo or info["testo"],
        "sommario": sommario,
        "pubblicato": (
            info["data"].strftime("%d/%m/%Y") if info["data"] else info["data_str"]
        ),
        "link": link,
    }


if __name__ == "__main__":
    articolo = get_anthropic_latest()

    if articolo:
        print("TITOLO:", articolo["titolo"])
        print("SOMMARIO:", articolo["sommario"])
        print("PUBBLICATO:", articolo["pubblicato"])
        print("LINK:", articolo["link"])
    else:
        print("Nessun articolo trovato.")