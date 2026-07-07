"""Shape factory — the "instant shape function".

Register a chart-shape detector once; run the whole rigorous pipeline on it (or a
BASKET of shapes) for free: survivorship-free, point-in-time PITFWU, two-step
(Tier-1 2016-20 / Tier-2 held-out 21-26), and orthogonality measured against the
REAL production t30v (not a proxy).

Bull Rider = a basket of orthogonal shapes. Add a shape =
    @register_shape("my_shape")
    def my_shape(o, h, l, c, vol):   # numpy arrays
        return bool_array_of_signal_days
Everything downstream is automatic.

Exits: v1 uses a SHARED time-exit (the validated ~20d hold — stops whipsaw). The
registry carries a per-shape `exit` slot so shapes can diverge / stack later
(Erik: "maybe they share, maybe each its own, maybe they stack — we don't know
yet"); the portfolio sim currently honours the shared default.

CLI:
  python scripts/shape_lab.py list
  python scripts/shape_lab.py edge cup_handle
  python scripts/shape_lab.py portfolio cup_handle,double_bottom
  python scripts/shape_lab.py ortho cup_handle,double_bottom
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import json
import numpy as np
import pandas as pd
import pitfwu_veneer as v
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S
from shapes_portfolio import simulate, perf, CAP0
# real_ensemble_equity imported lazily inside cmd_ortho (pulls the heavy t30v
# engine) so `edge`/`portfolio` stay fast.

HORIZON = 20
TIERS = [(pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"), "Tier-1 (2016-20)"),
         (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 held-out (21-26)")]

# ── registry ─────────────────────────────────────────────────────────────────
SHAPES = {}  # name -> {"fn": detector(o,h,l,c,vol)->bool[], "exit": {...}}


def register_shape(name, exit=None, regime=None):
    # regime: None = fire any time; "bull" = only when SPY>200MA; "bear" = only when below.
    def deco(fn):
        SHAPES[name] = {"fn": fn, "exit": exit or {"type": "time", "hold": HORIZON}, "regime": regime}
        return fn
    return deco


_BULL = {}


def bull_regime(end):
    """Point-in-time market regime: SPY close > its own 200-day MA (cached per end)."""
    key = str(end)
    if key not in _BULL:
        spy = v.split_adjusted("SPY", asof=end, ca=S.CA)["close"]
        _BULL[key] = spy > spy.rolling(200, min_periods=50).mean()
    return _BULL[key]


# ── shapes ───────────────────────────────────────────────────────────────────
@register_shape("cup_handle")
def cup_handle(o, h, l, c, vol):
    """Continuation breakout (momentum family). Specimen #1."""
    return S.cup_and_handle_breakouts(c, vol)


