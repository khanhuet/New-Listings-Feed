import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

def _csv(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]

@dataclass(frozen=True)
class Settings:
    telegram_token: str
    telegram_chat_id: str
    database_url: str
    poll_seconds: int
    request_timeout: int
    lookback_hours: int
    timezone: str
    announcement_keywords: tuple[str, ...]
    trading_keywords: tuple[str, ...]

    @classmethod
    def load(cls):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment variables.")
        return cls(
            telegram_token=token,
            telegram_chat_id=chat_id,
            database_url=os.getenv("DATABASE_URL", "sqlite:///./listing_bot.db"),
            poll_seconds=max(15, int(os.getenv("POLL_SECONDS", "30"))),
            request_timeout=max(5, int(os.getenv("REQUEST_TIMEOUT", "15"))),
            lookback_hours=max(1, int(os.getenv("LOOKBACK_HOURS", "72"))),
            timezone=os.getenv("DISPLAY_TIMEZONE", "Asia/Ho_Chi_Minh"),
            announcement_keywords=tuple(x.lower() for x in _csv(
                "ANNOUNCEMENT_KEYWORDS",
                "will list,listing,lists on,spot trading,will launch trading,will add support for,available for trading,listing announcement,new listing,launchpool,pre-market"
            )),
            trading_keywords=tuple(x.lower() for x in _csv(
                "TRADING_KEYWORDS", "trading will open,spot trading will open,trading starts,trading to begin,will open trading,will be available for trading"
            )),
        )

    @property
    def tz(self):
        return ZoneInfo(self.timezone)
