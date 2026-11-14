
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
CATEGORIE = set(ANTHROPIC_KNOWN_CATEGORIES)


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


def _normalizza_url(href):
    url = urljoin(ANTHROPIC_URL, href.strip())
    return url.split("?")[0].split("#")[0]


def _testo_fuori_dai_link(li):
    """Testo della voce escludendo quello dei link: la data è testo semplice,
    mentre titolo e descrizione sono dentro i link (e potrebbero citare date)."""
    pezzi = [s for s in li.find_all(string=True) if not s.find_parent("a")]
    return clean_text(" ".join(pezzi))


# ------------------------------------------------------------
# LISTA ARTICOLI
# ------------------------------------------------------------

def _leggi_voce(li):
    """
    Estrae i dati da un <li> della lista. Restituisce None se non è la voce
    di un articolo (menu, footer, carosello di immagini: niente data o niente
    link con testo).
    """

    match = DATE_PATTERN.search(_testo_fuori_dai_link(li)) or DATE_PATTERN.search(
        clean_text(li.get_text(" ", strip=True))
    )
    if not match:
        return None

    data_str = match.group(0)

    categoria = None
    link = None
    testi = []  # testi (unici, in ordine) dei link che puntano all'articolo

    for a in li.find_all("a", href=True):

        testo = clean_text(a.get_text(" ", strip=True))
        if not testo:
            continue  # link con sola immagine

        if testo in CATEGORIE:
            categoria = categoria or testo
            continue

        url = _normalizza_url(a["href"])
        if not ARTICLE_PATTERN.match(url):
            continue

        if link is None:
            link = url
        if url == link and testo not in testi:
            testi.append(testo)

    if not link or not testi:
        return None

    return {
        "titolo": testi[0],
        # il secondo testo che punta allo stesso articolo è la descrizione
        "sommario": testi[1] if len(testi) > 1 else "",
        "categoria": categoria,
        "data_str": data_str,
        "data": _parse_data_en(data_str),
        "link": link,
    }


def _lista_voci():
    """
    Legge la pagina News. Restituisce (tutte, candidate):
    tutte = ogni articolo trovato; candidate = solo quelli che passano
    il filtro per categoria. Entrambe senza duplicati.
    """

    response = requests.get(ANTHROPIC_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    tutte = []
    viste = set()

    for li in soup.find_all("li"):
        voce = _leggi_voce(li)
        if voce is None or voce["link"] in viste:
            continue
        viste.add(voce["link"])
        tutte.append(voce)

    candidate = [
        v for v in tutte
        if not ANTHROPIC_CATEGORY_FILTER or v["categoria"] == ANTHROPIC_CATEGORY_FILTER
    ]

    return tutte, candidate


# ------------------------------------------------------------
# ARTICOLO (solo se la lista non ha la descrizione)
# ------------------------------------------------------------

def _sommario_da_articolo(link):
    """Primo paragrafo vero dopo l'<h1>. Il meta description di Anthropic è
    generico per tutto il sito, quindi non si usa. Se la pagina non si apre
    restituisce stringa vuota."""

    try:
        response = requests.get(link, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Anthropic: impossibile aprire {link} - {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    h1 = soup.find("h1")
    if h1:
        for p in h1.find_all_next("p"):
            testo = clean_text(p.get_text(" ", strip=True))
            if len(testo) > 40:
                return testo

    return ""


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_anthropic_latest():
    """Restituisce l'articolo più recente della pagina News di Anthropic."""

    tutte, candidate = _lista_voci()

    if not candidate:
        if not tutte:
            logger.warning(
                "Anthropic: nessuna voce con data trovata nella lista News "
                "(probabile layout cambiato, blocco anti-bot o rendering "
                "lato client)"
            )
        else:
            dettaglio = "; ".join(
                f"{v['categoria']!r}: {v['titolo']} ({v['data_str']})"
                for v in tutte[:10]
            )
            logger.warning(
                f"Anthropic: nessun articolo nella categoria "
                f"'{ANTHROPIC_CATEGORY_FILTER}'. Trovati {len(tutte)} articoli "
                f"in altre categorie: {dettaglio}"
            )
        return None

    # Il più recente per data reale (a parità, vale l'ordine della pagina)
    candidate.sort(key=lambda v: v["data"] or datetime.min, reverse=True)
    ultima = candidate[0]

    sommario = ultima["sommario"] or _sommario_da_articolo(ultima["link"])

    return {
        "titolo": ultima["titolo"],
        "sommario": sommario,
        "pubblicato": (
            ultima["data"].strftime("%d/%m/%Y") if ultima["data"] else ultima["data_str"]
        ),
        "link": ultima["link"],
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