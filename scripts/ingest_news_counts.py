#!/usr/bin/env python3
"""
Pull Alpaca News article counts per (symbol, date) for the top-N liquidity
universe across the full backtest range. Output: parquet on local disk,
then uploaded to S3 for backtester consumption.

Path A — counts only, no NLP. Tests "news momentum" hypothesis: stocks
with elevated article volume are getting attention → more likely to move.

Usage:
    source backend/venv/bin/activate
    python3 scripts/ingest_news_counts.py \
        --start 2019-06-01 \
        --end 2026-06-03 \
        --max-symbols 100 \
        --out ~/rigacap-research/news/counts.parquet
"""
import argparse, os, sys, time
import gzip, pickle
from datetime import datetime, timedelta, date
from collections import defaultdict

import pandas as pd
import requests

# Load creds from .env
for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
    if line.startswith('ALPACA_'):
        k, v = line.strip().split('=', 1)
        os.environ[k] = v

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

NEWS_URL = 'https://data.alpaca.markets/v1beta1/news'
HEADERS = {
    'APCA-API-KEY-ID': os.environ['ALPACA_API_KEY'],
    'APCA-API-SECRET-KEY': os.environ['ALPACA_SECRET_KEY'],
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--start', default='2019-06-01')
    p.add_argument('--end',   default=date.today().isoformat())
    p.add_argument('--max-symbols', type=int, default=100)
    p.add_argument('--pickle', default=os.path.expanduser('~/rigacap-research/pickles/LATEST'))
    p.add_argument('--symbols', default=None,
                   help='Explicit comma-separated symbols (overrides top-N pickle universe)')
    p.add_argument('--out',   default=os.path.expanduser('~/rigacap-research/news/counts.parquet'))
    p.add_argument('--upload-s3', action='store_true', help='Upload result to S3')
    p.add_argument('--s3-key', default='research/news_counts/counts.parquet')
    return p.parse_args()


def get_top_symbols(pickle_path, max_n):
    """Return top N symbols by 60-day average volume across the pickle's
    latest 60 days. Same liquidity-rank logic as the backtester uses."""
    import os
    for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
        if line.startswith('DATABASE_URL='):
            os.environ['DATABASE_URL'] = line.strip().split('=', 1)[1]
            break
    os.environ.setdefault('LAMBDA_ROLE', 'worker')
    from app.services.scanner import scanner_service
    from app.services.walk_forward_service import walk_forward_service

    with gzip.open(pickle_path, 'rb') as f:
        cache = pickle.load(f)
    scanner_service.data_cache = cache
    # Use as-of the LAST pickle date (most current top-N)
    spy = cache.get('SPY')
    if spy is not None and not spy.empty:
        as_of = pd.Timestamp(spy.index.max()).to_pydatetime()
    else:
        as_of = datetime.now()
    return walk_forward_service._get_top_symbols_as_of(as_of, max_n)


def fetch_symbol_counts(symbol, start_iso, end_iso, session):
    """Return {date_iso: count} for a single symbol across [start_iso, end_iso].
    Uses Alpaca REST directly — SDK strips next_page_token (verified Jun 3)."""
    counts = defaultdict(int)
    page_token = None
    requests_made = 0
    while True:
        params = {'symbols': symbol, 'start': start_iso, 'end': end_iso, 'limit': 50}
        if page_token:
            params['page_token'] = page_token
        try:
            r = session.get(NEWS_URL, headers=HEADERS, params=params, timeout=30)
        except Exception as e:
            print(f'  [{symbol}] HTTP ERROR: {e}')
            break
        requests_made += 1
        if r.status_code == 429:
            print(f'  [{symbol}] rate-limited, sleeping 10s')
            time.sleep(10.0)
            continue
        if r.status_code != 200:
            print(f'  [{symbol}] HTTP {r.status_code}: {r.text[:120]}')
            break
        j = r.json()
        for a in j.get('news', []):
            ds = a['created_at'][:10]  # ISO date prefix
            counts[ds] += 1
        page_token = j.get('next_page_token')
        if not page_token:
            break
        # Historical news rate limit ~10k/min — light pause every 500 reqs
        if requests_made % 500 == 0:
            time.sleep(1.0)
    return dict(counts), requests_made


def main():
    args = parse_args()
    print(f'Date range: {args.start} → {args.end}')
    print(f'Pickle: {args.pickle}')

    if args.symbols:
        symbols = args.symbols.split(',')
        print(f'Using explicit symbols: {len(symbols)}')
    else:
        symbols = get_top_symbols(args.pickle, args.max_symbols)
        print(f'Top-{args.max_symbols} by liquidity: {len(symbols)} symbols')

    session = requests.Session()
    start_iso = f'{args.start}T00:00:00Z'
    end_iso = f'{args.end}T00:00:00Z'

    rows = []
    t0 = time.time()
    for i, sym in enumerate(symbols, 1):
        ti = time.time()
        counts, reqs = fetch_symbol_counts(sym, start_iso, end_iso, session)
        elapsed = time.time() - ti
        total_articles = sum(counts.values())
        for ds, ct in counts.items():
            rows.append({'symbol': sym, 'date': ds, 'article_count': ct})
        print(f'[{i:>3}/{len(symbols)}] {sym:<6} {total_articles:>7} articles  '
              f'{len(counts):>4} days  {reqs:>3} reqs  {elapsed:.1f}s  '
              f'(total elapsed {(time.time()-t0)/60:.1f}min)')

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['symbol', 'date']).reset_index(drop=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_parquet(args.out, index=False)
    print()
    print(f'Wrote {len(df)} rows ({len(df.symbol.unique())} symbols × {len(df.date.unique())} dates) to {args.out}')
    print(f'Total time: {(time.time()-t0)/60:.1f} min')

    if args.upload_s3:
        import boto3
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket = 'rigacap-prod-price-data-149218244179'
        s3.upload_file(args.out, bucket, args.s3_key)
        print(f'Uploaded to s3://{bucket}/{args.s3_key}')


if __name__ == '__main__':
    main()
