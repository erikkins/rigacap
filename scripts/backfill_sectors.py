#!/usr/bin/env python3
"""
One-time sector/industry backfill from yfinance.

Fetches `sector`, `industry`, `country` for every symbol in the local
universe and writes a single S3 file at `universe/sectors_cache.json`.

The product is loaded by `stock_universe_service.ensure_loaded()` and
merged into `symbol_info` so consumers (scanner sector cap, dashboards,
research scripts) see the data.

This is the SOURCE of sector data for the entire system — the NASDAQ
screener API stopped returning sector fields, and lazy yfinance lookups
in the dashboard detail endpoint never propagate back to S3.

Usage:
    source backend/venv/bin/activate
    python3 scripts/backfill_sectors.py                  # full universe (~80 min)
    python3 scripts/backfill_sectors.py --limit 500      # top 500 only
    python3 scripts/backfill_sectors.py --resume         # skip symbols already in S3 cache

Cron (deferred): run weekly via Lambda, merge new symbols, refresh stale.
"""
import argparse, json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
if not os.environ.get('DATABASE_URL'):
    for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
        if line.startswith('DATABASE_URL='):
            os.environ['DATABASE_URL'] = line.strip().split('=', 1)[1]
            break
os.environ.setdefault('LAMBDA_ROLE', 'worker')

import yfinance as yf
import boto3

S3_BUCKET = 'rigacap-prod-price-data-149218244179'
S3_KEY = 'universe/sectors_cache.json'
LOCAL_FALLBACK = '/tmp/sectors_cache.json'


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=0, help='Only fetch top N symbols (by alphabetical, 0=all)')
    p.add_argument('--resume', action='store_true', help='Skip symbols already in the existing S3 cache')
    p.add_argument('--sleep', type=float, default=0.1, help='Seconds between yfinance calls (default 0.1)')
    p.add_argument('--no-upload', action='store_true', help='Skip S3 upload, just write local file')
    return p.parse_args()


def load_existing_cache():
    """Load whatever's currently in S3 (if anything) for --resume mode."""
    try:
        s3 = boto3.Session(profile_name='rigacap').client('s3')
        resp = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        return json.loads(resp['Body'].read())
    except Exception:
        return {}


def upload_cache(cache):
    """Atomic-ish upload to S3."""
    s3 = boto3.Session(profile_name='rigacap').client('s3')
    body = json.dumps(cache, indent=2)
    s3.put_object(
        Bucket=S3_BUCKET, Key=S3_KEY,
        Body=body, ContentType='application/json',
    )
    print(f"  📤 Uploaded {len(cache)} entries to s3://{S3_BUCKET}/{S3_KEY}")


def fetch_one(symbol):
    """yfinance .info call — returns dict with sector/industry/country/long_name."""
    try:
        info = yf.Ticker(symbol).info or {}
        return {
            'sector': info.get('sector') or '',
            'industry': info.get('industry') or '',
            'country': info.get('country') or '',
            'long_name': info.get('longName') or info.get('shortName') or '',
        }
    except Exception as e:
        return {'sector': '', 'industry': '', 'country': '', 'long_name': '', '_error': str(e)[:80]}


def main():
    args = parse_args()
    import asyncio
    from app.services.stock_universe import stock_universe_service

    # Get universe
    syms = asyncio.get_event_loop().run_until_complete(stock_universe_service.ensure_loaded())
    syms = sorted(syms)
    if args.limit > 0:
        syms = syms[:args.limit]
    print(f"📊 Universe: {len(syms)} symbols")

    existing = load_existing_cache() if args.resume else {}
    if existing:
        print(f"📦 Resume mode: {len(existing)} entries already in S3 cache")

    cache = dict(existing)
    cache['_meta'] = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'source': 'yfinance .info',
        'symbol_count_in_run': len(syms),
    }

    to_fetch = [s for s in syms if s not in existing or not existing.get(s, {}).get('sector')]
    print(f"🔍 To fetch: {len(to_fetch)} symbols (already populated: {len(syms) - len(to_fetch)})")

    t0 = time.time()
    upload_every = 500   # save progress every N symbols
    sector_counts = {}

    for i, sym in enumerate(to_fetch, 1):
        info = fetch_one(sym)
        cache[sym] = info
        if info.get('sector'):
            sector_counts[info['sector']] = sector_counts.get(info['sector'], 0) + 1

        if i % 50 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            remain = (len(to_fetch) - i) / rate if rate > 0 else 0
            print(f"  [{i}/{len(to_fetch)}] {sym} sector={info.get('sector', '—')!r:>30}  "
                  f"({rate:.1f}/s, ~{remain/60:.1f}m left)")

        if i % upload_every == 0 and not args.no_upload:
            cache['_meta']['updated'] = datetime.now(timezone.utc).isoformat()
            cache['_meta']['symbol_count_in_run'] = i
            upload_cache(cache)

        time.sleep(args.sleep)

    # Final write
    cache['_meta']['updated'] = datetime.now(timezone.utc).isoformat()
    cache['_meta']['symbol_count_in_run'] = len(to_fetch)
    cache['_meta']['total_in_cache'] = len([k for k in cache if not k.startswith('_')])

    # Always write local copy
    with open(LOCAL_FALLBACK, 'w') as f:
        json.dump(cache, f, indent=2)
    print(f"\n💾 Local copy written: {LOCAL_FALLBACK}")

    if not args.no_upload:
        upload_cache(cache)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"DONE — {len(to_fetch)} symbols processed in {(time.time() - t0)/60:.1f} min")
    print(f"{'=' * 60}")
    total_with_sector = sum(1 for k, v in cache.items() if not k.startswith('_') and v.get('sector'))
    print(f"Total in cache with sector: {total_with_sector} / {len([k for k in cache if not k.startswith('_')])}")
    print(f"\nTop sectors:")
    for sec, n in sorted(sector_counts.items(), key=lambda x: -x[1])[:12]:
        print(f"  {sec:<30} {n}")


if __name__ == '__main__':
    main()
