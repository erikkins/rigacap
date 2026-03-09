"""
Configuration settings for the RigaCap API
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RigaCap API"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://rigacap.com")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://rigacap:rigacap@localhost:5432/rigacap"
    )

    # Redis (for caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5176",
        "https://rigacap.com",
        "https://www.rigacap.com",
    ]

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stripe
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")  # Monthly subscription price
    STRIPE_PRICE_ID_ANNUAL: str = os.getenv("STRIPE_PRICE_ID_ANNUAL", "")  # Annual subscription price
    STRIPE_REFERRAL_COUPON_ID: str = os.getenv("STRIPE_REFERRAL_COUPON_ID", "REFERRAL_1MONTH_FREE")

    # Cloudflare Turnstile
    TURNSTILE_SECRET_KEY: str = os.getenv("TURNSTILE_SECRET_KEY", "")
    TURNSTILE_SITE_KEY: str = os.getenv("TURNSTILE_SITE_KEY", "")

    # OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    APPLE_CLIENT_ID: str = os.getenv("APPLE_CLIENT_ID", "")
    APPLE_TEAM_ID: str = os.getenv("APPLE_TEAM_ID", "")
    APPLE_KEY_ID: str = os.getenv("APPLE_KEY_ID", "")
    
    # Trading strategy (legacy DWAP - kept for backward compatibility)
    DWAP_THRESHOLD_PCT: float = 5.0
    STOP_LOSS_PCT: float = 8.0
    PROFIT_TARGET_PCT: float = 20.0
    MIN_VOLUME: int = 500_000
    MIN_PRICE: float = 20.0
    VOLUME_SPIKE_MULT: float = 1.5

    # MOMENTUM STRATEGY v2 (Sharpe 1.48)
    MAX_POSITIONS: int = 5
    POSITION_SIZE_PCT: float = 18.0
    SHORT_MOMENTUM_DAYS: int = 10
    LONG_MOMENTUM_DAYS: int = 60
    TRAILING_STOP_PCT: float = 12.0
    MARKET_FILTER_ENABLED: bool = True
    REBALANCE_FREQUENCY: str = "weekly"

    # Scoring weights
    SHORT_MOM_WEIGHT: float = 0.5
    LONG_MOM_WEIGHT: float = 0.3
    VOLATILITY_PENALTY: float = 0.2

    # Quality filters
    NEAR_50D_HIGH_PCT: float = 5.0  # Within 5% of 50-day high
    MOMENTUM_SECTOR_CAP: int = 5  # Max stocks per sector in momentum top-N
    
    # Data
    DATA_LOOKBACK_DAYS: int = 252
    SCAN_INTERVAL_MINUTES: int = 15
    
    # Social Media APIs
    TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET: str = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    THREADS_ACCESS_TOKEN: str = os.getenv("THREADS_ACCESS_TOKEN", "")
    THREADS_USER_ID: str = os.getenv("THREADS_USER_ID", "")

    # Anthropic API (Claude for AI content generation)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Alpaca Market Data
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
    DATA_SOURCE_PRIMARY: str = os.getenv("DATA_SOURCE_PRIMARY", "alpaca")  # "alpaca" (Pro/SIP — consolidated volume) or "yfinance" (fallback)

    # Signal universe filter — 0 = full universe, >0 = top N by 60-day avg volume
    SIGNAL_UNIVERSE_SIZE: int = int(os.getenv("SIGNAL_UNIVERSE_SIZE", "0"))

    # Track Record — canonical walk-forward sim IDs (yearly sims stitched to +289%)
    TRACK_RECORD_SIM_IDS: List[int] = [113, 114, 115, 116, 112]

    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "rigacap-data")
    
    class Config:
        env_file = ".env"


settings = Settings()


# Stock universe
NASDAQ_100 = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AVGO', 'COST', 'NFLX',
    'AMD', 'ADBE', 'PEP', 'CSCO', 'TMUS', 'INTC', 'CMCSA', 'INTU', 'QCOM', 'TXN',
    'AMGN', 'AMAT', 'ISRG', 'HON', 'BKNG', 'VRTX', 'SBUX', 'GILD', 'MDLZ', 'ADI',
    'ADP', 'REGN', 'LRCX', 'PANW', 'MU', 'SNPS', 'KLAC', 'CDNS', 'MELI', 'ASML',
    'PYPL', 'CRWD', 'MAR', 'ORLY', 'CTAS', 'MNST', 'NXPI', 'MRVL', 'CSX', 'WDAY',
]

SP500_ADDITIONS = [
    'JPM', 'V', 'JNJ', 'WMT', 'PG', 'MA', 'UNH', 'HD', 'BAC', 'XOM',
    'CVX', 'LLY', 'ABBV', 'KO', 'MRK', 'PFE', 'TMO', 'ABT', 'CRM', 'ACN',
    'MCD', 'DHR', 'WFC', 'VZ', 'NKE', 'PM', 'UPS', 'NEE', 'RTX', 'SPGI',
]

EXCLUDED_SYMBOLS = [
    'VXX', 'UVXY', 'SVXY', 'SSO', 'SDS', 'SPXU', 'TQQQ', 'SQQQ',
    'QLD', 'QID', 'FAS', 'FAZ', 'TNA', 'TZA',
]

def get_universe():
    """Get tradeable stock universe"""
    all_symbols = set(NASDAQ_100 + SP500_ADDITIONS)
    return [s for s in all_symbols if s not in EXCLUDED_SYMBOLS]
