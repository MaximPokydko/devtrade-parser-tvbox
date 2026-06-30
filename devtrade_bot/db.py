"""Database layer: User / Script / Job models (PostgreSQL, async SQLAlchemy)."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from . import config


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scripts: Mapped[list["Script"]] = relationship(back_populates="user")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))
    strategy_json: Mapped[dict] = mapped_column(JSONB)
    pine_code: Mapped[str] = mapped_column(Text)
    validation_issues: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="scripts")


class Job(Base):
    """Task queue: bot inserts pending jobs, worker claims and processes them."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    script_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_models() -> None:
    """Create tables if missing; apply additive column migrations (no Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE scripts ADD COLUMN IF NOT EXISTS name VARCHAR(255)"))
