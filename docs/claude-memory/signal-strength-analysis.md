# Signal Strength Score — Factor Analysis & Formula (2026-02-25)

## Dataset
- 710 trades from 5 × 1-year walk-forward simulations (2021-2026)
- WF job IDs: 135, 136, 137, 138, 139 (with enriched metadata)
- All trades include 7 metadata fields: dwap_age, short_mom, long_mom, volatility, dist_from_high, vol_ratio, spy_trend
- Combined data saved at `/tmp/wf-all-trades.json`

## Factor Analysis Results

### Pearson Correlations (with pnl_pct)
| Factor | r | p-value | Significant? |
|--------|---|---------|-------------|
| momentum_score | -0.123 | 0.001 | ** (negative!) |
| long_mom | -0.117 | 0.002 | ** (negative!) |
| volatility | +0.059 | 0.12 | No |
| short_mom | +0.036 | 0.34 | No |
| pct_above_dwap | +0.005 | 0.89 | No |
| dwap_age | +0.014 | 0.72 | No |
| vol_ratio | -0.037 | 0.32 | No |
| spy_trend | -0.012 | 0.75 | No |
| dist_from_high | -0.035 | 0.35 | No |

**Key finding:** Most factors have very weak linear correlation. The strongest signal is that high momentum_score/long_mom actually correlates with *worse* returns (mean reversion effect).

### Quintile Analysis — Key Patterns
- **volatility**: ONLY factor with **monotonically increasing** quintile returns (Q1: +0.20% → Q5: +3.52%)
- **spy_trend**: +9.3pp win rate spread Q5 vs Q1, humped shape (Q3 peak at 6.6-8.4%)
- **dwap_age**: Stale crosses outperform (+5.5pp win rate Q5 vs Q1), confirms prior analysis
- **dist_from_high**: Consistent across 5/6 years (negative r). Q2 (-2.6 to -1.3) is sweet spot

### Year-over-Year Stability (5/6 = most stable)
- dist_from_high: 5/6 years same sign (most consistent)
- spy_trend: 5/6 years same sign
- momentum_score: 5/6 years same sign (negative)

### Strongest 2-Factor Interaction
- vol_ratio × momentum_score: High/High = +3.34% avg vs Low/Low = +0.42% avg

## Winning Formula: Penalty/Bonus Model (Formula B)

```python
def compute_signal_strength(volatility, spy_trend, dwap_age, dist_from_high, vol_ratio, momentum_score, **_):
    base = 60
    vol_bonus = min((volatility - 20) * 0.3, 15)      # Higher vol → better (monotonic)
    if 6 <= spy_trend <= 9: spy_bonus = 10              # Sweet spot
    elif spy_trend > 3: spy_bonus = 5
    else: spy_bonus = -5                                 # Bearish penalty
    age_bonus = min(dwap_age / 15, 10)                  # Stale crosses better
    dfh_bonus = 8 if -3 < dist_from_high < -1 else 0   # Near-high sweet spot
    combo_bonus = 8 if vol_ratio > 1.3 and momentum_score > 5 else 0  # Interaction
    return max(0, min(100, round(base + vol_bonus + spy_bonus + age_bonus + dfh_bonus + combo_bonus)))
```

### Validation Results
- **Pearson r:** +0.083 (p=0.027), statistically significant
- **Q5-Q1 avg spread:** +2.39%
- **Q5-Q1 win rate spread:** +1.2pp
- **Leave-one-year-out CV:** 4/5 full years pass (only 2022 bear year fails)

### Score Labels & Performance
| Label | Range | Count | Avg Return | Win Rate |
|-------|-------|-------|------------|----------|
| Weak | 0-60 | 30 (4%) | +0.00% | 40.0% |
| Moderate | 61-74 | 229 (32%) | +0.22% | 51.1% |
| Strong | 75-87 | 306 (43%) | +1.97% | 58.5% |
| Very Strong | 88-100 | 145 (20%) | +3.05% | 53.1% |

## Alternative Formulas Tested
- **Formula A (Empirical Bucket):** Best full-sample spread (+4.56%) but only 4/6 LOO-CV
- **Formula C (Simple Tiered):** Most robust to overfitting but weakest signal (+3.07% spread, r=0.062 n.s.)
- **Formula B2 (Refined B):** Attempted to fix Q4>Q5 inversion, lost one LOO year

## Implementation Notes
- The 7 metadata fields are computed in `backtester.py` during ensemble entry
- `_compute_dwap_age()` scans backward up to 252 days; uses `_days_between()` for tz safety
- `_compute_spy_trend()` returns SPY % above 200MA
- Fields propagate through: candidate dict → position dict → SimulatedTrade → PeriodTrade → JSON
