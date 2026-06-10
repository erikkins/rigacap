"""Inversion campaign — start from naive momentum (28.8% CAGR continuous) and
SUBTRACT drawdown as cheaply as possible, instead of starting from defense and
trying to add return back (the t30v exchange rate was ~1.6pp CAGR per 1pp DD saved).

Daily-resolution simulator over the PITFWU survivorship-free parquet, continuous
2017->2026 lens (what one investor actually experiences). All overlay parameters
are PRE-REGISTERED from prior validated work, not tuned here:
  - trail 30%            (t30v's exit)
  - DD-tighten 15 -> 8   (May 22 t15/s8, validated 50/52 dates on the old config)
  - SPY 200d MA regime   (literature-standard dual momentum)
  - DD-halve exposure    (pre-registered 50% while portfolio DD >= 15%)

Execution model: rebalance trades at rebalance-day close (matches the published
naive base so variant A reproduces the race's 28.8%); stop/regime signals read at
close[t], executed at close[t+1] (EOD parity, conservative).

Costs: real turnover tracked; net CAGR shown at 10bps and 20bps per side.
Checkpoints: scripts/inversion_results.json written after EVERY variant.

Usage: AWS_PROFILE=rigacap python scripts/inversion_campaign.py
"""
import os, sys, json
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")
import pandas as pd
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET

EXT = bool(os.environ.get("PITFWU_EXT"))
if EXT:
    v.EXT = True

START = pd.Timestamp(os.environ.get("INV_START", "2007-01-03" if EXT else "2017-01-03"))
END = pd.Timestamp("2026-05-29")
LOOKBACK = 250          # 12-month momentum, matches the race/copy
HOLD = 21               # monthly rebalance, matches the race
RESULTS_PATH = os.path.join(R, "scripts", "inversion_results_ext.json" if EXT else "inversion_results.json")
CLOSE_CACHE = os.path.expanduser("~/.cache/pitfwu_close_ext" if EXT else "~/.cache/pitfwu_close")
os.makedirs(CLOSE_CACHE, exist_ok=True)

_CA = v.load_corp_actions()
_ADJ = {}


def adj_close(sym):
    """Split-adjusted (as-of END) daily close series, disk-cached so re-runs are free."""
    if sym in _ADJ:
        return _ADJ[sym]
    p = os.path.join(CLOSE_CACHE, f"{sym}.parquet")
    if os.path.exists(p):
        s = pd.read_parquet(p)["close"]
    else:
        s = v.split_adjusted(sym, asof=END, ca=_CA)["close"]
        s.to_frame().to_parquet(p)
    _ADJ[sym] = s
    return s


def _passes_gate(ps, gate):
    if gate is None:
        return True
    px = ps.iloc[-1]
    if gate == "ma50":
        return px > ps.iloc[-50:].mean()
    if gate == "hi250_90":
        return px >= 0.90 * ps.iloc[-252:].max()
    raise ValueError(gate)


def top_momentum(d, topk, gate=None):
    """Rank top-100 candidates by 250d momentum, then GATE, then take top-K.
    Mirrors t30v's rank-then-quality-filter ordering. Fewer than K pass -> hold cash."""
    uni = [s for s in v.universe_asof_prod(d, 300, 15.0)
           if s not in _EXCLUDED_SET and not s.startswith("^")][:100]
    scored = []
    for sym in uni:
        try:
            ps = adj_close(sym).loc[:d]
        except Exception:
            continue
        if len(ps) < LOOKBACK + 1:
            continue
        scored.append((ps.iloc[-1] / ps.iloc[-1 - LOOKBACK] - 1, sym, ps))
    scored.sort(reverse=True, key=lambda x: x[0])
    out = []
    for _, sym, ps in scored:
        if _passes_gate(ps, gate):
            out.append(sym)
        if len(out) == topk:
            break
    return out


