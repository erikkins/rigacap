"""PITFWU price store — per-symbol RAW (as-traded) daily bars in S3.

Option A (Erik, Jun 2026): PITFWU = single source of truth — raw as-traded bars
(pitfwu/bars/{sym}.parquet) + a corp-actions calendar, with adjustment applied at
READ time. Per-symbol files make the daily append cheap (no 700 MB monolith
rewrite → no OOM) and scoped reads cheap (only the symbols the scan needs).

This module is the DEPLOYABLE backend port of scripts/pitfwu_freshness.py. It
covers the WRITE side (append today's RAW bars). The read veneer lands next.

Memory-safe by construction: fetches/holds only the touched symbols' recent bars,
never the full universe history.
"""
import io
import os
import logging
from typing import Dict, List, Optional

import boto3
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
BARS_PREFIX = "pitfwu/bars/"

_S3 = None


def _s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.client("s3", region_name="us-east-1")
    return _S3


def _alpaca_client():
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY, secret_key=settings.ALPACA_SECRET_KEY
    )


def _to_alpaca(sym: str) -> str:
    """pitfwu/yfinance hyphen share-class (BRK-B) -> Alpaca dot (BRK.B)."""
    return sym.replace("-", ".")


def _bars_to_df(rows) -> pd.DataFrame:
    df = pd.DataFrame([{
        "date": b.timestamp, "open": float(b.open), "high": float(b.high),
        "low": float(b.low), "close": float(b.close), "volume": int(b.volume),
    } for b in rows])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df.set_index("date").sort_index()


