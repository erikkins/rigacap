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
if os.environ.get("PITFWU_EXT"):
    v.EXT = True  # pre-2016 extended layer (survivorship-biased — label results)
from app.services.scanner import scanner_service, _EXCLUDED_SET
from app.services.walk_forward_service import walk_forward_service
from app.core.database import async_session
from app.services.strategy_analyzer import CustomBacktester

# The WF path instantiates CustomBacktester, whose configure() sets
# max_hold_days + profit_lock from the strategy params (overriding any default).
# trail/size DO apply (set as direct attrs after configure), but max_hold +
# profit_lock are ONLY set inside configure — so patch CustomBacktester.configure
# to set our values AFTER it runs. Research-only; prod default unchanged.
_MAX_HOLD = 60
_PLOCK = 0.0
_PLOCK_STOP = 8.0
_DISP = False
_DISP_MARGIN = 0.0
_DGATE = None
_CONV = 0.0
_SAMESEC = False
_SECMAP = {}
_VOLW = 0.0
_MOMDAYS = None  # (short_days, long_days) override — e.g. (250, 250) = 12-mo momentum ranking
_FORCE_QUALITY = False  # True = bypass passes_quality (MA20/50 trend + breakout) — ablation only
_MKTF = None  # None = leave strategy default; False = disable market regime filter (ablation)
_REFRESH_TOP_M = None  # P1 deliberate refresh: at period start, drop carried positions
                       # no longer in the top-M by composite score. None = off.
_REFRESH_BULL_ONLY = False  # P1b: refresh only when SPY > 200MA at period start
                            # (deliberate refresh in bulls, frozen book in stress)
_REFRESH_FACTOR_GATE = None  # P1c: pd.Series[bool] by date — refresh only when the
                             # MOMENTUM FACTOR is above its own 200d MA (the 2021-22
                             # unwind was index-invisible; SPY gate missed it)
_ENTRY_FACTOR_GATE = None    # P1d: block NEW ENTRIES (candidate generation) while the
                             # factor is below trend. Exits stay free; cash accumulates
                             # in unwinds. "Exits cheap, re-entries expensive" as a rule.
_GATE_SUSPENDED = False      # internal: refresh-ranking calls bypass the entry gate
                             # (else an unhealthy factor would empty top-M and dump the book)
_STOP_BAN_PERIODS = None     # P2 re-entry discipline: a symbol stopped out (trailing_stop)
                             # is ineligible for NEW entry for N subsequent periods
_STOP_BAN = {}               # symbol -> periods of ban remaining (cross-period state)
_REENTRY_MODE = False        # P3: smart regime re-entry (MA50 reclaim / V-bounce + latch)
_BEAR_KEEP = 0.0             # P3: keep top fraction of book (by unrealized P&L) on regime exit
_COOLDOWN_DAYS = 0           # P3: days in cash after regime exit before re-entry allowed


def _load_sectors():
    global _SECMAP
    if not _SECMAP:
        import json
        raw = json.loads(v.s3().get_object(Bucket=v.BUCKET, Key="universe/sectors_cache.json")["Body"].read())
        _SECMAP = {k: (val.get("sector") if isinstance(val, dict) else val) for k, val in raw.items()}
    return _SECMAP


_orig_run_backtest = CustomBacktester.run_backtest
def _patched_run_backtest(self, *args, **kwargs):
    """P1 refresh: before seeding, drop carried positions whose symbol has
    fallen out of the top-M composite ranking as of period start. Dropped
    value becomes cash via the existing carried_value accounting (same path
    as the 'no data at period start' drop), and the vacancies refill from
    the current ranking — deliberate book refresh instead of crisis-driven.
    NOTE: dropped positions don't book a trade record (capital chain stays
    correct; trade logs lose those exits). Research-only."""
    global _GATE_SUSPENDED
    ip = kwargs.get("initial_positions")
    start = kwargs.get("start_date")
    if _REFRESH_TOP_M and ip and start:
        d = pd.Timestamp(start)
        if _REFRESH_BULL_ONLY:
            spy = scanner_service.data_cache.get("SPY")
            row = self._get_row_for_date(spy, d) if spy is not None else None
            ma = row.get("ma_200") if row is not None else None
            if row is None or ma is None or pd.isna(ma) or row["close"] <= ma:
                return _orig_run_backtest(self, *args, **kwargs)  # stress: freeze book
        if _REFRESH_FACTOR_GATE is not None:
            seg = _REFRESH_FACTOR_GATE.loc[:d]
            if len(seg) == 0 or not bool(seg.iloc[-1]):
                return _orig_run_backtest(self, *args, **kwargs)  # factor stress: freeze book
        syms = kwargs.get("ticker_list") or list(scanner_service.data_cache.keys())
        scored = []
        _GATE_SUSPENDED = True
        try:
            for sym in syms:
                sd = self._calculate_momentum_score(sym, d)
                if sd:
                    scored.append((sd["composite_score"], sym))
        finally:
            _GATE_SUSPENDED = False
        scored.sort(reverse=True)
        top_m = set(s for _, s in scored[:_REFRESH_TOP_M])
        kept = {k: v for k, v in ip.items() if k in top_m}
        if len(kept) < len(ip):
            print(f"[REFRESH] top-{_REFRESH_TOP_M}: dropping {sorted(set(ip) - set(kept))} at {start}", flush=True)
        kwargs["initial_positions"] = kept
    result = _orig_run_backtest(self, *args, **kwargs)
    if _STOP_BAN_PERIODS:
        # decrement existing bans by one period, then ban this period's stop-outs
        for sym in list(_STOP_BAN):
            _STOP_BAN[sym] -= 1
            if _STOP_BAN[sym] <= 0:
                del _STOP_BAN[sym]
        for t in getattr(result, "trades", []) or []:
            if getattr(t, "exit_reason", None) == "trailing_stop":
                _STOP_BAN[getattr(t, "symbol", None)] = _STOP_BAN_PERIODS
    return result
CustomBacktester.run_backtest = _patched_run_backtest

_orig_calc_score = CustomBacktester._calculate_momentum_score
def _patched_calc_score(self, symbol, date):
    if _ENTRY_FACTOR_GATE is not None and not _GATE_SUSPENDED:
        seg = _ENTRY_FACTOR_GATE.loc[:pd.Timestamp(date)]
        if len(seg) and not bool(seg.iloc[-1]):
            return None  # factor below trend: no new entries (exits unaffected)
    if _STOP_BAN_PERIODS and not _GATE_SUSPENDED and _STOP_BAN.get(symbol, 0) > 0:
        return None  # recently stopped out: re-entry banned
    r = _orig_calc_score(self, symbol, date)
    if r is not None and _FORCE_QUALITY:
        r["passes_quality"] = True
    return r
CustomBacktester._calculate_momentum_score = _patched_calc_score

