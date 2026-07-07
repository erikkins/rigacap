"""PITFWU veneer — the as-of-T interaction layer.

The raw data on S3 (per-symbol parquet bars + corp-actions calendar + delistings)
is IMMUTABLE. This module never modifies it — it *composes* it into point-in-time
views on read:

  - universe_asof(T, N)        -> survivorship-free top-N by liquidity as-of T
  - split_adjusted(sym, asof)  -> raw bars with ONLY splits ex-date <= asof applied
  - last_trade(sym)            -> delisting date + terminal price (series end)

The invariant: nothing here ever uses information dated after `asof`. That's what
makes it point-in-time. Fully-adjusting to "today" (future splits baked in) is the
thing we are deliberately NOT doing.

Stage v1: split adjustment is applied for splits with ex-date <= a single asof date
(typically the backtest window end) — correct for returns, and the min-price leak
only bites when an in-window split pushes a price under $15 (rare in recent windows).
Stage v2 (full event engine) re-derives as-of EACH sim day. This module exposes both.
"""
import io
import os
import boto3
import pandas as pd

BUCKET = "rigacap-prod-price-data-149218244179"
# Offline / fast-path: if PITFWU_LOCAL points at a dir mirroring the S3 key
# layout (e.g. ~/pitfwu_cache/pitfwu/bars/AAPL.parquet), reads come from disk
# instead of S3 — required for plane/offline runs, and much faster otherwise.
PITFWU_LOCAL = os.environ.get("PITFWU_LOCAL")
_S3 = None
_PANEL = None
_CA = None

# EXT mode (Jun 10 2026): opt-in pre-2016 extension. When True, load_bars
# prepends pitfwu/bars_ext/ rows (yfinance, de-adjusted to as-traded, ~2005+),
# corp actions include calendar_pre2016 (yf splits ex<2016 only), and universe
# panels read the *_ext merged keys. Default False so every existing bench
# reproduces byte-for-byte. CAVEAT: pre-2016 layer is SURVIVORSHIP-BIASED
# (yfinance lacks delisted names) — label all pre-2016 results.
EXT = False
_CA_EXT = None


def s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.Session(profile_name="rigacap", region_name="us-east-1").client("s3")
    return _S3


def _read_parquet(key):
    if PITFWU_LOCAL:
        p = os.path.join(PITFWU_LOCAL, key)
        if os.path.exists(p):
            return pd.read_parquet(p)
    df = pd.read_parquet(io.BytesIO(s3().get_object(Bucket=BUCKET, Key=key)["Body"].read()))
    if PITFWU_LOCAL:  # write-through: warm the cache with exactly what we touch
        try:
            p = os.path.join(PITFWU_LOCAL, key)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            df.to_parquet(p)
        except Exception:
            pass
    return df



# ---------------------------------------------------------------- universe
def load_panel():
    """Liquidity panel: dates x symbols of 20d trailing avg dollar-volume."""
    global _PANEL
    if _PANEL is None:
        key = "pitfwu/universe/liquidity_dv20_ext.parquet" if EXT else "pitfwu/universe/liquidity_dv20.parquet"
        _PANEL = _read_parquet(key)
        _PANEL.index = pd.to_datetime(_PANEL.index)
    return _PANEL


# Rename stubs to drop in favor of the continuous-history ticker (the new ticker
# already carries the full back-history via Alpaca). Verified case-by-case — NOT
# applied blindly from name_changes, which contains noise (e.g. bogus META->METV)
# and occasional CUSIP changes. Extend as renames are confirmed.
RENAME_STUBS = {"FB"}  # -> META carries 2016+; FB is a sparse post-rename stub


def universe_asof(date, n=100, panel=None):
    """Survivorship-free top-N symbols by liquidity, using only data <= `date`.
    Includes names that later delisted (they rank by what they were on `date`).
    Drops known rename stubs so a renamed company isn't double-counted."""
    panel = panel if panel is not None else load_panel()
    asof = panel.loc[:pd.Timestamp(date)]
    if asof.empty:
        return []
    row = asof.iloc[-1].dropna()
    ranked = [s for s in row.sort_values(ascending=False).index if s not in RENAME_STUBS]
    return ranked[:n]


