"""
config.py — Tutte le variabili configurabili di FluxTrader.
Modifica i valori qui per personalizzare il comportamento del bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── CHIAVI API ────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HL_PRIVATE_KEY = os.getenv("HL_PRIVATE_KEY", "")
HL_WALLET_ADDRESS = os.getenv("HL_WALLET_ADDRESS", "")

# ─── MODALITA' BOT ────────────────────────────────────────
# True = simula i trade senza eseguirli (SAFE per testing)
# False = esegue trade REALI su HyperLiquid
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")

# True = usa il Testnet HL (soldi finti, interfaccia reale)
# False = usa il Mainnet HL (soldi VERI)
USE_TESTNET = os.getenv("USE_TESTNET", "False").lower() in ("true", "1", "yes")

# ─── TIMING ───────────────────────────────────────────────
NEWS_POLL_INTERVAL_MINUTES = 5  # Frequenza polling notizie (cambia qui!)

# ─── TRADING DEFAULTS ────────────────────────────────────
DEFAULT_TRADE_SIZE_USD = 100    # Bet di default in USD
DEFAULT_SLIPPAGE = 0.01         # 1% slippage per ordini market

# ─── FILTRI NOTIZIE ──────────────────────────────────────
NEWS_CATEGORIES = ["finance", "tech", "geopolitics", "war"]
NEWS_MIN_RELEVANCE_SCORE = 7   # Score Gemini 1-10, minimo per postare
MAX_NEWS_PER_POLL = 5           # Notizie massime per ciclo di polling

# ─── RSS FEEDS ───────────────────────────────────────────
RSS_FEEDS = [
    # BBC
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml", "source": "BBC", "category": "finance"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "source": "BBC", "category": "tech"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "source": "BBC", "category": "geopolitics"},
    # Google News
    {"url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en", "source": "Google News", "category": "finance"},
    {"url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en", "source": "Google News", "category": "tech"},
    # CNBC
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "source": "CNBC", "category": "finance"},
]

# ─── GEMINI MODEL ────────────────────────────────────────
# ─── AI MODEL ────────────────────────────────────────────
# Provider attivo: "groq" (gratis, consigliato) o "gemini" (richiede billing dall'UE)
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq")
GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"   # Modello Groq gratuito, molto capace

# ─── EMOJI / FORMATTAZIONE ───────────────────────────────
SENTIMENT_EMOJI = {
    "bullish": "🟢",
    "bearish": "🔴",
    "neutral": "🟡",
}
CATEGORY_EMOJI = {
    "finance": "💰",
    "tech": "🖥️",
    "geopolitics": "🌍",
    "war": "⚔️",
    "commodities": "🛢️",
    "bonds": "📜",
}
