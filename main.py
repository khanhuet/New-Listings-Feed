import asyncio
import logging
import os
from app.config import Settings
from app.store import make_store
from app.telegram import TelegramSender
from app.monitor import Monitor

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

async def main():
    settings = Settings.load()
    session_factory = make_store(settings.database_url)
    telegram = TelegramSender(settings.telegram_token, settings.telegram_chat_id)
    monitor = Monitor(settings, session_factory, telegram)
    try:
        await telegram.send("✅ <b>Listing Alert Bot is online</b>\nĐã khởi động bộ giám sát thông báo niêm yết.")
        await monitor.run()
    finally:
        await monitor.close()
        await telegram.close()

if __name__ == "__main__":
    asyncio.run(main())
