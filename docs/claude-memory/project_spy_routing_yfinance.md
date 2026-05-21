---
name: SPY routed through yfinance (philosophy, not bug fix)
description: SPY is fetched via yfinance with auto_adjust=True, not Alpaca, for benchmark/regime use. Reason is data philosophy, not Alpaca corruption.
type: project
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
## The setup (May 19 2026)

`market_data_provider.YFINANCE_PREFERRED = {'SPY'}` routes SPY through
yfinance for both initial fetch and daily incremental updates.

## Why — not the reason I first thought

Original framing (May 19): "Alpaca's SPY 2026-02-02 bar is corrupted —
low=$68.81 when the actual market low was ~$687.54."

**Corrected framing (May 21 2026, per Alpaca support response):** Alpaca's
data is NOT corrupted. The $69.005 low was a **real trade** that hit the
FINRA tape and the SIP feed at that price. Alpaca confirmed with Polygon/
Massive — same trade, same low, all SIP-honoring providers report it.

Alpaca's data policy: **strict SIP-faithfulness**. They never edit bars
unilaterally; they only update if the SIP issues a correction. The SIP
never corrected this trade.

yfinance and some other providers chose to **filter the obvious outlier**
at the data layer.

## Why we want the filtered version

For SPY's role in our system (benchmark + 200MA regime filter), an
anomalous single tick at $69 would distort the 200MA calc for the next
year of compounding. We're not auditing trade tape — we want a smooth
benchmark series. yfinance's outlier-filtered SPY is what our strategy
needs.

The 11y canonical pickle (Apr 28 marketing baseline) was implicitly built
from yfinance with `auto_adjust=True`. Our routing aligns prod to that.

## Net

- Both providers are correct by their own standards.
- We route SPY to yfinance because the cleaned version is what our use
  case needs.
- This is **philosophy alignment, not bug remediation**.

## Side effects to watch

- Settlement check probe must use an Alpaca-native symbol (AAPL after
  May 20 2026 — SPY-on-yfinance broke the check; see daily_scan handler
  in main.py).
- Other index symbols (^VIX, ^GSPC) were already on yfinance for
  unrelated reasons (Alpaca doesn't serve indices).
- Individual stocks remain on Alpaca SIP — they're not part of this
  routing carve-out.
