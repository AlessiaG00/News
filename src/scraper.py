import logging
from src.scrapers import ansa, bbc, corriere, guardian, NYT, openai, repubblica, sole24ore, anthropic, google_deepmind, google_research, deepseek

logger = logging.getLogger(__name__)

SCRAPERS = {
    "ANSA": ansa.get_top_story,
    "Corriere": corriere.get_top_story,
    "Repubblica": repubblica.get_top_story,
    "Sole24Ore": sole24ore.get_top_story,
    "BBC News": bbc.get_top_story,
    "The Guardian": guardian.get_top_story,
    "NYT": NYT.get_top_story,
    "OpenAI": openai.get_openai_latest,
    "Anthropic": anthropic.get_anthropic_latest,
    "Google Research": google_research.get_research_latest,
    "Google DeepMind": google_deepmind.get_deepmind_latest,
    "DeepSeek": deepseek.get_deepseek_latest,
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
                articolo["fonte"] = nome  
                articoli.append(articolo)
            else:
                logger.warning(f"{nome}: nessun dato valido restituito")
        except Exception as e:
            logger.error(f"{nome}: errore durante lo scraping - {e}")

    return articoli