"""
Genera l'HTML dell'email SENZA inviarla, usando gli articoli veri
raccolti dagli scraper. Utile per controllare contenuto e layout prima
di far partire il workflow.

Da mettere nella root della repo, accanto a main.py.
Esecuzione:  python preview_email.py
Poi apri preview.html nel browser.
"""

from mail import build_email_html
from src.scraper import get_all_articles


def main() -> int:
    print("Eseguo tutti gli scraper (può richiedere qualche secondo)...")
    articoli = get_all_articles()

    print(f"Raccolti {len(articoli)} articoli su {len(set(a.get('fonte') for a in articoli)) or 0} fonti diverse.")

    html = build_email_html(articoli)

    with open("preview.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Creato preview.html: aprilo nel browser per vedere l'email.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())