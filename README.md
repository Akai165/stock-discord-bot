# ⚡ FluxTrader — Discord × HyperLiquid News Trading Bot

> Un bot Discord che monitora feed RSS in tempo reale, analizza le notizie con AI (Groq / Gemini) e suggerisce operazioni di trading su **HyperLiquid** con un click.

---

## ✨ Funzionalità

| Feature | Descrizione |
|---|---|
| 📡 **RSS Polling** | Scarica automaticamente notizie da BBC, CNBC e Google News ogni N minuti |
| 🤖 **Analisi AI** | Classifica ogni notizia per sentiment, categoria e asset correlati usando **Groq** (gratis) o **Google Gemini** |
| 💬 **Discord Embed** | Pubblica embed ricchi con bottoni **BUY / SELL** cliccabili direttamente in chat |
| ⚡ **Trading su HyperLiquid** | Esegue ordini market e limit tramite l'SDK ufficiale HyperLiquid |
| 🧪 **Demo Mode** | Funziona senza credenziali HL, simulando i trade con prezzi reali di mercato |
| 🛡️ **Dry Run** | Modalità di sicurezza che simula gli ordini senza eseguirli mai |
| 📋 **Comandi manuali** | Gestione posizioni, saldo, ordini e cancellazioni via chat (`%buy`, `%sell`, ecc.) |

---

## 🏗️ Architettura

```
FluxTrader/
├── bot.py                  # Entry point — Discord client, loop polling, gestione eventi
├── config.py               # Variabili di configurazione (API keys, timing, filtri)
├── modules/
│   ├── ai_analyzer.py      # Analisi news con Groq / Gemini → JSON strutturato
│   ├── command_parser.py   # Parser comandi Discord (%buy, %sell, %positions, …)
│   ├── hl_trader.py        # Wrapper HyperLiquid SDK (ordini, posizioni, saldo)
│   └── news_fetcher.py     # Fetch RSS asincrono + deduplicazione via SHA256
├── data/
│   └── seen_news.json      # Cache hash notizie già viste (auto-generato)
├── .env.example            # Template variabili d'ambiente
├── requirements.txt        # Dipendenze Python
└── README.md
```

### Flusso dati

```
RSS Feeds ──► news_fetcher ──► filter_new_articles
                                      │
                               ai_analyzer (Groq/Gemini)
                                      │
                            ┌─────────▼──────────┐
                            │   Discord Embed     │
                            │  [🟢 BUY] [🔴 SELL] │
                            └────────┬────────────┘
                                     │ click
                               hl_trader.place_order()
                                     │
                             HyperLiquid Exchange
```

---

## 🚀 Installazione

### Prerequisiti

