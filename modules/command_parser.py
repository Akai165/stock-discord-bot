"""
Module to parse Discord text commands for trading.
Handles both trade commands (buy/sell) and informational commands (positions/balance/orders/cancel).
"""

import re
import shlex
from dataclasses import dataclass
from typing import Optional, Union

from config import DEFAULT_TRADE_SIZE_USD


@dataclass
class TradeCommand:
    """Represents a buy or sell command."""
    action: str           # 'buy' | 'sell'
    ticker: str           # 'BTC', 'NVDA', etc. (always uppercase)
    amount_usd: float     # dollar amount
    order_type: str       # 'market' | 'limit'
    limit_price: Optional[float] = None  # only for limit orders


@dataclass
class InfoCommand:
    """Represents an informational or management command."""
    action: str           # 'positions' | 'balance' | 'orders' | 'cancel'
    ticker: Optional[str] = None      # for cancel
    order_id: Optional[int] = None    # for cancel


def parse_message(content: str) -> Union[TradeCommand, InfoCommand, None]:
    """
    Parse a Discord message into a command object.
    
    Returns None if the message doesn't start with %.
    Returns TradeCommand for %buy/%sell.
    Returns InfoCommand for %positions, %balance, %orders, %cancel.
    
    If amount is missing, use DEFAULT_TRADE_SIZE_USD.
    If order_type is missing, default to 'market'.
    Ticker is always converted to uppercase.
    
    Raises ValueError with descriptive Italian message if:
    - %buy/%sell has no ticker
    - limit order has no --limit price
    - price is not a valid number
    - unknown command
    """
    if not content or not content.startswith('%'):
        return None

    try:
        parts = shlex.split(content)
    except ValueError:
        # Fallback for mismatched quotes
        parts = content.split()

    if not parts:
        return None

    command = parts[0][1:].lower()

    # Informational / Management Commands
    if command in ['positions', 'balance', 'orders']:
        return InfoCommand(action=command)

    if command == 'cancel':
        if len(parts) < 3:
            raise ValueError("Devi specificare il ticker e l'ID dell'ordine. Esempio: %cancel BTC 123456")
        ticker = parts[1].upper()
        try:
            order_id = int(parts[2])
        except ValueError:
            raise ValueError("L'ID dell'ordine deve essere un numero intero.")
        return InfoCommand(action=command, ticker=ticker, order_id=order_id)

    # Trading Commands
    if command in ['buy', 'sell']:
        if len(parts) < 2:
            raise ValueError(f"Manca il ticker per il comando {command}. Esempio: %{command} BTC")
        
        ticker = parts[1].upper()
        
        amount_usd = DEFAULT_TRADE_SIZE_USD
        order_type = 'market'
        limit_price = None

        idx = 2
        
        # 1. Parse amount (optional)
        if idx < len(parts) and parts[idx].lower() not in ['market', 'limit'] and parts[idx] != '--limit':
            try:
                # Remove dollar sign and normalize commas to dots for float parsing
                val_str = parts[idx].replace('$', '').replace(',', '.')
                amount_usd = float(val_str)
                if amount_usd <= 0:
                    raise ValueError("L'importo deve essere maggiore di zero.")
                idx += 1
            except ValueError as e:
                # Re-raise if it's our specific error
                if str(e) == "L'importo deve essere maggiore di zero.":
                    raise e
                # Otherwise, it might not be the amount, so we leave it and continue
                pass

        # 2. Parse order type (optional)
        if idx < len(parts) and parts[idx].lower() in ['market', 'limit']:
            order_type = parts[idx].lower()
            idx += 1
            
        # 3. Parse limit price (required if order type is limit, or if --limit flag is present)
        if '--limit' in parts[idx:]:
            limit_idx = parts.index('--limit', idx)
            order_type = 'limit'  # Enforce limit type if flag is provided
            if limit_idx + 1 < len(parts):
                try:
                    limit_price_str = parts[limit_idx + 1].replace(',', '.')
                    limit_price = float(limit_price_str)
                except ValueError:
                    raise ValueError("Prezzo limite non valido. Assicurati di inserire un numero dopo --limit.")
            else:
                raise ValueError("Devi specificare un prezzo per l'ordine limite con --limit.")
        
        if order_type == 'limit' and limit_price is None:
            raise ValueError("Devi specificare un prezzo per l'ordine limite usando --limit (es. --limit 100.5).")

        return TradeCommand(
            action=command,
            ticker=ticker,
            amount_usd=amount_usd,
            order_type=order_type,
            limit_price=limit_price
        )

    # Unknown Command
    raise ValueError(f"Comando '%{command}' sconosciuto. Usa %help per vedere i comandi disponibili.")


def format_help_message() -> str:
    """Return a formatted help string (in Italian) showing all commands and syntax."""
    return (
        "**Comandi Bot Trading**\n\n"
        "**Trading:**\n"
        "`%buy [ticker] [importo$] [market|limit] [--limit price]` - Compra un asset\n"
        "`%sell [ticker] [importo$] [market|limit] [--limit price]` - Vendi un asset\n"
        " *(Se l'importo è omesso, verrà usata la dimensione di default)*\n"
        " *(Se il tipo di ordine è omesso, verrà usato 'market')*\n\n"
        "**Esempi Trading:**\n"
        "`%buy BTC 100 market`\n"
        "`%buy NVDA 250 limit --limit 950.50`\n"
        "`%sell ETH 100`\n"
        "`%sell BTC market` (Usa importo di default)\n\n"
        "**Informazioni e Gestione:**\n"
        "`%positions` - Mostra le posizioni aperte\n"
        "`%balance` - Mostra il saldo del conto\n"
        "`%orders` - Mostra gli ordini aperti\n"
        "`%cancel [ticker] [order_id]` - Cancella un ordine specifico (es: `%cancel BTC 123456`)\n"
    )
