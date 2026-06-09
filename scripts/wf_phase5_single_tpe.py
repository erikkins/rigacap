#!/usr/bin/env python3
"""
Phase 5 — single-TPE-search baseline.

Question: does TPE find params that beat fixed-canonical when we DON'T
let it switch every period? Phase 2/3/4 showed per-period adaptive TPE
loses to fixed canonical on Date 3 across every risk preference. This
isolates "TPE finds good params" from "per-period switching destroys
compounding."

Approach (honest train/test split):
  1. Train on 2019-06-03 → 2020-12-31 (~18 months before Date 3 start)
     Run a SINGLE TPE optimization on this window to find best params.
  2. Test on 2021-01-25 → 2026-01-25 (5y, Date 3)
     Run WF with TPE-found params held fixed (no per-period switching).
  3. Compare to fixed-canonical Date 3 result (+186%).

No data leakage: training window ends 25 days before test window starts.
"""
import asyncio
import gzip
import json
import os
import pickle
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

if not os.environ.get('DATABASE_URL'):
    for line in open(os.path.join(os.path.dirname(__file__), '..', '.env')):
        if line.startswith('DATABASE_URL='):
            os.environ['DATABASE_URL'] = line.strip().split('=', 1)[1]
            break
os.environ.setdefault('LAMBDA_ROLE', 'worker')

PICKLE_PATH = '/tmp/parity_test/prod_after_refetch.pkl.gz'
TRAIN_START = '2019-06-03'   # earliest data in pickle
TRAIN_END   = '2020-12-31'   # 25+ days before test start (no leakage)
TEST_START  = '2021-01-25'   # Date 3 — the worst-case for per-period TPE
TEST_END    = '2026-01-25'
N_TRIALS    = 60             # higher than per-period (one-shot, can afford more)
OPTIMIZER   = 'v2m'
RISK_PREF   = 0.7            # return-favored (matches what Trial 37 era used)

OUT_DIR = '/tmp/tpe_phase5'
os.makedirs(OUT_DIR, exist_ok=True)


def load_pickle():
    abs_path = os.path.join(os.path.dirname(__file__), '..', PICKLE_PATH)
    if not os.path.exists(abs_path):
        abs_path = PICKLE_PATH
    print(f"📦 Loading pickle: {abs_path}")
    with gzip.open(abs_path, 'rb') as f:
        return pickle.load(f)


