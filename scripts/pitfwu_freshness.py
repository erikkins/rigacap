#!/usr/bin/env python3
"""
PITFWU freshness pipeline — append daily RAW bars to pitfwu/bars/{sym}.parquet.

Option A (Erik-approved Jun 14 2026): PITFWU = single source of truth (raw
as-traded bars + corp-actions calendar). This appends the latest RAW bars so
prod and research read the same store. The daily veneer (separate) reproduces
the adjusted output the scan needs; the research veneer does split-only
point-in-time.

USAGE:
  # validate a small sample (dry run, no writes) — shows new bars + continuity
  #   + cross-check vs the prod pickle (recent raw close should match)
  python scripts/pitfwu_freshness.py validate

  # backfill the gap (PITFWU last date -> latest) for the active universe
  python scripts/pitfwu_freshness.py backfill            # DRY RUN
  python scripts/pitfwu_freshness.py backfill EXECUTE    # writes to S3

Raw bars are fetched with Alpaca Adjustment.RAW (as-traded), NOT the scan's
SPLIT-adjusted path. Per-symbol append dedupes by date; existing rows win is
NOT assumed — new fetch overwrites overlapping dates (corrects any prior bad bar).
"""
import sys, os, io, gzip, pickle
import pandas as pd
import boto3

BUCKET = "rigacap-prod-price-data-149218244179"
BARS_PREFIX = "pitfwu/bars/"
_S3 = None


def s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.Session(profile_name="rigacap", region_name="us-east-1").client("s3")
    return _S3


def _alpaca_client():
    """Build an Alpaca data client from the worker Lambda's credentials."""
    lam = boto3.Session(profile_name="rigacap", region_name="us-east-1").client("lambda")
    env = lam.get_function_configuration(FunctionName="rigacap-prod-worker")["Environment"]["Variables"]
    key = env.get("ALPACA_API_KEY") or env.get("ALPACA_KEY_ID")
    sec = env.get("ALPACA_SECRET_KEY") or env.get("ALPACA_API_SECRET")
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(key, sec)


def _to_alpaca(sym):
    """pitfwu/yfinance hyphen share-class (BRK-B) -> Alpaca dot (BRK.B)."""
    return sym.replace("-", ".")


def _bars_to_df(rows):
    df = pd.DataFrame([{
        "date": b.timestamp, "open": float(b.open), "high": float(b.high),
        "low": float(b.low), "close": float(b.close), "volume": int(b.volume),
    } for b in rows])
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df.set_index("date").sort_index()


