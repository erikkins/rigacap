"""PITFWU pre-2016 extension (Jun 10 2026) — backfill bars to ~2005 via yfinance.

Why: decides the egate (needs 2008-09/2011/2015-16 factor-stress episodes),
stress-tests naive momentum's 28.8% against the 2009 momentum crash, and powers
the portfolio-race animation back-history.

Conventions (must match the immutable 2016+ layer):
  - bars are RAW AS-TRADED prices; splits applied at READ time via the calendar.
    yfinance 'Close' (auto_adjust=False) is SPLIT-ADJUSTED-TO-TODAY (dividends
    not adjusted), so we DE-ADJUST: raw[d] = yf_close[d] * prod(splits ex>d),
    volume inverse. The 2016 overlap vs Alpaca raw verifies this arithmetic.
  - price-return (no dividend adjustment) — matches v1.
  - NEW S3 keys only: pitfwu/bars_ext/{sym}.parquet (pre-2016 rows),
    pitfwu/corp_actions/calendar_pre2016.parquet (yf splits ex<2016 ONLY —
    2016+ stays Alpaca's; duplicates would double-adjust).

KNOWN LIMITATION (label every pre-2016 result): survivorship bias — yfinance
lacks delisted names (Lehman, WaMu, ...). Flattering to all strategies in
stress windows; direction still decisive.

Phases (each checkpointed, resumable):
  1. pool   — top N by 2016 liquidity from the existing dv20 panel
  2. pull   — batched yfinance download, de-adjust, validate vs 2016 overlap,
              write local cache + collect splits
  3. upload — push bars_ext + calendar_pre2016 to S3
  4. panels — recompute merged dv20/vol60/close panels (full span) -> *_ext

Usage: AWS_PROFILE=rigacap backend/venv/bin/python scripts/pitfwu_extend.py [pool|pull|upload|panels|all]
"""
import io
import json
import os
import sys
import time

R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "scripts"))
import pandas as pd
import pitfwu_veneer as v

POOL_N = 3000
START = "2004-12-01"
CUTOVER = pd.Timestamp("2016-01-04")     # first day of the existing layer
WORK = os.path.expanduser("~/.cache/pitfwu_ext")
BARS_DIR = os.path.join(WORK, "bars")
os.makedirs(BARS_DIR, exist_ok=True)
POOL_PATH = os.path.join(WORK, "pool.json")
SPLITS_PATH = os.path.join(WORK, "splits_pre2016.parquet")
PROGRESS_PATH = os.path.join(WORK, "progress.json")
VALIDATE_PATH = os.path.join(WORK, "validation.csv")
CHUNK = 50


def _progress():
    return json.load(open(PROGRESS_PATH)) if os.path.exists(PROGRESS_PATH) else {"done_chunks": []}


def phase_pool():
    if os.path.exists(POOL_PATH):
        pool = json.load(open(POOL_PATH))
        print(f"pool cached: {len(pool)} symbols")
        return pool
    dv = v.load_panel()  # dates x symbols, 20d dollar-volume
    h1 = dv.loc["2016-01-01":"2016-07-01"]
    rank = h1.max().dropna().sort_values(ascending=False)
    pool = [s for s in rank.index[:POOL_N] if "." not in s and "^" not in s]
    pool = list(dict.fromkeys(["SPY"] + pool))
    json.dump(pool, open(POOL_PATH, "w"))
    print(f"pool built: {len(pool)} symbols (top {POOL_N} by 2016H1 dollar-volume)")
    return pool


def _deadjust(df, splits):
    """raw[d] = adj[d] * prod(split ratios with ex-date > d); volume inverse."""
    if splits is None or splits.empty:
        return df
    out = df.copy()
    fut = splits.sort_index()
    # cumulative future factor per bar date: product of ratios strictly after d
    factor = pd.Series(1.0, index=out.index)
    for ex, ratio in fut.items():
        if ratio and ratio > 0:
            mask = out.index < ex
            factor[mask] *= ratio
    for c in ("open", "high", "low", "close"):
        out[c] = out[c] * factor
    out["volume"] = out["volume"] / factor
    return out


