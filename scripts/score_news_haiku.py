#!/usr/bin/env python3
"""
Score cached news headlines (Path B) for short-term stock-impact polarity
using Claude Haiku. Reads headlines.parquet, writes sentiment.parquet
with per-article scores + per (symbol, date) aggregates.

Cost: ~$25 for 325k articles with headline+summary. ONE-TIME PASS.
Output cached durably to S3 — backtester reads from sentiment.parquet,
never re-calls Claude.
"""
import argparse, json, os, sys, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--in',  dest='input_path',
                   default=os.path.expanduser('~/rigacap-research/news/headlines.parquet'))
    p.add_argument('--out', default=os.path.expanduser('~/rigacap-research/news/sentiment.parquet'))
    p.add_argument('--agg-out', default=os.path.expanduser('~/rigacap-research/news/sentiment_daily.parquet'))
    p.add_argument('--batch-size', type=int, default=50)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--model', default='claude-haiku-4-5-20251001')
    p.add_argument('--upload-s3', action='store_true')
    p.add_argument('--resume', action='store_true',
                   help='Skip articles already in output parquet')
    return p.parse_args()


SYSTEM = (
    "You score financial news headlines for SHORT-TERM stock-price impact. "
    "Output ONE integer per headline on its own line:\n"
    "  +1 = clearly positive for stock (earnings beat, contract win, upgrade, FDA approval, etc.)\n"
    "   0 = neutral / unclear / company not primary actor / commentary\n"
    "  -1 = clearly negative for stock (earnings miss, fraud, lawsuit, recall, downgrade, etc.)\n"
    "No labels. No explanation. Just N numbers, one per line."
)


def build_prompt(batch):
    """batch = list of dicts with 'headline' and optional 'summary'."""
    lines = []
    for i, art in enumerate(batch, 1):
        head = art['headline'].replace('\n', ' ').strip()
        summ = (art.get('summary') or '').replace('\n', ' ').strip()
        if summ:
            lines.append(f"{i}. {head} — {summ[:200]}")
        else:
            lines.append(f"{i}. {head}")
    return f"Score these {len(batch)} headlines:\n\n" + "\n".join(lines)


def score_batch(batch, api_key, model, max_retries=3):
    """Call Claude Haiku for a batch, return list of int scores in same order."""
    body = {
        'model': model,
        'max_tokens': 4 * len(batch) + 50,
        'system': SYSTEM,
        'messages': [{'role': 'user', 'content': build_prompt(batch)}],
    }
    for attempt in range(max_retries):
        try:
            r = httpx.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01',
                         'content-type': 'application/json'},
                json=body, timeout=120.0)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt + 1)
                continue
            r.raise_for_status()
            j = r.json()
            text = j['content'][0]['text'].strip()
            usage = j.get('usage', {})
            scores = []
            for line in text.split('\n'):
                line = line.strip().lstrip('+').replace('−', '-')
                if not line: continue
                try:
                    scores.append(max(-1, min(1, int(line.split()[0]))))
                except Exception:
                    pass
            if len(scores) != len(batch):
                # Misaligned: pad/truncate to length
                if len(scores) < len(batch):
                    scores += [0] * (len(batch) - len(scores))
                else:
                    scores = scores[:len(batch)]
            return scores, usage
        except Exception as e:
            print(f'  batch retry {attempt+1}: {e}', file=sys.stderr)
            time.sleep(2 ** attempt + 1)
    return [0] * len(batch), {}


