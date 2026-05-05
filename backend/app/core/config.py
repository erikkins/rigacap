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
    TIKTOK_CLIENT_KEY: str = os.getenv("TIKTOK_CLIENT_KEY", "")
    TIKTOK_CLIENT_SECRET: str = os.getenv("TIKTOK_CLIENT_SECRET", "")
    TIKTOK_ACCESS_TOKEN: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    
    # Trading strategy (legacy DWAP - kept for backward compatibility)
    DWAP_THRESHOLD_PCT: float = 5.5  # Run5 adaptive optimizer (was 6.5 Trial 37)
    STOP_LOSS_PCT: float = 8.0
    PROFIT_TARGET_PCT: float = 20.0
    MIN_VOLUME: int = 500_000
    MIN_PRICE: float = 15.0
    VOLUME_SPIKE_MULT: float = 1.5

    # ENSEMBLE STRATEGY — Run5 adaptive optimizer (Apr 18, 2026)
    # +297.8% over 5.3 years, Sharpe 1.10, MaxDD 29.97%
    # These defaults are from the latest period (period 138).
    # The biweekly TPE cron will update these dynamically.
    MAX_POSITIONS: int = 4
    POSITION_SIZE_PCT: float = 20.0
    SHORT_MOMENTUM_DAYS: int = 5
    LONG_MOMENTUM_DAYS: int = 60
    TRAILING_STOP_PCT: float = 12.0
    MARKET_FILTER_ENABLED: bool = True
    MARKET_FILTER_PANIC_ONLY: bool = False
    REBALANCE_FREQUENCY: str = "biweekly"

    # Scoring weights
    SHORT_MOM_WEIGHT: float = 0.3
    LONG_MOM_WEIGHT: float = 0.2
    VOLATILITY_PENALTY: float = 0.15

    # Quality filters
    NEAR_50D_HIGH_PCT: float = 7.0  # Run5 latest period
    MOMENTUM_SECTOR_CAP: int = 0  # Run5: no sector cap

    # Profit lock (tighten trailing stop once position is up X%)
    PROFIT_LOCK_PCT: float = 12.0  # Tighten stop once up 12%
    PROFIT_LOCK_STOP_PCT: float = 6.0  # Tightened trailing stop %

    # Anti-squeeze filters
    MAX_RECENT_RETURN_PCT: float = 40.0  # Reject if up >40% in last ~10d
    PRICE_VELOCITY_CAP_PCT: float = 965.0  # Reject extreme daily velocity
    
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

    # Liquidity tier bonus — top TIER1_SIZE symbols get +TIER1_BONUS added to composite_score
    SIGNAL_TIER1_SIZE: int = int(os.getenv("SIGNAL_TIER1_SIZE", "150"))
    SIGNAL_TIER1_BONUS: float = float(os.getenv("SIGNAL_TIER1_BONUS", "0"))

    # Track Record — TPE Trial 37, Jan 1 2021 start, single continuous sim
    TRACK_RECORD_SIM_IDS: List[int] = [922, 924, 925, 926, 927, 928, 929, 930]  # 8 start dates, same params, confidence band

    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "rigacap-data")
    
    class Config:
        env_file = ".env"
        extra = "allow"


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
    # Leveraged/inverse index ETFs
    'VXX', 'UVXY', 'SVXY', 'SSO', 'SDS', 'SPXU', 'TQQQ', 'SQQQ',
    'QLD', 'QID', 'FAS', 'FAZ', 'TNA', 'TZA',
    # 1x inverse index ETFs
    'PSQ', 'DOG', 'RWM', 'SBB', 'MYY', 'SEF', 'EUM', 'EFZ',
    # Leveraged/inverse sector & thematic ETFs
    'FNGD', 'FNGU', 'SOXL', 'SOXS', 'TECL', 'TECS',
    'TMF', 'TMV', 'ERX', 'ERY', 'GUSH', 'DRIP',
    # Leveraged/inverse single-stock ETFs (Direxion, GraniteShares, etc.)
    'TSLS', 'TSLQ', 'TSLL', 'NVDL', 'NVDS', 'NVDQ', 'NVD',
    'AAPD', 'AAPU', 'AMZU', 'AMZD', 'MSFU', 'MSFD',
    'METU', 'METD', 'CONL', 'CONY', 'MSTX', 'MSTU',
    # Index/broad market ETFs (individual stocks only)
    'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO',
    # Sector ETFs
    'XLB', 'XLE', 'XLF', 'XLK', 'XLV', 'SOXX', 'SMH', 'KRE', 'XBI',
    # International ETFs
    'FXI', 'KWEB', 'EEM', 'EFA', 'IEFA', 'VWO',
    # Smart beta / thematic ETFs
    'SCHD', 'SCHX', 'FNDX', 'ARKK',
    # Commodity ETFs (not equity momentum)
    'GLD', 'IAU', 'GLDM', 'IAUM', 'SGOL', 'SLV', 'SIVR',
    'DBC', 'DBA', 'USO', 'UNG', 'PDBC', 'GSG',
    # Bond/Treasury/Fixed-income ETFs (not equity momentum)
    'TLT', 'TLH', 'IEF', 'SHY', 'SPTL', 'AGG', 'BND', 'LQD', 'HYG', 'JNK',
    'JAAA', 'VTEB', 'USHY', 'JEPQ',
    # Crypto ETFs (spot and leveraged)
    'BITX', 'BITU', 'SBIT', 'IBIT', 'FBTC', 'ARKB', 'GBTC', 'ETHE', 'ETHA', 'ETH',
]

def get_universe():
    """Get tradeable stock universe"""
    all_symbols = set(NASDAQ_100 + SP500_ADDITIONS)
    return [s for s in all_symbols if s not in EXCLUDED_SYMBOLS]
