"""PITFWU veneer verification — regression suite.

The previous engine silently corrupted data for months. This suite proves the
PITFWU veneer is *correct*, not just self-consistent — three of the checks
cross-reference yfinance (an external split-adjusted source we don't control).

Run:  AWS_PROFILE=rigacap python scripts/pitfwu_verify.py
Exit code 0 = all pass. Keep it green before trusting any PITFWU number.
"""
import sys
import pandas as pd

sys.path.insert(0, "/Users/erikkins/CODE/stocker-app/scripts")
import pitfwu_veneer as v  # noqa: E402

_results = []


def check(name, cond, detail=""):
    _results.append(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def _yf_adj(sym, a, b):
    import yfinance as yf
    d = yf.download(sym, start=a, end=b, progress=False, auto_adjust=True)["Close"]
    d = d.iloc[:, 0] if hasattr(d, "columns") else d
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return d


def main():
    ca = v.load_corp_actions()
    panel = v.load_panel()

    # 1. point-in-time as-of: same date reads pre/post split depending on asof
    d = "2021-12-31"
    before = v.split_adjusted("AMZN", asof="2022-01-01", ca=ca).loc[:d]["close"].iloc[-1]
    after = v.split_adjusted("AMZN", asof="2026-06-04", ca=ca).loc[:d]["close"].iloc[-1]
    check("as-of point-in-time split (AMZN 20:1)", 18 < before / after < 22,
          f"ratio {before/after:.1f}x  (${before:.0f} pre vs ${after:.0f} post)")

    # 2. continuity: phantom -94% gone after adjustment
    raw = v.load_bars("AMZN")["close"]
    adj = v.split_adjusted("AMZN", asof="2026-06-04", ca=ca)["close"]
    ex = pd.Timestamp("2022-06-06")
    rret = raw.loc[:ex].iloc[-1] / raw.loc[raw.index < ex].iloc[-1] - 1
    aret = adj.loc[:ex].iloc[-1] / adj.loc[adj.index < ex].iloc[-1] - 1
    check("split continuity (no phantom jump)", abs(aret) < 0.1 and rret < -0.8,
          f"raw {rret*100:+.0f}% -> adjusted {aret*100:+.1f}%")

    # 3. independent gold-standard: AMZN (no dividend) must match yfinance ~exactly
    yf = _yf_adj("AMZN", "2022-01-03", "2026-05-30")
    both = pd.concat([adj.rename("p"), yf.rename("y")], axis=1).dropna()
    both = both / both.iloc[0]
    md = (both["p"] / both["y"] - 1).abs().max() * 100
    check("vs yfinance, single split, no div (AMZN)", both["p"].corr(both["y"]) > 0.999 and md < 2,
          f"corr {both['p'].corr(both['y']):.5f}, maxdiff {md:.2f}%")

    # 4. cumulative multi-split: NVDA 4:1 then 10:1
    adjn = v.split_adjusted("NVDA", asof="2026-06-04", ca=ca)["close"]
    yfn = _yf_adj("NVDA", "2021-01-04", "2026-05-30")
    bn = pd.concat([adjn.rename("p"), yfn.rename("y")], axis=1).dropna()
    bn = bn / bn.iloc[0]
    mdn = (bn["p"] / bn["y"] - 1).abs().max() * 100
    check("cumulative multi-split (NVDA 4:1x10:1)", bn["p"].corr(bn["y"]) > 0.999 and mdn < 3,
          f"corr {bn['p'].corr(bn['y']):.5f}, maxdiff {mdn:.2f}%")

    # 5. split-only (price return), NOT total return: AAPL must DIVERGE by div drag
    adja = v.split_adjusted("AAPL", asof="2026-06-04", ca=ca)["close"]
    yfa = _yf_adj("AAPL", "2022-01-03", "2026-05-30")
    ba = pd.concat([adja.rename("p"), yfa.rename("y")], axis=1).dropna()
    ba = ba / ba.iloc[0]
    drag = (ba["y"].iloc[-1] / ba["p"].iloc[-1] - 1) * 100
    check("price-return not total-return (AAPL div drag)", 0.5 < drag < 6,
          f"yfinance(total) higher by {drag:.2f}% = dividends (exact match = BUG)")

    # 6. merger terminal value: ATVI -> MSFT $95 cash
    _, lp = v.last_trade("ATVI")
    check("merger terminal value (ATVI -> $95)", 90 < lp < 96, f"last bar ${lp:.2f}")

    # 7. survivorship: SIVB ranked before death, gone after
    ub = v.universe_asof("2023-01-03", 600, panel)
    ua = v.universe_asof("2023-06-01", 600, panel)
    check("survivorship (SIVB pre/post collapse)", "SIVB" in ub and "SIVB" not in ua,
          f"in pre-collapse universe={('SIVB' in ub)}, post={('SIVB' in ua)}")

    print(f"\n{sum(_results)}/{len(_results)} PASS")
    return 0 if all(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
