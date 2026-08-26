"""
Costruzione e invio dell'email giornaliera con le notizie raccolte.

Le credenziali NON vanno mai scritte nel codice: si leggono da variabili
d'ambiente, che in GitHub Actions arrivano dai "Repository Secrets".
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from logger import get_logger

logger = get_logger(__name__)


def build_email_html(news_items: list[dict]) -> str:
    """
    news_items: lista di dict con almeno le chiavi:
        fonte, titolo, link, sommario (sommario opzionale)
    """
    today = date.today().strftime("%d/%m/%Y")

    # Raggruppa le notizie per fonte
    grouped: dict[str, list[dict]] = {}
    for item in news_items:
        grouped.setdefault(item.get("fonte", "Sconosciuta"), []).append(item)

    sections = []
    for fonte, items in grouped.items():
        rows = "".join(
            f"""
            <li style="margin-bottom:10px;">
                <a href="{item.get('link', '#')}" style="font-weight:bold; text-decoration:none; color:#1a0dab;">
                    {item['titolo']}
                </a>
                {f"<div style='color:#555; font-size:14px;'>{item['sommario']}</div>" if item.get('sommario') else ""}
            </li>
            """
            for item in items
        )
        sections.append(f"""
            <h2 style="border-bottom:2px solid #333; padding-bottom:4px;">{fonte}</h2>
            <ul style="list-style:none; padding-left:0;">{rows}</ul>
        """)

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width:700px; margin:auto;">
        <h1>📰 Rassegna stampa del {today}</h1>
        {''.join(sections)}
        <hr>
        <p style="color:#999; font-size:12px;">
            Email generata automaticamente da GitHub Actions.
        </p>
      </body>
    </html>
    """
    return html


def send_email(html_content: str, subject: str | None = None) -> None:
    smtp_server = os.environ["SMTP_SERVER"]          # es. smtp.gmail.com
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]           # per Gmail: App Password
    recipient = os.environ["EMAIL_RECIPIENT"]

    subject = subject or f"Rassegna stampa - {date.today().strftime('%d/%m/%Y')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_content, "html"))

    logger.info(f"Connessione a {smtp_server}:{smtp_port} per invio email a {recipient}")

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    logger.info("Email inviata con successo.")