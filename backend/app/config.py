"""Application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(
        default="postgresql://snapshot:snapshot@localhost:5432/market_snapshot",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # NSE / market
    primary_index: str = "NIFTY 50"
    nifty_options_symbol: str = "NIFTY"

    # yfinance symbols (override per deployment)
    yfin_nifty_symbol: str = "^NSEI"
    yfin_vix_symbol: str = "^INDIAVIX"
    yfin_gift_symbol: str = "^NSEI"  # set to actual GIFT ticker if available
    yfin_us_index_symbol: str = "^IXIC"  # NASDAQ; use ^GSPC for S&P
    yfin_gold_futures: str = "GC=F"
    yfin_usd_inr: str = "INR=X"
    yfin_crude_symbol: str = "CL=F"
    # US market global strip (all USD / dollar-denominated; no INR or India proxies)
    yfin_us_dow_symbol: str = "^DJI"
    yfin_dollar_index_symbol: str = "DX-Y.NYB"

    # X (Twitter) API v2 — env aliases match common hosting conventions
    x_bearer_token: Optional[str] = Field(default=None, validation_alias=AliasChoices("XBEARER_TOKEN", "x_bearer_token"))
    x_list_id: Optional[str] = Field(default=None, validation_alias=AliasChoices("X_LIST_ID", "x_list_id"))

    # Databento OPRA (US ETF options PCR for SPY / QQQ — optional; T+1 OI via prior weekday)
    databento_api_key: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("DATABENTO_API_KEY", "databento_api_key")
    )
    databento_dataset: str = Field(
        default="OPRA.PILLAR",
        validation_alias=AliasChoices("DATABENTO_DATASET", "databento_dataset"),
    )

    # Scheduler (IST) — also accepts SNAPSHOT_CRON_HOUR style env names
    snapshot_cron_hour: int = Field(default=16, validation_alias=AliasChoices("SNAPSHOT_CRON_HOUR", "snapshot_cron_hour"))
    snapshot_cron_minute: int = Field(
        default=0, validation_alias=AliasChoices("SNAPSHOT_CRON_MINUTE", "snapshot_cron_minute")
    )
    intraday_refresh_minutes: int = Field(
        default=0,
        validation_alias=AliasChoices("INTRADAY_REFRESH_MINUTES", "intraday_refresh_minutes"),
    )  # 0 = disabled; e.g. 30 or 60

    # Scheduled / intraday jobs only (`run_snapshot_pipeline` without full=True). Defaults avoid paid APIs (X 402) and heavy NSE/Databento hits every N minutes.
    scheduled_snapshot_include_x: bool = Field(
        default=False,
        validation_alias=AliasChoices("SCHEDULED_SNAPSHOT_INCLUDE_X", "scheduled_snapshot_include_x"),
    )
    scheduled_snapshot_include_nse_options: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "SCHEDULED_SNAPSHOT_INCLUDE_NSE_OPTIONS",
            "scheduled_snapshot_include_nse_options",
        ),
    )
    scheduled_us_snapshot_include_x: bool = Field(
        default=False,
        validation_alias=AliasChoices("SCHEDULED_US_SNAPSHOT_INCLUDE_X", "scheduled_us_snapshot_include_x"),
    )
    scheduled_us_snapshot_include_options: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "SCHEDULED_US_SNAPSHOT_INCLUDE_OPTIONS",
            "scheduled_us_snapshot_include_options",
        ),
    )

    # Sentiment / ML
    finbert_model: str = "ProsusAI/finbert"
    x_tweet_lookback_hours: int = 24
    x_max_tweets: int = 100

    api_cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        validation_alias=AliasChoices("API_CORS_ORIGINS", "api_cors_origins"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
