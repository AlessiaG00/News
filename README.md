# News

This project aims to create a daily newsletter covering news related to the Tech and AI world.

More specifically, the latest news article from the tech section of the following newspapers/news outlets is selected: La Repubblica, Corriere della Sera, Il Sole 24 Ore, BBC News, The Guardian, and The New York Times. 

To complement the newsletter, a dedicated section is included featuring the latest announcements from some of the leading AI companies, such as OpenAI, Anthropic, Google and DeepSeek.

```text
.
├── .github/
│   └── workflows/
│       └── daily_news.yml      # workflow GitHub Actions (esecuzione giornaliera)
├── logs/                       
├── src/
│   ├── scrapers/               
│   │   ├── anthropic.py
│   │   ├── bbc.py
│   │   ├── corriere.py
│   │   ├── deepseek.py
│   │   ├── google_deepmind.py
│   │   ├── google_research.py
│   │   ├── guardian.py
│   │   ├── NYT.py
│   │   ├── openai.py
│   │   ├── repubblica.py
│   │   └── sole24ore.py
│   ├── config.py               
│   └── scraper.py              
├── logger.py                   
├── mail.py                     
├── main.py                     
├── preview.html                
└── README.md

```