_orig_configure = CustomBacktester.configure
def _patched_configure(self, params):
    _orig_configure(self, params)
    # MIN-PRICE BUG FIX (Jun 10 2026): the backtester re-checks min_price ($15)
    # against END-adjusted prices — a stock at $150 in 2017 that later split 40:1
    # shows $3.75 adjusted and is silently excluded from entry (NVDA until 2020,
    # TSLA until ~2019). The $15 floor is already enforced POINT-IN-TIME at
    # universe selection (universe_asof_prod), so the bench disables the
    # adjusted-price re-check entirely. Research-only; prod (live prices) is correct.
    self.min_price = 0.0
    self.max_hold_days = _MAX_HOLD
    self.profit_lock_pct = _PLOCK
    self.profit_lock_stop_pct = _PLOCK_STOP
    self.allow_displacement = _DISP
    self.displacement_margin = _DISP_MARGIN
    self.displacement_regime_gate = _DGATE
    self.conviction_tilt = _CONV
    self.displacement_same_sector = _SAMESEC
    self.symbol_sectors = _SECMAP
    self.vol_weight = _VOLW
    if _MOMDAYS is not None:
        self.short_mom_days, self.long_mom_days = _MOMDAYS
    # NOTE: regime_reentry_mode/bear_keep_pct are passed through the WF call
    # (walk_forward_service overwrites backtester attrs at line ~873 from its
    # own params AFTER configure — setting them here gets stomped).
    # cooldown: WF line ~877 re-reads strategy_params.regime_cooldown_days,
    # so mutate the params object itself (shared with that read).
    if _COOLDOWN_DAYS:
        params.regime_cooldown_days = _COOLDOWN_DAYS
        self.regime_cooldown_days = _COOLDOWN_DAYS
    # Initial stop (Jun 12 research): entry-anchored floor under the wide trail.
    # New attr; nothing in walk_forward_service stomps it post-configure.
    self.initial_stop_pct = _INITIAL_STOP
_INITIAL_STOP = 0.0
CustomBacktester.configure = _patched_configure

_CA = v.load_corp_actions()
_RAW = {}  # symbol -> raw bars, loaded once and reused across windows


def _ind(df):
    df = df.copy(); pv = df["close"] * df["volume"]
    df["dwap"] = pv.rolling(200, min_periods=50).sum() / df["volume"].rolling(200, min_periods=50).sum()
    df["ma_50"] = df["close"].rolling(50, min_periods=1).mean(); df["ma_200"] = df["close"].rolling(200, min_periods=1).mean()
    df["vol_avg"] = df["volume"].rolling(20, min_periods=1).mean(); df["high_52w"] = df["close"].rolling(252, min_periods=1).max()
    return df


def _vix():
    # Disk-cached — yfinance hangs without timeout (burned 5.5h overnight Jun 10)
    # and the never-refetch rule applies anyway.
    cache = os.path.expanduser("~/.cache/pitfwu_close/_VIX_full.parquet")
    if os.path.exists(cache):
        return pd.read_parquet(cache)
    import yfinance as yf
    x = yf.download("^VIX", start="2004-12-01", end="2026-06-05", progress=False, auto_adjust=False, timeout=30)
    x.columns = [(c[0] if isinstance(c, tuple) else c).lower() for c in x.columns]
    x.index = pd.to_datetime(x.index).tz_localize(None).normalize()
    try:
        x.to_parquet(cache)
    except Exception:
        pass
    return x


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


async def wf(start, end, max_pos=6, size=15.0, trail=12.0, max_hold=60, plock=0.0, plock_stop=8.0,
             disp=False, disp_margin=0.0, dgate=None, conv=0.0, samesec=False, uni_n=100, volw=0.0,
             dwap_th=5.0, near_hi=3.0, mom_days=None, force_quality=False, raw=False, carry=True,
             refresh_top_m=None, refresh_bull_only=False, refresh_factor_gate=None,
             entry_factor_gate=None, stop_ban_periods=None, reentry_mode=False, bear_keep=0.0,
             cooldown_days=0, istop=0.0):
    global _MAX_HOLD, _PLOCK, _PLOCK_STOP, _DISP, _DISP_MARGIN, _DGATE, _CONV, _SAMESEC, _VOLW, _MOMDAYS, _FORCE_QUALITY, _REFRESH_TOP_M, _REFRESH_BULL_ONLY, _REFRESH_FACTOR_GATE, _ENTRY_FACTOR_GATE, _STOP_BAN_PERIODS, _STOP_BAN, _REENTRY_MODE, _BEAR_KEEP, _COOLDOWN_DAYS, _INITIAL_STOP
    _INITIAL_STOP = istop
    _MAX_HOLD, _PLOCK, _PLOCK_STOP = max_hold, plock, plock_stop
    _DISP, _DISP_MARGIN, _DGATE = disp, disp_margin, dgate
    _CONV = conv
    _SAMESEC = samesec
    _VOLW = volw
    _MOMDAYS = mom_days
    _FORCE_QUALITY = force_quality
    _REFRESH_TOP_M = refresh_top_m
    _REFRESH_BULL_ONLY = refresh_bull_only
    _REFRESH_FACTOR_GATE = refresh_factor_gate
    _ENTRY_FACTOR_GATE = entry_factor_gate
    _STOP_BAN_PERIODS = stop_ban_periods
    _STOP_BAN = {}  # fresh ban state per run
    _REENTRY_MODE = reentry_mode
    _BEAR_KEEP = bear_keep
    _COOLDOWN_DAYS = cooldown_days
    if samesec:
        _load_sectors()
    periods = walk_forward_service._get_period_dates(start, end, "biweekly")
    union = set()
    for ps, pe in periods:
        union |= set(_clean(v.universe_asof_prod(ps, uni_n * 3, 15.0))[:uni_n])
    cache = {}
    for sym in union | {"SPY"}:
        try: cache[sym] = _bars(sym, end)
        except Exception: pass
    cache["^VIX"] = _VIX
    scanner_service.data_cache = cache; scanner_service.universe = list(cache.keys())
    walk_forward_service._get_top_symbols_as_of = lambda asof, maxn: _clean(v.universe_asof_prod(asof, maxn * 3, 15.0))[:maxn]
    async with async_session() as db:
        r = await walk_forward_service.run_walk_forward_simulation(
            db, start, end, enable_ai_optimization=False, fixed_strategy_id=6, max_symbols=uni_n,
            reoptimization_frequency="biweekly", carry_positions=carry, n_trials=0,
            max_positions=max_pos, position_size_pct=size, dwap_threshold_pct=dwap_th,
            near_50d_high_pct=near_hi, trailing_stop_pct=trail,
            profit_lock_pct=plock, profit_lock_stop_pct=plock_stop,
            regime_reentry_mode=reentry_mode, bear_keep_pct=bear_keep)
    if raw:
        return r
    yrs = (end - start).days / 365.25
    return {"ann": ((1 + r.total_return_pct / 100) ** (1 / yrs) - 1) * 100,
            "sharpe": r.sharpe_ratio, "mdd": r.max_drawdown_pct, "total": r.total_return_pct,
            "trades": len(r.trades), "yrs": yrs, "size": size,
            "equity_curve": getattr(r, "equity_curve", None)}


_ADJ = {}  # symbol -> adjusted close series, cached


def _adj_close(sym, end):
    if sym not in _ADJ:
        _ADJ[sym] = v.split_adjusted(sym, asof=end, ca=_CA)["close"]
    return _ADJ[sym]


