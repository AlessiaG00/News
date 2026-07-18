
import os
from dotenv import load_dotenv

load_dotenv()


# Giornali di input
FEED_URLS = {
    "ANSA": "https://www.ansa.it/sito/ansait_rss.xml",
    "Corriere": "https://xml2.corriereobjects.it/rss/homepage.xml",
    "Repubblica": "https://www.repubblica.it/rss/homepage/rss2.0.xml",
    "Sole24Ore": "https://www.ilsole24ore.com/rss/italia.xml",
    "Il_Fatto_Quotidiano": "https://www.ilfattoquotidiano.it/feed/"
}