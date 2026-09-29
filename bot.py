"""
bot.py — Entry point per FluxTrader, il News Trading Discord Bot.

FluxTrader:
1. Ogni N minuti scarica notizie da RSS feed
2. Le analizza con Groq / Gemini AI per estrarre asset correlati
3. Posta la notizia su Discord con bottoni di trade rapido
4. Accetta comandi manuali %buy/%sell per trading su HyperLiquid
"""

import asyncio
import logging
import discord
from discord.ext import tasks
from discord import app_commands

from config import (
    DISCORD_TOKEN,
    DISCORD_CHANNEL_ID,
    NEWS_POLL_INTERVAL_MINUTES,
    MAX_NEWS_PER_POLL,
    DEFAULT_TRADE_SIZE_USD,
    DRY_RUN,
    USE_TESTNET,
    SENTIMENT_EMOJI,
    CATEGORY_EMOJI,
)
from modules.news_fetcher import fetch_all_feeds, filter_new_articles
from modules.ai_analyzer import analyze_news, build_discord_embed
from modules.hl_trader import HyperLiquidTrader
from modules.command_parser import parse_message, format_help_message, TradeCommand, InfoCommand

# ─── LOGGING ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fluxtrader")

# ─── DISCORD CLIENT ──────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ─── TRADER INSTANCE ─────────────────────────────────────
trader = HyperLiquidTrader()


# ═══════════════════════════════════════════════════════════
#  DISCORD BUTTONS — Trade rapido sotto ogni notizia
# ═══════════════════════════════════════════════════════════

class TradeButton(discord.ui.Button):
    """A single trade button (BUY or SELL) for a specific asset."""

    def __init__(self, ticker: str, direction: str, asset_name: str):
        self.ticker = ticker
        self.direction = direction  # "buy" or "sell"

        if direction == "buy":
            label = f"🟢 BUY {ticker}"
            style = discord.ButtonStyle.green
        else:
            label = f"🔴 SELL {ticker}"
            style = discord.ButtonStyle.red

        super().__init__(label=label, style=style, custom_id=f"trade_{direction}_{ticker}")
        self.asset_name = asset_name

    async def callback(self, interaction: discord.Interaction):
        """Execute trade when button is pressed."""
        await interaction.response.defer(ephemeral=True)

        is_buy = self.direction == "buy"
        result = await trader.place_order(
            ticker=self.ticker,
            is_buy=is_buy,
            usd_amount=DEFAULT_TRADE_SIZE_USD,
            order_type="market",
        )

        if result.get("error"):
            embed = discord.Embed(
                title="❌ Errore nell'ordine",
                description=f"```{result['error']}```",
                color=discord.Color.dark_red(),
            )
        else:
            dry_tag = " [DRY RUN]" if result.get("dry_run") else ""
            side_emoji = "📈" if is_buy else "📉"
            embed = discord.Embed(
                title=f"✅ Ordine eseguito{dry_tag}",
                color=discord.Color.green() if is_buy else discord.Color.red(),
            )
            embed.add_field(name="Operazione", value=f"{side_emoji} {'BUY' if is_buy else 'SELL'} {self.ticker}", inline=True)
            embed.add_field(name="Tipo", value=result.get("order_type", "market").upper(), inline=True)
            embed.add_field(name="Importo", value=f"${result.get('usd_amount', DEFAULT_TRADE_SIZE_USD):.2f}", inline=True)
            if result.get("size"):
                embed.add_field(name="Size", value=f"{result['size']} {self.ticker}", inline=True)
            if result.get("price"):
                embed.add_field(name="Prezzo", value=f"${result['price']:,.2f}", inline=True)
            if result.get("order_id"):
                embed.add_field(name="Order ID", value=str(result["order_id"]), inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)


class TradeButtonsView(discord.ui.View):
    """View containing all trade buttons for a news article."""

    def __init__(self, suggested_assets: list[dict]):
        super().__init__(timeout=None)  # Buttons don't expire

        # Add BUY and SELL buttons for each suggested asset (max 5 pairs = 10 buttons)
        for asset in suggested_assets[:5]:
            ticker = asset.get("ticker", "BTC")
            name = asset.get("name", ticker)
            direction = asset.get("direction", "buy")

            # Always add the suggested direction button first
            self.add_item(TradeButton(ticker=ticker, direction=direction, asset_name=name))

            # Add the opposite direction too
            opposite = "sell" if direction == "buy" else "buy"
            self.add_item(TradeButton(ticker=ticker, direction=opposite, asset_name=name))


