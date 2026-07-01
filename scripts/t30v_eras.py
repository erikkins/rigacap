"""t30v by era — for the 'modern-era winner' reframe.

Runs the REAL prod t30v on the same 4 non-overlapping eras as the shape-edge
breakdown, so t30v and the shapes sit side-by-side. Does t30v ALSO strengthen
in the modern era, or does it carry the long record while the shapes are the
modern booster? Pre-2016 = EXT (survivorship-biased). RESEARCH ONLY.
"""
import os, sys, asyncio
R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend")); sys.path.insert(0, os.path.join(R, "scripts"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]; break
os.environ.setdefault("LAMBDA_ROLE", "worker")

from datetime import datetime
import pitfwu_veneer as v
v.EXT = True
import pitfwu_wf_periods as wfp

ERAS = [
    ("2009-2012 *surv-bias*", datetime(2009, 1, 2), datetime(2012, 12, 31)),
    ("2013-2016 *surv-bias*", datetime(2013, 1, 2), datetime(2016, 12, 31)),
    ("2017-2020 clean",       datetime(2017, 1, 2), datetime(2020, 12, 31)),
    ("2021-2026 clean",       datetime(2021, 1, 2), datetime(2026, 5, 29)),
]

if __name__ == "__main__":
    print("REAL t30v (20x4.5%, trail30) by era:\n", flush=True)
    for label, s, e in ERAS:
        m = asyncio.run(wfp.wf(s, e, 20, 4.5, 30, conv=0.0, volw=1.0))
        print(f"  {label:<24} ann {m['ann']:>6.1f}%   sharpe {m['sharpe']:>5.2f}   mdd {m['mdd']:>5.1f}%", flush=True)
