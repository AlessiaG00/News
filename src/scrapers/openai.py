import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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
    OPENAI_RSS_CATEGORIES,
    OPENAI_RSS_URL,
    OPENAI_URLS,
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

def _lista_candidati_pagina(url):
    """
    Legge UNA pagina elenco e restituisce (candidati, altre_categorie).

    OpenAI mostra spesso la stessa card due volte (tab "Articoli" e tab
    "Media" della pagina, entrambe presenti nell'HTML): una versione ha la
    data, l'altra no (solo il tempo di lettura). Le due occorrenze dello
    stesso URL vengono quindi unite, tenendo la data appena una delle due
    la fornisce, invece di scartare una delle due copie a caso.
    """

    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    per_url = {}
    ordine = []
    altre_categorie = []
    altre_viste = set()

    for link in soup.find_all("a", href=True):

        full_url = urljoin(url, link["href"].strip())
        full_url = full_url.split("?")[0].split("#")[0]

        if not ARTICLE_PATTERN.match(full_url):
            continue

        # Testo del link = titolo + categoria + data (o tempo di lettura)
        # attaccati, es: "Introducing the ... BlueprintAzienda18 set 2026"
        raw_text = clean_text(link.get_text(" ", strip=True))

        if not raw_text:
            continue

        categoria = _trova_categoria(raw_text)

        if categoria is None:
            if full_url not in altre_viste:
                altre_viste.add(full_url)
                altre_categorie.append(raw_text)
            continue

        titolo, _, resto = raw_text.partition(categoria)
        titolo = titolo.strip()

        if len(titolo) < 5:
            continue

        data_card = _parse_card_date(resto)

        if full_url not in per_url:
            per_url[full_url] = {"titolo": titolo, "link": full_url, "data_card": data_card}
            ordine.append(full_url)
        else:
            # Stesso URL già visto (l'altra "vista" della card): tieni la
            # data appena una delle due occorrenze la fornisce
            esistente = per_url[full_url]
            if esistente["data_card"] is None and data_card is not None:
                esistente["data_card"] = data_card

    return [per_url[u] for u in ordine], altre_categorie


def _lista_candidati():
    """
    Legge tutte le pagine in OPENAI_URLS e unisce i risultati (stesso URL =
    stessa notizia, tenendo la data appena una delle pagine la fornisce).
    Se una pagina non si apre si prosegue con le altre; se non si apre
    nessuna, l'ultimo errore viene rilanciato (lo logga get_all_articles).
    """

    per_url = {}
    ordine = []
    altre_categorie = []
    ultimo_errore = None
    pagine_lette = 0

    for url in OPENAI_URLS:
        try:
            candidati, altre = _lista_candidati_pagina(url)
        except requests.RequestException as e:
            logger.warning(f"OpenAI: impossibile leggere {url} - {e}")
            ultimo_errore = e
            continue

        pagine_lette += 1
        altre_categorie.extend(altre)

        for c in candidati:
            if c["link"] not in per_url:
                per_url[c["link"]] = c
                ordine.append(c["link"])
            elif per_url[c["link"]]["data_card"] is None and c["data_card"] is not None:
                per_url[c["link"]]["data_card"] = c["data_card"]

    if pagine_lette == 0 and ultimo_errore is not None:
        raise ultimo_errore

    return [per_url[u] for u in ordine], altre_categorie


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
# RIPIEGO: PAGINE HTML
# ------------------------------------------------------------

def _da_pagine():
    """Ripiego: legge le pagine HTML delle categorie (vedi OPENAI_URLS)."""

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

    if migliore is not None and migliore_data is None:
        logger.warning(
            "OpenAI: nessuna data leggibile per gli articoli candidati; "
            "restituito il primo trovato nell'ordine della pagina, non "
            "necessariamente il più recente"
        )

    return migliore


# ------------------------------------------------------------
# FEED RSS
# ------------------------------------------------------------

def _formatta_data_rss(pub_date):
    """'Wed, 16 Sep 2026 10:00:00 GMT' -> (datetime, '16/09/2026')."""
    if not pub_date:
        return None, ""
    try:
        data = parsedate_to_datetime(pub_date)
    except (TypeError, ValueError):
        return None, pub_date
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data, data.strftime("%d/%m/%Y")


def _pulisci_descrizione(html_text):
    """Toglie i tag HTML dalla descrizione del feed e rimuove gli spazi che
    la pulizia lascia prima della punteggiatura ('prodotto .' -> 'prodotto.')."""
    testo = clean_text(html_text)
    return re.sub(r"\s+([.,;:!?])", r"\1", testo)


def _testo_elemento(item, tag):
    el = item.find(tag)
    return "".join(el.itertext()).strip() if el is not None else ""


def _da_rss():
    """
    Legge il feed RSS e restituisce l'articolo più recente tra le categorie
    in OPENAI_RSS_CATEGORIES, oppure None. Solleva requests.RequestException
    se il feed non si scarica (lo gestisce il chiamante).
    """

    response = requests.get(OPENAI_RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = root.findall("./channel/item")

    if not items:
        logger.warning("OpenAI: nessun articolo nel feed RSS")
        return None

    voci = []
    for item in items:
        titolo = clean_text(_testo_elemento(item, "title"))
        link = _testo_elemento(item, "link")
        if not titolo or not link:
            continue
        data, pubblicato = _formatta_data_rss(_testo_elemento(item, "pubDate"))
        voci.append({
            "titolo": titolo,
            "sommario": _pulisci_descrizione(_testo_elemento(item, "description")),
            "pubblicato": pubblicato,
            "data": data,
            "link": link,
            "categorie": [
                c.text.strip() for c in item.findall("category") if c.text
            ],
        })

    if not voci:
        logger.warning("OpenAI: feed RSS senza articoli leggibili")
        return None

    if any(v["categorie"] for v in voci):
        volute = {c.casefold() for c in OPENAI_RSS_CATEGORIES}
        scelte = [
            v for v in voci
            if any(c.casefold() in volute for c in v["categorie"])
        ]
        if not scelte:
            trovate = sorted({c for v in voci for c in v["categorie"]})
            logger.warning(
                f"OpenAI: nel feed nessun articolo con categorie "
                f"{OPENAI_RSS_CATEGORIES}. Categorie presenti: {trovate}"
            )
            return None
    else:
        logger.warning(
            "OpenAI: il feed non indica le categorie, impossibile filtrare "
            "per Ricerca/Prodotto: uso l'articolo più recente in assoluto"
        )
        scelte = voci

    # Il più recente per data reale (a parità vale l'ordine del feed)
    scelte.sort(
        key=lambda v: v["data"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    migliore = scelte[0]

    return {
        "titolo": migliore["titolo"],
        "sommario": migliore["sommario"],
        "pubblicato": migliore["pubblicato"],
        "link": migliore["link"],
    }


# ------------------------------------------------------------
# FUNZIONE PUBBLICA
# ------------------------------------------------------------

def get_openai_latest():
    """Restituisce l'articolo più recente tra le categorie OpenAI configurate:
    prima dal feed RSS, poi (ripiego) dalle pagine HTML."""

    try:
        articolo = _da_rss()
        if articolo:
            return articolo
    except (requests.RequestException, ET.ParseError) as e:
        logger.warning(f"OpenAI: feed RSS non utilizzabile ({e}), provo le pagine HTML")

    return _da_pagine()


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