_VOL60 = None
_CLOSE = None


def load_vol60():
    global _VOL60
    if _VOL60 is None:
        key = "pitfwu/universe/vol60_ext.parquet" if EXT else "pitfwu/universe/vol60.parquet"
        _VOL60 = _read_parquet(key)
        _VOL60.index = pd.to_datetime(_VOL60.index)
    return _VOL60


def load_close_panel():
    global _CLOSE
    if _CLOSE is None:
        key = "pitfwu/universe/close_ext.parquet" if EXT else "pitfwu/universe/close.parquet"
        _CLOSE = _read_parquet(key)
        _CLOSE.index = pd.to_datetime(_CLOSE.index)
    return _CLOSE


def universe_asof_prod(date, n=100, min_price=15.0):
    """PRODUCTION-MATCHING universe: top-N by 60-day average VOLUME, with a
    min-price floor (close >= min_price) applied at the selection date. Mirrors
    backend _get_top_symbols_as_of exactly — the only difference is the candidate
    pool is the survivorship-free PITFWU set. Point-in-time (uses only data <= date)."""
    d = pd.Timestamp(date)
    vol = load_vol60().loc[:d]
    if vol.empty:
        return []
    vrow = vol.iloc[-1].dropna()
    crow = load_close_panel().loc[:d].iloc[-1]
    eligible = [s for s in vrow.index if s not in RENAME_STUBS and crow.get(s, 0) >= min_price]
    return list(vrow[eligible].sort_values(ascending=False).head(n).index)


# ---------------------------------------------------------------- corp-actions
def load_corp_actions():
    global _CA, _CA_EXT
    if _CA is None:
        _CA = _read_parquet("pitfwu/corp_actions/calendar.parquet")
    if EXT:
        if _CA_EXT is None:
            pre = _read_parquet("pitfwu/corp_actions/calendar_pre2016.parquet")
            _CA_EXT = pd.concat([pre, _CA], ignore_index=True)
        return _CA_EXT
    return _CA


def split_factors(symbol, ca=None):
    """Return sorted [(ex_date, factor)] for `symbol` — forward splits (factor>1,
    price divides) and reverse splits (factor<1, price multiplies)."""
    ca = ca if ca is not None else load_corp_actions()
    out = []
    sub = ca[(ca["symbol"] == symbol) & (ca["type"].isin(["forward_splits", "reverse_splits"]))]
    for _, e in sub.iterrows():
        try:
            old, new = float(e["old_rate"]), float(e["new_rate"])
            if old > 0 and new > 0 and e.get("date"):
                out.append((pd.Timestamp(e["date"]), new / old))  # forward 2:1 -> new/old=2
        except (TypeError, ValueError):
            continue
    return sorted(out)


# ---------------------------------------------------------------- bars
def load_bars(symbol):
    df = _read_parquet(f"pitfwu/bars/{symbol}.parquet")
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date").sort_index()
    if EXT:
        try:
            pre = _read_parquet(f"pitfwu/bars_ext/{symbol}.parquet")
            pre.index = pd.to_datetime(pre.index).tz_localize(None).normalize()
            df = pd.concat([pre[pre.index < df.index.min()], df]).sort_index()
        except Exception:
            pass  # no pre-2016 extension for this symbol
    return df


def split_adjusted(symbol, asof=None, ca=None):
    """Raw bars with splits whose ex-date <= `asof` applied (point-in-time as-of
    `asof`; None = apply all known splits). Prices BEFORE each split ex-date are
    divided by the factor (forward) / multiplied (reverse); volume inverse."""
    df = load_bars(symbol).copy()
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


def last_trade(symbol):
    """(last_trade_date, last_close) — for delisting handling: a held position
    whose series ends mid-window is closed at this terminal price."""
    df = load_bars(symbol)
    return df.index.max(), float(df["close"].iloc[-1])
