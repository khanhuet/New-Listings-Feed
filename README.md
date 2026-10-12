# Telegram Listing Alert Bot (MVP)

Python bot that monitors official announcement pages for Binance, OKX, MEXC, Bitget, Gate.io, Upbit, KuCoin, Bybit, HTX, BingX and LBank; sends detected listing announcements to one Telegram channel; and schedules a best-effort T-10 trading reminder when it can extract an unambiguous date/time.

## Important limitations

- This is an MVP starter, not a guaranteed real-time listing feed. Exchange announcement pages are often JavaScript-rendered, change markup, localize content, or block generic scraping. Some pages may return no links to this parser.
- Before relying on it for trading, verify every adapter against the live official source. Replace generic HTML polling with official announcement APIs/RSS/webhooks where available.
- Time extraction is heuristic. A date/time without timezone is interpreted in `DISPLAY_TIMEZONE`; exchange-specific timezone rules should be implemented and tested before relying on T-10 alerts. If time isn't confidently detected, the immediate alert says to check the official source and no reminder is scheduled.
- Respect each exchange's terms, robots rules and rate limits. Never reduce polling interval without validating the source's limits.
- Use a persistent PostgreSQL database in production. SQLite is only for local smoke tests.

## 1. Create the Telegram channel and bot

1. Create the bot through `@BotFather`; copy its token.
2. Add the bot to your channel as an administrator with permission to post messages.
3. Set `TELEGRAM_CHAT_ID` to the channel ID. Public channel: `@your_channel_username`. Private channel: use the numeric `-100...` channel ID.
4. Never commit the token to GitHub. If it leaks, revoke it with BotFather immediately.

## 2. Run locally

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`, set real `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then:

```bash
python -m app.main
```

PowerShell alternative to `cp`:
```powershell
Copy-Item .env.example .env
```

## 3. Deploy to GitHub + Render

1. Create a GitHub repository and upload these files. Do not upload `.env`.
2. In Render, create a new **Blueprint** from that GitHub repository.
3. Review `render.yaml`; it creates a background worker and PostgreSQL database. A paid worker/database plan may be required; check current Render pricing and plan availability.
4. Enter `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Render environment variables when prompted.
5. Deploy and inspect logs. You should receive a startup message in the channel.
6. If Render's database plan/region/connection settings differ, create PostgreSQL manually and set `DATABASE_URL` to its internal connection string.

## 4. Validate the sources before using in production

For each exchange:
- Check the configured page loads from Render.
- Confirm new announcements appear in its HTML links. If the page uses JavaScript, generic HTML scraping may not work.
- Publish/identify a known old listing announcement and confirm title, link, and category matching.
- Test that the bot sends a single message, then restarts without resending it.
- Test date/time extraction against real announcements and timezone.
- Add adapter-specific parsers/APIs where needed.

## 5. How T-10 works

The bot attempts to parse an explicit calendar date and time from the announcement detail page. If it finds a plausible time, it saves a reminder to the database for 10 minutes before that time. If an announcement is first discovered fewer than 10 minutes before trading, it sends the immediate alert but cannot retroactively send a T-10 alert.

## Environment variables

See `.env.example`. `SOURCE_<EXCHANGE>_URL` overrides a source URL; set it to `disabled` to disable a source. `POLL_SECONDS` is clamped to at least 15 seconds to reduce accidental over-polling.


## Evidence links in Telegram messages

Both the immediate listing alert and the T-10 reminder include a clickable link and the full URL of the announcement page discovered by the source adapter. Always verify that each exchange adapter resolves to the specific announcement article, not a generic listing/category page. The generic HTML parser cannot guarantee this for every exchange; implement and test exchange-specific parsers before production use.