def run(topk=20, trail=None, dd_tighten=None, regime=None, dd_halve=False, label="",
        entry_gate=None, ext_regime=None, full_curve=False):
    """Daily event loop. Returns metrics dict.
    trail: None or pct (0.30). dd_tighten: None or (dd_thresh, tight_trail) e.g. (0.15, 0.08).
    regime: None | 'rebal' (cash at rebalance if SPY<200MA) | 'daily' (also exit mid-period t+1).
    dd_halve: 50%% exposure while portfolio DD >= 15%% (applied at rebalance sizing).
    entry_gate: None | 'ma50' (close > 50d MA) | 'hi250_90' (close >= 90%% of 252d high)
      — applied to top-100 momentum candidates BEFORE taking top-K (rank then gate, like t30v).
    ext_regime: pd.Series[bool] daily — replaces the SPY-MA regime test (e.g. factor-trend).
      Used with regime='rebal'/'daily' semantics."""
    spy = adj_close("SPY").loc[:END]
    spy_ma = spy.rolling(200, min_periods=100).mean()
    cal = spy.loc[START:END].index
    ridx = set(range(0, len(cal) - 1, HOLD))

    cash = 1.0
    pos = {}            # sym -> dict(shares, hwm)
    eq_hist = []
    peak = 1.0
    pending_sells = set()
    traded = 0.0        # cumulative one-side traded notional (in equity units)
    regime_ok_hist = True

    def price(sym, t, ps_cache={}):
        ps = adj_close(sym)
        seg = ps.loc[:t]
        return float(seg.iloc[-1]) if len(seg) else None

    for i, t in enumerate(cal):
        # ---- mark to market; force-close delisted (series ended before t)
        equity = cash
        for sym in list(pos):
            ps = adj_close(sym)
            if ps.index.max() < t:                       # delisted: close at terminal price
                proceeds = pos[sym]["shares"] * float(ps.iloc[-1])
                cash += proceeds; traded += proceeds
                del pos[sym]; pending_sells.discard(sym)
                equity = cash + sum(p["shares"] * price(s2, t) for s2, p in pos.items())
                continue
        px = {sym: price(sym, t) for sym in pos}
        equity = cash + sum(pos[sym]["shares"] * px[sym] for sym in pos)

        # ---- execute pending sells (signals from t-1) at today's close
        for sym in list(pending_sells):
            if sym in pos:
                proceeds = pos[sym]["shares"] * px[sym]
                cash += proceeds; traded += proceeds
                del pos[sym]
        pending_sells.clear()
        equity = cash + sum(pos[sym]["shares"] * px[sym] for sym in pos)

        peak = max(peak, equity)
        dd = 1 - equity / peak

        # ---- effective trail (DD-tighten)
        eff_trail = trail
        if trail is not None and dd_tighten is not None and dd >= dd_tighten[0]:
            eff_trail = dd_tighten[1]

        # ---- regime state at close[t]
        if ext_regime is not None:
            seg = ext_regime.loc[:t]
            regime_ok = bool(seg.iloc[-1]) if len(seg) else True
        else:
            regime_ok = bool(spy.loc[:t].iloc[-1] > spy_ma.loc[:t].iloc[-1])

        # ---- signal generation at close[t] -> execute t+1
        if regime == "daily" and not regime_ok:
            pending_sells |= set(pos.keys())
        elif eff_trail is not None:
            for sym in pos:
                pos[sym]["hwm"] = max(pos[sym]["hwm"], px[sym])
                if px[sym] <= pos[sym]["hwm"] * (1 - eff_trail):
                    pending_sells.add(sym)

        # ---- rebalance at close[t] (same-day, matches naive base)
        if i in ridx and i + HOLD < len(cal):
            in_regime = regime_ok if regime else True
            target = top_momentum(t, topk, gate=entry_gate) if in_regime else []
            tgt = set(target)
            for sym in list(pos):                        # sell drops
                if sym not in tgt:
                    proceeds = pos[sym]["shares"] * px[sym]
                    cash += proceeds; traded += proceeds
                    del pos[sym]; pending_sells.discard(sym)
            equity = cash + sum(pos[sym]["shares"] * px[sym] for sym in pos)
            expo = 0.5 if (dd_halve and dd >= 0.15) else 1.0
            if target:
                w = equity * expo / len(target)
                for sym in target:
                    p0 = price(sym, t)
                    if p0 is None or p0 <= 0:
                        continue
                    cur = pos.get(sym, {"shares": 0.0, "hwm": p0})
                    cur_val = cur["shares"] * p0
                    delta = w - cur_val
                    traded += abs(delta)
                    cur["shares"] = w / p0
                    cur["hwm"] = max(cur.get("hwm", p0), p0)
                    cash -= delta
                    pos[sym] = cur
                    pending_sells.discard(sym)

        equity = cash + sum(pos[sym]["shares"] * price(sym, t) for sym in pos)
        eq_hist.append((t, equity))

    s = pd.Series([e for _, e in eq_hist], index=[d for d, _ in eq_hist])
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = (s.iloc[-1] ** (1 / yrs) - 1) * 100
    dr = s.pct_change().dropna()
    sharpe = (dr.mean() / dr.std()) * (252 ** 0.5) if dr.std() > 0 else 0
    mdd = (1 - s / s.cummax()).max() * 100
    turn_yr = traded / 2 / yrs                            # round-trip turnover x/yr
    drag10 = turn_yr * 2 * 0.0010 * 100                   # pp/yr at 10bps per side
    drag20 = turn_yr * 2 * 0.0020 * 100
    yearly = {str(y): round(float(g.iloc[-1] / g.iloc[0] - 1) * 100, 1)
              for y, g in s.groupby(s.index.year) if len(g) > 30}
    return {"label": label, "cagr": round(cagr, 2), "net10": round(cagr - drag10, 2),
            "net20": round(cagr - drag20, 2), "sharpe": round(float(sharpe), 2),
            "mdd": round(float(mdd), 2), "calmar": round(cagr / mdd, 2) if mdd > 0 else None,
            "turnover_x_yr": round(turn_yr, 1), "end_mult": round(float(s.iloc[-1]), 2),
            "yearly": yearly,
            "series": s if full_curve else None,
            "curve": {"dates": [d.strftime("%Y-%m-%d") for d in s.index[::5]],
                      "equity": [round(float(x), 4) for x in s.values[::5]]}}


