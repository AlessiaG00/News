
import os
from dotenv import load_dotenv

load_dotenv()


# Giornali di input
FEED_URLS = {
    "ANSA": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
    "Corriere": "https://xml2.corriereobjects.it/rss/tecnologia.xml",
    "Repubblica": "https://www.repubblica.it/rss/tecnologia/rss2.0.xml",
    "Sole24Ore": "https://www.ilsole24ore.com/rss/tecnologia.xml",
    "BBC": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "Guardian": "https://www.theguardian.com/technology/rss",
    "NYT": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"
}


# --- AI Blog ---

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20

#### Open AI

OPENAI_URL = "https://openai.com/it-IT/news/company-announcements/"
OPENAI_CATEGORY_LABEL = "Azienda"
OPENAI_CANDIDATES_TO_CHECK = 5
OPENAI_ARTICLE_PATTERN = r"^https://openai\.com/index/[^/]+/?$"

MESI_IT = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}

### ANTHROPIC

# ============================================================
# ANTHROPIC — da incollare in src/config.py
# (HEADERS e REQUEST_TIMEOUT sono già stati aggiunti con OpenAI)
# ============================================================

ANTHROPIC_URL = "https://www.anthropic.com/news"
ANTHROPIC_CATEGORY_FILTER = "Announcements"

ANTHROPIC_KNOWN_CATEGORIES = [
    "Announcements",
    "Societal Impacts",
    "Policy",
    "Product",
    "Features",
    "Alignment",
    "Research",
    "Commitments",
]

ANTHROPIC_DATE_PATTERN = (
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}"
)

ANTHROPIC_ARTICLE_PATTERN = r"^https://www\.anthropic\.com/news/[^/?#]+/?$"

MESI_EN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# --- Google Research ------------------------------------------

GOOGLE_RESEARCH_RSS_URL = "https://research.google/blog/rss/"
GOOGLE_RESEARCH_CATEGORY_FILTER = None

# --- Google DeepMind ------------------------------------------

DEEPMIND_RSS_URL = "https://deepmind.google/blog/rss.xml"

### DEEPSEEK 

DEEPSEEK_ENTRY_URL = "https://api-docs.deepseek.com/news/news260424"
DEEPSEEK_NEWS_LINK_PATTERN = r"^https://api-docs\.deepseek\.com/news/news\d+/?$"

DEEPSEEK_DATE_SUFFIX_PATTERN = r"\s+(\d{4})/(\d{2})/(\d{2})\s*$"


### EMAIL 
EMAIL_SEZIONI = [
    {
        "titolo": "📰 Italia",
        "colore": "#1a56a0",
        "fonti": ["ANSA", "Corriere", "Repubblica", "Sole24Ore"],
    },
    {
        "titolo": "🌍 World",
        "colore": "#b45309",
        "fonti": ["BBC News", "The Guardian", "NYT"],
    },
]
 
# Tutte le fonti non elencate sopra finiscono qui (i blog AI)
EMAIL_SEZIONE_RESTANTI = {
    "titolo": "🤖 AI",
    "colore": "#6d28d9",
}