def main():
    args = parse_args()

    # Load Anthropic key from Lambda config if not in env
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        import subprocess
        out = subprocess.check_output([
            'aws', 'lambda', 'get-function-configuration',
            '--function-name', 'rigacap-prod-worker',
            '--region', 'us-east-1',
            '--query', 'Environment.Variables.ANTHROPIC_API_KEY',
            '--output', 'text',
            '--profile', 'rigacap',
        ], text=True).strip()
        api_key = out

    print(f'Loading {args.input_path}...')
    df = pd.read_parquet(args.input_path)
    print(f'  {len(df):,} article-symbol rows, {df.id.nunique():,} unique articles')

    # Dedupe by article ID (article may surface under multiple symbols, score once)
    unique_articles = df.drop_duplicates(subset=['id']).copy()
    print(f'  {len(unique_articles):,} unique articles to score')

    # Resume support
    done_ids = set()
    if args.resume and os.path.exists(args.out):
        existing = pd.read_parquet(args.out)
        done_ids = set(existing.id.tolist())
        print(f'  Resuming: {len(done_ids):,} already scored')
        unique_articles = unique_articles[~unique_articles.id.isin(done_ids)]

    if len(unique_articles) == 0:
        print('All articles already scored.')
    else:
        # Build batches
        batches = []
        records = unique_articles.to_dict('records')
        for i in range(0, len(records), args.batch_size):
            batches.append(records[i:i + args.batch_size])
        print(f'  {len(batches):,} batches of {args.batch_size} '
              f'(parallel workers: {args.workers})')

        # Score in parallel
        all_results = []
        total_in_tok = total_out_tok = 0
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as exe:
            futures = {exe.submit(score_batch, batch, api_key, args.model): batch
                       for batch in batches}
            for j, fut in enumerate(as_completed(futures), 1):
                batch = futures[fut]
                scores, usage = fut.result()
                for art, score in zip(batch, scores):
                    all_results.append({'id': art['id'], 'sentiment': score})
                total_in_tok += usage.get('input_tokens', 0)
                total_out_tok += usage.get('output_tokens', 0)
                if j % 50 == 0 or j == len(batches):
                    elapsed = time.time() - t0
                    rate = j / elapsed if elapsed > 0 else 0
                    eta_sec = (len(batches) - j) / rate if rate > 0 else 0
                    cost = total_in_tok * 0.80/1e6 + total_out_tok * 4.00/1e6
                    print(f'  [{j:>4}/{len(batches)}] {elapsed/60:.1f}min  '
                          f'tokens in={total_in_tok:,} out={total_out_tok:,}  '
                          f'cost so far=${cost:.2f}  ETA {eta_sec/60:.0f}min')

        scored_df = pd.DataFrame(all_results)
        # Re-join headline info for the output
        out_df = unique_articles[['id', 'symbol', 'date', 'headline']].merge(
            scored_df, on='id', how='left')

        # Merge with existing if resume
        if args.resume and len(done_ids) > 0:
            existing = pd.read_parquet(args.out)
            out_df = pd.concat([existing, out_df], ignore_index=True)
            out_df = out_df.drop_duplicates(subset=['id'])

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        out_df.to_parquet(args.out, index=False)
        print(f'\nWrote {len(out_df):,} scored articles to {args.out}')

    # Build per-(symbol, date) aggregate from ALL article-symbol mappings
    print('\nBuilding daily aggregates...')
    scored = pd.read_parquet(args.out)  # canonical scores by article id
    score_map = dict(zip(scored.id, scored.sentiment))

    # Use full df (with all symbol mappings) — same article may map to multiple symbols
    df['sentiment'] = df.id.map(score_map).fillna(0).astype(int)
    daily = df.groupby(['symbol', 'date']).agg(
        article_count=('id', 'count'),
        sentiment_sum=('sentiment', 'sum'),
        sentiment_mean=('sentiment', 'mean'),
        pos_count=('sentiment', lambda s: int((s > 0).sum())),
        neg_count=('sentiment', lambda s: int((s < 0).sum())),
    ).reset_index()
    daily.to_parquet(args.agg_out, index=False)
    print(f'Wrote {len(daily):,} (symbol, date) aggregates to {args.agg_out}')
    print(f'Mean sentiment_mean: {daily.sentiment_mean.mean():+.3f}')
    print(f'Articles with sentiment > 0: {(scored.sentiment > 0).sum():,}')
    print(f'Articles with sentiment < 0: {(scored.sentiment < 0).sum():,}')
    print(f'Articles with sentiment = 0: {(scored.sentiment == 0).sum():,}')

    if args.upload_s3:
        import boto3
        bucket = 'rigacap-prod-price-data-149218244179'
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.upload_file(args.out, bucket, 'research/news_sentiment/articles.parquet')
        s3.upload_file(args.agg_out, bucket, 'research/news_sentiment/sentiment_daily.parquet')
        print(f'Uploaded both parquets to s3://{bucket}/research/news_sentiment/')


if __name__ == '__main__':
    main()
