# src/scraper.py

import logging
from scrapers import ansa, corriere, repubblica, sole24ore, ilfattoquotidiano

logger = logging.getLogger(__name__)

# Mappa nome -> funzione, così aggiungere un giornale in futuro
# significa aggiungere una riga qui, non toccare la logica sotto
SCRAPERS = {
    "ANSA": ansa.get_top_story,
    "Corriere": corriere.get_top_story,
    "Il Fatto Quotidiano": ilfattoquotidiano.get_top_story(),
    "Repubblica": repubblica.get_top_story,
    "Sole24Ore": sole24ore.get_top_story,
}


def get_all_articles() -> list[dict]:
    """
    Esegue tutti gli scraper e restituisce la lista degli articoli
    recuperati con successo. Se uno scraper fallisce, viene loggato
    e saltato, senza bloccare gli altri.
    """
    articoli = []

    for nome, funzione in SCRAPERS.items():
        try:
            articolo = funzione()
            if articolo and articolo.get("titolo"):
                articoli.append(articolo)
            else:
                logger.warning(f"{nome}: nessun dato valido restituito")
        except Exception as e:
            logger.error(f"{nome}: errore durante lo scraping - {e}")

    return articoli