VARIANTS = [
    ("A_base",                 dict(topk=20)),
    ("B_200ma_rebal",          dict(topk=20, regime="rebal")),
    ("C_200ma_daily",          dict(topk=20, regime="daily")),
    ("D_trail30",              dict(topk=20, trail=0.30)),
    ("E_trail30_ddtighten",    dict(topk=20, trail=0.30, dd_tighten=(0.15, 0.08))),
    ("F_200ma_trail30",        dict(topk=20, regime="rebal", trail=0.30)),
    ("G_200ma_daily_t30_ddt",  dict(topk=20, regime="daily", trail=0.30, dd_tighten=(0.15, 0.08))),
    ("H_ddhalve",              dict(topk=20, dd_halve=True)),
    ("I_top10",                dict(topk=10)),
    ("J_top10_defended",       dict(topk=10, regime="rebal", trail=0.30, dd_tighten=(0.15, 0.08))),
]


def factor_trend_series():
    """Always-invested naive factor curve vs its OWN 200d MA — the regime signal
    watching the thing that actually crashes (the factor), not the index.
    Built from the base run (full daily curve); signal True = factor above trend."""
    base = run(topk=20, full_curve=True)["series"]
    ma = base.rolling(200, min_periods=100).mean()
    return (base > ma).fillna(True)


# Round 2 — informed by round 1 (Tier-1 hypothesis only; survivors go to held-out
# per-window validation). Round 1 lessons: SPY-level regime is blind to factor
# unwinds (B/C); DD-tighten whipsaws against forced monthly re-entry (E/J);
# trail30 alone is best offense (D, 34.5%/43%); t30v's entry gates are what
# actually held its MDD to 18% through 2021-23. Round 2: soft entry-quality
# gates + factor-level trend filter, canonical params only.
ROUND2 = [
    ("K_factor_trend",         dict(topk=20, regime="daily")),                     # ext_regime injected
    ("L_gate_hi250",           dict(topk=20, entry_gate="hi250_90")),
    ("M_gate_ma50",            dict(topk=20, entry_gate="ma50")),
    ("N_gate_hi250_trail30",   dict(topk=20, entry_gate="hi250_90", trail=0.30)),
    ("O_gate_ma50_trail30",    dict(topk=20, entry_gate="ma50", trail=0.30)),
    ("P_ma50_t30_ftrend",      dict(topk=20, entry_gate="ma50", trail=0.30, regime="daily")),
    ("Q_hi250_t30_ftrend",     dict(topk=20, entry_gate="hi250_90", trail=0.30, regime="daily")),
]
_NEEDS_FTREND = {"K_factor_trend", "P_ma50_t30_ftrend", "Q_hi250_t30_ftrend"}


def main():
    results = {}
    if os.path.exists(RESULTS_PATH):
        results = json.load(open(RESULTS_PATH))
    print(f"=== INVERSION CAMPAIGN — naive base + minimal defense, continuous {START.date()} -> {END.date()} ===", flush=True)
    print(f"{'variant':24} {'CAGR':>6} {'net@10':>7} {'net@20':>7} {'sharpe':>7} {'MDD':>6} {'calmar':>7} {'turn/yr':>8}", flush=True)
    todo = VARIANTS + ROUND2
    ftrend = factor_trend_series() if any(n in _NEEDS_FTREND and n not in results
                                          for n, _ in todo) else None
    for name, kw in todo:
        if name in _NEEDS_FTREND:
            kw = dict(kw, ext_regime=ftrend)
        if name in results:
            r = results[name]
            print(f"{name:24} {r['cagr']:5.1f}% {r['net10']:6.1f}% {r['net20']:6.1f}% "
                  f"{r['sharpe']:7.2f} {r['mdd']:5.1f}% {r['calmar']:7.2f} {r['turnover_x_yr']:7.1f}x  (cached)", flush=True)
            continue
        r = run(label=name, **kw)
        r.pop("series", None)                              # pd.Series isn't JSON-serializable
        results[name] = r
        with open(RESULTS_PATH, "w") as f:                 # checkpoint EVERY variant
            json.dump(results, f)
        print(f"{name:24} {r['cagr']:5.1f}% {r['net10']:6.1f}% {r['net20']:6.1f}% "
              f"{r['sharpe']:7.2f} {r['mdd']:5.1f}% {r['calmar']:7.2f} {r['turnover_x_yr']:7.1f}x", flush=True)
        print(f"    yearly: {results[name]['yearly']}", flush=True)
    print(f"\nWROTE {RESULTS_PATH}", flush=True)


if __name__ == "__main__":
    main()
