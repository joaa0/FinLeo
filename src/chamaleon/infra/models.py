from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255))
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    daily_nudge_enabled: Mapped[bool] = mapped_column(default=True)
    nudge_hour: Mapped[int] = mapped_column(default=10)
    nudge_minute: Mapped[int] = mapped_column(default=0)
    last_nudge_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reports: Mapped[list["GeneratedReport"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recurring_rules: Mapped[list["RecurringRule"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="transactions")


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    __table_args__ = (UniqueConstraint("user_id", "period_label", name="uq_generated_reports_user_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_label: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), default="generated")
    delivery_channel: Mapped[str] = mapped_column(String(32), default="email")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="reports")


class RecurringRule(Base):
    __tablename__ = "recurring_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    description: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(64))
    transaction_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    day_of_month: Mapped[int] = mapped_column()
    reminder_days_before: Mapped[int] = mapped_column(default=1)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_reminder_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="recurring_rules")