def phase_pull():
    import yfinance as yf
    pool = phase_pool()
    existing = set()
    prog = _progress()
    chunks = [pool[i:i + CHUNK] for i in range(0, len(pool), CHUNK)]
    all_splits = []
    if os.path.exists(SPLITS_PATH):
        all_splits.append(pd.read_parquet(SPLITS_PATH))
    val_rows = []
    for ci, chunk in enumerate(chunks):
        if ci in prog["done_chunks"]:
            continue
        try:
            data = yf.download(" ".join(chunk), start=START, progress=False,
                               auto_adjust=False, actions=True, group_by="ticker",
                               threads=True, timeout=60)
        except Exception as ex:
            print(f"chunk {ci}: download failed ({ex}) — retry next run", flush=True)
            time.sleep(10)
            continue
        kept = 0
        for sym in chunk:
            try:
                sub = data[sym].dropna(subset=["Close"])
            except Exception:
                continue
            if sub.empty or sub.index.min() >= CUTOVER:
                continue  # no pre-2016 history
            sub = sub.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                      "Close": "close", "Volume": "volume",
                                      "Stock Splits": "splits"})
            sub.index = pd.to_datetime(sub.index).tz_localize(None).normalize()
            spl = sub["splits"][sub["splits"] > 0] if "splits" in sub else pd.Series(dtype=float)
            raw = _deadjust(sub[["open", "high", "low", "close", "volume"]], spl)
            # validation: overlap vs existing Alpaca raw bars (first ~8 days of 2016)
            try:
                alp = v.load_bars(sym)["close"].loc["2016-01-04":"2016-01-15"]
                yfc = raw["close"].loc["2016-01-04":"2016-01-15"]
                common = alp.index.intersection(yfc.index)
                ratio = float((yfc.loc[common] / alp.loc[common]).median()) if len(common) >= 3 else None
            except Exception:
                ratio = None
            ok = ratio is not None and abs(ratio - 1) < 0.02
            val_rows.append({"symbol": sym, "ratio": ratio, "ok": ok,
                             "first": str(raw.index.min().date())})
            if not ok:
                continue  # exclude mismatches; reported in validation.csv
            pre = raw[raw.index < CUTOVER]
            if len(pre) < 60:
                continue
            pre.to_parquet(os.path.join(BARS_DIR, f"{sym}.parquet"))
            for ex, ratio_s in spl.items():
                if pd.Timestamp(ex) < CUTOVER and ratio_s > 0:
                    all_splits.append(pd.DataFrame([{
                        "symbol": sym, "type": "forward_splits" if ratio_s > 1 else "reverse_splits",
                        "date": pd.Timestamp(ex), "old_rate": 1.0, "new_rate": float(ratio_s)}]))
            kept += 1
        prog["done_chunks"].append(ci)
        json.dump(prog, open(PROGRESS_PATH, "w"))
        if all_splits:
            pd.concat([s for s in all_splits if isinstance(s, pd.DataFrame)],
                      ignore_index=True).drop_duplicates().to_parquet(SPLITS_PATH)
        if val_rows:
            df_new = pd.DataFrame(val_rows)
            if os.path.exists(VALIDATE_PATH):
                df_new = pd.concat([pd.read_csv(VALIDATE_PATH), df_new], ignore_index=True)
            df_new.drop_duplicates(subset="symbol", keep="last").to_csv(VALIDATE_PATH, index=False)
            val_rows = []
        print(f"chunk {ci + 1}/{len(chunks)}: kept {kept}/{len(chunk)}", flush=True)
        time.sleep(2)
    n_files = len(os.listdir(BARS_DIR))
    print(f"PULL DONE: {n_files} symbols with pre-2016 bars cached at {BARS_DIR}", flush=True)


def phase_upload():
    s3 = v.s3()
    files = sorted(os.listdir(BARS_DIR))
    for i, f in enumerate(files):
        s3.upload_file(os.path.join(BARS_DIR, f), v.BUCKET, f"pitfwu/bars_ext/{f}")
        if (i + 1) % 250 == 0:
            print(f"uploaded {i + 1}/{len(files)}", flush=True)
    if os.path.exists(SPLITS_PATH):
        s3.upload_file(SPLITS_PATH, v.BUCKET, "pitfwu/corp_actions/calendar_pre2016.parquet")
    print(f"UPLOAD DONE: {len(files)} bars_ext + calendar_pre2016", flush=True)


def phase_panels():
    """Merged full-span universe panels: pre-2016 (from bars_ext pool) stitched
    above the existing 2016+ panels -> universe/{vol60,close,liquidity_dv20}_ext."""
    closes, vols = {}, {}
    for f in sorted(os.listdir(BARS_DIR)):
        sym = f.replace(".parquet", "")
        df = pd.read_parquet(os.path.join(BARS_DIR, f))
        closes[sym] = df["close"]
        vols[sym] = df["volume"]
    close_pre = pd.DataFrame(closes)
    volume_pre = pd.DataFrame(vols)
    vol60_pre = volume_pre.rolling(60, min_periods=20).mean()
    dv20_pre = (close_pre * volume_pre).rolling(20, min_periods=5).mean()
    s3 = v.s3()
    for name, pre, full_loader in [("close", close_pre, v.load_close_panel),
                                   ("vol60", vol60_pre, v.load_vol60),
                                   ("liquidity_dv20", dv20_pre, v.load_panel)]:
        post = full_loader()
        merged = pd.concat([pre[pre.index < CUTOVER], post], axis=0).sort_index()
        buf = io.BytesIO()
        merged.to_parquet(buf)
        buf.seek(0)
        s3.put_object(Bucket=v.BUCKET, Key=f"pitfwu/universe/{name}_ext.parquet", Body=buf.read())
        print(f"panel {name}_ext: {merged.shape[0]} days x {merged.shape[1]} symbols "
              f"({merged.index.min().date()} -> {merged.index.max().date()})", flush=True)
    print("PANELS DONE", flush=True)


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    if phase in ("pool", "all"):
        phase_pool()
    if phase in ("pull", "all"):
        phase_pull()
    if phase in ("upload", "all"):
        phase_upload()
    if phase in ("panels", "all"):
        phase_panels()
