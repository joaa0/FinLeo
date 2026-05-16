from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    database_url: str
    log_level: str = "INFO"
    app_env: str = "development"
    openai_api_key: str | None = None
    openai_model: str = "mistral-small-latest"
    openai_base_url: str = "https://api.mistral.ai/v1"
    mistral_transcription_model: str = "voxtral-mini-latest"
    mistral_transcription_language: str = "pt"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_from: str | None = None
    report_email_subject: str = "Seu relatorio financeiro ChamaLeon"
    cache_ttl_seconds: int = 60
    auto_create_schema: bool = True
    reminder_check_interval_minutes: int = 15
    daily_nudge_start_hour: int = 8
    daily_nudge_end_hour: int = 20
    parser_ai_confidence_threshold: float = 0.80
    weekly_closure_hour: int = 9

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN nao configurado")
        if not database_url:
            raise ValueError("DATABASE_URL nao configurado")

        smtp_port_raw = os.getenv("SMTP_PORT", "587").strip() or "587"
        cache_ttl_raw = os.getenv("CACHE_TTL_SECONDS", "60").strip() or "60"
        reminder_check_interval_raw = os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "15").strip() or "15"
        nudge_start_raw = os.getenv("DAILY_NUDGE_START_HOUR", "8").strip() or "8"
        nudge_end_raw = os.getenv("DAILY_NUDGE_END_HOUR", "20").strip() or "20"
        parser_ai_threshold_raw = os.getenv("PARSER_AI_CONFIDENCE_THRESHOLD", "0.80").strip() or "0.80"
        weekly_closure_hour_raw = os.getenv("WEEKLY_CLOSURE_HOUR", "9").strip() or "9"
        return cls(
            telegram_bot_token=token,
            database_url=database_url,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            app_env=os.getenv("APP_ENV", "development").strip() or "development",
            openai_api_key=os.getenv("MISTRAL_API_KEY") or os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "mistral-small-latest").strip() or "mistral-small-latest",
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.mistral.ai/v1").strip() or "https://api.mistral.ai/v1",
            mistral_transcription_model=os.getenv("MISTRAL_TRANSCRIPTION_MODEL", "voxtral-mini-latest").strip() or "voxtral-mini-latest",
            mistral_transcription_language=os.getenv("MISTRAL_TRANSCRIPTION_LANGUAGE", "pt").strip() or "pt",
            smtp_host=os.getenv("SMTP_HOST") or None,
            smtp_port=int(smtp_port_raw),
            smtp_username=os.getenv("SMTP_USERNAME") or None,
            smtp_password=os.getenv("SMTP_PASSWORD") or None,
            smtp_use_tls=_as_bool(os.getenv("SMTP_USE_TLS"), True),
            email_from=os.getenv("EMAIL_FROM") or None,
            report_email_subject=os.getenv("REPORT_EMAIL_SUBJECT", "Seu relatorio financeiro ChamaLeon"),
            cache_ttl_seconds=int(cache_ttl_raw),
            auto_create_schema=_as_bool(os.getenv("AUTO_CREATE_SCHEMA"), True),
            reminder_check_interval_minutes=int(reminder_check_interval_raw),
            daily_nudge_start_hour=int(nudge_start_raw),
            daily_nudge_end_hour=int(nudge_end_raw),
            parser_ai_confidence_threshold=float(parser_ai_threshold_raw),
            weekly_closure_hour=int(weekly_closure_hour_raw),
        )
