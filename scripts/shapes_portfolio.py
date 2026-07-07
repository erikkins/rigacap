"""Bull Rider portfolio sim — the go/no-go. Trade cup-and-handle breakouts as a
diversified rolling basket and measure SLEEVE-level performance held-out vs SPY.

Why a portfolio: per-trade the edge is modest (held-out ~+1.3% median, 54% win,
~20d hold) and STOPS whipsaw it (proven). So we trade the clean entry with a
plain time-exit, diversified across N concurrent slots, and let it compound.

Mechanics (survivorship-free, point-in-time PITFWU; daily mark-to-market):
  - up to N concurrent equal-weight positions (each gets equity/N at entry)
  - enter at the breakout day's close; if more signals than free slots, take the
    earliest/most-liquid first (deterministic, no lookahead)
  - EXIT purely on a HOLD-day time stop (no tight stop — that whipsawed)
  - delisted mid-hold → exit at the last available bar (honest)
  - COST bps round-trip; idle cash earns 0 (no leverage)
Reports CAGR / Sharpe / MaxDD vs SPY for Tier-1, Tier-2 held-out, and full.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache \
       backend/venv/bin/python scripts/shapes_portfolio.py [N] [HOLD]
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

COST = 0.0015
CAP0 = 100_000.0


def load_panel(start, end):
    """Aligned close panel + per-symbol signal/liquidity over the rigorous PiT union."""
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    closes, sigs, dvol = {}, {}, {}
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["close", "volume"]]
        except Exception:
            continue
        c = df["close"]
        closes[s] = c
        sig = S.cup_and_handle_breakouts(c.to_numpy(float), df["volume"].to_numpy(float))
        sigs[s] = pd.Series(sig, index=df.index)
        dvol[s] = (c * df["volume"]).rolling(20, min_periods=5).mean()  # $ volume for tie-break
    close = pd.DataFrame(closes).sort_index()
    sig = pd.DataFrame(sigs).reindex(close.index).fillna(False)
    return close, sig, pd.DataFrame(dvol).reindex(close.index)


def simulate(close, sig, dvol, start, end, N, HOLD, hold_panel=None, shape_panel=None,
             cap_per_shape=None, exit_specs=None):
    # hold_panel: per-(date,symbol) time-backstop days (also the exit for "time" shapes).
    # shape_panel + cap_per_shape: cap positions from any one shape (breadth/decorrelation).
    # exit_specs: list indexed by shape-id giving each shape's exit RULE — "time",
    #   "trail" (pct off close high-water-mark), or "target_stop" — evaluated on closes
    #   (consistent with the sim's close-based mark-to-market). hold_panel is the backstop.
    from collections import Counter
    dates = close.index
    win = dates[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    # per-symbol valid-date arrays for exit scheduling (HOLD bars ahead in ITS calendar)
    valid = {s: close[s].dropna().index for s in close.columns}
    pos = {}          # sym -> dict(shares, exit_date, last)
    cash = CAP0
    eq_dates, eq_vals = [], []
    last_px = {}

    for today in win:
        row = close.loc[today]
        # update last-known prices
        for s in close.columns:
            px = row[s]
            if px == px:  # not NaN
                last_px[s] = px
        # 1) exits — each position by ITS shape's rule (close-based); time backstop applies to all
        to_sell = []
        for s, p in pos.items():
            c_t = last_px.get(s, p["last"])
            if c_t > p["hi"]:
                p["hi"] = c_t
            spec = exit_specs[p["shape"]] if (exit_specs and 0 <= p["shape"] < len(exit_specs)) else None
            typ = spec["type"] if spec else "time"
            sell = today >= p["exit_date"]  # time backstop for every exit type
            if not sell and typ == "trail":
                sell = c_t <= p["hi"] * (1 - spec["pct"])
            elif not sell and typ == "target_stop":
                sell = c_t >= p["entry"] * (1 + spec["target"]) or c_t <= p["entry"] * (1 - spec["stop"])
            if sell:
                to_sell.append(s)
        for s in to_sell:
            px = last_px.get(s, pos[s]["last"])
            cash += pos[s]["shares"] * px * (1 - COST)
            del pos[s]
        # 2) entries — today's breakouts, not held, slots free; tie-break by $ volume desc.
        if len(pos) < N:
            cands = [s for s in close.columns
                     if bool(sig.loc[today, s]) and s not in pos and (row[s] == row[s])]
            cands.sort(key=lambda s: -(dvol.loc[today, s] if dvol.loc[today, s] == dvol.loc[today, s] else 0))
            scount = Counter(p.get("shape", -1) for p in pos.values())
            for s in cands:
                if len(pos) >= N:
                    break
                sid = int(shape_panel.loc[today, s]) if shape_panel is not None else -1
                if cap_per_shape is not None and scount[sid] >= cap_per_shape:
                    continue  # this shape is at its cap — force breadth
                price = row[s]
                alloc = (cash + sum(pos[x]["shares"] * last_px.get(x, pos[x]["last"]) for x in pos)) / N
                alloc = min(alloc, cash)
                if alloc <= 0:
                    break
                shares = alloc / price
                cash -= alloc + alloc * COST
                vd = valid[s]
                j = vd.get_indexer([today])[0]
                hh = HOLD
                if hold_panel is not None:
                    hv = hold_panel.loc[today, s]
                    if hv == hv and hv > 0:  # not NaN
                        hh = int(hv)
                exit_date = vd[min(j + hh, len(vd) - 1)] if j >= 0 else today
                pos[s] = {"shares": shares, "exit_date": exit_date, "last": price, "shape": sid,
                          "entry": price, "hi": price}
                scount[sid] += 1
        # 3) mark to market
        mtm = cash + sum(pos[s]["shares"] * last_px.get(s, pos[s]["last"]) for s in pos)
        eq_dates.append(today); eq_vals.append(mtm)
    return pd.Series(eq_vals, index=pd.DatetimeIndex(eq_dates))


def perf(eq, ppy=252):
    e = eq.to_numpy(float)
    days = max(1, (eq.index[-1] - eq.index[0]).days)
    cagr = (e[-1] / e[0]) ** (365.25 / days) - 1
    dr = e[1:] / e[:-1] - 1
    sharpe = dr.mean() / dr.std() * np.sqrt(ppy) if dr.std() > 0 else 0.0  # ppy = return periods/yr
    peak = np.maximum.accumulate(e)
    mdd = ((e - peak) / peak).min()
    return cagr * 100, sharpe, mdd * 100


def spy_perf(start, end):
    try:
        spy = v.split_adjusted("SPY", asof=end, ca=S.CA)["close"]
        spy = spy[(spy.index >= pd.Timestamp(start)) & (spy.index <= pd.Timestamp(end))]
        return perf(spy / spy.iloc[0] * CAP0)
    except Exception:
        return None


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    HOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    full = (pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"))
    print(f"Loading panel (one-time)... N={N} slots, HOLD={HOLD}d, cost={COST*1e4:.0f}bps")
    close, sig, dvol = load_panel(*full)
    print(f"  {close.shape[1]} symbols, {close.shape[0]} trading days")

    windows = [
        (pd.Timestamp("2016-06-01"), pd.Timestamp("2020-12-31"), "Tier-1 (2016-2020)"),
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 HELD-OUT (2021-26)"),
        (full[0], full[1], "Full (2016-2026)"),
    ]
    out = []
    print(f"\n  {'window':<26} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>8}   {'SPY CAGR':>8} {'SPY Shp':>7} {'SPY DD':>7}")
    for start, end, label in windows:
        eq = simulate(close, sig, dvol, start, end, N, HOLD)
        cagr, shp, mdd = perf(eq)
        sp = spy_perf(start, end) or (float("nan"),) * 3
        print(f"  {label:<26} {cagr:>6.1f}% {shp:>7.2f} {mdd:>7.1f}%   {sp[0]:>7.1f}% {sp[1]:>7.2f} {sp[2]:>6.1f}%")
        out.append({"window": label, "N": N, "HOLD": HOLD,
                    "cagr": cagr, "sharpe": shp, "maxdd": mdd,
                    "spy_cagr": sp[0], "spy_sharpe": sp[1], "spy_maxdd": sp[2],
                    "final_equity": float(eq.iloc[-1])})
    path = os.path.join(R, "scripts", "shapes_portfolio_results.json")
    json.dump(out, open(path, "w"), indent=2)
    print(f"\nThe go/no-go: does the HELD-OUT sleeve beat SPY on risk-adjusted (Sharpe/MaxDD)?\nsaved → {path}")
