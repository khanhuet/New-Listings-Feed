from sqlalchemy import create_engine, String, Text, DateTime, Boolean, Integer, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

class Base(DeclarativeBase):
    pass

class SeenItem(Base):
    __tablename__ = "seen_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(32), index=True)
    item_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relevant: Mapped[bool] = mapped_column(Boolean, default=False)

class TradingReminder(Base):
    __tablename__ = "trading_reminders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    trading_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    remind_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled: Mapped[bool] = mapped_column(Boolean, default=False)

def make_store(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    # Tracking query strings can cause duplicate announcements; retain path, drop query/fragment.
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))

def was_seen(session, item_key: str) -> bool:
    return session.scalar(select(SeenItem.id).where(SeenItem.item_key == item_key)) is not None
