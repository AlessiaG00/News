import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from logger import get_logger

logger = get_logger(__name__)


def build_email_html(news_items: list[dict]) -> str:
    """
    Costruisce un layout HTML responsive moderno e pulito per la rassegna stampa.
    """
    today = date.today().strftime("%d/%m/%Y")

    grouped: dict[str, list[dict]] = {}
    for item in news_items:
        grouped.setdefault(item.get("fonte", "Sconosciuta"), []).append(item)

    sections = []
    for fonte, items in grouped.items():
        cards = []
        for item in items:
            sommario_html = (
                f'<p style="margin: 8px 0 0 0; color: #4B5563; font-size: 14px; line-height: 1.5;">{item["sommario"]}</p>'
                if item.get("sommario")
                else ""
            )
            
            cards.append(f"""
            <div style="background-color: #ffffff; border: 1px solid #E5E7EB; border-radius: 8px; padding: 18px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                <a href="{item.get('link', '#')}" target="_blank" style="font-size: 16px; font-weight: 600; color: #111827; text-decoration: none; line-height: 1.4; display: block;">
                    {item['titolo']}
                </a>
                {sommario_html}
                <div style="margin-top: 12px;">
                    <a href="{item.get('link', '#')}" target="_blank" style="display: inline-block; font-size: 12px; font-weight: 600; color: #2563EB; text-decoration: none;">
                        Leggi notizia &rarr;
                    </a>
                </div>
            </div>
            """)

        sections.append(f"""
        <div style="margin-bottom: 28px;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="background-color: #EFF6FF; color: #1D4ED8; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px;">
                    {fonte}
                </span>
            </div>
            {"".join(cards)}
        </div>
        """)

    html = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F3F4F6; padding: 24px 12px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 640px;">
                        <!-- HEADER -->
                        <tr>
                            <td style="background-color: #1E293B; border-radius: 12px 12px 0 0; padding: 32px 24px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; tracking: -0.02em;">
                                    📰 Rassegna Stampa
                                </h1>
                                <p style="color: #94A3B8; margin: 6px 0 0 0; font-size: 14px;">
                                    {today}
                                </p>
                            </td>
                        </tr>
                        
                        <!-- CONTENUTO -->
                        <tr>
                            <td style="background-color: #F8FAFC; padding: 24px 20px; border-left: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0;">
                                {''.join(sections)}
                            </td>
                        </tr>
                        
                        <!-- FOOTER -->
                        <tr>
                            <td style="background-color: #ffffff; border-radius: 0 0 12px 12px; padding: 20px; text-align: center; border: 1px solid #E2E8F0; border-top: none;">
                                <p style="color: #9CA3AF; font-size: 12px; margin: 0; line-height: 1.5;">
                                    Generato automaticamente tramite <strong>GitHub Actions</strong>.<br>
                                    Ricevi questa email perché iscritto alla newsletter interna.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


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