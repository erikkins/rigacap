"""PITFWU per-period walk-forward — the authoritative bench.

Reuses production's run_walk_forward_simulation (correct per-period universe
re-rank + position carry) but injects the PITFWU survivorship-free panel
(monkeypatched _get_top_symbols_as_of) over clean split-adjusted bars, no-AI,
fixed M3 params. This is the methodology that matches production, on honest data.

BASE only for now (VB params not yet plumbed through the WF path).
Usage: AWS_PROFILE=rigacap python scripts/pitfwu_wf_periods.py [dist]
"""
import os, sys, asyncio
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")
import pandas as pd
from datetime import datetime
import pitfwu_veneer as v
from app.services.scanner import scanner_service, _EXCLUDED_SET
from app.services.walk_forward_service import walk_forward_service
from app.core.database import async_session

_CA = v.load_corp_actions()
_RAW = {}  # symbol -> raw bars, loaded once and reused across windows


def _ind(df):
    df = df.copy(); pv = df["close"] * df["volume"]
    df["dwap"] = pv.rolling(200, min_periods=50).sum() / df["volume"].rolling(200, min_periods=50).sum()
    df["ma_50"] = df["close"].rolling(50, min_periods=1).mean(); df["ma_200"] = df["close"].rolling(200, min_periods=1).mean()
    df["vol_avg"] = df["volume"].rolling(20, min_periods=1).mean(); df["high_52w"] = df["close"].rolling(252, min_periods=1).max()
    return df


def _vix():
    import yfinance as yf
    x = yf.download("^VIX", start="2021-06-01", end="2026-06-05", progress=False, auto_adjust=False)
    x.columns = [(c[0] if isinstance(c, tuple) else c).lower() for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None).normalize(); return x


_VIX = _vix()


def _clean(u):
    return [s for s in u if s not in _EXCLUDED_SET and not s.startswith("^")]


def _bars(sym, end):
    if sym not in _RAW:
        _RAW[sym] = v.load_bars(sym)
    df = _RAW[sym].copy(); asof = pd.Timestamp(end)
    for ex, f in v.split_factors(sym, _CA):
        if ex <= asof:
            m = df.index < ex
            for c in ("open", "high", "low", "close"):
                df.loc[m, c] = df.loc[m, c] / f
            df["volume"] = df["volume"].astype(float); df.loc[m, "volume"] = df.loc[m, "volume"] * f
    return _ind(df)


async def wf(start, end, max_pos=6, size=15.0, trail=12.0):
    periods = walk_forward_service._get_period_dates(start, end, "biweekly")
    union = set()
    for ps, pe in periods:
        union |= set(_clean(v.universe_asof_prod(ps, 300, 15.0))[:100])
    cache = {}
    for sym in union | {"SPY"}:
        try: cache[sym] = _bars(sym, end)
        except Exception: pass
    cache["^VIX"] = _VIX
    scanner_service.data_cache = cache; scanner_service.universe = list(cache.keys())
    walk_forward_service._get_top_symbols_as_of = lambda asof, maxn: _clean(v.universe_asof_prod(asof, maxn * 3, 15.0))[:maxn]
    async with async_session() as db:
        r = await walk_forward_service.run_walk_forward_simulation(
            db, start, end, enable_ai_optimization=False, fixed_strategy_id=6, max_symbols=100,
            reoptimization_frequency="biweekly", carry_positions=True, n_trials=0,
            max_positions=max_pos, position_size_pct=size, dwap_threshold_pct=5.0,
            near_50d_high_pct=3.0, trailing_stop_pct=trail)
    yrs = (end - start).days / 365.25
    return {"ann": ((1 + r.total_return_pct / 100) ** (1 / yrs) - 1) * 100,
            "sharpe": r.sharpe_ratio, "mdd": r.max_drawdown_pct, "total": r.total_return_pct,
            "trades": len(r.trades), "yrs": yrs, "size": size}