def naive_momentum(start, end, lookback=120, hold=21, topk=20):
    """Pure momentum factor: top-K by trailing `lookback`-day return, equal-weight,
    rebalance every `hold` trading days, NO DWAP/stop/sizing/regime. Survivorship-free.
    Delisting handled by the price series simply ending (close at last traded)."""
    cal = _adj_close("SPY", end).loc[pd.Timestamp(start):pd.Timestamp(end)].index
    if len(cal) < lookback + hold:
        return None
    ridx = list(range(0, len(cal) - 1, hold))
    eq = [1.0]
    for i in range(len(ridx) - 1):
        d, nd = cal[ridx[i]], cal[ridx[i + 1]]
        uni = [s for s in v.universe_asof_prod(d, 300, 15.0) if s not in _EXCLUDED_SET and not s.startswith("^")][:100]
        scored = []
        for sym in uni:
            try:
                ps = _adj_close(sym, end).loc[:d]
            except Exception:
                continue
            if len(ps) < lookback + 1:
                continue
            scored.append((ps.iloc[-1] / ps.iloc[-1 - lookback] - 1, sym))
        scored.sort(reverse=True)
        top = [s for _, s in scored[:topk]]
        if not top:
            eq.append(eq[-1]); continue
        rets = []
        for sym in top:
            ps = _adj_close(sym, end)
            p0 = ps.loc[:d].iloc[-1]
            seg = ps.loc[d:nd]
            p1 = seg.iloc[-1] if len(seg) else p0
            rets.append(p1 / p0 - 1)
        eq.append(eq[-1] * (1 + sum(rets) / len(rets)))
    s = pd.Series(eq)
    yrs = (end - start).days / 365.25
    ann = (s.iloc[-1] ** (1 / yrs) - 1) * 100
    pr = s.pct_change().dropna()
    ppy = len(pr) / yrs
    sharpe = (pr.mean() / pr.std()) * (ppy ** 0.5) if pr.std() > 0 else 0
    mdd = (1 - s / s.cummax()).max() * 100
    return {"ann": ann, "sharpe": sharpe, "mdd": mdd}


def naive_curve(start, end, lookback=120, hold=21, topk=20):
    """Same as naive_momentum but returns (dates, equity) for the portfolio-race animation."""
    cal = _adj_close("SPY", end).loc[pd.Timestamp(start):pd.Timestamp(end)].index
    if len(cal) < lookback + hold:
        return [], []
    ridx = list(range(0, len(cal) - 1, hold))
    eq = [1.0]
    dates = [cal[ridx[0]]]
    for i in range(len(ridx) - 1):
        d, nd = cal[ridx[i]], cal[ridx[i + 1]]
        uni = [s for s in v.universe_asof_prod(d, 300, 15.0) if s not in _EXCLUDED_SET and not s.startswith("^")][:100]
        scored = []
        for sym in uni:
            try:
                ps = _adj_close(sym, end).loc[:d]
            except Exception:
                continue
            if len(ps) < lookback + 1:
                continue
            scored.append((ps.iloc[-1] / ps.iloc[-1 - lookback] - 1, sym))
        scored.sort(reverse=True)
        top = [s for _, s in scored[:topk]]
        if not top:
            eq.append(eq[-1]); dates.append(nd); continue
        rets = []
        for sym in top:
            ps = _adj_close(sym, end)
            p0 = ps.loc[:d].iloc[-1]
            seg = ps.loc[d:nd]
            p1 = seg.iloc[-1] if len(seg) else p0
            rets.append(p1 / p0 - 1)
        eq.append(eq[-1] * (1 + sum(rets) / len(rets))); dates.append(nd)
    return dates, eq


