import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date
from html import escape

from logger import get_logger
from src.config import EMAIL_SEZIONE_RESTANTI, EMAIL_SEZIONI

logger = get_logger(__name__)

FONT = "Arial, Helvetica, sans-serif"


def _render_item(item: dict, colore: str) -> str:
    """Genera il blocco di un singolo articolo. Tutti i campi sono opzionali
    tranne il titolo (se manca, usa un testo di ripiego)."""

    fonte = escape(str(item.get("fonte") or "Sconosciuta"))
    titolo = escape(str(item.get("titolo") or "(senza titolo)"))
    link = str(item.get("link") or "").strip()
    sommario = item.get("sommario")
    autore = item.get("autore")
    pubblicato = item.get("pubblicato")

    # Titolo: link cliccabile solo se l'URL è valido
    if link.startswith(("http://", "https://")):
        titolo_html = (
            f'<a href="{escape(link, quote=True)}" '
            f'style="font-weight:bold; text-decoration:none; color:#111827;">'
            f"{titolo}</a>"
        )
    else:
        titolo_html = f'<span style="font-weight:bold; color:#111827;">{titolo}</span>'

    sommario_html = ""
    if sommario:
        sommario_html = (
            f'<div style="color:#4b5563; font-size:14px; line-height:1.45; margin-top:6px;">'
            f"{escape(str(sommario))}</div>"
        )

    # Riga "autore · data": mostra solo le parti presenti
    meta_parts = [escape(str(x)) for x in (autore, pubblicato) if x]
    meta_html = ""
    if meta_parts:
        meta_html = (
            f'<div style="color:#9ca3af; font-size:12px; margin-top:6px;">'
            f'{" &middot; ".join(meta_parts)}</div>'
        )

    return f"""
        <tr>
          <td style="padding:14px 20px; border-bottom:1px solid #e5e7eb; font-family:{FONT};">
            <div style="font-size:11px; font-weight:bold; letter-spacing:0.8px; text-transform:uppercase; color:{colore};">{fonte}</div>
            <div style="font-size:16px; line-height:1.35; margin-top:4px;">{titolo_html}</div>
            {sommario_html}
            {meta_html}
          </td>
        </tr>
    """


def _raggruppa_per_sezione(news_items: list[dict]) -> list[tuple[str, str, list[dict]]]:
    """
    Assegna ogni articolo a una sezione in base al nome della fonte
    (senza distinguere maiuscole/minuscole). Le fonti non elencate in
    EMAIL_SEZIONI finiscono nella sezione EMAIL_SEZIONE_RESTANTI.
    Restituisce [(titolo, colore, [articoli]), ...] già ordinato.
    """
    posizione = {}  # nome fonte (minuscolo) -> (indice sezione, posizione)
    for i, sezione in enumerate(EMAIL_SEZIONI):
        for pos, fonte in enumerate(sezione["fonti"]):
            posizione[fonte.casefold()] = (i, pos)

    per_sezione = [[] for _ in EMAIL_SEZIONI]
    restanti = []

    for item in news_items:
        chiave = str(item.get("fonte") or "").casefold()
        if chiave in posizione:
            i, pos = posizione[chiave]
            per_sezione[i].append((pos, item))
        else:
            restanti.append(item)

    risultato = []
    for sezione, voci in zip(EMAIL_SEZIONI, per_sezione):
        voci.sort(key=lambda v: v[0])   # ordine della lista in config
        risultato.append((sezione["titolo"], sezione["colore"], [v[1] for v in voci]))

    risultato.append(
        (EMAIL_SEZIONE_RESTANTI["titolo"], EMAIL_SEZIONE_RESTANTI["colore"], restanti)
    )
    return risultato


def _render_sezione(titolo: str, colore: str, items: list[dict]) -> str:
    """Intestazione colorata + articoli. Stringa vuota se non c'è nulla."""

    rows = []
    for item in items:
        try:
            rows.append(_render_item(item, colore))
        except Exception:
            # Un articolo problematico non deve bloccare tutta l'email
            fonte = item.get("fonte", "Sconosciuta") if isinstance(item, dict) else "?"
            logger.exception(f"{fonte}: articolo non renderizzabile, saltato")

    if not rows:
        return ""

    rows_html = "".join(rows)

    return f"""
        <tr>
          <td style="background-color:{colore}; color:#ffffff; padding:10px 20px; font-family:{FONT}; font-size:15px; font-weight:bold;">
            {escape(titolo)}
          </td>
        </tr>
        {rows_html}
    """


def build_email_html(news_items: list[dict]) -> str:
    """
    news_items: lista di dict con le chiavi:
        fonte, titolo, link, sommario, autore, pubblicato
    (tutte opzionali: se mancano, quella riga non viene mostrata)

    Layout: una sezione per gruppo di fonti (vedi EMAIL_SEZIONI in config.py).
    """
    today = date.today().strftime("%d/%m/%Y")

    sezioni_html = "".join(
        _render_sezione(titolo, colore, items)
        for titolo, colore, items in _raggruppa_per_sezione(news_items)
    )

    if not sezioni_html:
        sezioni_html = f"""
        <tr>
          <td style="padding:24px 20px; font-family:{FONT}; font-size:14px; color:#6b7280;">
            Nessuna notizia raccolta oggi.
          </td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body style="margin:0; padding:0; background-color:#f3f4f6;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6;">
      <tr>
        <td align="center" style="padding:20px 10px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px; background-color:#ffffff;">
            <tr>
              <td style="padding:24px 20px 16px 20px; font-family:{FONT};">
                <div style="font-size:22px; font-weight:bold; color:#111827;">📰 Rassegna stampa Tech</div>
                <div style="font-size:13px; color:#6b7280; margin-top:4px;">{today}</div>
              </td>
            </tr>
            {sezioni_html}
            <tr>
              <td style="padding:16px 20px; font-family:{FONT}; font-size:12px; color:#9ca3af;">
                Email generata automaticamente da GitHub Actions.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

def send_email(html_content: str, subject: str | None = None) -> None:
    smtp_server = os.environ["SMTP_SERVER"]          
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]           

    # Supporta uno o più destinatari separati da virgola
    recipients = [r.strip() for r in os.environ["EMAIL_RECIPIENT"].split(",") if r.strip()]

    subject = subject or f"Rassegna stampa - {date.today().strftime('%d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients) 
    msg.attach(MIMEText(html_content, "html"))

    logger.info(f"Connessione a {smtp_server}:{smtp_port} per invio email a {len(recipients)} destinatari")

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())  # lista, non stringa singola

    logger.info("Email inviata con successo.")