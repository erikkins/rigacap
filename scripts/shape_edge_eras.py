"""WHY is the system recent-only? Measure each shape's RAW entry edge per era.

If the Bull Rider shapes had edge in 2009-2015 too, the blend's pre-2016 failure
was something else (t30v's own weakness / the switch). If they had NO edge pre-2016,
the shapes themselves are a modern-market phenomenon (structure change or overfit).

Edge = median forward return (at the shape's OWN hold horizon) of signal days MINUS
the universe baseline at the same horizon, per non-overlapping ~4y era. Two-step in
spirit (many eras). Pre-2016 = survivorship-BIASED (labeled). RESEARCH ONLY, local.
"""
import os, sys
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import numpy as np
import pandas as pd
import pitfwu_veneer as v
v.EXT = True
from app.services.scanner import _EXCLUDED_SET
import shapes_entry_edge as S
from shape_lab import SHAPES

CA = S.CA
TEST = ["cup_handle", "vcp", "double_bottom", "inv_hs"]
ERAS = [
    ("2009-2012 *surv-bias*", "2009-01-02", "2012-12-31"),
    ("2013-2016 *surv-bias*", "2013-01-02", "2016-12-31"),
    ("2017-2020 clean",       "2017-01-02", "2020-12-31"),
    ("2021-2026 clean",       "2021-01-02", "2026-05-29"),
]


def measure(start, end):
    holds = sorted({SHAPES[sh]["exit"]["hold"] for sh in TEST})
    union = set()
    for d in pd.date_range(start, end, freq="14D"):
        union |= set([s for s in v.universe_asof_prod(d, 300, 15.0)
                      if s not in _EXCLUDED_SET and not s.startswith("^")][:100])
    sig_ret = {sh: [] for sh in TEST}
    base_ret = {h: [] for h in holds}  # baseline forward returns by horizon
    for s in union:
        try:
            df = v.split_adjusted(s, asof=end, ca=CA)[["open", "high", "low", "close", "volume"]]
        except Exception:
            continue
        o, h, l, c, vol = (df[k].to_numpy(float) for k in ["open", "high", "low", "close", "volume"])
        cs = df["close"]
        inwin = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        fwd = {hh: (cs.shift(-hh) / cs - 1.0).to_numpy() for hh in holds}
        for hh in holds:
            base_ret[hh].extend(fwd[hh][inwin & ~np.isnan(fwd[hh])].tolist())
        for sh in TEST:
            hh = SHAPES[sh]["exit"]["hold"]
            mask = SHAPES[sh]["fn"](o, h, l, c, vol) & inwin
            fr = fwd[hh][mask]
            sig_ret[sh].extend(fr[~np.isnan(fr)].tolist())
    out = {}
    for sh in TEST:
        hh = SHAPES[sh]["exit"]["hold"]
        a = np.array(sig_ret[sh]); b = np.array(base_ret[hh])
        if len(a) == 0:
            out[sh] = (0, 0.0, 0.0, 0.0); continue
        out[sh] = (len(a), np.median(a) * 100, (a > 0).mean() * 100,
                   (np.median(a) - np.median(b)) * 100)
    return out


if __name__ == "__main__":
    print("RAW SHAPE ENTRY EDGE by era (edge = median fwd@hold minus baseline)\n", flush=True)
    rows = {}
    for label, s, e in ERAS:
        rows[label] = measure(pd.Timestamp(s), pd.Timestamp(e))
        print(f"  done {label}", flush=True)
    print(f"\n  {'shape':<14}" + "".join(f"{lbl.split(' ')[0]:>22}" for lbl, _, _ in ERAS))
    for sh in TEST:
        line = f"  {sh:<14}"
        for label, _, _ in ERAS:
            n, med, win, edge = rows[label][sh]
            line += f"{f'edge{edge:+.2f}% w{win:.0f} n{n}':>22}"
        print(line)