def fetch_raw_bars(symbols: List[str], start, end, client=None) -> Dict[str, pd.DataFrame]:
    """Fetch RAW (as-traded) daily bars over [start, end], keyed by the ORIGINAL
    (hyphen) symbol. Resilient: a batch that 400s on one bad symbol is retried
    per-symbol so the bad one is skipped, not the whole batch."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed
    client = client or _alpaca_client()
    start_dt = pd.Timestamp(start).to_pydatetime()
    end_dt = pd.Timestamp(end).to_pydatetime()
    out, bad = {}, []
    BATCH = 100
    syms = list(symbols)
    amap = {_to_alpaca(s): s for s in syms}  # alpaca-format -> original

    def _req(sym_list):
        return client.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=sym_list, timeframe=TimeFrame.Day,
            start=start_dt, end=end_dt, feed=DataFeed.SIP,
            adjustment=Adjustment.RAW)).data

    for i in range(0, len(syms), BATCH):
        batch = [_to_alpaca(s) for s in syms[i:i + BATCH]]
        try:
            data = _req(batch)
        except Exception:
            data = {}
            for a in batch:
                try:
                    data.update(_req([a]))
                except Exception:
                    bad.append(amap.get(a, a))
        for a, rows in data.items():
            if rows:
                out[amap.get(a, a)] = _bars_to_df(rows)
    if bad:
        logger.warning(f"[PITFWU] skipped {len(bad)} bad/unknown symbols (first 10): {bad[:10]}")
    return out


def _read_pitfwu_bars(symbol: str) -> Optional[pd.DataFrame]:
    """Read pitfwu/bars/{sym}.parquet -> DataFrame(index=date, OHLCV) or None."""
    try:
        raw = _s3().get_object(Bucket=BUCKET, Key=f"{BARS_PREFIX}{symbol}.parquet")["Body"].read()
        df = pd.read_parquet(io.BytesIO(raw))
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        return df.set_index("date").sort_index()
    except _s3().exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def _write_pitfwu_bars(symbol: str, df: pd.DataFrame):
    out = df.reset_index()[["date", "open", "high", "low", "close", "volume"]]
    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    buf.seek(0)
    _s3().put_object(Bucket=BUCKET, Key=f"{BARS_PREFIX}{symbol}.parquet", Body=buf.getvalue())


def pitfwu_last_date(ref: str = "AAPL"):
    df = _read_pitfwu_bars(ref)
    return df.index.max() if df is not None else None


# ----------------------------------------------------------------- READ veneer
# Split-adjust the RAW bars at read time (Option A). Ported from
# scripts/pitfwu_veneer.py (non-EXT path — live needs current data, not the
# survivorship-caveated pre-2016 extension). Validated 100% vs the pickle.
_CA = None
CORP_ACTIONS_KEY = "pitfwu/corp_actions/calendar.parquet"


def load_corp_actions():
    global _CA
    if _CA is None:
        try:
            raw = _s3().get_object(Bucket=BUCKET, Key=CORP_ACTIONS_KEY)["Body"].read()
            _CA = pd.read_parquet(io.BytesIO(raw))
        except Exception as e:
            logger.warning(f"[PITFWU] corp-actions load failed ({e}); split-adjust = no-op")
            _CA = pd.DataFrame(columns=["symbol", "type", "old_rate", "new_rate", "date"])
    return _CA


def split_factors(symbol: str, ca=None):
    """Sorted [(ex_date, factor)] — forward (factor>1) and reverse (factor<1) splits."""
    ca = ca if ca is not None else load_corp_actions()
    out = []
    if ca is None or ca.empty:
        return out
    sub = ca[(ca["symbol"] == symbol) & (ca["type"].isin(["forward_splits", "reverse_splits"]))]
    for _, e in sub.iterrows():
        try:
            old, new = float(e["old_rate"]), float(e["new_rate"])
            if old > 0 and new > 0 and e.get("date"):
                out.append((pd.Timestamp(e["date"]), new / old))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def split_adjusted(symbol: str, asof=None, ca=None) -> Optional[pd.DataFrame]:
    """RAW bars with splits (ex-date <= asof) applied. None asof = all known
    splits (fully adjusted to today, matching the pickle/all_data.parquet)."""
    df = _read_pitfwu_bars(symbol)
    if df is None or df.empty:
        return None
    df = df.copy()
    asof = pd.Timestamp(asof) if asof is not None else df.index.max()
    for ex, factor in split_factors(symbol, ca):
        if ex <= asof:
            mask = df.index < ex
            for col in ("open", "high", "low", "close"):
                if col in df:
                    df.loc[mask, col] = df.loc[mask, col] / factor
            if "volume" in df:
                df["volume"] = df["volume"].astype(float)
                df.loc[mask, "volume"] = df.loc[mask, "volume"] * factor
    return df


def load_scoped(symbols: List[str]) -> tuple:
    """Read split-adjusted bars for `symbols` from PITFWU. Returns
    ({sym: df}, missing[]) — `missing` = symbols with no PITFWU file (caller
    falls back to all_data.parquet for those so a gap never drops a name)."""
    ca = load_corp_actions()
    out, missing = {}, []
    for s in symbols:
        df = split_adjusted(s, ca=ca)
        if df is None or df.empty:
            missing.append(s)
        else:
            df.index.name = "date"
            out[s] = df
    return out, missing


def append_pitfwu_bars(symbols: List[str], start, end, execute: bool = False, client=None) -> dict:
    """Fetch RAW bars [start,end] and append to each symbol's pitfwu/bars file.
    Only dates AFTER the symbol's current last bar are added (new fetch wins on
    overlaps, correcting any prior bad bar). DRY RUN unless execute=True."""
    fresh = fetch_raw_bars(symbols, start, end, client=client)
    summary = {"appended": 0, "new_symbol": 0, "skipped_no_new": 0, "no_fetch": 0}
    for sym in symbols:
        new = fresh.get(sym)
        if new is None or new.empty:
            summary["no_fetch"] += 1
            continue
        existing = _read_pitfwu_bars(sym)
        if existing is None:
            merged = new
            summary["new_symbol"] += 1
        else:
            add = new[new.index > existing.index.max()]
            if add.empty:
                summary["skipped_no_new"] += 1
                continue
            merged = pd.concat([existing, add]).sort_index()
            merged = merged[~merged.index.duplicated(keep="last")]
            summary["appended"] += 1
        if execute:
            _write_pitfwu_bars(sym, merged)
    return summary