async def main():
    from app.services.walk_forward_service import walk_forward_service
    from app.services.scanner import scanner_service
    from app.core.database import async_session

    cache = load_pickle()
    scanner_service.data_cache = cache
    scanner_service.universe = list(cache.keys())
    print(f"  ✅ {len(cache)} symbols\n")

    # ─── Stage 1: ONE TPE optimization on training window ───
    print("=" * 70)
    print(f"STAGE 1: Single TPE search on {TRAIN_START} → {TRAIN_END}")
    print(f"  optimizer=v2m, risk_pref={RISK_PREF}, n_trials={N_TRIALS}")
    print("=" * 70)

    train_end_dt = datetime.strptime(TRAIN_END, '%Y-%m-%d')
    top_symbols = walk_forward_service._get_top_symbols_as_of(train_end_dt, max_symbols=200)
    print(f"  Training universe: {len(top_symbols)} symbols\n")

    t0 = time.time()
    ai_result = walk_forward_service._run_ai_optimization_at_date(
        as_of_date=train_end_dt,
        strategy_type='ensemble',
        lookback_days=60 * 6,  # 6-month lookback so TPE sees more market regimes
        ticker_list=top_symbols,
        warm_start_params=None,
        n_trials=N_TRIALS,
        optimizer_version=OPTIMIZER,
        risk_preference=RISK_PREF,
    )
    dur = time.time() - t0

    if not ai_result:
        print("❌ TPE returned no result — aborting")
        return

    print(f"✅ TPE complete in {dur/60:.1f} min")
    print(f"  Regime detected:    {ai_result.market_regime}")
    print(f"  Adaptive score:     {ai_result.adaptive_score:.2f}")
    print(f"  Expected return:    {ai_result.expected_return_pct:+.2f}%")
    print(f"  Expected Sharpe:    {ai_result.expected_sharpe:.2f}")
    print(f"  Expected MaxDD:     {ai_result.expected_max_dd:.2f}%")
    print(f"\nBest params found by TPE:")
    best_params = ai_result.best_params or {}
    for k, v in sorted(best_params.items()):
        print(f"   {k:<30}  {v}")

    # Save params
    params_path = os.path.join(OUT_DIR, 'tpe_best_params.json')
    with open(params_path, 'w') as f:
        json.dump({
            'train_window': f'{TRAIN_START} → {TRAIN_END}',
            'regime': ai_result.market_regime,
            'adaptive_score': ai_result.adaptive_score,
            'best_params': best_params,
        }, f, indent=2, default=str)
    print(f"\n💾 Saved → {params_path}")

    # ─── Stage 2: 5y WF using TPE-found params held fixed ───
    print()
    print("=" * 70)
    print(f"STAGE 2: 5y WF with TPE-found params held FIXED")
    print(f"  {TEST_START} → {TEST_END}")
    print("=" * 70)

    # Run WF with enable_ai_optimization=False (so no per-period switching)
    # but pass the TPE-found params via the strategy-override args.
    test_start = datetime.strptime(TEST_START, '%Y-%m-%d')
    test_end = datetime.strptime(TEST_END, '%Y-%m-%d')

    t0 = time.time()
    async with async_session() as db:
        result = await walk_forward_service.run_walk_forward_simulation(
            db=db,
            start_date=test_start,
            end_date=test_end,
            reoptimization_frequency='biweekly',
            min_score_diff=10.0,
            enable_ai_optimization=False,        # ← critical: no per-period TPE
            max_symbols=200,
            fixed_strategy_id=5,
            n_trials=0,
            carry_positions=True,
            # Override the canonical fixed-strategy params with TPE-found ones.
            # Only the 5 CLI-overridable knobs flow through here; the rest
            # come from the StrategyParams defaults inside _test_param_combination.
            max_positions=best_params.get('max_positions', 6),
            position_size_pct=best_params.get('position_size_pct', 15.0),
            near_50d_high_pct=best_params.get('near_50d_high_pct', 3.0),
            trailing_stop_pct=best_params.get('trailing_stop_pct', 12.0),
            dwap_threshold_pct=best_params.get('dwap_threshold_pct', 5.0),
            periods_limit=0,
        )
    dur = time.time() - t0

    print(f"\n{'=' * 70}")
    print(f"RESULTS")
    print(f"{'=' * 70}")
    print(f"  Total return:    {result.total_return_pct:+.2f}%")
    print(f"  Sharpe:          {result.sharpe_ratio:.2f}")
    print(f"  MaxDD:           {result.max_drawdown_pct:.2f}%")
    print(f"  Benchmark (SPY): {getattr(result, 'benchmark_return_pct', 0):+.2f}%")
    print(f"  Trades:          {len(result.trades)}")
    print(f"  Duration:        {dur/60:.1f} min")
    years = (test_end - test_start).days / 365.25
    ann = (1 + result.total_return_pct/100) ** (1/years) - 1
    print(f"  Annualized:      {ann*100:+.2f}%")
    print()
    print(f"vs fixed-canonical Date 3 (+186% / Sharpe ? / MaxDD ?):")
    print(f"  return delta:    {result.total_return_pct - 186:+.2f}pp")

    # Save full result
    pkl_path = os.path.join(OUT_DIR, 'result.pkl')
    json_path = os.path.join(OUT_DIR, 'result.json')
    with open(pkl_path, 'wb') as f:
        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(json_path, 'w') as f:
        json.dump({
            'total_return_pct': result.total_return_pct,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown_pct': result.max_drawdown_pct,
            'benchmark_return_pct': getattr(result, 'benchmark_return_pct', None),
            'trades_count': len(result.trades),
            'tpe_best_params': best_params,
        }, f, indent=2, default=str)
    print(f"\n💾 Result → {pkl_path}")


if __name__ == '__main__':
    asyncio.run(main())