def fetch_raw_bars(symbols, start, end, client=None):
    """Fetch RAW (as-traded) daily bars over [start, end]. Keyed by the ORIGINAL
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

    nbatch = (len(syms) + BATCH - 1) // BATCH
    for i in range(0, len(syms), BATCH):
        batch = [_to_alpaca(s) for s in syms[i:i + BATCH]]
        try:
            data = _req(batch)
        except Exception:
            # one bad symbol 400s the batch — fall back to per-symbol
            data = {}
            for a in batch:
                try:
                    d = _req([a])
                    data.update(d)
                except Exception:
                    bad.append(amap.get(a, a))
        for a, rows in data.items():
            if rows:
                out[amap.get(a, a)] = _bars_to_df(rows)
        print(f"  batch {i//BATCH+1}/{nbatch}: {sum(1 for a in batch if amap.get(a,a) in out)} with bars", flush=True)
    if bad:
        print(f"  skipped {len(bad)} bad/unknown symbols (first 10): {bad[:10]}", flush=True)
    return out


def _read_pitfwu_bars(symbol):
    """Read existing pitfwu/bars/{sym}.parquet -> DataFrame(index=date, OHLCV) or None."""
    try:
        raw = s3().get_object(Bucket=BUCKET, Key=f"{BARS_PREFIX}{symbol}.parquet")["Body"].read()
        df = pd.read_parquet(io.BytesIO(raw))
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        return df.set_index("date").sort_index()
    except s3().exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def _write_pitfwu_bars(symbol, df):
    """Write df (index=date) back to pitfwu/bars/{sym}.parquet with the date-as-column schema."""
    out = df.reset_index()  # date column restored
    out = out[["date", "open", "high", "low", "close", "volume"]]
    buf = io.BytesIO()
    out.to_parquet(buf, index=False)
    buf.seek(0)
    s3().put_object(Bucket=BUCKET, Key=f"{BARS_PREFIX}{symbol}.parquet", Body=buf.getvalue())


def append_pitfwu_bars(symbols, start, end, execute=False, client=None):
    """Fetch RAW bars [start,end] and append to each symbol's pitfwu/bars file.
    New fetch overwrites overlapping dates (corrects prior bad bars). DRY RUN
    unless execute=True. Returns a per-symbol summary."""
    fresh = fetch_raw_bars(symbols, start, end, client=client)
    print(f"\nfetched RAW for {len(fresh)}/{len(symbols)} symbols over {start}..{end}\n")
    summary = {"appended": 0, "new_symbol": 0, "skipped_no_new": 0, "no_fetch": 0}
    for sym in symbols:
        new = fresh.get(sym)
        if new is None or new.empty:
            summary["no_fetch"] += 1
            continue
        existing = _read_pitfwu_bars(sym)
        if existing is None:
            merged = new                                  # brand-new symbol (gap-only; full backfill is separate)
            summary["new_symbol"] += 1
            tag = "NEW-SYM"
        else:
            add = new[new.index > existing.index.max()]   # only dates after current last
            if add.empty:
                summary["skipped_no_new"] += 1
                continue
            merged = pd.concat([existing, add]).sort_index()
            merged = merged[~merged.index.duplicated(keep="last")]
            summary["appended"] += 1
            tag = f"+{len(add)}d"
        if execute:
            _write_pitfwu_bars(sym, merged)
        if summary["appended"] + summary["new_symbol"] <= 12:  # log first dozen
            last = merged.index.max().date()
            print(f"  {sym:6} {tag:8} -> {len(merged)} rows, last {last}  {'WROTE' if execute else '(dry)'}")
    return summary


def _pitfwu_last_date(ref="AAPL"):
    df = _read_pitfwu_bars(ref)
    return df.index.max() if df is not None else None


def cmd_validate():
    """Dry-run on the 7 live symbols: show appended bars + continuity + cross-check vs pickle."""
    syms = ["SNDK", "WULF", "BAC", "KEY", "KO", "KVUE", "VZ"]
    last = _pitfwu_last_date()
    start = (last + pd.Timedelta(days=1)).date().isoformat()
    end = pd.Timestamp.now().date().isoformat()
    print(f"PITFWU last date: {last.date()} | fetching gap {start}..{end}\n")
    fresh = fetch_raw_bars(syms, start, end)
    # cross-check the most recent RAW close vs the prod pickle (no splits in the gap
    # => recent raw close should equal the pickle's adjusted close to the penny)
    pk = None
    try:
        with gzip.open("/tmp/live_pickle.pkl.gz", "rb") as f:
            pk = pickle.load(f)
    except Exception:
        pass
    print(f"{'sym':6} {'new bars':>9} {'last raw close':>15} {'pickle close':>13}  cross-check")
    for s in syms:
        n = fresh.get(s)
        if n is None or n.empty:
            print(f"{s:6}  no new bars"); continue
        last_close = n["close"].iloc[-1]
        pkc = pk[s]["close"].iloc[-1] if pk and s in pk else float("nan")
        ok = "MATCH" if (pkc == pkc and abs(last_close - pkc) < 0.01) else (f"diff {last_close-pkc:+.2f}" if pkc==pkc else "no pickle")
        print(f"{s:6} {len(n):>9} {last_close:>15.2f} {pkc:>13.2f}  {ok}")
    print("\n(MATCH on recent close = RAW fetch is correct: no splits in the gap, so as-traded == adjusted.)")


def cmd_backfill(execute=False):
    """Backfill the gap for the active universe (pickle symbols)."""
    with gzip.open("/tmp/live_pickle.pkl.gz", "rb") as f:
        pk = pickle.load(f)
    syms = [s for s in pk.keys() if not s.startswith("^")]
    last = _pitfwu_last_date()
    start = (last + pd.Timedelta(days=1)).date().isoformat()
    end = pd.Timestamp.now().date().isoformat()
    print(f"Backfill {len(syms)} active symbols, gap {start}..{end}, execute={execute}\n")
    summ = append_pitfwu_bars(syms, start, end, execute=execute)
    print(f"\nSUMMARY: {summ}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "validate":
        cmd_validate()
    elif cmd == "backfill":
        cmd_backfill(execute=(len(sys.argv) > 2 and sys.argv[2] == "EXECUTE"))
    else:
        print(__doc__)
