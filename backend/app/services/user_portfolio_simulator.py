"""
User Portfolio Simulator — replays signals from a subscriber's signup
forward to produce a hypothetical portfolio state.

Mirrors the model portfolio's allocation rules (max 6 × 15% of current
cash, 12% trailing stop, panic-crash regime exit) but starts from the
user's signup_date with their portfolio_size as starting capital.

Reads historical scan data from S3 (snapshots/<date>/dashboard.json) and
daily closes from prices/<symbol>.csv. The output is a single state
snapshot — written to user_portfolio_state by the daily-scan hook,
read by GET /api/signals/my-portfolio-banner.
"""

from __future__ import annotations

import csv as _csv
import io as _io
import json
import logging
from dataclasses import dataclass, field
from datetime import date as _date, datetime, timedelta as _td
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

S3_PRICE_BUCKET = "rigacap-prod-price-data-149218244179"

# Mirror model_portfolio_service constants — keep in lockstep.
MAX_POSITIONS = 6
POSITION_SIZE_PCT = 0.15
TRAILING_STOP_PCT = 12.0
MIN_ALLOCATION_DOLLARS = 100  # Skip if 15% of cash falls below this floor

_s3_client = None
_snapshot_cache: Dict[str, Optional[dict]] = {}
_price_cache: Dict[str, List[dict]] = {}


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3", region_name="us-east-1")
    return _s3_client


def _load_snapshot(date_str: str) -> Optional[dict]:
    """Load snapshots/<date>/dashboard.json — cached per-process."""
    if date_str in _snapshot_cache:
        return _snapshot_cache[date_str]
    try:
        obj = _get_s3_client().get_object(
            Bucket=S3_PRICE_BUCKET,
            Key=f"snapshots/{date_str}/dashboard.json",
        )
        snap = json.loads(obj["Body"].read())
        _snapshot_cache[date_str] = snap
        return snap
    except Exception:
        _snapshot_cache[date_str] = None
        return None


def _load_prices(symbol: str) -> List[dict]:
    """Load full prices/{symbol}.csv as a list of {date, close}. Cached."""
    if symbol in _price_cache:
        return _price_cache[symbol]
    rows: List[dict] = []
    try:
        obj = _get_s3_client().get_object(
            Bucket=S3_PRICE_BUCKET, Key=f"prices/{symbol}.csv"
        )
        body = obj["Body"].read().decode("utf-8", errors="replace")
        reader = _csv.DictReader(_io.StringIO(body))
        for row in reader:
            try:
                rows.append({
                    "date": row["date"],
                    "close": float(row["close"]),
                })
            except (KeyError, ValueError):
                continue
    except Exception as e:
        logger.warning(f"user-sim: prices/{symbol}.csv load failed: {e}")
    _price_cache[symbol] = rows
    return rows


def _close_for(symbol: str, date_str: str) -> Optional[float]:
    """Closing price for a symbol on a specific date, or None."""
    for row in _load_prices(symbol):
        if row["date"] == date_str:
            return row["close"]
    return None


@dataclass
class _SimPosition:
    symbol: str
    entry_date: str
    entry_price: float
    shares: float
    cost_basis: float
    hwm: float


@dataclass
class SimResult:
    as_of_date: str
    portfolio_value: float
    cost_basis: float  # Of currently open positions
    open_pnl_dollars: float
    open_pnl_pct: float
    open_positions_count: int
    closed_trades_count: int
    winning_trades_count: int
    total_pnl_dollars: float  # Realized + unrealized vs starting capital
    cash: float
    open_positions: List[dict] = field(default_factory=list)


