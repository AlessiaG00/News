
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