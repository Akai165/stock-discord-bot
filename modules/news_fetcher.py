"""
Modulo per il recupero delle notizie via feed RSS.
Gestisce la deduplicazione degli articoli tramite hashing dei titoli.
"""

import os
import json
import hashlib
import logging
import asyncio
from typing import List, Dict, Set

import aiohttp
import feedparser

# Import config from parent
from config import RSS_FEEDS, MAX_NEWS_PER_POLL

logger = logging.getLogger(__name__)

# Definizione del percorso del file dei salvataggi (data/seen_news.json relativo alla root del progetto)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SEEN_NEWS_FILE = os.path.join(DATA_DIR, "seen_news.json")


async def _fetch_single_feed(session: aiohttp.ClientSession, category: str, feed_url: str, source_name: str) -> List[Dict]:
    """
    Funzione di supporto per scaricare e parsare un singolo feed in modo asincrono.
    """
    try:
        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status != 200:
                logger.error(f"Errore HTTP {response.status} scaricando il feed: {feed_url}")
                return []
            
            content = await response.text()
            
            # feedparser.parse blocks, but for small feeds it's generally fine. 
            # In a heavy environment we could run it in a thread pool.
            parsed = feedparser.parse(content)
            
            articles = []
            for entry in parsed.entries:
                article = {
                    "title": getattr(entry, "title", "No Title"),
                    "description": getattr(entry, "summary", getattr(entry, "description", "")),
                    "link": getattr(entry, "link", ""),
                    "source": source_name,
                    "category": category,
                    "published": getattr(entry, "published", "")
                }
                articles.append(article)
            
            return articles
    except asyncio.TimeoutError:
        logger.error(f"Timeout durante il recupero del feed: {feed_url}")
        return []
    except Exception as e:
        logger.exception(f"Errore imprevisto parsando il feed {feed_url}: {e}")
        return []


async def fetch_all_feeds() -> list[dict]:
    """Fetch all RSS feeds defined in config.RSS_FEEDS.
    Returns list of article dicts: {title, description, link, source, category, published}
    Parse with feedparser. Use aiohttp to fetch each feed URL.
    Limit to MAX_NEWS_PER_POLL newest articles total.
    """
    all_articles = []
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # RSS_FEEDS è una lista di dict: [{"url": "...", "source": "...", "category": "..."}]
        for feed_entry in RSS_FEEDS:
            feed_url = feed_entry.get("url", "")
            source_name = feed_entry.get("source", "Unknown")
            category = feed_entry.get("category", "finance")
            
            if feed_url:
                tasks.append(_fetch_single_feed(session, category, feed_url, source_name))

        # Esegue le richieste in parallelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, list):
                all_articles.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Eccezione asincrona sollevata durante fetch_all_feeds: {res}")
                
    # Restituisce tutti gli articoli trovati — il limite verrà applicato
    # DOPO la deduplicazione in bot.py, non prima
    logger.info(f"Totale articoli recuperati dai feed: {len(all_articles)}")
    return all_articles


def _load_seen_hashes() -> set[str]:
    """Load seen news hashes from data/seen_news.json"""
    if not os.path.exists(SEEN_NEWS_FILE):
        return set()
        
    try:
        with open(SEEN_NEWS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(data)
            return set()
    except json.JSONDecodeError:
        logger.warning(f"File {SEEN_NEWS_FILE} corrotto, inizio con un set vuoto.")
        return set()
    except Exception as e:
        logger.error(f"Errore leggendo {SEEN_NEWS_FILE}: {e}")
        return set()


def _save_seen_hashes(hashes: set[str]):
    """Save hashes to data/seen_news.json. Create data/ dir if missing."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    try:
        with open(SEEN_NEWS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(hashes), f, indent=4)
    except Exception as e:
        logger.error(f"Errore salvando gli hash su {SEEN_NEWS_FILE}: {e}")


def _hash_article(title: str) -> str:
    """SHA256 hash of lowercase stripped title"""
    if not title:
        return ""
    clean_title = title.strip().lower()
    return hashlib.sha256(clean_title.encode('utf-8')).hexdigest()


def filter_new_articles(articles: list[dict]) -> list[dict]:
    """Remove already-seen articles, mark current ones as seen, save to disk.
    Returns only new articles."""
    seen_hashes = _load_seen_hashes()
    new_articles = []
    
    for article in articles:
        title = article.get("title", "")
        article_hash = _hash_article(title)
        
        if article_hash and article_hash not in seen_hashes:
            new_articles.append(article)
            seen_hashes.add(article_hash)
            
    if new_articles:
        _save_seen_hashes(seen_hashes)
        logger.info(f"Trovati {len(new_articles)} nuovi articoli, hash aggiornati.")
        
    return new_articles