@register_shape("double_bottom", exit={"type": "time", "hold": 10})  # reversals fade faster (exit_lab held-out)
def double_bottom(o, h, l, c, vol):
    """W-bottom REVERSAL (different regime than a breakout → candidate orthogonal
    pivot). Two troughs at a similar level separated by a middle peak; signal on
    the day price breaks above that peak (the neckline) on above-avg volume."""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    W = 120  # ~6mo
    for t in range(W, n):
        if c[t] < 15 or vol[t] < 500_000:
            continue
        w = c[t - W:t + 1]
        m = len(w)
        i1 = int(np.argmin(w[: m // 2]))                 # first trough
        i2 = m // 2 + int(np.argmin(w[m // 2:]))         # second trough
        if i2 <= i1 + 10:
            continue
        t1, t2 = w[i1], w[i2]
        if t1 <= 0 or abs(t2 - t1) / t1 > 0.05:          # troughs within 5%
            continue
        mid = w[i1:i2 + 1]
        peak = mid.max()
        peak_i = i1 + int(np.argmax(mid))
        if peak_i <= i1 or peak_i >= i2:                 # peak strictly between troughs
            continue
        if (peak - max(t1, t2)) / max(t1, t2) < 0.08:    # neckline >= 8% above troughs
            continue
        vbase = vol[max(0, t - 20):t].mean() if t >= 5 else vol[t]
        if c[t] > peak and c[t - 1] <= peak and vol[t] > vbase:  # breakout above neckline
            sig[t] = True
    return sig


@register_shape("pullback_bounce", exit={"type": "time", "hold": 10}, regime="bear")  # Bear Ripper #1
def pullback_bounce(o, h, l, c, vol):
    """MEAN-REVERSION: buy an oversold dip. omr_regime_test showed its edge lives in
    BEAR/high-vol regimes (snapback rallies), not bull → BEAR RIPPER, bear-gated,
    ~10d hold. (The longer-term-uptrend filter below is the stock's own trend.)"""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    cs = pd.Series(c)
    ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
    hi20 = cs.rolling(20, min_periods=5).max().to_numpy()
    lo10 = cs.rolling(10, min_periods=3).min().to_numpy()
    for t in range(200, n):
        if c[t] < 15 or vol[t] < 500_000:
            continue
        if c[t] <= ma200[t]:                          # longer-term uptrend
            continue
        if c[t - 1] > lo10[t - 1] * 1.01:             # yesterday at/near a 10-day low
            continue
        if hi20[t] <= 0 or (hi20[t] - c[t - 1]) / hi20[t] < 0.08:  # pulled back >= 8% off 20d high
            continue
        if c[t] > c[t - 1] and c[t] > o[t]:           # bounce: up day off the low
            sig[t] = True
    return sig


@register_shape("vcp", exit={"type": "time", "hold": 20})  # trail_30 won per-TRADE median but
def vcp(o, h, l, c, vol):                                   # blew up portfolio DD (-52%); time wins at book level
    """Volatility-Contraction Pattern breakout (momentum family — a CONTROL: should
    correlate with cup-and-handle and add less). Uptrend + recent vol contracted vs
    longer-term, then breakout above the 15-day high on volume."""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    cs = pd.Series(c)
    ma50 = cs.rolling(50, min_periods=10).mean().to_numpy()
    ret = cs.pct_change()
    v20 = ret.rolling(20, min_periods=5).std().to_numpy()
    v60 = ret.rolling(60, min_periods=20).std().to_numpy()
    hi15 = cs.shift(1).rolling(15, min_periods=5).max().to_numpy()  # prior 15d high (excl today)
    for t in range(60, n):
        if c[t] < 15 or vol[t] < 500_000:
            continue
        if c[t] <= ma50[t]:                           # uptrend
            continue
        if not (v60[t] > 0 and v20[t] < 0.6 * v60[t]):  # volatility contraction
            continue
        vbase = vol[max(0, t - 20):t].mean() if t >= 5 else vol[t]
        if hi15[t] == hi15[t] and c[t] > hi15[t] and vol[t] > vbase:  # breakout on volume
            sig[t] = True
    return sig


@register_shape("inv_hs", exit={"type": "time", "hold": 20})  # exit_lab held-out winner
def inv_hs(o, h, l, c, vol):
    """Inverse HEAD-AND-SHOULDERS — bottoming reversal. Left shoulder, lower head,
    right shoulder (~symmetric, both above the head), breakout above the neckline."""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    W = 120
    for t in range(W, n):
        if c[t] < 15 or vol[t] < 500_000:
            continue
        w = c[t - W:t + 1]
        m = len(w)
        a, b = m // 3, 2 * m // 3
        ls_i = int(np.argmin(w[:a])); ls = w[ls_i]
        head_i = a + int(np.argmin(w[a:b])); head = w[head_i]
        rs_i = b + int(np.argmin(w[b:])); rs = w[rs_i]
        if not (head < ls and head < rs) or head <= 0:
            continue
        if max(ls, rs) <= 0 or abs(ls - rs) / max(ls, rs) > 0.10:   # shoulders ~symmetric
            continue
        if (min(ls, rs) - head) / head < 0.05:                      # head clearly below shoulders
            continue
        neckline = max(w[ls_i:head_i + 1].max() if head_i > ls_i else head,
                       w[head_i:rs_i + 1].max() if rs_i > head_i else head)
        vbase = vol[max(0, t - 20):t].mean() if t >= 5 else vol[t]
        if c[t] > neckline and c[t - 1] <= neckline and vol[t] > vbase:
            sig[t] = True
    return sig


@register_shape("pullback_ma", exit={"type": "time", "hold": 20})
def pullback_ma(o, h, l, c, vol):
    """Trend-CONTINUATION — buys WEAKNESS, not a breakout, so it should be orthogonal
    to the cup/vcp/db/inv-hs breakout cousins. Established, RISING uptrend (MA50>MA200,
    MA50 climbing, price above MA50); price dips back to touch/near the rising 20-day MA
    (within 2%), then turns up off it on an up day reclaiming the MA."""
    n = len(c)
    sig = np.zeros(n, dtype=bool)
    cs = pd.Series(c)
    ma20 = cs.rolling(20, min_periods=5).mean().to_numpy()
    ma50 = cs.rolling(50, min_periods=10).mean().to_numpy()
    ma200 = cs.rolling(200, min_periods=50).mean().to_numpy()
    for t in range(200, n):
        if c[t] < 15 or vol[t] < 500_000:
            continue
        if not (ma50[t] > ma200[t] and ma50[t] > ma50[t - 10] and c[t] > ma50[t]):  # rising uptrend
            continue
        if l[t - 1] > ma20[t - 1] * 1.02:               # yesterday dipped to/through the rising 20MA
            continue
        if c[t] > c[t - 1] and c[t] > o[t] and c[t] > ma20[t]:  # turn back up, reclaim the MA
            sig[t] = True
    return sig


# ── data: build close/dvol panels + a COMBINED signal panel for the basket ────
def load(shapes, start, end):
    # each shape carries its own exit hold (per-shape exits); basket = OR of
    # signals, and each entry cell gets the MIN hold among the shapes that fired.
    specs = [(SHAPES[s]["fn"], SHAPES[s]["exit"], SHAPES[s].get("regime")) for s in shapes]
    exit_specs = [SHAPES[s]["exit"] for s in shapes]  # sid -> exit rule (time/trail/target)
    bull = bull_regime(end)
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    closes, sigs, dvol, holds, sids = {}, {}, {}, {}, {}
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, hi, lo, c, vol = (df[k].to_numpy(float) for k in ["open", "high", "low", "close", "volume"])
        bull_on = bull.reindex(df.index, method="ffill").fillna(False).to_numpy().astype(bool)
        n = len(c)
        combined = np.zeros(n, dtype=bool)
        hold_arr = np.full(n, float(HORIZON))
        sid_arr = np.full(n, -1.0)  # which shape (index in `shapes`) first fired each cell
        for i, (fn, ex, reg) in enumerate(specs):
            hd = ex.get("hold", ex.get("max_hold", HORIZON))  # time→hold; trail/target→max_hold backstop
            ssig = fn(o, hi, lo, c, vol)
            if reg == "bull":
                ssig = ssig & bull_on
            elif reg == "bear":
                ssig = ssig & (~bull_on)
            sid_arr = np.where(ssig & (sid_arr < 0), float(i), sid_arr)
            hold_arr = np.where(ssig & combined, np.minimum(hold_arr, hd),
                                np.where(ssig, float(hd), hold_arr))
            combined |= ssig
        closes[s] = df["close"]
        sigs[s] = pd.Series(combined, index=df.index)
        holds[s] = pd.Series(hold_arr, index=df.index)
        sids[s] = pd.Series(sid_arr, index=df.index)
        dvol[s] = (df["close"] * df["volume"]).rolling(20, min_periods=5).mean()
    close = pd.DataFrame(closes).sort_index()
    idx = close.index
    return (close, pd.DataFrame(sigs).reindex(idx).fillna(False),
            pd.DataFrame(dvol).reindex(idx), pd.DataFrame(holds).reindex(idx),
            pd.DataFrame(sids).reindex(idx).fillna(-1.0), exit_specs)


# ── pipeline ─────────────────────────────────────────────────────────────────
def cmd_edge(shapes):
    print(f"\n### ENTRY EDGE — {'+'.join(shapes)} (fwd {HORIZON}d) ###")
    for start, end, label in TIERS:
        close, sig, _, _, _, _ = load(shapes, start, end)
        sg, base = [], []
        for s in close.columns:
            c = close[s]
            fwd = (c.shift(-HORIZON) / c - 1.0)
            sub = (close.index >= start) & (close.index <= end)
            base.extend(fwd[sub].dropna().tolist())
            mask = sig[s].to_numpy() & sub
            sg.extend(fwd.to_numpy()[mask][~np.isnan(fwd.to_numpy()[mask])].tolist())
        sg, base = np.array(sg), np.array(base)
        if len(sg) == 0:
            print(f"  {label}: no signals"); continue
        print(f"  {label}: n={len(sg)}  median {np.median(sg)*100:+.2f}%  "
              f"win {np.mean(sg>0)*100:.1f}%  edge {np.median(sg)*100-np.median(base)*100:+.2f}%")


def cmd_portfolio(shapes, N=15, HOLD=HORIZON):
    print(f"\n### PORTFOLIO — {'+'.join(shapes)} (N={N}, hold {HOLD}d) ###")
    cap = max(1, (N + len(shapes) - 1) // len(shapes))  # per-shape cap forces breadth
    for start, end, label in TIERS:
        close, sig, dvol, hold, sid, exspecs = load(shapes, start, end)
        eq = simulate(close, sig, dvol, start, end, N, HOLD, hold_panel=hold, shape_panel=sid,
                      cap_per_shape=cap, exit_specs=exspecs)
        cagr, shp, mdd = perf(eq)
        try:
            spy = v.split_adjusted("SPY", asof=end, ca=S.CA)["close"]
            spy = spy[(spy.index >= start) & (spy.index <= end)]
            sc, ss, sm = perf(spy / spy.iloc[0] * CAP0)
        except Exception:
            sc = ss = sm = float("nan")
        print(f"  {label}: CAGR {cagr:.1f}% Sharpe {shp:.2f} MaxDD {mdd:.1f}%   "
              f"(SPY {sc:.1f}% / {ss:.2f} / {sm:.1f}%)")


def cmd_ortho(shapes, N=15, HOLD=HORIZON):
    from shapes_orthogonality import real_ensemble_equity  # lazy: pulls the t30v engine
    print(f"\n### ORTHOGONALITY vs REAL t30v — {'+'.join(shapes)} (N={N}, hold {HOLD}d) ###")
    cap = max(1, (N + len(shapes) - 1) // len(shapes))  # per-shape cap forces breadth
    for start, end, label in TIERS:
        close, sig, dvol, hold, sid, exspecs = load(shapes, start, end)
        br = simulate(close, sig, dvol, start, end, N, HOLD, hold_panel=hold, shape_panel=sid,
                      cap_per_shape=cap, exit_specs=exspecs)
        en, eres = real_ensemble_equity(start, end)
        bc, bs, bm = perf(br)
        print(f"\n  {label}")
        print(f"    standalone: shape CAGR {bc:.1f}% Sharpe {bs:.2f} MaxDD {bm:.1f}%  |  "
              f"REAL t30v ann {eres['ann']:.1f}% Sharpe {eres['sharpe']:.2f} MaxDD {eres['mdd']:.1f}%")
        grid = en.index
        try:
            spy = v.split_adjusted("SPY", asof=end, ca=S.CA)["close"]
        except Exception:
            spy = None
        cols = {"Shape": br.reindex(grid, method="ffill").pct_change(), "t30v": en.pct_change()}
        if spy is not None:
            cols["SPY"] = spy.reindex(grid, method="ffill").pct_change()
        rdf = pd.DataFrame(cols).dropna()
        corr = rdf.corr()
        print(f"    corr(shape,t30v)={corr.loc['Shape','t30v']:.2f}  "
              f"corr(shape,SPY)={corr.loc['Shape','SPY']:.2f}" if spy is not None
              else f"    corr(shape,t30v)={corr.loc['Shape','t30v']:.2f}")
        best = None
        for w in [0.0, 0.25, 0.5, 0.7, 0.75, 1.0]:
            r = w * rdf["t30v"] + (1 - w) * rdf["Shape"]
            cagr, shp, mdd = perf(CAP0 * (1 + r).cumprod(), ppy=26)
            if best is None or shp > best[1]:
                best = (w, shp, cagr, mdd)
            if w in (0.0, 0.25, 0.5, 0.75, 1.0):
                print(f"      blend {int(w*100):>3}% t30v: CAGR {cagr:.1f}% Sharpe {shp:.2f} MaxDD {mdd:.1f}%")
        print(f"    >> best Sharpe {best[1]:.2f} at {int(best[0]*100)}% t30v "
              f"(vs t30v-alone {eres['sharpe']:.2f})  [MDD on biweekly grid ~approx]")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else ["cup_handle"]
    for nm in names:
        if cmd != "list" and nm not in SHAPES:
            print(f"unknown shape '{nm}'. registered: {list(SHAPES)}"); sys.exit(1)
    if cmd == "list":
        print("registered shapes:", list(SHAPES))
    elif cmd == "edge":
        cmd_edge(names)
    elif cmd == "portfolio":
        cmd_portfolio(names)
    elif cmd == "ortho":
        cmd_ortho(names)
    else:
        print("commands: list | edge | portfolio | ortho   <shape1,shape2,...>")
