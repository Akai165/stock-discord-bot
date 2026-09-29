"""
AI Analyzer module for processing news articles using Google Gemini API.
Suggests trading assets based on the news content.
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any
from google import genai
from groq import AsyncGroq

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    AI_PROVIDER,
    NEWS_MIN_RELEVANCE_SCORE,
    NEWS_CATEGORIES,
    SENTIMENT_EMOJI,
    CATEGORY_EMOJI
)

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize logger
logger = logging.getLogger(__name__)

async def analyze_news(title: str, description: str) -> Optional[Dict[str, Any]]:
    """
    Send news to Gemini for analysis.
    Returns parsed JSON dict or None if irrelevant.
    
    Args:
        title (str): News article title.
        description (str): News article description.
        
    Returns:
        Optional[Dict[str, Any]]: Parsed JSON dict or None if irrelevant or error.
    """
    prompt = f"""Analizza questa notizia e rispondi SOLO con JSON valido, nessun testo extra.

Titolo: {title}
Descrizione: {description}

JSON format:
{{
  "relevant": true/false,
  "relevance_score": 1-10,
  "sentiment": "bullish" | "bearish" | "neutral",
  "category": "finance" | "tech" | "geopolitics" | "war" | "commodities" | "bonds",
  "suggested_assets": [
    {{"ticker": "BTC", "name": "Bitcoin", "direction": "buy" | "sell", "reason": "..."}}
  ],
  "summary_it": "Riassunto in italiano in 1-2 frasi"
}}

REGOLE STRICT PER suggested_assets (EVITA ALLUCINAZIONI):
1. SE NON C'È UNA CORRELAZIONE DIRETTA, RESTITUISCI UNA LISTA VUOTA []. Non forzare mai un trade.
2. REGOLA 1:1 SULLE AZIENDE: Se la notizia riguarda un'azienda specifica, puoi suggerire il trade SOLO SE l'azienda è nella Whitelist qui sotto. Se l'azienda non è in lista (es. Bethesda, Ubisoft, Nintendo, Ferrari), RESTITUISCI []. NON suggerire NVDA, BTC o competitor a caso.
3. Seleziona SOLO tra i seguenti asset supportati (Whitelist Completa):
   - Azioni Tech & AI: AAPL (Apple), MSFT (Microsoft), GOOGL (Google/Alphabet), AMZN (Amazon), META (Facebook), NVDA (Nvidia), TSLA (Tesla), AMD, INTC (Intel), MU (Micron), TSM, ARM, SMCI, PLTR (Palantir)
   - Azioni Crypto/Fintech: COIN (Coinbase), MSTR (MicroStrategy), HOOD (Robinhood)
   - Azioni varie/Meme: GME (GameStop), AMC, BABA (Alibaba)
   - Materie prime: GOLD (Oro), SILVER (Argento), WTI (Petrolio USA), BRENT (Petrolio Europa), COPPER (Rame), NATGAS (Gas Naturale)
   - Indici/Macro: SPX (S&P 500), NDAQ (Nasdaq)
   - Crypto Majors & Altcoins: BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK, DOGE, DOT, MATIC, SHIB, PEPE, WIF, BONK, ARB, OP, SUI, APT, TIA, INJ, RNDR, NEAR, FET, WLD, ONDO
4. Correlazioni Macro/Geopolitiche:
   - Guerra / Tensioni globali -> GOLD, BRENT, WTI (MAI azioni specifiche, MAI crypto a meno che non menzionate)
   - Tassi d'interesse FED / Inflazione USA -> SPX, NDAQ, BTC, GOLD
   - Semiconduttori (settore generale) -> NVDA, AMD, TSM
"""

    try:
        if AI_PROVIDER.lower() == "groq":
            if not GROQ_API_KEY:
                logger.error("GROQ_API_KEY non configurata nel file .env")
                return None
            
            groq_client = AsyncGroq(api_key=GROQ_API_KEY)
            response = await groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=GROQ_MODEL,
                temperature=0.1
            )
            raw_text = response.choices[0].message.content
        else:
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY non configurata nel file .env")
                return None
            
            client = genai.Client(api_key=GEMINI_API_KEY)
            # Run synchronous API call in a separate thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt
            )
            raw_text = response.text
            
        if not raw_text:
            logger.warning("Empty response received from Gemini.")
            return None

        # Clean up markdown code blocks if present
        json_text = raw_text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        elif json_text.startswith("```"):
            json_text = json_text[3:]
            
        if json_text.endswith("```"):
            json_text = json_text[:-3]
            
        json_text = json_text.strip()

        # Parse the JSON response
        try:
            analysis = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AI: {e}. Raw text: {raw_text}")
            return None
        
        # Check relevance
        relevance_score = analysis.get("relevance_score", 0)
        if relevance_score < NEWS_MIN_RELEVANCE_SCORE:
            logger.debug(f"News irrelevant. Score: {relevance_score} < {NEWS_MIN_RELEVANCE_SCORE}")
            return None
            
        # Check category
        category = analysis.get("category", "")
        valid_categories = NEWS_CATEGORIES + ['commodities', 'bonds']
        if category not in valid_categories:
            logger.debug(f"News category '{category}' not in valid categories.")
            return None
            
        return analysis

    except Exception as e:
        logger.error(f"Error during AI API call ({AI_PROVIDER}): {e}")
        return None

def build_discord_embed(article: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a structured dict with all info needed for the Discord embed.
    
    Args:
        article (Dict[str, Any]): Raw news article data.
        analysis (Dict[str, Any]): Analysis data from Gemini.
        
    Returns:
        Dict[str, Any]: Dictionary ready to be formatted into a Discord Embed.
    """
    sentiment = analysis.get("sentiment", "neutral")
    category = analysis.get("category", "unknown")
    
    # Retrieve emojis from config or use defaults
    sentiment_emoji = SENTIMENT_EMOJI.get(sentiment, "➖")
    category_emoji = CATEGORY_EMOJI.get(category, "📰")

    return {
        "title": article.get("title", "No Title"),
        "description": article.get("description", "No Description"),
        "url": article.get("link", ""),
        "source": article.get("source", "Unknown Source"),
        "category": category,
        "category_emoji": category_emoji,
        "sentiment": sentiment,
        "sentiment_emoji": sentiment_emoji,
        "summary_it": analysis.get("summary_it", ""),
        "suggested_assets": analysis.get("suggested_assets", []),
        "relevance_score": analysis.get("relevance_score", 0)
    }