# ═══════════════════════════════════════════════════════════
#  NEWS EMBED BUILDER
# ═══════════════════════════════════════════════════════════

def create_news_embed(embed_data: dict) -> discord.Embed:
    """Create a rich Discord embed from the analyzed news data."""

    sentiment = embed_data.get("sentiment", "neutral")
    sentiment_emoji = SENTIMENT_EMOJI.get(sentiment, "🟡")
    category = embed_data.get("category", "finance")
    category_emoji = CATEGORY_EMOJI.get(category, "📰")

    # Color based on sentiment
    color_map = {
        "bullish": discord.Color.green(),
        "bearish": discord.Color.red(),
        "neutral": discord.Color.gold(),
    }

    embed = discord.Embed(
        title=f"📰 {embed_data.get('title', 'Notizia')}",
        url=embed_data.get("url", ""),
        description=embed_data.get("summary_it", ""),
        color=color_map.get(sentiment, discord.Color.blurple()),
    )

    # Header field with category and sentiment
    embed.add_field(
        name="Classificazione",
        value=f"{category_emoji} **{category.upper()}** — {sentiment_emoji} **{sentiment.upper()}**",
        inline=False,
    )

    # Suggested assets
    assets_text = ""
    for asset in embed_data.get("suggested_assets", []):
        direction_emoji = "📈" if asset.get("direction") == "buy" else "📉"
        assets_text += f"{direction_emoji} **{asset['ticker']}** ({asset.get('name', '')}) — {asset.get('reason', '')}\n"

    if assets_text:
        embed.add_field(name="🎯 Asset Suggeriti", value=assets_text, inline=False)

    # Command hint
    tickers = [a["ticker"] for a in embed_data.get("suggested_assets", [])[:3]]
    if tickers:
        hint = f"```%buy {tickers[0]} {DEFAULT_TRADE_SIZE_USD} market```"
        embed.add_field(name="⚡ Comando rapido", value=hint, inline=False)

    # Footer
    source = embed_data.get("source", "RSS")
    score = embed_data.get("relevance_score", "?")
    dry_tag = " | 🧪 DRY RUN" if DRY_RUN else " | ⚡ LIVE"
    embed.set_footer(text=f"📡 {source} | ⭐ Relevance: {score}/10{dry_tag}")

    return embed


# ═══════════════════════════════════════════════════════════
#  NEWS POLLING LOOP
# ═══════════════════════════════════════════════════════════

@tasks.loop(minutes=NEWS_POLL_INTERVAL_MINUTES)
async def news_poll_loop():
    """Main loop: fetch news → analyze with Gemini → post to Discord."""
    logger.info("🔄 Inizio ciclo polling notizie...")

    try:
        # 1. Fetch RSS feeds
        articles = await fetch_all_feeds()
        logger.info(f"📡 Trovati {len(articles)} articoli dai feed RSS")

        # 2. Filter out already-seen articles
        new_articles = filter_new_articles(articles)
        # Applica il limite DOPO il filtro (non prima — altrimenti i già-visti bloccano i nuovi)
        new_articles = new_articles[:MAX_NEWS_PER_POLL]
        logger.info(f"🆕 {len(new_articles)} nuovi articoli da analizzare")

        if not new_articles:
            logger.info("Nessuna notizia nuova, skip ciclo.")
            return

        # 3. Get Discord channel
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            logger.error(f"❌ Canale Discord {DISCORD_CHANNEL_ID} non trovato!")
            return

        # 4. Analyze each article with Gemini and post
        posted = 0
        for article in new_articles:
            try:
                analysis = await analyze_news(article["title"], article.get("description", ""))

                if analysis is None:
                    logger.debug(f"Skip (non rilevante): {article['title'][:60]}")
                    continue

                # Build embed data
                embed_data = build_discord_embed(article, analysis)

                # Create Discord embed and buttons
                embed = create_news_embed(embed_data)
                view = TradeButtonsView(analysis.get("suggested_assets", []))

                # Post to Discord
                await channel.send(embed=embed, view=view)
                posted += 1
                logger.info(f"✅ Postato: {article['title'][:60]}...")

                # Small delay between posts to avoid spam
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Errore analisi articolo '{article.get('title', '?')[:40]}': {e}")
                continue

        logger.info(f"📊 Ciclo completato: {posted} notizie postate su Discord")

    except Exception as e:
        logger.error(f"❌ Errore nel polling loop: {e}", exc_info=True)