def _starts_ends():
    starts = [datetime(y, m, 3) for y in (2022, 2023) for m in (1, 4, 7, 10)] + \
             [datetime(2024, m, 3) for m in (1, 4)]
    out = []
    for s in starts:
        e = datetime(2026, 5, 29) if s.year + 2 > 2026 else datetime(s.year + 2, s.month, 28)
        out.append((s, e))
    return out


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "cost":
        # net-of-cost: annual drag = (trades/yr) * round_trip_cost * size_pct
        CONFIGS = [
            ("20x4.5 t12 (broad)",  20, 4.5, 12.0),
            ("20x4.5 t25 (b+hold)", 20, 4.5, 25.0),
            ("30x3.0 t25 (maxdiv)", 30, 3.0, 25.0),
        ]
        se = _starts_ends()
        print(f"=== NET-OF-COST — gross vs net at 10bps / 20bps round-trip, across {len(se)} starts ===")
        for label, mp, sz, tr in CONFIGS:
            anns, tpy = [], []
            for s, e in se:
                r = await wf(s, e, mp, sz, tr)
                anns.append(r["ann"]); tpy.append(r["trades"] / r["yrs"])
            A = pd.Series(anns); tradesyr = pd.Series(tpy).mean()
            # drag(pp) = trades/yr * cost_rt(frac) * size_pct(frac) * 100
            d10 = tradesyr * 0.0010 * (sz / 100) * 100
            d20 = tradesyr * 0.0020 * (sz / 100) * 100
            print(f"  {label:22} gross_ann={A.mean():5.1f}%  trades/yr={tradesyr:5.0f}  "
                  f"net@10bps={A.mean()-d10:5.1f}%  net@20bps={A.mean()-d20:5.1f}%  (drag 10/20 = {d10:.1f}/{d20:.1f}pp)", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        # size + exit sweep, each config through the full start-date distribution
        CONFIGS = [
            ("6x15  trail12  (T3 baseline)", 6, 15.0, 12.0),
            ("12x7.5 trail12 (mid)",         12, 7.5, 12.0),
            ("20x4.5 trail12 (broad)",       20, 4.5, 12.0),
            ("20x4.5 trail25 (broad+hold)",  20, 4.5, 25.0),
            ("30x3.0 trail25 (max diversify)", 30, 3.0, 25.0),
        ]
        se = _starts_ends()
        print(f"=== SIZE+EXIT SWEEP — each config across {len(se)} start dates (2y windows) ===")
        for label, mp, sz, tr in CONFIGS:
            anns, mdds, shps = [], [], []
            for s, e in se:
                r = await wf(s, e, mp, sz, tr)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            print(f"  {label:32} ann mean={A.mean():5.1f}% std={A.std():4.1f}%  "
                  f"sharpe={S.mean():5.2f}  mdd mean={M.mean():4.1f}% worst={M.max():4.1f}%  "
                  f"min_ann={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "dist":
        # start-date distribution: 2y forward windows, quarterly starts
        starts = [datetime(y, m, 3) for y in (2022, 2023) for m in (1, 4, 7, 10)] + \
                 [datetime(2024, m, 3) for m in (1, 4)]
        print("=== PITFWU per-period WF BASE — start-date distribution (2y windows) ===")
        rows = []
        for s in starts:
            e = datetime(min(s.year + 2, 2026), s.month, min(s.day if not (s.year+2>2026) else 29, 28))
            e = datetime(2026, 5, 29) if s.year + 2 > 2026 else datetime(s.year + 2, s.month, 28)
            r = await wf(s, e)
            rows.append((s, r)); print(f"  {s.date()} -> {e.date()}:  ann={r['ann']:6.1f}%  sharpe={r['sharpe']:5.2f}  mdd={r['mdd']:5.1f}%", flush=True)
        anns = [r["ann"] for _, r in rows]; mdds = [r["mdd"] for _, r in rows]
        print(f"\n  ann: mean={pd.Series(anns).mean():.1f}%  std={pd.Series(anns).std():.1f}%  min={min(anns):.1f}%  max={max(anns):.1f}%")
        print(f"  mdd: mean={pd.Series(mdds).mean():.1f}%  std={pd.Series(mdds).std():.1f}%  worst={max(mdds):.1f}%")
        print(f"  -> start-date variance: {pd.Series(anns).std():.1f}pp ann std across {len(starts)} starts")
    else:
        s, e = datetime(2022, 1, 3), datetime(2026, 5, 29)
        r = await wf(s, e)
        print(f"WF BASE bear-incl: ann={r['ann']:.1f}%  sharpe={r['sharpe']:.2f}  mdd={r['mdd']:.1f}%")

asyncio.run(main())
