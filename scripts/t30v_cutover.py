"""t30v go-live cutover (Jun 10 2026, Erik-approved runsheet).

1. ARCHIVE  — full dump of model_positions (all types), model_portfolio_state,
              strategy 6 row, strategy_adaptive_params -> S3 (nothing deleted
              that isn't preserved; AMD +80.7% memorial included).
2. RESET    — delete ALL model_positions, reset every state row to fresh $100k.
3. FLIP     — strategy 6 row -> t30v (20 x 4.5%, trail 30, vol_weight 1.0,
              dd_tighten zeroed) AND a new strategy_adaptive_params row
              (source=t30v_cutover) because the live trail reads the LATEST
              adaptive row (signals.py ~820), not the strategy row.
4. CB CLEAR — delete stale circuit-breaker pause state in S3 (old tight-trail
              artifact; CIRCUIT_BREAKER_ENABLED stays on for t30v).
5. VERIFY   — re-read everything.

Default is DRY RUN. `EXECUTE` as argv[1] performs the cutover.
Usage: AWS_PROFILE=rigacap backend/venv/bin/python scripts/t30v_cutover.py [EXECUTE]
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime

R = "/Users/erikkins/CODE/stocker-app"
sys.path.insert(0, os.path.join(R, "backend"))
for _l in open(os.path.join(R, ".env")):
    if _l.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = _l.strip().split("=", 1)[1]
        break
os.environ.setdefault("LAMBDA_ROLE", "worker")

import boto3
from sqlalchemy import text
from app.core.database import async_session

EXECUTE = len(sys.argv) > 1 and sys.argv[1] == "EXECUTE"
BUCKET = "rigacap-prod-price-data-149218244179"
ARCHIVE_KEY = f"archive/pre-t30v-reset-{date.today().isoformat()}.json"

T30V_PARAMS = {
    # t30v: validated 21y continuous 8.3%/0.73/19.3 (fixed bench), Tier-2
    # held-out window-mean 15.6%/1.00. Parity with the research bench config.
    "max_positions": 20,
    "position_size_pct": 4.5,
    "trailing_stop_pct": 30.0,
    "vol_weight": 1.0,
    "baseline_trail_pct": 30.0,
    "dd_tighten_threshold_pct": 0.0,   # t30v has NO dd-tighten
    "dd_tighten_stop_pct": 8.0,
    "dwap_threshold_pct": 5.0,
    "near_50d_high_pct": 3.0,
    "min_price": 15.0,
    "min_volume": 500000,
    "market_filter_enabled": True,
    "short_momentum_days": 5,
    "long_momentum_days": 60,
    "short_mom_weight": 0.3,
    "long_mom_weight": 0.2,
    "volatility_penalty": 0.15,
    "volume_spike_mult": 1.3,
}

ADAPTIVE_EFFECTIVE = {
    # what signals.py serves as regime_adjustments.effective -> live trail etc.
    "trailing_stop_pct": 30.0,
    "near_50d_high_pct": 3.0,
    "max_positions": 20,
    "position_size_pct": 4.5,
    "vol_weight": 1.0,
    "exit_type": "trailing_stop",
    "market_filter_enabled": True,
    "min_price": 15.0,
    "min_volume": 500000,
}


async def main():
    mode = "EXECUTE" if EXECUTE else "DRY RUN"
    print(f"=== t30v CUTOVER — {mode} ===")
    async with async_session() as db:
        # ---- 1. ARCHIVE
        archive = {"archived_at": datetime.utcnow().isoformat(), "tables": {}}
        for tbl in ("model_positions", "model_portfolio_state", "strategy_adaptive_params"):
            rows = (await db.execute(text(f"SELECT * FROM {tbl}"))).mappings().all()
            archive["tables"][tbl] = [
                {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
                for r in rows
            ]
            print(f"archive: {tbl} -> {len(rows)} rows")
        s6 = (await db.execute(text("SELECT * FROM strategy_definitions WHERE id=6"))).mappings().first()
        archive["tables"]["strategy_definitions_row6"] = {
            k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(s6).items()
        }
        amd = [r for r in archive["tables"]["model_positions"]
               if r.get("symbol") == "AMD" and (r.get("pnl_pct") or 0) > 50]
        if amd:
            print(f"o7 AMD memorial: {amd[0].get('pnl_pct')}% ({amd[0].get('entry_date')} -> {amd[0].get('exit_date')})")
        if EXECUTE:
            boto3.Session(profile_name="rigacap", region_name="us-east-1").client("s3").put_object(
                Bucket=BUCKET, Key=ARCHIVE_KEY, Body=json.dumps(archive, default=str).encode())
            print(f"ARCHIVED -> s3://{BUCKET}/{ARCHIVE_KEY}")

        # ---- 2. RESET
        n_pos = (await db.execute(text("SELECT count(*) FROM model_positions"))).scalar()
        print(f"reset: DELETE {n_pos} model_positions rows; reset state rows to $100k")
        if EXECUTE:
            await db.execute(text("DELETE FROM model_positions"))
            await db.execute(text(
                "UPDATE model_portfolio_state SET starting_capital=100000, current_cash=100000, "
                "total_trades=0, winning_trades=0, total_pnl=0, updated_at=now()"))

        # ---- 3. FLIP
        print(f"flip: strategy 6 parameters -> t30v {json.dumps(T30V_PARAMS)[:120]}...")
        print(f"flip: INSERT strategy_adaptive_params (source=t30v_cutover) -> {json.dumps(ADAPTIVE_EFFECTIVE)[:120]}...")
        if EXECUTE:
            await db.execute(
                text("UPDATE strategy_definitions SET parameters=:p WHERE id=6"),
                {"p": json.dumps(T30V_PARAMS)})
            await db.execute(
                text("INSERT INTO strategy_adaptive_params (effective_date, source, params_json) "
                     "VALUES (:d, 't30v_cutover', :p)"),
                {"d": date.today(), "p": json.dumps(ADAPTIVE_EFFECTIVE)})
            await db.commit()
            print("DB COMMITTED")

    # ---- 4. CB state clear
    s3 = boto3.Session(profile_name="rigacap", region_name="us-east-1").client("s3")
    cb_keys = s3.list_objects_v2(Bucket=BUCKET, Prefix="cb-state/").get("Contents", [])
    for o in cb_keys:
        print(f"cb-state: {'DELETE' if EXECUTE else 'would delete'} {o['Key']}")
        if EXECUTE:
            s3.delete_object(Bucket=BUCKET, Key=o["Key"])

    # ---- 5. VERIFY
    if EXECUTE:
        async with async_session() as db:
            n = (await db.execute(text("SELECT count(*) FROM model_positions"))).scalar()
            st = (await db.execute(text("SELECT portfolio_type, current_cash, total_trades FROM model_portfolio_state"))).fetchall()
            p6 = (await db.execute(text("SELECT parameters FROM strategy_definitions WHERE id=6"))).scalar()
            ap = (await db.execute(text("SELECT effective_date, source FROM strategy_adaptive_params ORDER BY effective_date DESC LIMIT 1"))).first()
            p6d = p6 if isinstance(p6, dict) else json.loads(p6)
            print(f"VERIFY: positions={n} (want 0)")
            print(f"VERIFY: state={st}")
            print(f"VERIFY: s6 max_pos={p6d['max_positions']} size={p6d['position_size_pct']} trail={p6d['trailing_stop_pct']} volw={p6d['vol_weight']}")
            print(f"VERIFY: latest adaptive row = {ap}")
    print(f"=== {mode} COMPLETE ===")

asyncio.run(main())