def simulate(
    signup_date: _date,
    portfolio_size: float,
    as_of_date: Optional[_date] = None,
    trade_log: Optional[List[dict]] = None,
) -> SimResult:
    """
    Replay signals from signup_date forward at the user's portfolio_size.

    Returns a SimResult with the state as of as_of_date (default: today).

    Algorithm:
      1. Walk each weekday in [signup_date, as_of_date].
      2. For each open position: update HWM with that day's close, then
         check trailing stop (12% from HWM) and Panic-Crash regime exit.
         Trailing stop overrides if both fire.
      3. After exits, add fresh signals (is_fresh=True) up to 6 positions,
         allocating 15% of *current* cash per entry. Skip if cash drops
         below the $100 minimum.
      4. After the walk, mark unrealized P&L using the latest available
         close per open symbol.

    No re-fetching from market-data providers; everything reads from
    the S3 snapshot + per-symbol CSV cache.
    """
    if as_of_date is None:
        as_of_date = _date.today()

    cash = float(portfolio_size)
    starting_capital = float(portfolio_size)
    open_positions: List[_SimPosition] = []
    closed_count = 0
    winning_count = 0
    realized_pnl = 0.0

    cur = signup_date
    while cur <= as_of_date:
        if cur.weekday() < 5:
            date_str = cur.isoformat()
            snap = _load_snapshot(date_str)

            # Step 1: process exits for open positions using today's close
            if open_positions:
                regime_action = (
                    (snap or {}).get("regime_forecast", {}).get(
                        "recommended_action", "stay_invested"
                    )
                )
                survivors: List[_SimPosition] = []
                for pos in open_positions:
                    close = _close_for(pos.symbol, date_str)
                    if close is None:
                        # No close for this date — keep position open, no HWM update
                        survivors.append(pos)
                        continue
                    if close > pos.hwm:
                        pos.hwm = close

                    trailing_level = pos.hwm * (1 - TRAILING_STOP_PCT / 100)
                    exit_reason: Optional[str] = None
                    if regime_action == "go_to_cash":
                        exit_reason = "regime_exit"
                    if close <= trailing_level:
                        exit_reason = "trailing_stop"

                    if exit_reason:
                        proceeds = pos.shares * close
                        trade_pnl = proceeds - pos.cost_basis
                        realized_pnl += trade_pnl
                        closed_count += 1
                        if trade_pnl > 0:
                            winning_count += 1
                        cash += proceeds
                        if trade_log is not None:
                            trade_log.append({
                                "symbol": pos.symbol,
                                "entry_date": pos.entry_date,
                                "entry_price": round(pos.entry_price, 2),
                                "exit_date": date_str,
                                "exit_price": round(close, 2),
                                "hwm": round(pos.hwm, 2),
                                "trailing_level": round(trailing_level, 2),
                                "exit_reason": exit_reason,
                                "pnl_dollars": round(trade_pnl, 2),
                                "pnl_pct": round((close / pos.entry_price - 1) * 100, 2),
                            })
                    else:
                        survivors.append(pos)
                open_positions = survivors

            # Step 2: process fresh-signal entries if there's space
            if snap and len(open_positions) < MAX_POSITIONS:
                fresh = [s for s in snap.get("buy_signals", []) if s.get("is_fresh")]
                held_symbols = {p.symbol for p in open_positions}
                for sig in fresh:
                    if len(open_positions) >= MAX_POSITIONS:
                        break
                    sym = sig.get("symbol")
                    if not sym or sym in held_symbols:
                        continue
                    entry_price = sig.get("price", 0) or 0
                    if entry_price <= 0:
                        continue
                    alloc = cash * POSITION_SIZE_PCT
                    if alloc < MIN_ALLOCATION_DOLLARS:
                        break
                    shares = alloc / entry_price
                    open_positions.append(
                        _SimPosition(
                            symbol=sym,
                            entry_date=date_str,
                            entry_price=entry_price,
                            shares=shares,
                            cost_basis=alloc,
                            hwm=entry_price,
                        )
                    )
                    cash -= alloc
                    held_symbols.add(sym)
                    if trade_log is not None:
                        trade_log.append({
                            "symbol": sym,
                            "entry_date": date_str,
                            "entry_price": round(entry_price, 2),
                            "alloc": round(alloc, 2),
                            "shares": round(shares, 4),
                            "ensemble_entry_date": sig.get("ensemble_entry_date"),
                            "action": "ENTRY",
                        })

        cur += _td(days=1)

    # Mark-to-market on as_of_date
    open_value = 0.0
    open_cost_basis = 0.0
    open_dicts: List[dict] = []
    as_of_str = as_of_date.isoformat()
    for pos in open_positions:
        latest_close = _close_for(pos.symbol, as_of_str)
        if latest_close is None:
            # Fall back to most recent close on or before as_of_date
            for row in reversed(_load_prices(pos.symbol)):
                if row["date"] <= as_of_str:
                    latest_close = row["close"]
                    break
        if latest_close is None:
            latest_close = pos.entry_price  # last-resort fallback
        market_value = pos.shares * latest_close
        open_value += market_value
        open_cost_basis += pos.cost_basis
        open_dicts.append({
            "symbol": pos.symbol,
            "entry_date": pos.entry_date,
            "entry_price": round(pos.entry_price, 2),
            "current_price": round(latest_close, 2),
            "shares": round(pos.shares, 4),
            "cost_basis": round(pos.cost_basis, 2),
            "market_value": round(market_value, 2),
            "pnl_dollars": round(market_value - pos.cost_basis, 2),
            "pnl_pct": round(((latest_close / pos.entry_price) - 1) * 100, 2),
            "highest_price": round(pos.hwm, 2),
        })

    portfolio_value = cash + open_value
    open_pnl_dollars = open_value - open_cost_basis
    open_pnl_pct = (open_pnl_dollars / open_cost_basis * 100) if open_cost_basis > 0 else 0.0
    total_pnl_dollars = portfolio_value - starting_capital

    return SimResult(
        as_of_date=as_of_str,
        portfolio_value=round(portfolio_value, 2),
        cost_basis=round(open_cost_basis, 2),
        open_pnl_dollars=round(open_pnl_dollars, 2),
        open_pnl_pct=round(open_pnl_pct, 2),
        open_positions_count=len(open_positions),
        closed_trades_count=closed_count,
        winning_trades_count=winning_count,
        total_pnl_dollars=round(total_pnl_dollars, 2),
        cash=round(cash, 2),
        open_positions=open_dicts,
    )


def clear_caches() -> None:
    """Drop in-process caches. Useful when invoking from a long-lived Lambda."""
    _snapshot_cache.clear()
    _price_cache.clear()
