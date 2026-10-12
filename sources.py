"""Configurable announcement-page monitors.

Important: exchange pages change frequently. These are starting URLs, not a guarantee
that generic HTML parsing will discover every announcement. Verify each source during
deployment and prefer official APIs/RSS where the exchange provides them.
"""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str

DEFAULTS = [
    ("binance", "Binance", "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing"),
    ("okx", "OKX", "https://www.okx.com/help/section/announcements-new-listings"),
    ("mexc", "MEXC", "https://www.mexc.com/announcements"),
    ("bitget", "Bitget", "https://www.bitget.com/support/sections/12560603807910"),
    ("gateio", "Gate.io", "https://www.gate.com/announcements"),
    ("upbit", "Upbit", "https://upbit.com/service_center/notice"),
    ("kucoin", "KuCoin", "https://www.kucoin.com/announcement"),
    ("bybit", "Bybit", "https://announcements.bybit.com/en/"),
    ("htx", "HTX", "https://www.htx.com/support/en-us/list/360000039942"),
    ("bingx", "BingX", "https://bingx.com/en/support/announcement"),
    ("lbank", "LBank", "https://www.lbank.com/support/announcement"),
]

def get_sources() -> list[Source]:
    """Override any URL with SOURCE_<KEY>_URL environment variables."""
    result = []
    for key, name, default_url in DEFAULTS:
        url = os.getenv(f"SOURCE_{key.upper()}_URL", default_url).strip()
        if url and not url.lower().startswith("disabled"):
            result.append(Source(key, name, url))
    return result