@news_poll_loop.before_loop
async def before_news_poll():
    """Wait until the Discord bot is ready before starting the loop."""
    await client.wait_until_ready()
    logger.info(f"⏰ News polling attivo ogni {NEWS_POLL_INTERVAL_MINUTES} minuti")


# ═══════════════════════════════════════════════════════════
#  COMMAND HANDLER
# ═══════════════════════════════════════════════════════════

@client.event
async def on_message(message: discord.Message):
    """Handle incoming Discord messages for trade commands."""

    # Ignore bot's own messages
    if message.author == client.user:
        return

    # Only process messages starting with %
    if not message.content.startswith("%"):
        return

    content = message.content.strip()

    # ─── %help ────────────────────────────────────────────
    if content.lower() == "%help":
        embed = discord.Embed(
            title="📖 Comandi disponibili",
            description=format_help_message(),
            color=discord.Color.blurple(),
        )
        await message.reply(embed=embed)
        return

    # ─── Parse command ────────────────────────────────────
    try:
        cmd = parse_message(content)
    except ValueError as e:
        embed = discord.Embed(
            title="❌ Errore nel comando",
            description=str(e),
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="💡 Aiuto", value="Usa `%help` per vedere i comandi disponibili")
        await message.reply(embed=embed)
        return

    if cmd is None:
        return

    # ─── Trade Commands (%buy / %sell) ────────────────────
    if isinstance(cmd, TradeCommand):
        # Send typing indicator
        async with message.channel.typing():
            is_buy = cmd.action == "buy"
            result = await trader.place_order(
                ticker=cmd.ticker,
                is_buy=is_buy,
                usd_amount=cmd.amount_usd,
                order_type=cmd.order_type,
                limit_price=cmd.limit_price,
            )

        if result.get("error"):
            embed = discord.Embed(
                title="❌ Errore nell'ordine",
                description=f"```{result['error']}```",
                color=discord.Color.dark_red(),
            )
        else:
            dry_tag = " [DRY RUN]" if result.get("dry_run") else ""
            side_emoji = "📈" if is_buy else "📉"
            embed = discord.Embed(
                title=f"✅ Ordine eseguito{dry_tag}",
                color=discord.Color.green() if is_buy else discord.Color.red(),
            )
            embed.add_field(name="Operazione", value=f"{side_emoji} {'BUY' if is_buy else 'SELL'} {cmd.ticker}", inline=True)
            embed.add_field(name="Tipo", value=cmd.order_type.upper(), inline=True)
            embed.add_field(name="Importo", value=f"${cmd.amount_usd:.2f}", inline=True)
            if result.get("size"):
                embed.add_field(name="Size", value=f"{result['size']} {cmd.ticker}", inline=True)
            if result.get("price"):
                embed.add_field(name="Prezzo", value=f"${result['price']:,.2f}", inline=True)
            if result.get("order_id"):
                embed.add_field(name="Order ID", value=str(result["order_id"]), inline=True)
            if cmd.order_type == "limit" and cmd.limit_price:
                embed.add_field(name="Limite", value=f"${cmd.limit_price:,.2f}", inline=True)

        await message.reply(embed=embed)
        return

    # ─── Info Commands (%positions, %balance, %orders, %cancel) ─
    if isinstance(cmd, InfoCommand):

        if cmd.action == "positions":
            async with message.channel.typing():
                positions = await trader.get_positions()

            if not positions:
                embed = discord.Embed(
                    title="📊 Posizioni Aperte",
                    description="Nessuna posizione aperta." + (" (DRY RUN)" if DRY_RUN else ""),
                    color=discord.Color.light_grey(),
                )
            else:
                embed = discord.Embed(
                    title="📊 Posizioni Aperte",
                    color=discord.Color.blue(),
                )
                for pos in positions:
                    pnl = pos.get("unrealized_pnl", 0)
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    embed.add_field(
                        name=f"{pos['ticker']}",
                        value=(
                            f"Size: {pos['size']}\n"
                            f"Entry: ${pos.get('entry_price', 0):,.2f}\n"
                            f"{pnl_emoji} PnL: ${pnl:,.2f}"
                        ),
                        inline=True,
                    )
            await message.reply(embed=embed)

        elif cmd.action == "balance":
            async with message.channel.typing():
                balance = await trader.get_balance()

            embed = discord.Embed(
                title="💰 Balance Account",
                color=discord.Color.gold(),
            )
            dry_tag = " (DRY RUN)" if DRY_RUN else ""
            embed.add_field(name="Equity Totale", value=f"${balance.get('total_equity', 0):,.2f}{dry_tag}", inline=True)
            embed.add_field(name="Disponibile", value=f"${balance.get('available_balance', 0):,.2f}", inline=True)
            embed.add_field(name="Margine Usato", value=f"${balance.get('margin_used', 0):,.2f}", inline=True)
            await message.reply(embed=embed)

        elif cmd.action == "orders":
            async with message.channel.typing():
                orders = await trader.get_open_orders()

            if not orders:
                embed = discord.Embed(
                    title="📋 Ordini Aperti",
                    description="Nessun ordine aperto." + (" (DRY RUN)" if DRY_RUN else ""),
                    color=discord.Color.light_grey(),
                )
            else:
                embed = discord.Embed(
                    title="📋 Ordini Aperti",
                    color=discord.Color.blue(),
                )
                for order in orders:
                    side_emoji = "📈" if order.get("side") == "buy" else "📉"
                    embed.add_field(
                        name=f"{side_emoji} {order['ticker']}",
                        value=(
                            f"Size: {order['size']}\n"
                            f"Prezzo: ${order.get('price', 0):,.2f}\n"
                            f"ID: {order.get('order_id', '?')}"
                        ),
                        inline=True,
                    )
            await message.reply(embed=embed)

        elif cmd.action == "cancel":
            if not cmd.ticker or not cmd.order_id:
                embed = discord.Embed(
                    title="❌ Errore",
                    description="Uso: `%cancel [TICKER] [ORDER_ID]`",
                    color=discord.Color.dark_red(),
                )
            else:
                async with message.channel.typing():
                    result = await trader.cancel_order(cmd.ticker, cmd.order_id)

                if result.get("error"):
                    embed = discord.Embed(
                        title="❌ Errore cancellazione",
                        description=f"```{result['error']}```",
                        color=discord.Color.dark_red(),
                    )
                else:
                    embed = discord.Embed(
                        title="✅ Ordine cancellato",
                        description=f"Order ID `{cmd.order_id}` su {cmd.ticker} cancellato.",
                        color=discord.Color.green(),
                    )
            await message.reply(embed=embed)

        return


# ═══════════════════════════════════════════════════════════
#  BOT STARTUP
# ═══════════════════════════════════════════════════════════

@client.event
async def on_ready():
    """Called when bot is connected and ready."""
    logger.info(f"{'='*50}")
    logger.info(f"🤖 Bot connesso come: {client.user}")
    logger.info(f"📡 Canale notizie: {DISCORD_CHANNEL_ID}")
    logger.info(f"⏰ Polling ogni: {NEWS_POLL_INTERVAL_MINUTES} min")
    logger.info(f"💵 Trade default: ${DEFAULT_TRADE_SIZE_USD}")
    logger.info(f"{'🧪 TESTNET (soldi finti)' if USE_TESTNET else '⚡ MAINNET (soldi REALI)'}")
    logger.info(f"{'🧪 MODALITA DRY RUN (simulazione)' if DRY_RUN else '🔴 MODALITA LIVE (ordini eseguiti)'}")
    logger.info(f"{'='*50}")

    # Start the news polling loop
    if not news_poll_loop.is_running():
        news_poll_loop.start()


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    """Entry point."""
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN non configurato! Copia .env.example in .env e inserisci il token.")
        return

    logger.info("🚀 Avvio FluxTrader — News Trading Bot...")
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
