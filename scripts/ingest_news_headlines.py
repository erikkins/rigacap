#!/usr/bin/env python3
"""
Path B — pull HEADLINES + SUMMARIES per article for top-N liquidity universe.
Output: parquet with one row per article (id, symbol, date, headline, summary).
Feeds into score_news_sentiment.py (Claude Haiku polarity scoring).
"""
import argparse, os, sys, time
import gzip, pickle
from datetime import datetime, date
from collections import defaultdict

import pandas as pd
import requests

# Load creds
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
    p.add_argument('--symbols', default=None)
    p.add_argument('--out',   default=os.path.expanduser('~/rigacap-research/news/headlines.parquet'))
    p.add_argument('--upload-s3', action='store_true')
    p.add_argument('--s3-key', default='research/news_headlines/headlines.parquet')
    return p.parse_args()


def get_top_symbols(pickle_path, max_n):
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
    spy = cache.get('SPY')
    as_of = pd.Timestamp(spy.index.max()).to_pydatetime() if spy is not None else datetime.now()
    return walk_forward_service._get_top_symbols_as_of(as_of, max_n)


def fetch_articles(symbol, start_iso, end_iso, session):
    """Yield article dicts (id, symbol, date, headline, summary) for symbol."""
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
            yield {
                'id': a['id'],
                'symbol': symbol,
                'date': a['created_at'][:10],
                'created_at': a['created_at'],
                'headline': (a.get('headline') or '')[:500],
                'summary': (a.get('summary') or '')[:1000],
            }
        page_token = j.get('next_page_token')
        if not page_token:
            break
        if requests_made % 500 == 0:
            time.sleep(1.0)


def main():
    args = parse_args()
    print(f'Date range: {args.start} → {args.end}')
    if args.symbols:
        symbols = args.symbols.split(',')
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
        sym_rows = list(fetch_articles(sym, start_iso, end_iso, session))
        rows.extend(sym_rows)
        elapsed = time.time() - ti
        print(f'[{i:>3}/{len(symbols)}] {sym:<6} {len(sym_rows):>7} articles  '
              f'{elapsed:.1f}s  (total elapsed {(time.time()-t0)/60:.1f}min)')

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    # De-duplicate (same article may surface under multiple symbols)
    df = df.drop_duplicates(subset=['id', 'symbol']).sort_values(['symbol', 'date']).reset_index(drop=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_parquet(args.out, index=False)
    print()
    print(f'Wrote {len(df):,} article-symbol rows ({df.id.nunique():,} unique articles, '
          f'{df.symbol.nunique()} symbols) to {args.out}')
    print(f'Total time: {(time.time()-t0)/60:.1f} min')

    if args.upload_s3:
        import boto3
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket = 'rigacap-prod-price-data-149218244179'
        s3.upload_file(args.out, bucket, args.s3_key)
        print(f'Uploaded to s3://{bucket}/{args.s3_key}')


if __name__ == '__main__':
    main()
