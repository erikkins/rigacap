#!/usr/bin/env python3
"""
Test: Relative Strength Leaders as secondary strategy leg.

Runs alongside the existing momentum-breakout strategy. When primary has
open slots unfilled (low signal environment), RS Leaders fills them with
the strongest stocks by 6-month relative strength vs SPY.

Usage:
    source backend/venv/bin/activate
    caffeinate -i python3 scripts/test_rs_leaders.py [--rs-slots 3]
"""

import argparse
import asyncio
import gzip
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# DATABASE_URL is required — load from .env if not already in environment.
# Never hardcode a real credential here (see memory: feedback_never_check_in_secrets.md).
if not os.environ.get('DATABASE_URL'):
    _dotenv = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_dotenv):
        for _line in open(_dotenv):
            if _line.startswith('DATABASE_URL='):
                os.environ['DATABASE_URL'] = _line.strip().split('=', 1)[1]
                break
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('ERROR: DATABASE_URL not set. Create .env at repo root or export it.')
os.environ.setdefault('LAMBDA_ROLE', 'worker')


def parse_args():
    p = argparse.ArgumentParser(description='RS Leaders Strategy Test')
    p.add_argument('--start', default='2021-01-01')
    p.add_argument('--end', default='2026-04-01')
    p.add_argument('--max-positions', type=int, default=6)
    p.add_argument('--position-size', type=float, default=15.0)
    p.add_argument('--rs-slots', type=int, default=2,
                   help='Max slots reserved for RS Leaders when primary is quiet (default: 2)')
    p.add_argument('--rs-lookback', type=int, default=126,
                   help='RS lookback days (~6 months, default: 126)')
    p.add_argument('--rs-min-idle-periods', type=int, default=2,
                   help='Primary must be idle this many periods before RS activates (default: 2)')
    p.add_argument('--trailing-stop', type=float, default=12.0)
    p.add_argument('--near-50d-high', type=float, default=5.0)
    p.add_argument('--dwap-threshold', type=float, default=5.0)
    p.add_argument('--pickle', default='backend/data/all_data.pkl.gz')
    p.add_argument('--max-symbols', type=int, default=500)
    return p.parse_args()