def _starts_ends():
    starts = [datetime(y, m, 3) for y in (2022, 2023) for m in (1, 4, 7, 10)] + \
             [datetime(2024, m, 3) for m in (1, 4)]
    out = []
    for s in starts:
        e = datetime(2026, 5, 29) if s.year + 2 > 2026 else datetime(s.year + 2, s.month, 28)
        out.append((s, e))
    return out


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "race":
        # Portfolio-race animation data: $100k in t30v vs SPY vs naive momentum,
        # 2017-2026, on survivorship-free parquet. Emits value + drawdown series
        # on a weekly grid -> frontend/public/portfolio-race.json.
        import json as _json, pandas as _pd
        s = datetime(2017, 1, 3); e = datetime(2026, 5, 29)
        print("=== PORTFOLIO RACE ($100k each): t30v vs SPY vs naive ===", flush=True)
        print("running t30v WF (2017-2026)...", flush=True)
        res = await wf(s, e, 20, 4.5, 30, conv=0.0, volw=1.0)
        ec = res.get("equity_curve") or []
        print(f"  t30v: {len(ec)} curve points, total {res['total']:.0f}% / mdd {res['mdd']:.1f}%", flush=True)
        print("running naive momentum (250d = 12-month, matches copy)...", flush=True)
        n_dates, n_eq = naive_curve(s, e, lookback=250)
        print(f"  naive: {len(n_eq)} points", flush=True)
        spy = _adj_close("SPY", e).loc[_pd.Timestamp(s):_pd.Timestamp(e)]
        grid = _pd.date_range(s, e, freq="W-FRI")

        def _al(dates, vals):
            ser = _pd.Series(list(vals), index=_pd.DatetimeIndex([_pd.Timestamp(x) for x in dates])).sort_index()
            ser = ser[~ser.index.duplicated(keep="last")]
            return ser.reindex(grid, method="ffill").ffill().bfill()

        t = _al([p["date"] for p in ec], [float(p["equity"]) for p in ec])
        n = _al(n_dates, n_eq)
        sp = _al(spy.index, spy.values)
        out = {"start_capital": 100000, "as_of": "2026-05-29", "backtested": True,
               "dates": [d.strftime("%Y-%m-%d") for d in grid], "series": {}}
        for name, ser in [("rigacap", t), ("spy", sp), ("naive", n)]:
            norm = ser / ser.iloc[0] * 100000.0
            dd = (norm / norm.cummax() - 1.0) * 100.0
            out["series"][name] = {"value": [round(float(x)) for x in norm],
                                   "dd": [round(float(x), 1) for x in dd]}
        path = "/Users/erikkins/CODE/stocker-app/frontend/public/portfolio-race.json"
        with open(path, "w") as f:
            _json.dump(out, f)
        print(f"WROTE {path} ({len(grid)} weekly points)", flush=True)
        for name in ("rigacap", "spy", "naive"):
            vv = out["series"][name]["value"]; dd = out["series"][name]["dd"]
            print(f"  {name:8} end=${vv[-1]:,}  worst_dd={min(dd):.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "diag":
        # Trade-level forensic: run the naive-equivalent frame config over 2020
        # (clean melt-up year; daily-sim naive made +83.2%) and dump every trade
        # — exit reasons, P&L, hold time — to find where the frame loses 20pp.
        import json as _json
        s = datetime.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime(2020, 1, 2)
        e = datetime.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else datetime(2021, 1, 29)
        _nocarry = len(sys.argv) > 4 and sys.argv[4] == "nocarry"
        if _nocarry:
            r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, force_quality=True,
                         dwap_th=-1000.0, mom_days=(250, 250), carry=False, raw=True)
        else:
            r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, force_quality=True,
                         dwap_th=-1000.0, mom_days=(250, 250), disp=True, disp_margin=0.0, raw=True)
        trades = []
        for t in r.trades:
            d = t if isinstance(t, dict) else getattr(t, "__dict__", {"repr": str(t)})
            trades.append({k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()})
        out = {"total_return_pct": r.total_return_pct, "max_drawdown_pct": r.max_drawdown_pct,
               "sharpe": r.sharpe_ratio, "n_trades": len(trades), "trades": trades,
               "equity_curve": getattr(r, "equity_curve", None)}
        path = os.path.join(R, "scripts", f"diag_{s.year}_{e.year}_trades.json")
        with open(path, "w") as f:
            _json.dump(out, f, default=str)
        print(f"DIAG {s.date()}->{e.date()}: total={r.total_return_pct:.1f}% mdd={r.max_drawdown_pct:.1f}% trades={len(trades)}")
        print(f"WROTE {path}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "race2":
        # Portfolio-race v2 (requires PITFWU_EXT=1): $100k in t30v vs SPY vs naive,
        # 2007-2026 at DAILY resolution (the weekly/monthly grids of v1 masked
        # naive's true -57% trough). Same JSON shape as v1 -> drop-in for the
        # animation component. Pre-2016 layer survivorship caveat applies.
        import json as _json
        import importlib.util as _ilu
        s, e = datetime(2007, 1, 3), datetime(2026, 5, 29)
        print("=== RACE v2 (daily, 2007-2026): t30v vs SPY vs naive ===", flush=True)
        r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, raw=True)
        ec = r.equity_curve or []
        print(f"t30v: {len(ec)} daily points", flush=True)
        _spec = _ilu.spec_from_file_location("ic", os.path.join(R, "scripts", "inversion_campaign.py"))
        _ic = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_ic)
        nser = _ic.run(topk=20, full_curve=True)["series"]
        print(f"naive: {len(nser)} daily points", flush=True)
        spy = v.split_adjusted("SPY", asof=e, ca=v.load_corp_actions())["close"].loc[pd.Timestamp(s):pd.Timestamp(e)]
        grid = spy.index  # daily trading-day grid from SPY

        def _al(idx, vals):
            ser = pd.Series(list(vals), index=pd.DatetimeIndex([pd.Timestamp(x) for x in idx])).sort_index()
            ser = ser[~ser.index.duplicated(keep="last")]
            return ser.reindex(grid, method="ffill").ffill().bfill()

        t = _al([p["date"] for p in ec], [float(p["equity"]) for p in ec])
        n = _al(nser.index, nser.values)
        out = {"start_capital": 100000, "as_of": "2026-05-29", "backtested": True,
               "resolution": "daily", "span": "2007-2026",
               "dates": [d.strftime("%Y-%m-%d") for d in grid], "series": {}}
        for name, ser in [("rigacap", t), ("spy", _al(spy.index, spy.values)), ("naive", n)]:
            norm = ser / ser.iloc[0] * 100000.0
            dd = (norm / norm.cummax() - 1.0) * 100.0
            out["series"][name] = {"value": [round(float(x)) for x in norm],
                                   "dd": [round(float(x), 1) for x in dd]}
        path = os.path.join(R, "frontend", "public", "portfolio-race.json")
        with open(path, "w") as f:
            _json.dump(out, f)
        print(f"WROTE {path} ({len(grid)} daily points)", flush=True)
        for name in ("rigacap", "spy", "naive"):
            vv = out["series"][name]["value"]; dd = out["series"][name]["dd"]
            print(f"  {name:8} end=${vv[-1]:,}  worst_dd={min(dd):.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "smoke_p3":
        # 6-month window covering a regime exit+recovery (2022H2-2023H1) with
        # BOTH new code paths on — verifies the wired read-sites don't crash
        # and the latch/keep mechanics engage before burning 4 long runs.
        s, e = datetime(2022, 9, 1), datetime(2023, 3, 31)
        r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, reentry_mode=True, bear_keep=0.5)
        print(f"SMOKE P3: ann={r['ann']:.1f}% mdd={r['mdd']:.1f}% trades={r['trades']}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "egate_t2":
        # TIER-2 for t30v_egate_only (13.3/0.96/17.4 continuous, fixed bench):
        # held-out off-grid 2y starts, gate vs no-gate head-to-head per window.
        import json as _json
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("ic", os.path.join(R, "scripts", "inversion_campaign.py"))
        _ic = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_ic)
        _base = _ic.run(topk=20, full_curve=True)["series"]
        fgate = (_base > _base.rolling(200, min_periods=100).mean()).fillna(True)
        print(f"[FGATE] {int(fgate.sum())}/{len(fgate)} days healthy", flush=True)
        held = [(2022, 3), (2022, 6), (2022, 9), (2022, 12),
                (2023, 3), (2023, 6), (2023, 9), (2023, 12), (2024, 3), (2024, 6)]
        se = [(datetime(y, m, 3), datetime(2026, 5, 29) if y + 2 > 2026 else datetime(y + 2, m, 28))
              for y, m in held]
        path = os.path.join(R, "scripts", "egate_t2_results.json")
        results = _json.load(open(path)) if os.path.exists(path) else {}
        print(f"=== EGATE TIER-2: {len(se)} held-out starts, gate vs base ===", flush=True)
        for s, e in se:
            key = str(s.date())
            if key in results:
                r = results[key]
                print(f"  {key} (cached) gate ann={r['gate']['ann']:+6.1f}% mdd={r['gate']['mdd']:.1f}% | "
                      f"base ann={r['base']['ann']:+6.1f}% mdd={r['base']['mdd']:.1f}%", flush=True)
                continue
            rg = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, entry_factor_gate=fgate)
            rb = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0)
            rg.pop("equity_curve", None); rb.pop("equity_curve", None)
            results[key] = {"gate": rg, "base": rb}
            with open(path, "w") as f:
                _json.dump(results, f)
            print(f"  {key}  gate ann={rg['ann']:+6.1f}% sharpe={rg['sharpe']:.2f} mdd={rg['mdd']:.1f}% | "
                  f"base ann={rb['ann']:+6.1f}% sharpe={rb['sharpe']:.2f} mdd={rb['mdd']:.1f}%", flush=True)
        ga = pd.Series([v["gate"]["ann"] for v in results.values()])
        ba = pd.Series([v["base"]["ann"] for v in results.values()])
        gm = pd.Series([v["gate"]["mdd"] for v in results.values()])
        bm = pd.Series([v["base"]["mdd"] for v in results.values()])
        gs = pd.Series([v["gate"]["sharpe"] for v in results.values()])
        bs = pd.Series([v["base"]["sharpe"] for v in results.values()])
        print(f"\n  GATE: ann={ga.mean():5.1f}% sharpe={gs.mean():.2f} mdd={gm.mean():.1f}%/worst {gm.max():.1f}% min_ann={ga.min():+.1f}%")
        print(f"  BASE: ann={ba.mean():5.1f}% sharpe={bs.mean():.2f} mdd={bm.mean():.1f}%/worst {bm.max():.1f}% min_ann={ba.min():+.1f}%")
        print(f"  gate wins ann on {int((ga.values > ba.values).sum())}/{len(ga)} windows", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "istop_t2":
        # TIER-2 for istop15 (Pareto on both continuous lenses, Jun 12):
        # same 10 held-out starts as egate_t2; base reused from its cache.
        # Also runs istop15+egate combo (both levers adoption-pending).
        import json as _json
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("ic", os.path.join(R, "scripts", "inversion_campaign.py"))
        _ic = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_ic)
        _b = _ic.run(topk=20, full_curve=True)["series"]
        fgate = (_b > _b.rolling(200, min_periods=100).mean()).fillna(True)
        held = [(2022, 3), (2022, 6), (2022, 9), (2022, 12),
                (2023, 3), (2023, 6), (2023, 9), (2023, 12), (2024, 3), (2024, 6)]
        se = [(datetime(y, m, 3), datetime(2026, 5, 29) if y + 2 > 2026 else datetime(y + 2, m, 28))
              for y, m in held]
        epath = os.path.join(R, "scripts", "egate_t2_results.json")
        ecache = _json.load(open(epath)) if os.path.exists(epath) else {}
        path = os.path.join(R, "scripts", "istop_t2_results.json")
        results = _json.load(open(path)) if os.path.exists(path) else {}
        print(f"=== ISTOP15 TIER-2: {len(se)} held-out starts (base from egate_t2 cache) ===", flush=True)
        for s_, e_ in se:
            key = str(s_.date())
            if key in results:
                print(f"  {key} (cached)", flush=True)
                continue
            ri = await wf(s_, e_, 20, 4.5, 30, 60, conv=0.0, volw=1.0, istop=15.0)
            rc = await wf(s_, e_, 20, 4.5, 30, 60, conv=0.0, volw=1.0, istop=15.0, entry_factor_gate=fgate)
            rb = ecache.get(key, {}).get("base")
            if rb is None:
                rb = await wf(s_, e_, 20, 4.5, 30, 60, conv=0.0, volw=1.0)
                rb.pop("equity_curve", None)
            ri.pop("equity_curve", None); rc.pop("equity_curve", None)
            results[key] = {"istop15": ri, "combo": rc, "base": rb}
            with open(path, "w") as f:
                _json.dump(results, f)
            print(f"  {key}  i15 ann={ri['ann']:+6.1f}% mdd={ri['mdd']:4.1f}% | combo ann={rc['ann']:+6.1f}% mdd={rc['mdd']:4.1f}% | base ann={rb['ann']:+6.1f}% mdd={rb['mdd']:4.1f}%", flush=True)
        import pandas as _pd
        for nm in ("istop15", "combo", "base"):
            a = _pd.Series([v[nm]["ann"] for v in results.values()])
            m = _pd.Series([v[nm]["mdd"] for v in results.values()])
            sh = _pd.Series([v[nm]["sharpe"] for v in results.values()])
            print(f"  {nm:8} ann={a.mean():5.1f}% sharpe={sh.mean():.2f} mdd={m.mean():.1f}%/worst {m.max():.1f}% min_ann={a.min():+.1f}%", flush=True)
        ia = _pd.Series([v["istop15"]["ann"] for v in results.values()])
        ba = _pd.Series([v["base"]["ann"] for v in results.values()])
        print(f"  istop15 wins ann on {int((ia.values > ba.values).sum())}/{len(ia)} windows", flush=True)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "istop":
        import json as _json
        s, e = datetime(2017, 1, 3), datetime(2026, 5, 29)
        suffix = ""
        if os.environ.get("PITFWU_EXT"):
            s = datetime(2007, 1, 3)
            suffix = "_ext"
        CONFIGS = [
            ("t30v_base_FIXED", 0.0),
            ("t30v_istop8", 8.0),
            ("t30v_istop12", 12.0),
            ("t30v_istop15", 15.0),
            ("t30v_istop20", 20.0),
        ]
        path = os.path.join(R, "scripts", f"istop_results{suffix}.json")
        results = _json.load(open(path)) if os.path.exists(path) else {}
        print(f"=== INITIAL-STOP SWEEP (continuous {s.date()} -> {e.date()}{' EXT' if suffix else ''}) ===", flush=True)
        for name, isv in CONFIGS:
            if name in results:
                r = results[name]
                print(f"  {name:18} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}%  (cached)", flush=True)
                continue
            r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, istop=isv)
            r.pop("equity_curve", None)
            results[name] = r
            with open(path, "w") as f:
                _json.dump(results, f)
            print(f"  {name:18} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}% trades={r['trades']}", flush=True)
        print(f"WROTE {path}", flush=True)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "ablate":
        # t30v control ablation on the CONTINUOUS 2017-2026 lens — which gate is
        # the drawdown technology, and what does each cost in CAGR? Inversion
        # campaign (Jun 9) proved naive+overlays can't get MDD under ~40%; t30v
        # held 17.9% through the same 2021-23 factor unwind. Decompose why.
        # Disable values: dwap_th=-1000 -> pct_above_dwap >= -10 always true;
        # near_hi=1000 -> dist_from_high >= -1000 always true.
        import json as _json
        s, e = datetime(2017, 1, 3), datetime(2026, 5, 29)
        if os.environ.get("PITFWU_EXT"):
            # Extended-history runs (2007+, survivorship-biased pre-2016 — label
            # results). Only the decision-critical configs; results to _ext file.
            s = datetime(2007, 1, 3)
            CONFIGS = [
                ("t30v_base_FIXED", dict()),
                ("t30v_egate_only", dict(entry_gate_factor=True)),
            ]
            path = os.path.join(R, "scripts", "ablation_results_ext.json")
            results = _json.load(open(path)) if os.path.exists(path) else {}
            print(f"=== EXT ABLATION (continuous {s.date()} -> {e.date()}, survivorship-biased pre-2016) ===", flush=True)
            for name, kw in CONFIGS:
                if name in results:
                    r = results[name]
                    print(f"  {name:18} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}%  (cached)", flush=True)
                    continue
                ef = kw.pop("entry_gate_factor", False)
                fgate = None
                if ef:
                    import importlib.util as _ilu
                    _spec = _ilu.spec_from_file_location("ic", os.path.join(R, "scripts", "inversion_campaign.py"))
                    _ic = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_ic)
                    _b = _ic.run(topk=20, full_curve=True)["series"]
                    fgate = (_b > _b.rolling(200, min_periods=100).mean()).fillna(True)
                    print(f"[FGATE-EXT] {int(fgate.sum())}/{len(fgate)} days healthy", flush=True)
                r = await wf(s, e, 20, 4.5, 30, 60, conv=0.0, volw=1.0, entry_factor_gate=fgate, **kw)
                r.pop("equity_curve", None)
                results[name] = r
                with open(path, "w") as f:
                    _json.dump(results, f)
                print(f"  {name:18} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}% trades={r['trades']}", flush=True)
            print(f"WROTE {path}", flush=True)
            return
        CONFIGS = [
            ("no_nearhigh",  dict(near_hi=1000.0)),
            ("no_dwap",      dict(dwap_th=-1000.0)),
            ("no_gates",     dict(dwap_th=-1000.0, near_hi=1000.0)),
            ("no_volw",      dict(volw=0.0)),
            ("trail40",      dict(trail_override=40.0)),
            # Ranking-horizon hybrids: gates ADD return (no_nearhigh/no_dwap both
            # WORSE than base), so the gap vs naive-250d's 28.8% is likely the
            # 10d/60d composite horizon. t30v discipline + 12-mo momentum ranking:
            ("m250",         dict(mom_days=(250, 250))),
            ("m120_250",     dict(mom_days=(120, 250))),
            # m250 barely moved the needle (10.7% vs 9.8%) -> the 19pp gap to
            # naive-250d (29.9%) is the FRAME, not the ranking. Biggest unablated
            # structural constraint: max_hold=60 force-closes every position at
            # ~3mo — momentum winners run 6-12mo. Let winners run:
            ("hold_inf",      dict(max_hold_override=9999)),
            ("m250_hold_inf", dict(mom_days=(250, 250), max_hold_override=9999)),
            # hold_inf == base exactly -> max_hold never binds (period carry
            # resets entry age; no-op like cb_tighten). Gap must be the FILTERS
            # or the frame mechanics. Decompose:
            ("no_quality",        dict(force_quality=True)),                         # trend+breakout off, DWAP on
            ("no_filters_at_all", dict(force_quality=True, dwap_th=-1000.0)),        # pure 10/60 score in frame
            ("m250_no_filters",   dict(force_quality=True, dwap_th=-1000.0,
                                       mom_days=(250, 250))),                        # naive selection in t30v frame
            # no_filters_at_all still ~8% -> the gap is FRAME MECHANICS, prime
            # suspect = NO INCUMBENT DISPLACEMENT (stale book; naive rotates
            # wholesale monthly; cf. May 29 displacement-gap finding). Close the loop:
            ("m250_nf_disp0",  dict(force_quality=True, dwap_th=-1000.0,
                                    mom_days=(250, 250), disp=True, disp_margin=0.0)),
            ("m250_nf_disp10", dict(force_quality=True, dwap_th=-1000.0,
                                    mom_days=(250, 250), disp=True, disp_margin=10.0)),
            # and displacement ON TOP of full t30v (filters intact) — the actual
            # relaxed-product candidate if disp is the lever:
            ("t30v_disp10",    dict(disp=True, disp_margin=10.0)),
            # Jun 10 forensic: disp0 = noise-churn (median hold 5d, −0.57%/swap);
            # vacancy-only = stagnation. The frame's missing mode is WHOLESALE
            # PERIODIC ROTATION = carry_positions=False (biweekly naive):
            ("m250_nf_nocarry", dict(force_quality=True, dwap_th=-1000.0,
                                     mom_days=(250, 250), carry=False)),
            # and the same periodic-rotation mode with t30v's filters back ON
            # (the candidate product shape: disciplined periodic rotation):
            ("t30v_m250_nocarry", dict(mom_days=(250, 250), carry=False)),
            # Jun 10: leak forensic showed the REGIME FILTER is the dominant
            # return tax (V-recovery re-entry lag: Jan-2019 cash through the
            # V-bottom, May/Aug-2019 whipsaws, Jan-2020 virus-dip). Price the
            # insurance exactly — same strategies, market filter OFF:
            ("m250_nf_nocarry_noreg", dict(force_quality=True, dwap_th=-1000.0,
                                           mom_days=(250, 250), carry=False, no_mktf=True)),
            ("t30v_noregime",         dict(no_mktf=True)),
            # P1 DELIBERATE REFRESH (Jun 10, Erik-approved program): carried t30v
            # + drop holdings out of top-M at period boundaries. Crisis-independent
            # book refresh — t30v_noregime (0.8%) proved regime flushes were the
            # only refresher. M sweep; regime stays ON.
            ("t30v_refresh60", dict(refresh_top_m=60)),
            ("t30v_refresh40", dict(refresh_top_m=40)),
            ("t30v_refresh30", dict(refresh_top_m=30)),
            # P1b: unconditional refresh worsened MDD 9-15pp (rotating into
            # unwind bounces). Gate the refresh on SPY>200MA at the boundary:
            # deliberate refresh in bulls, frozen book in stress.
            ("t30v_refresh60_bull", dict(refresh_top_m=60, refresh_bull_only=True)),
            ("t30v_refresh40_bull", dict(refresh_top_m=40, refresh_bull_only=True)),
            # P1c: SPY gate didn't cut MDD (refresh60_bull 11.3/26.9) — the 2021-22
            # unwind is INDEX-invisible. Gate refresh on the FACTOR's own 200d trend
            # (wrong gate = postponed refresh, never a forced trade):
            ("t30v_refresh60_factor", dict(refresh_top_m=60, factor_gate=True)),
            ("t30v_refresh40_factor", dict(refresh_top_m=40, factor_gate=True)),
            # MIN-PRICE FIX BASELINE: t30v base re-run on the fixed bench
            # (min_price=0; NVDA/TSLA no longer excluded pre-2020). All configs
            # cached ABOVE this line ran on the bugged bench — within-file
            # comparisons above are consistent; new-vs-old are NOT. This is the
            # corrected continuous t30v number (race 9.8% is biased low).
            ("t30v_base_FIXED", dict()),
            # P1d (fixed bench): "exits cheap, re-entries expensive" as a rule.
            # Drop out-of-top-M ALWAYS (drops are exits — safe); block NEW
            # ENTRIES while the factor is below trend (cash accumulates in
            # unwinds instead of refilling into bounces).
            ("t30v_drop60_egate",  dict(refresh_top_m=60, entry_gate_factor=True)),
            ("t30v_egate_only",    dict(entry_gate_factor=True)),
            # P2 RE-ENTRY DISCIPLINE (fixed bench, from base): a trailing-stop
            # exit bans the symbol from re-entry for N periods (2/4/8 weeks).
            ("t30v_ban1", dict(stop_ban_periods=1)),
            ("t30v_ban2", dict(stop_ban_periods=2)),
            ("t30v_ban4", dict(stop_ban_periods=4)),
            # P2 verdict: bans redundant (near-high gate already enforces re-entry
            # discipline; ban1≡base exactly). P3 REGIME RE-ENTRY SPEED — newly
            # wired read-sites (regime_reentry_mode/_check_regime_reentry,
            # bear_keep_pct, cash_mode_day_count were ALL dead wires):
            ("t30v_smartreentry",  dict(reentry_mode=True)),
            ("t30v_bearkeep50",    dict(bear_keep=0.5)),
            ("t30v_smart_keep50",  dict(reentry_mode=True, bear_keep=0.5)),
            ("t30v_cooldown10",    dict(cooldown_days=10)),
        ]
        path = os.path.join(R, "scripts", "ablation_results.json")
        results = _json.load(open(path)) if os.path.exists(path) else {}
        print("=== t30v ABLATION (continuous 2017-2026) — base ref: 9.8% CAGR / 17.9% DD (race) ===", flush=True)
        for name, kw in CONFIGS:
            if name in results:
                r = results[name]
                print(f"  {name:14} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}%  (cached)", flush=True)
                continue
            tr = kw.pop("trail_override", 30.0)
            vw = kw.pop("volw", 1.0)
            mh = kw.pop("max_hold_override", 60)
            fq = kw.pop("force_quality", False)
            nm = kw.pop("no_mktf", False)
            rm = kw.pop("refresh_top_m", None)
            rb = kw.pop("refresh_bull_only", False)
            fg = kw.pop("factor_gate", False)
            ef = kw.pop("entry_gate_factor", False)
            sb = kw.pop("stop_ban_periods", None)
            rmode = kw.pop("reentry_mode", False)
            bk = kw.pop("bear_keep", 0.0)
            cd = kw.pop("cooldown_days", 0)
            fgate = None
            if fg or ef:
                global _FGATE_SERIES
                if "_FGATE_SERIES" not in globals() or _FGATE_SERIES is None:
                    import importlib.util as _ilu
                    _spec = _ilu.spec_from_file_location("ic", os.path.join(R, "scripts", "inversion_campaign.py"))
                    _ic = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_ic)
                    _base = _ic.run(topk=20, full_curve=True)["series"]
                    _ma = _base.rolling(200, min_periods=100).mean()
                    _FGATE_SERIES = (_base > _ma).fillna(True)
                    print(f"[FGATE] factor-trend gate built: {int(_FGATE_SERIES.sum())}/{len(_FGATE_SERIES)} days healthy", flush=True)
                fgate = _FGATE_SERIES
            from app.core.config import settings as _settings
            _old_mf = _settings.MARKET_FILTER_ENABLED
            if nm:
                _settings.MARKET_FILTER_ENABLED = False
            try:
                r = await wf(s, e, 20, 4.5, tr, mh, conv=0.0, volw=vw, force_quality=fq,
                             refresh_top_m=rm, refresh_bull_only=rb,
                             refresh_factor_gate=fgate if fg else None,
                             entry_factor_gate=fgate if ef else None,
                             stop_ban_periods=sb, reentry_mode=rmode, bear_keep=bk,
                             cooldown_days=cd, **kw)
            finally:
                _settings.MARKET_FILTER_ENABLED = _old_mf
            r.pop("equity_curve", None)
            results[name] = r
            with open(path, "w") as f:    # checkpoint after EVERY config
                _json.dump(results, f)
            print(f"  {name:14} ann={r['ann']:5.1f}% sharpe={r['sharpe']:5.2f} mdd={r['mdd']:5.1f}% trades={r['trades']}", flush=True)
        print(f"WROTE {path}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "naive":
        # factor decomposition: pure momentum factor vs t30v (implementation edge = the gap)
        se = []
        for y in range(2017, 2025):
            for mo in (1, 7):
                s = datetime(y, mo, 3)
                e = datetime(2026, 5, 29) if datetime(y + 2, mo, 28) > datetime(2026, 5, 29) else datetime(y + 2, mo, 28)
                if (e - s).days >= 540:
                    se.append((s, e))
        print(f"=== FACTOR DECOMP: naive momentum vs t30v, {len(se)} windows (2017-2026) ===")
        print(f"  {'config':22} {'ann':>6} {'sharpe':>7} {'worst_mdd':>10}")
        print(f"  {'t30v (full strategy)':22} {'14.0%':>6} {'0.92':>7} {'17.0%':>10}  <- reference")
        for lb in [60, 120, 250]:
            anns, shps, mdds = [], [], []
            for s, e in se:
                r = naive_momentum(s, e, lookback=lb)
                if r:
                    anns.append(r["ann"]); shps.append(r["sharpe"]); mdds.append(r["mdd"])
            A = pd.Series(anns); S = pd.Series(shps); M = pd.Series(mdds)
            print(f"  naive mom {lb}d{'':<11} {A.mean():5.1f}% {S.mean():6.2f} {M.max():9.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "vol":
        # inverse-vol (risk-parity) sizing, alone and combined with conviction. SHARPE focus.
        CONFIGS = [
            ("conv0.5 (t30c)",   0.5, 0.0),
            ("conv0.3",          0.3, 0.0),
            ("vol0.5 only",      0.0, 0.5),
            ("vol1.0 only",      0.0, 1.0),
            ("conv0.5+vol0.5",   0.5, 0.5),
            ("conv0.5+vol1.0",   0.5, 1.0),
            ("conv0.3+vol0.5",   0.3, 0.5),
        ]
        se = _starts_ends()
        print(f"=== INVERSE-VOL SIZING (t30c base), {len(se)} starts — SHARPE focus ===")
        for label, cv, vw in CONFIGS:
            anns, mdds, shps = [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, conv=cv, volw=vw)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            cal = A.mean() / M.mean() if M.mean() > 0 else 0
            star = " ★" if S.mean() >= 1.0 else ""
            print(f"  {label:18} SHARPE={S.mean():.2f}{star}  ann={A.mean():5.1f}% std={A.std():4.1f}% "
                  f"calmar={cal:4.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% min={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "breadth":
        # universe breadth on t30c (20 positions, conviction 0.5): does a wider
        # candidate pool give the book more strong names to hold (esp. in chop)?
        se = _starts_ends()
        print(f"=== UNIVERSE BREADTH (t30c: 20x conv0.5/trail30), {len(se)} starts ===")
        for un in [100, 150, 200, 300]:
            anns, mdds, shps = [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, conv=0.5, uni_n=un)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            cal = A.mean() / M.mean() if M.mean() > 0 else 0
            tag = " (=t30c baseline ~12.8%)" if un == 100 else ""
            print(f"  top-{un:<4} ann={A.mean():5.1f}% std={A.std():4.1f}% sharpe={S.mean():.2f} "
                  f"calmar={cal:4.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% min={A.min():+5.1f}%{tag}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "sizet2":
        # Tier-2: conviction tilt on HELD-OUT off-grid start dates. worst-MDD is the
        # binding constraint (>20% = North Star fail), so it's the decision column.
        held = [(2022, 3), (2022, 6), (2022, 9), (2022, 12),
                (2023, 3), (2023, 6), (2023, 9), (2023, 12), (2024, 3), (2024, 6)]
        se = [(datetime(y, m, 3), datetime(2026, 5, 29) if y + 2 > 2026 else datetime(y + 2, m, 28))
              for y, m in held]
        print(f"=== SIZING TIER-2 (held-out, {len(se)} off-grid starts) — replicate + stay <20% MDD? ===")
        # (label, conv, volw)
        for label, cv, vw in [("conv0.5 t30c", 0.5, 0.0), ("conv0.3", 0.3, 0.0),
                              ("vol1.0 t30v", 0.0, 1.0), ("vol0.5", 0.0, 0.5)]:
            anns, mdds, shps = [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, conv=cv, volw=vw)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            cal = A.mean() / M.mean() if M.mean() > 0 else 0
            flag = "  <-- worst MDD > 20%" if M.max() > 20 else ""
            star = " ★1.0" if S.mean() >= 1.0 else ""
            print(f"  {label:14} ann={A.mean():5.1f}% std={A.std():4.1f}% sharpe={S.mean():.2f}{star} "
                  f"calmar={cal:4.2f} mdd_mean={M.mean():4.1f}% WORST={M.max():4.1f}% min={A.min():+5.1f}%{flag}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "secdisp":
        # same-sector displacement (sector-neutral "hold the sector leader") +/- trend gate
        CONFIGS = [
            ("no-disp",            False, 0,  None,     False),
            ("global m10 trend2",  True,  10, "trend2", False),
            ("samesec m10",        True,  10, None,     True),
            ("samesec m10 trend2", True,  10, "trend2", True),
            ("samesec m5",         True,  5,  None,     True),
            ("samesec m20",        True,  20, None,     True),
        ]
        se = _starts_ends()
        sm = _load_sectors()
        print(f"=== SAME-SECTOR DISPLACEMENT (t30), {len(se)} starts | sector map: {len(sm)} symbols ===")
        for label, dp, dm, gt, ss in CONFIGS:
            anns, mdds, shps, tpy = [], [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, disp=dp, disp_margin=dm, dgate=gt, samesec=ss)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"]); tpy.append(r["trades"] / r["yrs"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps); T = pd.Series(tpy).mean()
            d20 = T * 0.002 * 0.045 * 100
            print(f"  {label:20} gross={A.mean():5.1f}% net@20bps={A.mean()-d20:5.1f}% std={A.std():4.1f}% "
                  f"sharpe={S.mean():.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% trd/yr={T:4.0f} min={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "size":
        # conviction-weighted sizing sweep on t30 (tilt 0 = equal-weight baseline)
        se = _starts_ends()
        print(f"=== CONVICTION SIZING (t30 20x4.5/trail30), {len(se)} starts ===")
        for tilt in [0.0, 0.3, 0.5, 0.8, 1.0]:
            anns, mdds, shps = [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, conv=tilt)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            cal = A.mean() / M.mean() if M.mean() > 0 else 0
            tag = " (equal-weight=baseline)" if tilt == 0 else ""
            print(f"  tilt={tilt:.1f}  ann={A.mean():5.1f}% std={A.std():4.1f}% sharpe={S.mean():.2f} "
                  f"calmar={cal:4.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% min={A.min():+5.1f}%{tag}", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "tdisp":
        # TREND-gated displacement: only displace when SPY is genuinely trending (not chop)
        CONFIGS = [
            ("no-disp",        False, 0,  None),
            ("m10 nogate",     True,  10, None),
            ("m10 trend",      True,  10, "trend"),
            ("m10 trend2",     True,  10, "trend2"),
            ("m5  trend2",     True,  5,  "trend2"),
            ("m10 spy20",      True,  10, "spy20"),
        ]
        se = _starts_ends()
        print(f"=== TREND-GATED DISPLACEMENT (t30), {len(se)} starts ===")
        for label, dp, dm, gt in CONFIGS:
            anns, mdds, shps, tpy = [], [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, disp=dp, disp_margin=dm, dgate=gt)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"]); tpy.append(r["trades"] / r["yrs"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps); T = pd.Series(tpy).mean()
            d20 = T * 0.002 * 0.045 * 100
            print(f"  {label:12} gross={A.mean():5.1f}% net@20bps={A.mean()-d20:5.1f}% std={A.std():4.1f}% "
                  f"sharpe={S.mean():.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% trd/yr={T:4.0f} min={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "gdisp":
        # regime-GATED displacement at fixed margin: lagging vs timely gates head-to-head
        # (label, disp, margin, gate)
        CONFIGS = [
            ("no-disp",      False, 0,  None),
            ("m10 nogate",   True,  10, None),
            ("m10 spy200",   True,  10, "spy200"),
            ("m10 spy50",    True,  10, "spy50"),
            ("m10 vix25",    True,  10, "vix25"),
            ("m10 spy60ret", True,  10, "spy60ret"),
        ]
        se = _starts_ends()
        print(f"=== GATED DISPLACEMENT (t30, margin=10), {len(se)} starts — lagging vs timely gate ===")
        for label, dp, dm, gt in CONFIGS:
            anns, mdds, shps, tpy = [], [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, disp=dp, disp_margin=dm, dgate=gt)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"]); tpy.append(r["trades"] / r["yrs"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps); T = pd.Series(tpy).mean()
            d20 = T * 0.002 * 0.045 * 100
            print(f"  {label:12} gross={A.mean():5.1f}% net@20bps={A.mean()-d20:5.1f}% std={A.std():4.1f}% "
                  f"sharpe={S.mean():.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% trd/yr={T:4.0f} min={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "disp":
        # displacement margin sweep on t30, across the distribution, net-of-cost + turnover
        CONFIGS = [("no-disp", False, 0), ("m=5", True, 5), ("m=10", True, 10),
                   ("m=20", True, 20), ("m=40", True, 40)]
        se = _starts_ends()
        print(f"=== DISPLACEMENT margin sweep (t30 20x4.5/trail30), {len(se)} starts ===")
        for label, dp, dm in CONFIGS:
            anns, mdds, shps, tpy = [], [], [], []
            for s, e in se:
                r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, disp=dp, disp_margin=dm)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"]); tpy.append(r["trades"] / r["yrs"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps); T = pd.Series(tpy).mean()
            d20 = T * 0.002 * 0.045 * 100
            print(f"  t30 {label:8} gross={A.mean():5.1f}% net@20bps={A.mean()-d20:5.1f}% std={A.std():4.1f}% "
                  f"sharpe={S.mean():.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% trd/yr={T:4.0f} min={A.min():+5.1f}%", flush=True)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "longhist":
        # t30 across the FULL 2016-2026 span (2018-Q4 + 2020-COVID + 2022 bear),
        # semi-annual starts, 2y windows (>=1.5y). Free regime extension.
        se = []
        for y in range(2017, 2025):  # 2017+ = full 200d indicator warmup after 2016-01 bar start
            for m in (1, 7):
                s = datetime(y, m, 3)
                e = datetime(2026, 5, 29) if datetime(y + 2, m, 28) > datetime(2026, 5, 29) else datetime(y + 2, m, 28)
                if (e - s).days >= 540:
                    se.append((s, e))
        _tilt = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
        _vw = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
        print(f"=== t30 LONG-HISTORY (conv={_tilt} vol={_vw}) ({len(se)} windows, 2017-2026; 2018-Q4, COVID, 2022) ===")
        rows = []
        for s, e in se:
            r = await wf(s, e, 20, 4.5, 30, 60, 0, 8, conv=_tilt, volw=_vw)
            rows.append(r)
            print(f"  {s.date()} -> {e.date()}:  ann={r['ann']:+6.1f}%  sharpe={r['sharpe']:5.2f}  mdd={r['mdd']:4.1f}%", flush=True)
        A = pd.Series([r["ann"] for r in rows]); M = pd.Series([r["mdd"] for r in rows]); S = pd.Series([r["sharpe"] for r in rows])
        print(f"\n  ALL {len(rows)} windows: ann mean={A.mean():.1f}% std={A.std():.1f}% sharpe={S.mean():.2f} "
              f"mdd mean={M.mean():.1f}%/worst={M.max():.1f}% min_ann={A.min():+.1f}% pos={100*(A>0).mean():.0f}%")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        # Tier-2: HELD-OUT start dates (off the quarterly tuning grid: Mar/Jun/Sep/Dec)
        # + per-window so bull (2024 starts) vs bear (2022-23 starts) is visible.
        held = [(2022, 3), (2022, 6), (2022, 9), (2022, 12),
                (2023, 3), (2023, 6), (2023, 9), (2023, 12), (2024, 3), (2024, 6)]
        se = [(datetime(y, m, 3), datetime(2026, 5, 29) if y + 2 > 2026 else datetime(y + 2, m, 28))
              for y, m in held]
        print(f"=== TIER-2 HELD-OUT ({len(se)} off-grid starts) — does it replicate out-of-sample? ===")
        for label, mp, sz, tr in [("t25 (suspect)", 20, 4.5, 25), ("t30 (robust)", 20, 4.5, 30), ("t40", 20, 4.5, 40)]:
            rows = []
            for s, e in se:
                rows.append((s, e, await wf(s, e, mp, sz, tr, 60, 0, 8)))
            A = pd.Series([r["ann"] for _, _, r in rows]); M = pd.Series([r["mdd"] for _, _, r in rows])
            S = pd.Series([r["sharpe"] for _, _, r in rows])
            print(f"  {label:14} ann mean={A.mean():5.1f}% std={A.std():4.1f}% sharpe={S.mean():5.2f} "
                  f"mdd={M.mean():4.1f}%/{M.max():4.1f}% min={A.min():+5.1f}%", flush=True)
            if "robust" in label:
                print("    per-window (bull 2024 starts run into the AI bull; 2022-23 are bear-starts):")
                for s, e, r in rows:
                    print(f"      {s.date()} -> {e.date()}:  ann={r['ann']:+6.1f}%  sharpe={r['sharpe']:5.2f}  mdd={r['mdd']:4.1f}%")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "exit":
        # exit refinement at 20x4.5: trail tightness x hold horizon x profit-lock
        # (label, max_pos, size, trail, max_hold, plock, plock_stop)
        # trail width is the real exit lever (hold-horizon is moot — 25% trail
        # already runs winners ~7-8mo). Sweep trail; one plock config to test if
        # profit-lock binds at all in this path.
        CONFIGS = [
            ("t18",          20, 4.5, 18, 60, 0,  8),
            ("t25",          20, 4.5, 25, 60, 0,  8),
            ("t30",          20, 4.5, 30, 60, 0,  8),
            ("t35",          20, 4.5, 35, 60, 0,  8),
            ("t40",          20, 4.5, 40, 60, 0,  8),
            ("t30 plock15-8", 20, 4.5, 30, 60, 15, 8),
        ]
        se = _starts_ends()
        print(f"=== EXIT REFINEMENT (20x4.5) across {len(se)} starts ===")
        for label, mp, sz, tr, mh, pl, pls in CONFIGS:
            anns, mdds, shps, mins = [], [], [], []
            for s, e in se:
                r = await wf(s, e, mp, sz, tr, mh, pl, pls)
                anns.append(r["ann"]); mdds.append(r["mdd"]); shps.append(r["sharpe"])
            A = pd.Series(anns); M = pd.Series(mdds); S = pd.Series(shps)
            cal = A.mean() / M.mean() if M.mean() > 0 else 0
            print(f"  {label:22} ann={A.mean():5.1f}% std={A.std():4.1f}% sharpe={S.mean():5.2f} "
                  f"calmar={cal:4.2f} mdd={M.mean():4.1f}%/{M.max():4.1f}% min={A.min():+5.1f}%", flush=True)
        return
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
