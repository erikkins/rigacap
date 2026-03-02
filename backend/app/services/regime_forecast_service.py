"""
Regime Forecast Service — Daily regime forecast storage, accuracy tracking, and heatmap data.

Persists daily snapshots from MarketRegimeService.predict_transitions() for
historical analysis, forecast accuracy measurement, and visualization.
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import RegimeForecastSnapshot, RegimeHistory

logger = logging.getLogger(__name__)


class RegimeForecastService:
    """Persist and query regime forecast snapshots."""

    async def take_snapshot(self, db: AsyncSession) -> dict:
        """
        Call predict_transitions() and store today's forecast.
        Called daily after scan completes.
        """
        from app.services.market_regime import market_regime_service
        from app.services.scanner import scanner_service

        spy_df = scanner_service.data_cache.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data not in cache"}

        vix_df = scanner_service.data_cache.get("^VIX")
        if vix_df is None:
            vix_df = scanner_service.data_cache.get("VIX")

        try:
            forecast = market_regime_service.predict_transitions(
                spy_df, scanner_service.data_cache, vix_df
            )
        except Exception as e:
            logger.error(f"Regime forecast failed: {e}")
            return {"error": str(e)}

        today_dt = datetime.combine(date.today(), datetime.min.time())

        # Get SPY/VIX close
        spy_close = float(spy_df["close"].iloc[-1]) if not spy_df.empty else None
        vix_close = None
        if vix_df is not None and not vix_df.empty:
            vix_close = float(vix_df["close"].iloc[-1])

        # Upsert
        existing = await db.execute(
            select(RegimeForecastSnapshot).where(
                RegimeForecastSnapshot.snapshot_date == today_dt
            )
        )
        snap = existing.scalar_one_or_none()

        forecast_dict = forecast.to_dict() if hasattr(forecast, "to_dict") else {}
        probabilities = forecast_dict.get("transition_probabilities", {})

        if snap:
            snap.current_regime = forecast_dict.get("current_regime", "unknown")
            snap.probabilities_json = json.dumps(probabilities)
            snap.outlook = forecast_dict.get("outlook")
            snap.recommended_action = forecast_dict.get("recommended_action")
            snap.risk_change = forecast_dict.get("risk_change")
            snap.spy_close = spy_close
            snap.vix_close = vix_close
        else:
            snap = RegimeForecastSnapshot(
                snapshot_date=today_dt,
                current_regime=forecast_dict.get("current_regime", "unknown"),
                probabilities_json=json.dumps(probabilities),
                outlook=forecast_dict.get("outlook"),
                recommended_action=forecast_dict.get("recommended_action"),
                risk_change=forecast_dict.get("risk_change"),
                spy_close=spy_close,
                vix_close=vix_close,
            )
            db.add(snap)

        await db.commit()
        logger.info(f"[REGIME-FORECAST] Snapshot taken: {forecast_dict.get('current_regime')}")
        return {
            "date": str(date.today()),
            "regime": forecast_dict.get("current_regime"),
            "outlook": forecast_dict.get("outlook"),
            "recommended_action": forecast_dict.get("recommended_action"),
        }

    async def get_forecast_history(
        self, db: AsyncSession, days: int = 90
    ) -> List[dict]:
        """Return forecast snapshots ordered by date."""
        cutoff = datetime.combine(
            date.today() - timedelta(days=days), datetime.min.time()
        )
        result = await db.execute(
            select(RegimeForecastSnapshot)
            .where(RegimeForecastSnapshot.snapshot_date >= cutoff)
            .order_by(asc(RegimeForecastSnapshot.snapshot_date))
        )
        snapshots = result.scalars().all()

        return [
            {
                "date": s.snapshot_date.strftime("%Y-%m-%d") if s.snapshot_date else "",
                "regime": s.current_regime,
                "probabilities": json.loads(s.probabilities_json) if s.probabilities_json else {},
                "outlook": s.outlook,
                "recommended_action": s.recommended_action,
                "risk_change": s.risk_change,
                "spy_close": s.spy_close,
                "vix_close": s.vix_close,
            }
            for s in snapshots
        ]

    async def get_forecast_accuracy(
        self, db: AsyncSession, days: int = 90
    ) -> dict:
        """
        Compare each forecast's predicted regime vs the actual regime N days later.
        Returns accuracy % and a confusion matrix.
        """
        cutoff = datetime.combine(
            date.today() - timedelta(days=days), datetime.min.time()
        )
        result = await db.execute(
            select(RegimeForecastSnapshot)
            .where(RegimeForecastSnapshot.snapshot_date >= cutoff)
            .order_by(asc(RegimeForecastSnapshot.snapshot_date))
        )
        snapshots = list(result.scalars().all())

        if len(snapshots) < 2:
            return {"accuracy_pct": None, "total_forecasts": len(snapshots), "note": "Not enough data"}

        # Build date→regime lookup
        date_regime = {
            s.snapshot_date.strftime("%Y-%m-%d"): s.current_regime
            for s in snapshots
        }

        correct = 0
        total = 0
        confusion = {}  # {predicted: {actual: count}}

        for snap in snapshots:
            # Get the regime that had the highest probability
            probs = json.loads(snap.probabilities_json) if snap.probabilities_json else {}
            if not probs:
                continue

            predicted_regime = max(probs, key=probs.get)

            # Check what the actual regime was the next day
            next_date = snap.snapshot_date + timedelta(days=1)
            actual_regime = date_regime.get(next_date.strftime("%Y-%m-%d"))
            if not actual_regime:
                # Try +2 days (weekend/holiday)
                next_date = snap.snapshot_date + timedelta(days=2)
                actual_regime = date_regime.get(next_date.strftime("%Y-%m-%d"))
            if not actual_regime:
                next_date = snap.snapshot_date + timedelta(days=3)
                actual_regime = date_regime.get(next_date.strftime("%Y-%m-%d"))
            if not actual_regime:
                continue

            total += 1
            if predicted_regime == actual_regime:
                correct += 1

            if predicted_regime not in confusion:
                confusion[predicted_regime] = {}
            confusion[predicted_regime][actual_regime] = confusion[predicted_regime].get(actual_regime, 0) + 1

        accuracy = round((correct / total * 100), 1) if total > 0 else None

        return {
            "accuracy_pct": accuracy,
            "correct": correct,
            "total_forecasts": total,
            "confusion_matrix": confusion,
        }

    async def get_transition_heatmap(
        self, db: AsyncSession, days: int = 60
    ) -> List[dict]:
        """Return daily probability arrays for heatmap visualization."""
        cutoff = datetime.combine(
            date.today() - timedelta(days=days), datetime.min.time()
        )
        result = await db.execute(
            select(RegimeForecastSnapshot)
            .where(RegimeForecastSnapshot.snapshot_date >= cutoff)
            .order_by(asc(RegimeForecastSnapshot.snapshot_date))
        )
        snapshots = result.scalars().all()

        return [
            {
                "date": s.snapshot_date.strftime("%Y-%m-%d") if s.snapshot_date else "",
                "regime": s.current_regime,
                "probabilities": json.loads(s.probabilities_json) if s.probabilities_json else {},
            }
            for s in snapshots
        ]


    async def backfill_regime_history(self, db: AsyncSession) -> dict:
        """
        One-time backfill: compute weekly regime classifications from cached SPY/VIX data
        and bulk insert into regime_history table.
        """
        from app.services.market_regime import market_regime_service, REGIME_DEFINITIONS
        from app.services.scanner import scanner_service

        spy_df = scanner_service.data_cache.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data not in cache"}

        vix_df = scanner_service.data_cache.get("^VIX")
        if vix_df is None:
            vix_df = scanner_service.data_cache.get("VIX")

        history = market_regime_service.get_regime_history(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df,
            sample_frequency='weekly'
        )

        inserted = 0
        skipped = 0

        for regime in history:
            regime_dict = regime.to_dict()
            week_dt = datetime.strptime(regime.date, "%Y-%m-%d") if isinstance(regime.date, str) else regime.date

            existing = await db.execute(
                select(RegimeHistory).where(RegimeHistory.week_date == week_dt)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            regime_def = REGIME_DEFINITIONS.get(regime.regime_type, {})
            db.add(RegimeHistory(
                week_date=week_dt,
                regime_type=regime.regime_type.value,
                regime_name=regime.regime_name,
                confidence=regime.confidence,
                risk_level=regime_def.get("risk_level"),
                color=regime_dict.get("color", "#6B7280"),
                bg_color=regime_dict.get("bg_color", "rgba(107, 114, 128, 0.1)"),
            ))
            inserted += 1

        await db.commit()
        logger.info(f"[REGIME-HISTORY] Backfill complete: {inserted} inserted, {skipped} skipped")
        return {"status": "success", "inserted": inserted, "skipped": skipped, "total_history": len(history)}

    async def update_regime_history(self, db: AsyncSession) -> dict:
        """
        Incremental update: compute regimes from the latest stored week_date forward.
        Called daily after scan completes. Skips if table is empty (needs backfill first).
        """
        from app.services.market_regime import market_regime_service, REGIME_DEFINITIONS
        from app.services.scanner import scanner_service

        spy_df = scanner_service.data_cache.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data not in cache"}

        vix_df = scanner_service.data_cache.get("^VIX")
        if vix_df is None:
            vix_df = scanner_service.data_cache.get("VIX")

        # Find latest stored week_date
        result = await db.execute(
            select(RegimeHistory.week_date).order_by(desc(RegimeHistory.week_date)).limit(1)
        )
        latest_row = result.scalar_one_or_none()

        if not latest_row:
            # Table is empty — skip incremental, needs backfill first
            return {"status": "skipped", "reason": "no existing data, run backfill first"}

        # Start from the latest stored date (will be skipped as duplicate)
        start_date = latest_row

        history = market_regime_service.get_regime_history(
            spy_df=spy_df,
            universe_dfs=scanner_service.data_cache,
            vix_df=vix_df,
            start_date=start_date,
            sample_frequency='weekly'
        )

        inserted = 0
        for regime in history:
            regime_dict = regime.to_dict()
            week_dt = datetime.strptime(regime.date, "%Y-%m-%d") if isinstance(regime.date, str) else regime.date

            existing = await db.execute(
                select(RegimeHistory).where(RegimeHistory.week_date == week_dt)
            )
            if existing.scalar_one_or_none():
                continue

            regime_def = REGIME_DEFINITIONS.get(regime.regime_type, {})
            db.add(RegimeHistory(
                week_date=week_dt,
                regime_type=regime.regime_type.value,
                regime_name=regime.regime_name,
                confidence=regime.confidence,
                risk_level=regime_def.get("risk_level"),
                color=regime_dict.get("color", "#6B7280"),
                bg_color=regime_dict.get("bg_color", "rgba(107, 114, 128, 0.1)"),
            ))
            inserted += 1

        await db.commit()
        if inserted > 0:
            logger.info(f"[REGIME-HISTORY] Incremental update: {inserted} new rows")
        return {"status": "success", "inserted": inserted}

    async def get_regime_periods_from_db(
        self, db: AsyncSession, start_date: str = None, end_date: str = None
    ) -> Optional[dict]:
        """
        Query regime_history table and group consecutive same-regime rows into periods.
        Returns None if no data in DB (caller should fall back to on-the-fly).
        """
        query = select(RegimeHistory).order_by(asc(RegimeHistory.week_date))

        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(RegimeHistory.week_date >= start_dt)
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            query = query.where(RegimeHistory.week_date <= end_dt)

        result = await db.execute(query)
        rows = result.scalars().all()

        if not rows:
            return None

        # Group consecutive same-regime rows into periods
        periods = []
        current = {
            "start_date": rows[0].week_date.strftime("%Y-%m-%d"),
            "regime_type": rows[0].regime_type,
            "regime_name": rows[0].regime_name,
            "color": rows[0].color,
            "bg_color": rows[0].bg_color,
        }

        for row in rows[1:]:
            if row.regime_type != current["regime_type"]:
                current["end_date"] = row.week_date.strftime("%Y-%m-%d")
                periods.append(current)
                current = {
                    "start_date": row.week_date.strftime("%Y-%m-%d"),
                    "regime_type": row.regime_type,
                    "regime_name": row.regime_name,
                    "color": row.color,
                    "bg_color": row.bg_color,
                }
            else:
                current["end_date"] = row.week_date.strftime("%Y-%m-%d")

        current["end_date"] = rows[-1].week_date.strftime("%Y-%m-%d")
        periods.append(current)

        # Build regime changes list
        changes = []
        for i in range(1, len(rows)):
            if rows[i].regime_type != rows[i - 1].regime_type:
                changes.append({
                    "date": rows[i].week_date.strftime("%Y-%m-%d"),
                    "from_regime": rows[i - 1].regime_type,
                    "from_name": rows[i - 1].regime_name,
                    "to_regime": rows[i].regime_type,
                    "to_name": rows[i].regime_name,
                    "from_color": rows[i - 1].color,
                    "to_color": rows[i].color,
                })

        return {
            "start_date": rows[0].week_date.strftime("%Y-%m-%d"),
            "end_date": rows[-1].week_date.strftime("%Y-%m-%d"),
            "periods": periods,
            "regime_changes": changes,
            "total_changes": len(changes),
        }


# Singleton
regime_forecast_service = RegimeForecastService()
