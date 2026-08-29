"""
Entry point del progetto.
Eseguito ogni mattina da GitHub Actions (vedi workflows/daily_news.yml).

Flusso:
1. Richiama tutti gli scraper tramite src.utils.scraper
2. Costruisce l'HTML dell'email
3. Invia l'email
4. Logga ogni fase ed eventuali errori
"""

import sys

from logger import get_logger
from mail import build_email_html, send_email
from src.scraper import get_all_articles

logger = get_logger(__name__)


def main() -> int:
    logger.info("Avvio raccolta notizie...")

    try:
        news_items = get_all_articles()
    except Exception:
        logger.exception("Errore durante l'esecuzione degli scraper")
        return 1

    if not news_items:
        logger.warning("Nessuna notizia raccolta: invio comunque un'email vuota di avviso.")

    logger.info(f"Raccolte {len(news_items)} notizie totali.")

    try:
        html = build_email_html(news_items)
        send_email(html)
    except Exception:
        logger.exception("Errore durante l'invio dell'email")
        return 1

    logger.info("Esecuzione completata con successo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())