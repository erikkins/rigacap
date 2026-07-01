"""Orthogonality test — does Bull Rider DIVERSIFY, even though it ~= SPY alone?

A sleeve that merely matches SPY can still earn its place IF it's uncorrelated
with what we already run (the defensive Ensemble) — a blend would then beat
either alone. This measures that directly, all on the SAME survivorship-free,
point-in-time PITFWU panel so it's apples-to-apples:

  - Bull Rider stream : cup-and-handle entry + 20d time-exit (the validated build)
  - Ensemble stream   : the production ensemble ENTRY (DWAP+5%, near-50d-high,
                        >MA20/MA50, vol>500k, px>15) on the same sim. PROXY — it
                        uses the same N/time-exit, so it's an ENTRY-correlation
                        read, not the exact t30v product (own exit/regime/rebal).
  - SPY               : buy-hold

Outputs: daily-return correlation matrix (Bull Rider / Ensemble / SPY) and a
blend sweep (Ensemble weight 0->1) → Sharpe/CAGR/MaxDD, to see if any mix beats
standalone. Held-out Tier-2 is the verdict. RESEARCH ONLY, local, ~$0.

Usage: AWS_PROFILE=rigacap PITFWU_LOCAL=~/pitfwu_cache \
       backend/venv/bin/python scripts/shapes_orthogonality.py [N] [HOLD]
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
import asyncio
import pitfwu_wf_periods as wfp  # the VALIDATED prod t30v (strategy_id 6, biweekly walk-forward)


def real_ensemble_equity(start, end):
    """Equity of the ACTUAL prod t30v (20x4.5%, trail 30, vol_weight 1.0) — the exact
    config + engine behind the advertised numbers (~17% MDD). Returns (biweekly
    equity series, engine metrics dict). Bull Rider is a SEPARATE strategy — we only
    need THIS leg to reproduce production."""
    res = asyncio.run(wfp.wf(start.to_pydatetime(), end.to_pydatetime(), 20, 4.5, 30, conv=0.0, volw=1.0))
    ec = res["equity_curve"]
    eq = pd.Series([p["equity"] for p in ec], index=pd.to_datetime([p["date"] for p in ec]))
    return eq[~eq.index.duplicated()].sort_index(), res


def build_panels(start, end):
    """close + $vol panels and BOTH signal panels (cup-and-handle, ensemble) on the union."""
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    closes, cup, ens, dvol = {}, {}, {}, {}
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=S.CA)[["close", "volume"]]
        except Exception:
            continue
        c, vol = df["close"], df["volume"]
        closes[s] = c
        cup[s] = pd.Series(S.cup_and_handle_breakouts(c.to_numpy(float), vol.to_numpy(float)), index=df.index)
        dwap = (c * vol).rolling(200, min_periods=50).sum() / vol.rolling(200, min_periods=50).sum()
        ma20, ma50, hi50 = c.rolling(20, 1).mean(), c.rolling(50, 1).mean(), c.rolling(50, 1).max()
        ens[s] = (c > dwap * 1.05) & (c >= hi50 * 0.97) & (c > ma20) & (c > ma50) & (vol >= 500_000) & (c >= 15)
        dvol[s] = (c * vol).rolling(20, min_periods=5).mean()
    close = pd.DataFrame(closes).sort_index()
    idx = close.index
    return (close, pd.DataFrame(cup).reindex(idx).fillna(False),
            pd.DataFrame(ens).reindex(idx).fillna(False), pd.DataFrame(dvol).reindex(idx))


def daily_ret(eq):
    return eq.pct_change().dropna()


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    HOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    full = (pd.Timestamp("2016-06-01"), pd.Timestamp("2026-05-29"))
    print(f"Building panels (one-time)... N={N}, HOLD={HOLD}")
    close, cup_sig, ens_sig, dvol = build_panels(*full)
    print(f"  {close.shape[1]} symbols, {close.shape[0]} days")

    try:
        spy = v.split_adjusted("SPY", asof=full[1], ca=S.CA)["close"]
    except Exception:
        spy = None

    out = []
    for start, end, label in [
        (pd.Timestamp("2021-01-01"), pd.Timestamp("2026-05-29"), "Tier-2 HELD-OUT (2021-26)"),
        (full[0], full[1], "Full (2016-2026)"),
    ]:
        br = simulate(close, cup_sig, dvol, start, end, N, HOLD)   # Bull Rider — its OWN daily sim
        en, eres = real_ensemble_equity(start, end)                # REAL prod t30v (biweekly grid)
        bc, bs, bm = perf(br)
        print(f"\n  standalone: BullRider CAGR {bc:.1f}% Sharpe {bs:.2f} MaxDD {bm:.1f}%  |  "
              f"REAL t30v (prod engine) ann {eres['ann']:.1f}% Sharpe {eres['sharpe']:.2f} MaxDD {eres['mdd']:.1f}%")

        # Line the two curves up on t30v's biweekly grid (Bull Rider keeps its own
        # logic; we only align dates to measure co-movement + blends).
        grid = en.index
        cols = {"BullRider": br.reindex(grid, method="ffill").pct_change(),
                "Ensemble(t30v)": en.pct_change()}
        if spy is not None:
            cols["SPY"] = spy.reindex(grid, method="ffill").pct_change()
        rdf = pd.DataFrame(cols).dropna()
        corr = rdf.corr()

        print(f"\n================ {label} ================")
        print("  biweekly-return correlation:")
        print(corr.round(2).to_string().replace("\n", "\n  "))

        print(f"\n  blend (t30v w / Bull Rider 1-w):  {'w':>4} {'CAGR':>7} {'Sharpe':>7} {'MaxDD':>8}")
        blend_rows = []
        for w in [0.0, 0.25, 0.5, 0.7, 0.75, 1.0]:
            r = w * rdf["Ensemble(t30v)"] + (1 - w) * rdf["BullRider"]
            eq = CAP0 * (1 + r).cumprod()
            cagr, shp, mdd = perf(eq, ppy=26)  # biweekly returns
            tag = "  <- Bull Rider" if w == 0 else ("  <- t30v" if w == 1 else "")
            print(f"  {'':>34} {w:>4.2f} {cagr:>6.1f}% {shp:>7.2f} {mdd:>7.1f}%{tag}")
            blend_rows.append({"w_ens": w, "cagr": cagr, "sharpe": shp, "maxdd": mdd})
        out.append({"window": label, "corr": corr.round(3).to_dict(), "blend": blend_rows,
                    "t30v_standalone": {"ann": eres["ann"], "sharpe": eres["sharpe"], "mdd": eres["mdd"]}})

    path = os.path.join(R, "scripts", "shapes_orthogonality_results.json")
    json.dump(out, open(path, "w"), indent=2)
    print(f"\nVERDICT: if BullRider~SPY corr is high AND no blend beats Ensemble-alone "
          f"Sharpe, Bull Rider doesn't diversify.\nsaved → {path}")