- Python **3.11+**
- Un bot Discord (da [Discord Developer Portal](https://discord.com/developers/applications))
- Una chiave API **Groq** gratuita da [console.groq.com](https://console.groq.com) *(consigliato)*
- *(Opzionale)* Wallet HyperLiquid per trading reale

### 1. Clona il repository

```bash
git clone https://github.com/tuo-utente/FluxTrader.git
cd FluxTrader
```

### 2. Crea e attiva il virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Installa le dipendenze

```bash
pip install -r requirements.txt
```

### 4. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` e compila i valori (vedi sezione [Configurazione](#️-configurazione)):

```env
DISCORD_TOKEN=il_tuo_token_discord
DISCORD_CHANNEL_ID=1234567890

GROQ_API_KEY=la_tua_chiave_groq

# Opzionale — lascia vuoti per Demo Mode
HL_PRIVATE_KEY=
HL_WALLET_ADDRESS=

DRY_RUN=True
USE_TESTNET=False
```

### 5. Avvia il bot

```bash
python bot.py
```

---

## ⚙️ Configurazione

### Variabili d'ambiente (`.env`)

| Variabile | Obbligatoria | Descrizione |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Token del bot Discord |
| `DISCORD_CHANNEL_ID` | ✅ | ID del canale dove postare le notizie |
| `GROQ_API_KEY` | ✅* | Chiave API Groq (gratis su [console.groq.com](https://console.groq.com)) |
| `GEMINI_API_KEY` | ✅* | Chiave API Google Gemini (alternativa a Groq) |
| `HL_PRIVATE_KEY` | ❌ | Chiave privata wallet HyperLiquid |
| `HL_WALLET_ADDRESS` | ❌ | Indirizzo wallet HyperLiquid |
| `DRY_RUN` | ❌ | `True` = simula ordini (default: `True`) |
| `USE_TESTNET` | ❌ | `True` = usa Testnet HL (default: `False`) |
| `AI_PROVIDER` | ❌ | `"groq"` o `"gemini"` (default: `"groq"`) |

> *\* Almeno uno tra `GROQ_API_KEY` e `GEMINI_API_KEY` è necessario.*

### Parametri in `config.py`

| Parametro | Default | Descrizione |
|---|---|---|
| `NEWS_POLL_INTERVAL_MINUTES` | `5` | Frequenza polling notizie (minuti) |
| `DEFAULT_TRADE_SIZE_USD` | `100` | Importo default per i trade in USD |
| `DEFAULT_SLIPPAGE` | `0.01` | Slippage per ordini market (1%) |
| `NEWS_MIN_RELEVANCE_SCORE` | `7` | Score minimo AI (1–10) per pubblicare |
| `MAX_NEWS_PER_POLL` | `5` | Notizie massime per ciclo di polling |

### Feed RSS configurati

- 🌐 **BBC** — Business, Technology, World
- 📊 **CNBC** — Finance
- 🔍 **Google News** — Business, Technology

Puoi aggiungere feed personalizzati modificando la lista `RSS_FEEDS` in `config.py`.

---

## 💬 Comandi Discord

### Trading

| Comando | Descrizione | Esempio |
|---|---|---|
| `%buy [ticker] [importo] [tipo]` | Acquista un asset | `%buy BTC 100 market` |
| `%sell [ticker] [importo] [tipo]` | Vendi un asset | `%sell ETH 50` |
| `%buy ... --limit [prezzo]` | Ordine limite di acquisto | `%buy NVDA 250 limit --limit 950.50` |
| `%sell ... --limit [prezzo]` | Ordine limite di vendita | `%sell BTC 100 --limit 60000` |

> Se l'importo è omesso usa il `DEFAULT_TRADE_SIZE_USD` configurato.
> Se il tipo è omesso usa `market`.

### Informazioni Account

| Comando | Descrizione |
|---|---|
| `%positions` | Mostra le posizioni aperte con PnL unrealizzato |
| `%balance` | Mostra equity totale, disponibile e margine usato |
| `%orders` | Lista ordini limite aperti |
| `%cancel [ticker] [order_id]` | Cancella un ordine specifico |
| `%help` | Mostra tutti i comandi disponibili |

---

## 🎯 Asset Supportati

FluxTrader è configurato per analizzare e tradare i seguenti asset su HyperLiquid:

| Categoria | Asset |
|---|---|
| 🖥️ **Tech & AI** | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, AMD, INTC, MU, TSM, ARM, SMCI, PLTR |
| 💰 **Crypto/Fintech** | COIN, MSTR, HOOD |
| 🎮 **Meme/Other** | GME, AMC, BABA |
| 🛢️ **Materie Prime** | GOLD, SILVER, WTI, BRENT, COPPER, NATGAS |
| 📈 **Indici** | SPX, NDAQ |
| ₿ **Crypto Majors** | BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK, DOGE, DOT |
| 🐸 **Altcoins/Meme** | MATIC, SHIB, PEPE, WIF, BONK, ARB, OP, SUI, APT, TIA, INJ, RNDR, NEAR, FET, WLD, ONDO |

---

## 🧠 Come funziona l'AI

Ogni articolo viene inviato al modello AI con un prompt strutturato. Il modello restituisce un JSON con:

```json
{
  "relevant": true,
  "relevance_score": 8,
  "sentiment": "bullish",
  "category": "tech",
  "suggested_assets": [
    {
      "ticker": "NVDA",
      "name": "Nvidia",
      "direction": "buy",
      "reason": "Partnership AI annunciata aumenterà domanda GPU"
    }
  ],
  "summary_it": "Riassunto della notizia in italiano."
}
```

Le notizie con `relevance_score < 7` (configurabile) vengono scartate automaticamente.

**Regole anti-allucinazione** integrate nel prompt:
- Se non c'è correlazione diretta, l'AI restituisce `[]` invece di forzare un trade
- Solo asset dalla whitelist approvata vengono suggeriti
- Correlazioni macro predefinite (es. guerra → GOLD/OIL, non azioni tech)

---

## 🔒 Modalità di Sicurezza

FluxTrader supporta tre livelli di sicurezza:

```
Demo Mode (nessuna HL_PRIVATE_KEY)
  └─► Trade simulati con prezzi reali HL API

DRY_RUN=True (chiave HL presente ma simulazione attiva)
  └─► Calcola size, mostra risultato, NON invia ordine

LIVE Mode (DRY_RUN=False + HL_PRIVATE_KEY)
  └─► Ordini eseguiti REALMENTE su HyperLiquid
```

> **ATTENZIONE:** Per passare in modalità LIVE, imposta `DRY_RUN=False` e fornisci `HL_PRIVATE_KEY`. Gli ordini saranno **reali e irreversibili**. Testa sempre prima su Testnet (`USE_TESTNET=True`).

---

## 📦 Dipendenze

```
discord.py>=2.3.0              # Discord bot framework
feedparser>=6.0.0              # Parser feed RSS
google-genai>=1.0.0            # Google Gemini AI SDK
groq>=0.5.0                    # Groq AI SDK (llama-3.3-70b)
hyperliquid-python-sdk>=0.4.0  # HyperLiquid trading SDK
eth-account>=0.11.0            # Ethereum wallet management
python-dotenv>=1.0.0           # Caricamento variabili .env
aiohttp>=3.9.0                 # HTTP client asincrono per i feed
```

---

## 🗂️ Descrizione Moduli

### `bot.py`
Entry point principale. Gestisce il client Discord, il loop di polling notizie (`@tasks.loop`), gli embed con bottoni interattivi (`TradeButtonsView`) e il routing dei comandi via `on_message`.

### `modules/ai_analyzer.py`
Analizza notizie tramite Groq (`llama-3.3-70b-versatile`) o Google Gemini (`gemini-2.0-flash`). Restituisce un dizionario strutturato con sentiment, categoria e asset suggeriti. Gestisce il cleanup dei blocchi markdown nella risposta JSON.

### `modules/hl_trader.py`
Wrapper asincrono per l'SDK HyperLiquid. Supporta:
- `place_order()` — market e limit orders
- `get_positions()` — posizioni aperte con PnL
- `get_balance()` — saldo e margine
- `get_open_orders()` — ordini limite attivi
- `cancel_order()` — cancellazione ordini

Tutte le operazioni SDK sincrone vengono eseguite in `asyncio.to_thread` per non bloccare il bot.

### `modules/news_fetcher.py`
Fetch asincrono parallelo di tutti i feed RSS tramite `aiohttp`. Deduplicazione articoli tramite hash SHA256 del titolo, persistita in `data/seen_news.json`.

### `modules/command_parser.py`
Parser robusto per comandi Discord. Gestisce argomenti opzionali, flag `--limit`, normalizzazione del ticker (uppercase), validazione importi e messaggi di errore in italiano.

---

## 📝 Licenza

Distribuito sotto licenza **MIT**. Vedi `LICENSE` per i dettagli.

---

## ⚠️ Disclaimer

Questo software è a scopo **educativo e sperimentale**. Il trading di criptovalute e derivati comporta rischi significativi di perdita del capitale. Non costituisce consiglio finanziario. Usare a proprio rischio.
