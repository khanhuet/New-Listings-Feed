import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from dateutil import parser as date_parser
from app.sources import get_sources, Source
from app.store import SeenItem, TradingReminder, normalize_url

log = logging.getLogger("listingbot")

def item_hash(source_key: str, url: str, title: str) -> str:
    raw = f"{source_key}|{normalize_url(url)}|{title.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def is_listing(title: str, keywords: tuple[str, ...]) -> bool:
    t = title.lower()
    return any(k in t for k in keywords)

def extract_trading_time(text: str, display_tz):
    """Best-effort time parser. Only creates a reminder when a clear date and time are found.

    Announcement wording and timezone differ by exchange/language. This MVP treats a
    time with no timezone as DISPLAY_TIMEZONE; validate each exchange before relying on it.
    """
    patterns = [
        r'(?P<date>\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\b)'
        r'.{0,100}?\b(?P<time>\d{1,2}:\d{2}(?::\d{2})?\s*(?:UTC[+-]\d{1,2}(?::?\d{2})?|GMT[+-]\d{1,2}(?::?\d{2})?|UTC|GMT|KST|SGT|HKT|EST|PST)?)\b',
        r'\b(?P<time>\d{1,2}:\d{2}\s*(?:UTC[+-]\d{1,2}(?::?\d{2})?|GMT[+-]\d{1,2}(?::?\d{2})?|UTC|GMT|KST|SGT|HKT))\b'
        r'.{0,100}?\b(?P<date>20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})\b',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if not m:
            continue
        try:
            raw = f"{m.group('date')} {m.group('time')}"
            dt = date_parser.parse(raw, fuzzy=True, default=datetime.now(display_tz).replace(hour=0, minute=0, second=0, microsecond=0))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=display_tz)
            # Ignore implausible dates to avoid accidentally scheduling a false reminder.
            now = datetime.now(timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
            if now - timedelta(hours=1) <= dt_utc <= now + timedelta(days=60):
                return dt_utc
        except (ValueError, TypeError, OverflowError):
            continue
    return None

class Monitor:
    def __init__(self, settings, session_factory, telegram):
        self.settings = settings
        self.session_factory = session_factory
        self.telegram = telegram
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": "ListingAlertBot/1.0 (announcement monitoring; contact admin)"},
        )
        self.last_ok = {}

    async def close(self):
        await self.client.aclose()

    async def fetch_links(self, source: Source):
        response = await self.client.get(source.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        found, seen_urls = [], set()
        for a in soup.select("a[href]"):
            title = " ".join(a.get_text(" ", strip=True).split())
            href = urljoin(str(response.url), a.get("href", ""))
            if not title or len(title) < 8 or not href.startswith(("http://", "https://")):
                continue
            if source.name.lower() not in href.lower() and not any(
                domain in href.lower() for domain in ("binance.com", "okx.com", "mexc.com", "bitget.com",
                "gate.com", "upbit.com", "kucoin.com", "bybit.com", "htx.com", "bingx.com", "lbank.com")
            ):
                continue
            clean = normalize_url(href)
            if clean in seen_urls:
                continue
            seen_urls.add(clean)
            found.append((title[:500], clean))
        return found[:300]

    async def fetch_detail(self, url: str):
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return " ".join(soup.get_text(" ", strip=True).split())[:20000]
        except Exception as exc:
            log.debug("Could not fetch detail %s: %s", url, exc)
            return ""

    async def scan_source(self, source: Source):
        try:
            links = await self.fetch_links(source)
            self.last_ok[source.key] = datetime.now(timezone.utc)
        except Exception:
            log.exception("Source fetch failed: %s (%s)", source.name, source.url)
            return
        for title, url in links:
            key = item_hash(source.key, url, title)
            with self.session_factory() as session:
                if session.scalar(select(SeenItem.id).where(SeenItem.item_key == key)) is not None:
                    continue
                # Save all newly discovered links so old content doesn't repeatedly reappear.
                relevant = is_listing(title, self.settings.announcement_keywords)
                item = SeenItem(source_key=source.key, item_key=key, title=title, url=url,
                                first_seen_at=datetime.now(timezone.utc), relevant=relevant)
                session.add(item)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    continue
            if not relevant:
                continue
            detail = await self.fetch_detail(url)
            combined = f"{title}. {detail}"
            trading_at = extract_trading_time(combined, self.settings.tz)
            message = (
                f"🟢 <b>LISTING NEWS</b>\n"
                f"🏦 <b>{source.name}</b>\n"
                f"🪙 {self.telegram.escape(title)}\n"
                f"🕒 Trading: {trading_at.astimezone(self.settings.tz).strftime('%Y-%m-%d %H:%M %Z') if trading_at else 'Not detected — check official source'}\n"
                f"🔎 <b>Evidence:</b> <a href=\"{self.telegram.escape(url)}\">Open official announcement</a>\n"
                f"<code>{self.telegram.escape(url)}</code>"
            )
            try:
                await self.telegram.send(message)
                with self.session_factory() as session:
                    row = session.scalar(select(SeenItem).where(SeenItem.item_key == key))
                    if row:
                        row.sent_at = datetime.now(timezone.utc)
                        session.commit()
                    if trading_at:
                        existing = session.scalar(select(TradingReminder).where(TradingReminder.item_key == key))
                        if not existing:
                            session.add(TradingReminder(
                                item_key=key, source_name=source.name, title=title, url=url,
                                trading_at_utc=trading_at,
                                remind_at_utc=trading_at - timedelta(minutes=10),
                            ))
                            session.commit()
            except Exception:
                log.exception("Telegram send failed for %s", title)

    async def reminder_loop(self):
        while True:
            now = datetime.now(timezone.utc)
            with self.session_factory() as session:
                due = session.scalars(select(TradingReminder).where(
                    TradingReminder.sent.is_(False),
                    TradingReminder.canceled.is_(False),
                    TradingReminder.remind_at_utc <= now,
                    TradingReminder.trading_at_utc > now,
                ).limit(100)).all()
                for reminder in due:
                    try:
                        local = reminder.trading_at_utc.astimezone(self.settings.tz)
                        await self.telegram.send(
                            f"⏰ <b>TRADING OPENS IN 10 MINUTES</b>\n"
                            f"🏦 <b>{self.telegram.escape(reminder.source_name)}</b>\n"
                            f"🪙 {self.telegram.escape(reminder.title)}\n"
                            f"🕒 Opening: {local.strftime('%Y-%m-%d %H:%M %Z')}\n"
                            f"🔎 <b>Evidence:</b> <a href=\"{self.telegram.escape(reminder.url)}\">Open official announcement</a>\n"
                            f"<code>{self.telegram.escape(reminder.url)}</code>"
                        )
                        reminder.sent = True
                        session.commit()
                    except Exception:
                        session.rollback()
                        log.exception("Reminder failed for %s", reminder.title)
            await asyncio.sleep(2)

    async def run(self):
        sources = get_sources()
        log.info("Monitoring %d sources every %d seconds", len(sources), self.settings.poll_seconds)
        reminder_task = asyncio.create_task(self.reminder_loop())
        try:
            while True:
                # Scan sources concurrently but bound concurrency to avoid hammering websites.
                semaphore = asyncio.Semaphore(4)
                async def bounded(source):
                    async with semaphore:
                        await self.scan_source(source)
                await asyncio.gather(*(bounded(s) for s in sources))
                await asyncio.sleep(self.settings.poll_seconds)
        finally:
            reminder_task.cancel()
            await self.close()
