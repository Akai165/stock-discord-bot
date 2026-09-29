"""
Module for HyperLiquid trading operations.
Wraps the HyperLiquid Python SDK for use in a Discord bot.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from config import HL_PRIVATE_KEY, HL_WALLET_ADDRESS, DRY_RUN, DEFAULT_SLIPPAGE, USE_TESTNET

logger = logging.getLogger(__name__)

class HyperLiquidTrader:
    """
    Trader class for HyperLiquid.
    All SDK operations are synchronous, so they are wrapped in asyncio.to_thread 
    to remain compatible with asynchronous applications like a Discord bot.
    """

    # Prezzi mock usati in DEMO MODE (nessuna credenziale HL)
    MOCK_PRICES: dict = {
        "BTC": 67500.0, "ETH": 3500.0, "SOL": 170.0,
        "NVDA": 950.0, "AAPL": 215.0, "TSLA": 180.0,
        "META": 520.0, "XAU": 2350.0, "WTI": 78.0,
        "BRENT": 82.0, "GOLD": 2350.0, "SILVER": 28.0,
        "BNB": 580.0, "AVAX": 38.0, "LINK": 15.0,
    }

    def __init__(self) -> None:
        """
        Initialize HyperLiquidTrader.

        - Info (dati pubblici) viene sempre inizializzato — non richiede credenziali.
        - Exchange (trading reale) viene inizializzato solo se HL_PRIVATE_KEY è presente
          e DRY_RUN=False.
        - Se mancano le credenziali HL, il bot funziona in DEMO MODE completa:
          i prezzi vengono letti dall'API pubblica (o da mock se non raggiungibile),
          i trade vengono simulati con risposta realistica.
        """
        self.account = None
        self.info = None
        self.exchange = None
        self._has_key = bool(HL_PRIVATE_KEY)

        api_url = constants.TESTNET_API_URL if USE_TESTNET else constants.MAINNET_API_URL
        network_name = "TESTNET 🧪 (soldi finti)" if USE_TESTNET else "MAINNET ⚡ (soldi REALI)"

        # Info è un'API pubblica — nessuna chiave necessaria
        try:
            self.info = Info(api_url, skip_ws=True)
            logger.info(f"✅ HyperLiquid Info connesso ({network_name})")
        except Exception as e:
            logger.warning(f"⚠️ Info HL non raggiungibile, uso prezzi mock: {e}")

        # Exchange richiede credenziali
        if self._has_key and not DRY_RUN:
            try:
                self.account = Account.from_key(HL_PRIVATE_KEY)
                self.exchange = Exchange(self.account, api_url)
                logger.info(f"✅ HyperLiquid Exchange pronto ({network_name})")
            except Exception as e:
                logger.error(f"❌ Errore inizializzazione Exchange HL: {e}")
        elif not self._has_key:
            logger.info("ℹ️  Nessuna HL_PRIVATE_KEY — bot in DEMO MODE (trade simulati con prezzi reali)")
        else:
            logger.info("ℹ️  DRY_RUN attivo — ordini simulati, nessun trade reale eseguito")

    async def get_asset_price(self, ticker: str) -> Optional[float]:
        """
        Get current mid-market price for a ticker.
        Uses self.info.all_mids() (public API, no credentials needed).
        Falls back to MOCK_PRICES if Info is unavailable.
        """
        # Prova API pubblica HL
        if self.info:
            try:
                mids = await asyncio.to_thread(self.info.all_mids)
                price_str = mids.get(ticker)
                if price_str:
                    return float(price_str)
                logger.warning(f"Ticker '{ticker}' non trovato su HL, uso prezzo mock.")
            except Exception as e:
                logger.warning(f"Impossibile leggere prezzo HL per {ticker}: {e}")

        # Fallback: prezzi mock hardcoded
        mock = self.MOCK_PRICES.get(ticker.upper())
        if mock:
            logger.info(f"[MOCK] Prezzo {ticker}: ${mock}")
            return mock

        logger.warning(f"Ticker '{ticker}' non trovato. Aggiungilo a MOCK_PRICES in hl_trader.py.")
        return None

    async def place_order(
        self,
        ticker: str,
        is_buy: bool,
        usd_amount: float,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place a trade on HyperLiquid.
        
        Steps:
        1. Get current price via get_asset_price()
        2. Calculate size: size = usd_amount / price
        3. If DRY_RUN, return a simulated response dict without calling exchange
        4. If order_type == 'market': call market_open
           If order_type == 'limit': call order
        5. Return result dict
        """
        # Sempre simulato se DRY_RUN o nessuna chiave
        is_demo = DRY_RUN or not self._has_key

        try:
            price = await self.get_asset_price(ticker)
            if price is None or price <= 0:
                return {"error": f"Impossibile ottenere il prezzo per {ticker}."}
            
            # Calculate size based on USD amount and current price
            size = round(usd_amount / price, 4)  # Rounding size to a sensible number of decimals

            side_str = "BUY" if is_buy else "SELL"
            
            # DEMO / DRY RUN — simulazione
            if is_demo:
                demo_label = "DEMO" if not self._has_key else "DRY_RUN"
                logger.info(f"[{demo_label}] Ordine simulato: {side_str} {size} {ticker} @ ${price:.2f} (${usd_amount})")
                return {
                    "ticker": ticker,
                    "side": side_str,
                    "size": size,
                    "price": limit_price if order_type == 'limit' else price,
                    "usd_amount": usd_amount,
                    "order_type": order_type,
                    "status": "simulated",
                    "order_id": f"{demo_label.lower()}_12345",
                    "dry_run": True
                }
            
            if not self.exchange:
                return {"error": "Exchange non inizializzato correttamente."}

            logger.info(f"Piazzando ordine reale: {side_str} {size} {ticker} (tipo: {order_type})")
            
            if order_type == "market":
                result = await asyncio.to_thread(
                    self.exchange.market_open,
                    coin=ticker,
                    is_buy=is_buy,
                    sz=size,
                    slippage=DEFAULT_SLIPPAGE
                )
            elif order_type == "limit":
                if limit_price is None:
                    return {"error": "Il prezzo limite è richiesto per ordini di tipo 'limit'."}
                result = await asyncio.to_thread(
                    self.exchange.order,
                    coin=ticker,
                    is_buy=is_buy,
                    sz=size,
                    limit_px=limit_price,
                    order_type={'limit': {'tif': 'Gtc'}}
                )
            else:
                return {"error": f"Tipo di ordine non supportato: {order_type}"}

            # Parse simple success output from HL response dict
            order_id = "unknown"
            status_data = result.get("response", {}).get("data", {}).get("statuses", [])
            if status_data and len(status_data) > 0:
                resting = status_data[0].get("resting")
                if resting:
                    order_id = resting.get("oid", "unknown")

            return {
                "ticker": ticker,
                "side": side_str,
                "size": size,
                "price": limit_price if order_type == 'limit' else price,
                "usd_amount": usd_amount,
                "order_type": order_type,
                "status": "success",
                "order_id": order_id,
                "raw_result": result,
                "dry_run": False
            }

        except Exception as e:
            logger.error(f"Errore durante l'invio dell'ordine per {ticker}: {e}")
            return {"error": str(e), "status": "failed"}

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get open positions. Uses self.info.user_state(HL_WALLET_ADDRESS).
        Parse the 'assetPositions' from the response.
        Return list of: {ticker, size, entry_price, unrealized_pnl, liquidation_price}
        If DRY_RUN, return empty list with a note.
        """
        if DRY_RUN or not self._has_key:
            logger.info("[DEMO] Richiesta posizioni aperte simulata — nessuna credenziale HL.")
            return []

        if not self.info or not HL_WALLET_ADDRESS:
            logger.error("Info non disponibile o HL_WALLET_ADDRESS mancante.")
            return []

        try:
            state = await asyncio.to_thread(self.info.user_state, HL_WALLET_ADDRESS)
            positions_data = state.get("assetPositions", [])
            
            positions = []
            for pos in positions_data:
                p = pos.get("position", {})
                if p:
                    ticker = p.get("coin")
                    size = float(p.get("szi", 0))
                    entry_price = float(p.get("entryPx", 0))
                    unrealized_pnl = float(p.get("unrealizedPnl", 0))
                    liquidation_price = float(p.get("liquidationPx", 0))
                    
                    positions.append({
                        "ticker": ticker,
                        "size": size,
                        "entry_price": entry_price,
                        "unrealized_pnl": unrealized_pnl,
                        "liquidation_price": liquidation_price
                    })
            return positions

        except Exception as e:
            logger.error(f"Errore durante il recupero delle posizioni: {e}")
            return []

    async def get_balance(self) -> Dict[str, Any]:
        """
        Get account balance. Uses self.info.user_state(HL_WALLET_ADDRESS).
        Parse 'marginSummary' from response.
        Return: {total_equity, available_balance, margin_used}
        If DRY_RUN, return simulated balance.
        """
        if DRY_RUN or not self._has_key:
            logger.info("[DEMO] Richiesta saldo simulata.")
            return {
                "total_equity": 10000.0,
                "available_balance": 10000.0,
                "margin_used": 0.0,
                "dry_run": True
            }

        if not self.info or not HL_WALLET_ADDRESS:
            return {"error": "Info non disponibile o HL_WALLET_ADDRESS mancante."}

        try:
            state = await asyncio.to_thread(self.info.user_state, HL_WALLET_ADDRESS)
            margin_summary = state.get("marginSummary", {})
            
            return {
                "total_equity": float(margin_summary.get("accountValue", 0)),
                "available_balance": float(margin_summary.get("withdrawable", 0)),
                "margin_used": float(margin_summary.get("totalMarginUsed", 0)),
                "dry_run": False
            }

        except Exception as e:
            logger.error(f"Errore durante il recupero del saldo: {e}")
            return {"error": str(e)}

    async def cancel_order(self, ticker: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an open order. Uses self.exchange.cancel(coin=ticker, oid=order_id).
        Return result dict.
        If DRY_RUN, return simulated cancellation.
        """
        if DRY_RUN or not self._has_key:
            logger.info(f"[DEMO] Cancellazione ordine {order_id} per {ticker} simulata.")
            return {"status": "success", "order_id": order_id, "dry_run": True}

        if not self.exchange:
            return {"error": "Exchange non inizializzato."}
            
        try:
            result = await asyncio.to_thread(
                self.exchange.cancel,
                coin=ticker,
                oid=order_id
            )
            logger.info(f"Ordine {order_id} cancellato per {ticker}.")
            return {"status": "success", "raw_result": result, "dry_run": False}
        except Exception as e:
            logger.error(f"Errore durante la cancellazione dell'ordine {order_id}: {e}")
            return {"error": str(e)}

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get open orders. Uses self.info.open_orders(HL_WALLET_ADDRESS).
        Return list of: {ticker, side, size, price, order_id}
        If DRY_RUN, return empty list.
        """
        if DRY_RUN or not self._has_key:
            logger.info("[DEMO] Richiesta ordini aperti simulata.")
            return []

        if not self.info or not HL_WALLET_ADDRESS:
            return []
            
        try:
            open_orders_data = await asyncio.to_thread(self.info.open_orders, HL_WALLET_ADDRESS)
            
            orders = []
            for o in open_orders_data:
                orders.append({
                    "ticker": o.get("coin"),
                    "side": "BUY" if o.get("isBuy") else "SELL",
                    "size": float(o.get("sz", 0)),
                    "price": float(o.get("limitPx", 0)),
                    "order_id": o.get("oid")
                })
            return orders
        except Exception as e:
            logger.error(f"Errore durante il recupero degli ordini aperti: {e}")
            return []
