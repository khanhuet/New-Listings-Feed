import html
import httpx
import logging

log = logging.getLogger("listingbot.telegram")

class TelegramSender:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.client = httpx.AsyncClient(timeout=15)

    @staticmethod
    def escape(value: str) -> str:
        return html.escape(value, quote=True)

    async def send(self, text: str):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        response = await self.client.post(url, json={
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API returned error: {data}")
        log.info("Telegram message sent")

    async def close(self):
        await self.client.aclose()