def load_pickle(path):
    abs_path = os.path.join(os.path.dirname(__file__), '..', path)
    if not os.path.exists(abs_path):
        abs_path = path
    print(f"Loading pickle: {abs_path}")
    with gzip.open(abs_path, 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded {len(data)} symbols")
    return data


def get_row(df, date):
    """Get the row for a given date, handling timezone mismatches."""
    try:
        if date in df.index:
            return df.loc[date]
        date_str = date.strftime('%Y-%m-%d')
        matches = df.index[df.index.strftime('%Y-%m-%d') == date_str]
        if len(matches) > 0:
            return df.loc[matches[0]]
    except (KeyError, IndexError):
        pass
    return None


def compute_relative_strength(data_cache, date, lookback=126, min_price=20, min_volume=500000, top_n=20):
    """
    Rank stocks by relative strength vs SPY over lookback period.
    Returns list of {symbol, rs_score, price, volume} sorted by RS descending.
    """
    spy_df = data_cache.get('SPY')
    if spy_df is None:
        return []

    spy_row = get_row(spy_df, date)
    if spy_row is None:
        return []

    spy_loc = spy_df.index.get_loc(spy_row.name)
    if spy_loc < lookback:
        return []

    spy_now = spy_df.iloc[spy_loc]['close']
    spy_then = spy_df.iloc[spy_loc - lookback]['close']
    spy_return = (spy_now / spy_then - 1)

    candidates = []
    for symbol, df in data_cache.items():
        if symbol in ('SPY', '^VIX', '^GSPC') or symbol.startswith('^'):
            continue

        row = get_row(df, date)
        if row is None:
            continue

        loc = df.index.get_loc(row.name)
        if loc < lookback:
            continue

        price = row['close']
        volume = row['volume']

        if price < min_price or volume < min_volume:
            continue

        price_then = df.iloc[loc - lookback]['close']
        stock_return = (price / price_then - 1)

        # Relative strength = stock return - SPY return
        rs_score = (stock_return - spy_return) * 100

        # Basic quality: must be above 50-day MA
        ma_50 = df['close'].iloc[max(0, loc-49):loc+1].mean()
        if price < ma_50:
            continue

        candidates.append({
            'symbol': symbol,
            'rs_score': rs_score,
            'price': price,
            'volume': volume,
            'return_6m': stock_return * 100,
        })

    candidates.sort(key=lambda x: -x['rs_score'])
    return candidates[:top_n]


def run_backtest(args, data_cache):
    """
    Run the dual-strategy backtest:
    - Primary: momentum-breakout (existing logic)
    - Secondary: RS Leaders (fills gaps when primary is quiet)
    """
    from app.services.scanner import scanner_service
    from app.services.backtester import BacktesterService as Backtester
    from app.core.config import settings

    scanner_service.data_cache = data_cache
    scanner_service.universe = list(data_cache.keys())

    # Get trading dates from SPY
    spy_df = data_cache['SPY']
    start_date = pd.Timestamp(args.start)
    end_date = pd.Timestamp(args.end)
    dates = spy_df.index[(spy_df.index >= start_date) & (spy_df.index <= end_date)]

    # Excluded symbols
    from app.services.stock_universe import EXCLUDED_PATTERNS
    import re
    excluded = set()
    for symbol in data_cache.keys():
        for pattern in EXCLUDED_PATTERNS:
            if re.match(pattern, symbol):
                excluded.add(symbol)
                break

    # Get top symbols by average volume (last 20 trading days from start)
    symbol_volumes = {}
    for sym, df in data_cache.items():
        if sym in excluded or sym.startswith('^'):
            continue
        # Use average volume near start date
        mask = df.index <= start_date + pd.Timedelta(days=30)
        recent = df[mask].tail(20)
        if len(recent) > 0:
            avg_vol = recent['volume'].mean()
            last_price = recent['close'].iloc[-1]
            if avg_vol >= 500000 and last_price >= 20:
                symbol_volumes[sym] = avg_vol
    symbols = sorted(symbol_volumes.keys(), key=lambda s: -symbol_volumes[s])[:args.max_symbols]
    print(f"Universe: {len(symbols)} symbols (from {len(data_cache)} total, {len(excluded)} excluded)")

    # Initialize backtester for primary strategy scoring
    backtester = Backtester()
    backtester.near_50d_high_pct = args.near_50d_high
    backtester.trailing_stop_pct = args.trailing_stop / 100
    backtester.max_positions = args.max_positions
    backtester.position_size_pct = args.position_size / 100
    backtester.min_price = 20
    backtester.min_volume = 500000
    backtester.dwap_threshold_pct = args.dwap_threshold / 100

    capital = 100000
    positions = {}  # symbol -> {entry_price, entry_date, shares, high_water_mark, source}
    trades = []
    equity_curve = []

    in_cash_mode = False
    primary_idle_periods = 0  # How many rebalance periods with <2 primary entries
    last_rebalance = None

    trailing_stop_pct = args.trailing_stop / 100

    for i, date in enumerate(dates):
        date_str = date.strftime('%Y-%m-%d')

        # Check market regime (SPY < 200MA = cash mode)
        if settings.MARKET_FILTER_ENABLED:
            market_ok = backtester._check_market_regime(date, panic_only=settings.MARKET_FILTER_PANIC_ONLY)
            if not market_ok and not in_cash_mode:
                in_cash_mode = True
                # Close all positions
                for sym in list(positions.keys()):
                    pos = positions[sym]
                    row = get_row(data_cache[sym], date)
                    if row is None:
                        continue
                    price = row['close']
                    pnl_pct = (price / pos['entry_price'] - 1) * 100
                    pnl_dollars = (price - pos['entry_price']) * pos['shares']
                    trades.append({
                        'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': date_str,
                        'entry_price': pos['entry_price'], 'exit_price': price,
                        'pnl_pct': round(pnl_pct, 2), 'pnl_dollars': round(pnl_dollars, 2),
                        'exit_reason': 'market_regime', 'source': pos.get('source', 'primary'),
                        'shares': pos['shares'],
                    })
                    capital += pos['shares'] * price
                positions.clear()
            elif market_ok:
                in_cash_mode = False

        if in_cash_mode:
            pos_value = sum(
                pos['shares'] * (get_row(data_cache[s], date) or {}).get('close', pos['entry_price'])
                for s, pos in positions.items()
                if s in data_cache
            )
            equity_curve.append({'date': date_str, 'equity': capital + pos_value})
            continue

        # Check trailing stops on existing positions
        for sym in list(positions.keys()):
            if sym not in data_cache:
                continue
            pos = positions[sym]
            row = get_row(data_cache[sym], date)
            if row is None:
                continue
            price = row['close']

            # Update HWM
            if price > pos.get('high_water_mark', pos['entry_price']):
                pos['high_water_mark'] = price

            hwm = pos['high_water_mark']
            stop_level = hwm * (1 - trailing_stop_pct)

            if price <= stop_level:
                pnl_pct = (price / pos['entry_price'] - 1) * 100
                pnl_dollars = (price - pos['entry_price']) * pos['shares']
                trades.append({
                    'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': date_str,
                    'entry_price': pos['entry_price'], 'exit_price': price,
                    'pnl_pct': round(pnl_pct, 2), 'pnl_dollars': round(pnl_dollars, 2),
                    'exit_reason': 'trailing_stop', 'source': pos.get('source', 'primary'),
                    'shares': pos['shares'],
                })
                capital += pos['shares'] * price
                del positions[sym]

        # Biweekly rebalance check (Fridays, every 2 weeks)
        is_friday = date.weekday() == 4
        days_since_rebalance = (date - last_rebalance).days if last_rebalance else 999
        should_rebalance = is_friday and days_since_rebalance >= 10

        if should_rebalance and len(positions) < args.max_positions:
            open_slots = args.max_positions - len(positions)
            held_symbols = set(positions.keys())

            # --- PRIMARY: Momentum-breakout candidates ---
            primary_candidates = []
            for sym in symbols:
                if sym in held_symbols:
                    continue
                score = backtester._calculate_momentum_score(sym, date)
                if score and score['passes_quality']:
                    primary_candidates.append(score)

            primary_candidates.sort(key=lambda x: -x['composite_score'])
            if should_rebalance and i < 200:  # Debug first ~9 months
                checked = sum(1 for s in symbols if s not in held_symbols)
                print(f"[DEBUG {date_str}] {checked} syms, {len(primary_candidates)} primary cands, {primary_idle_periods} idle, {len(positions)} pos")
            primary_entries = 0

            for cand in primary_candidates:
                if len(positions) >= args.max_positions:
                    break
                pos_value = capital * (args.position_size / 100)
                if pos_value > capital:
                    break
                shares = pos_value / cand['price']
                capital -= shares * cand['price']
                positions[cand['symbol']] = {
                    'entry_price': cand['price'],
                    'entry_date': date_str,
                    'shares': round(shares, 2),
                    'high_water_mark': cand['price'],
                    'source': 'primary',
                }
                held_symbols.add(cand['symbol'])
                primary_entries += 1

            # --- SECONDARY: RS Leaders (always fill remaining slots) ---
            # Primary gets first pick, RS fills whatever's left
            primary_positions = sum(1 for p in positions.values() if p.get('source') == 'primary')
            rs_positions = sum(1 for p in positions.values() if p.get('source') == 'rs_leader')
            if len(positions) < args.max_positions and rs_positions < args.rs_slots:
                rs_slots = min(args.rs_slots, args.max_positions - len(positions))
                rs_candidates = compute_relative_strength(
                    data_cache, date, lookback=args.rs_lookback,
                )
                rs_entries = 0
                for cand in rs_candidates:
                    if rs_entries >= rs_slots:
                        break
                    if cand['symbol'] in held_symbols:
                        continue
                    if cand['symbol'] in excluded:
                        continue
                    pos_value = capital * (args.position_size / 100)
                    if pos_value > capital:
                        break
                    shares = pos_value / cand['price']
                    capital -= shares * cand['price']
                    positions[cand['symbol']] = {
                        'entry_price': cand['price'],
                        'entry_date': date_str,
                        'shares': round(shares, 2),
                        'high_water_mark': cand['price'],
                        'source': 'rs_leader',
                    }
                    held_symbols.add(cand['symbol'])
                    rs_entries += 1

                if rs_entries > 0:
                    pass  # Will show in summary

            last_rebalance = date

        # Record equity
        pos_value = 0
        for sym, pos in positions.items():
            if sym in data_cache:
                row = get_row(data_cache[sym], date)
                if row is not None:
                    pos_value += pos['shares'] * row['close']
        equity_curve.append({'date': date_str, 'equity': capital + pos_value})

    # Close remaining positions at end
    for sym, pos in positions.items():
        row = get_row(data_cache[sym], dates[-1])
        if row is None:
            continue
        price = row['close']
        pnl_pct = (price / pos['entry_price'] - 1) * 100
        pnl_dollars = (price - pos['entry_price']) * pos['shares']
        trades.append({
            'symbol': sym, 'entry_date': pos['entry_date'], 'exit_date': dates[-1].strftime('%Y-%m-%d'),
            'entry_price': pos['entry_price'], 'exit_price': price,
            'pnl_pct': round(pnl_pct, 2), 'pnl_dollars': round(pnl_dollars, 2),
            'exit_reason': 'end_of_sim', 'source': pos.get('source', 'primary'),
            'shares': pos['shares'],
        })
        capital += pos['shares'] * price

    return trades, equity_curve, capital


def analyze_results(trades, equity_curve, final_capital, args):
    """Print results with primary vs RS breakdown."""
    primary_trades = [t for t in trades if t.get('source') == 'primary']
    rs_trades = [t for t in trades if t.get('source') == 'rs_leader']

    total_return = (final_capital / 100000 - 1) * 100

    print(f"\n{'='*60}")
    print(f"DUAL STRATEGY RESULTS")
    print(f"{'='*60}")
    print(f"  Total return: {total_return:+.1f}%")
    print(f"  Final capital: ${final_capital:,.0f}")
    print(f"  Total trades: {len(trades)}")

    for label, subset in [("PRIMARY (momentum-breakout)", primary_trades), ("RS LEADERS", rs_trades)]:
        if not subset:
            print(f"\n  {label}: 0 trades")
            continue
        closed = [t for t in subset if t['exit_reason'] != 'end_of_sim']
        winners = [t for t in closed if t['pnl_pct'] > 0]
        losers = [t for t in closed if t['pnl_pct'] <= 0]
        total_pnl = sum(t['pnl_dollars'] for t in closed)
        avg_win = sum(t['pnl_pct'] for t in winners) / len(winners) if winners else 0
        avg_loss = sum(t['pnl_pct'] for t in losers) / len(losers) if losers else 0
        print(f"\n  {label}:")
        print(f"    Trades: {len(closed)} ({len(winners)}W / {len(losers)}L)")
        print(f"    Win rate: {len(winners)/len(closed)*100:.0f}%")
        print(f"    Avg win: {avg_win:+.1f}% | Avg loss: {avg_loss:+.1f}%")
        print(f"    Total PnL: ${total_pnl:+,.0f}")

    # Year-by-year
    print(f"\n  Year-by-Year:")
    trades_by_exit = sorted([t for t in trades if t.get('exit_date')], key=lambda t: t['exit_date'])
    capital = 100000
    prev_year = args.start[:4]
    year_start = capital
    for t in trades_by_exit:
        year = t['exit_date'][:4]
        if year != prev_year:
            yr_ret = (capital / year_start - 1) * 100
            rs_count = len([x for x in trades_by_exit if x['exit_date'][:4] == prev_year and x.get('source') == 'rs_leader'])
            print(f"    {prev_year}: {yr_ret:+.1f}% (RS trades: {rs_count})")
            year_start = capital
            prev_year = year
        capital += t.get('pnl_dollars', 0)
    yr_ret = (capital / year_start - 1) * 100
    rs_count = len([x for x in trades_by_exit if x['exit_date'][:4] == prev_year and x.get('source') == 'rs_leader'])
    print(f"    {prev_year}: {yr_ret:+.1f}% (RS trades: {rs_count})")

    # Max drawdown
    peak = 0
    max_dd = 0
    for pt in equity_curve:
        eq = pt['equity']
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    print(f"\n  Max Drawdown: {max_dd:.1f}%")
    print(f"{'='*60}")


def main():
    args = parse_args()
    data_cache = load_pickle(args.pickle)

    t0 = time.time()
    trades, equity_curve, final_capital = run_backtest(args, data_cache)
    dur = time.time() - t0

    analyze_results(trades, equity_curve, final_capital, args)
    print(f"\n  Duration: {dur:.0f}s")


if __name__ == '__main__':
    main()
