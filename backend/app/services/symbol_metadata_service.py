"""
Symbol metadata + corporate-actions service.

Handles:
- Per-symbol identity tracking (Alpaca asset_id UUID → detect ticker reuse)
- Nightly corporate-actions poll (splits, dividends, spinoffs, mergers)
- Quarantine + audit-log writes

Called from the nightly data-hygiene Lambda handler. Idempotent — safe
to re-run.
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, and_, or_

from app.core.config import settings
from app.core.database import async_session, SymbolMetadata, SymbolMetadataEvent

logger = logging.getLogger(__name__)


class SymbolMetadataService:
    """Asset-ID integrity + corp-actions pipeline."""

    def _get_trading_client(self):
        """Alpaca TradingClient for asset metadata (separate from price data)."""
        from alpaca.trading.client import TradingClient
        return TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=False,
        )

    def _get_corp_actions_client(self):
        """Alpaca CorporateActionsClient for splits/dividends/etc."""
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        return CorporateActionsClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )

    # ─────────────────────────── Asset-ID integrity ───────────────────────────

    async def verify_asset_ids(
        self, symbols: List[str], record_events: bool = True
    ) -> Dict[str, Dict]:
        """
        For each symbol in `symbols`, compare the stored asset_id against
        Alpaca's current asset_id. Records SymbolMetadataEvent entries for
        any mismatches and returns a summary.

        BULK-FETCH (Apr 28 2026): single API call to Alpaca's get_all_assets()
        returns the full US equity universe (~10K assets), then per-symbol
        lookups happen against an in-memory hash map. Drops 4677-symbol
        verification from ~15 min (was timing out the 15-min Lambda) to
        ~2-3 sec. Replaces the prior per-symbol-with-thread-pool approach
        which never met its claimed 2-3 min throughput in production.

        Symbol normalization: Alpaca uses dots (BRK.B) where our pickle uses
        hyphens (BRK-B). The hash-map lookup converts hyphens→dots.

        Inactive list is queried as a fallback only when symbols aren't
        found in the active list — handles delisted-but-still-tracked names.

        Returns dict keyed by symbol: {
            "status": "ok" | "new" | "reused" | "missing_in_alpaca",
            "stored_asset_id": str | None,
            "current_asset_id": str | None,
        }
        """
        import asyncio as _asyncio
        from alpaca.trading.requests import GetAssetsRequest
        from alpaca.trading.enums import AssetClass, AssetStatus

        client = self._get_trading_client()
        loop = _asyncio.get_event_loop()

        def _to_alpaca(sym: str) -> str:
            """yfinance hyphens → Alpaca dots (BRK-B → BRK.B)."""
            return sym.replace('-', '.')

        # 1. Bulk fetch active US equities (one API call, ~10K rows, ~1-2s)
        try:
            active_req = GetAssetsRequest(
                asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE
            )
            active_assets = await loop.run_in_executor(
                None, client.get_all_assets, active_req
            )
        except Exception as e:
            logger.error(f"get_all_assets(active) failed: {e}")
            active_assets = []

        active_by_symbol: Dict[str, object] = {a.symbol: a for a in active_assets}
        # print() not logger.info() — Lambda CloudWatch swallows logger.info; print is "must-see"
        print(f"verify_asset_ids: fetched {len(active_by_symbol)} active assets")

        # 2. Find symbols missing from active list — fetch inactive only if any
        missing_in_active = [s for s in symbols if _to_alpaca(s) not in active_by_symbol]
        inactive_by_symbol: Dict[str, object] = {}
        if missing_in_active:
            try:
                inactive_req = GetAssetsRequest(
                    asset_class=AssetClass.US_EQUITY, status=AssetStatus.INACTIVE
                )
                inactive_assets = await loop.run_in_executor(
                    None, client.get_all_assets, inactive_req
                )
                inactive_by_symbol = {a.symbol: a for a in inactive_assets}
                print(
                    f"verify_asset_ids: fetched {len(inactive_by_symbol)} inactive assets "
                    f"(needed for {len(missing_in_active)} not-in-active symbols)"
                )
            except Exception as e:
                print(f"⚠️ get_all_assets(inactive) failed: {e}")

        # 3. Process all symbols against the in-memory maps
        summary: Dict[str, Dict] = {}

        async with async_session() as db:
            result = await db.execute(
                select(SymbolMetadata).where(SymbolMetadata.symbol.in_(symbols))
            )
            stored = {row.symbol: row for row in result.scalars().all()}

            for symbol in symbols:
                alpaca_sym = _to_alpaca(symbol)
                asset = active_by_symbol.get(alpaca_sym) or inactive_by_symbol.get(alpaca_sym)
                stored_meta = stored.get(symbol)

                if asset is None:
                    summary[symbol] = {
                        "status": "missing_in_alpaca",
                        "stored_asset_id": stored_meta.asset_id if stored_meta else None,
                        "current_asset_id": None,
                    }
                    if record_events:
                        db.add(SymbolMetadataEvent(
                            symbol=symbol,
                            event_type="missing_in_alpaca",
                            details_json=json.dumps({"reason": "not in active or inactive list"}),
                        ))
                    continue

                try:
                    current_id = str(asset.id) if asset.id else None
                except Exception as e:
                    summary[symbol] = {
                        "status": "missing_in_alpaca",
                        "stored_asset_id": stored_meta.asset_id if stored_meta else None,
                        "current_asset_id": None,
                        "error": str(e)[:200],
                    }
                    continue

                # No prior record — create one (first verification)
                if stored_meta is None:
                    db.add(SymbolMetadata(
                        symbol=symbol,
                        asset_id=current_id,
                        status="active",
                        last_verified_at=datetime.utcnow(),
                    ))
                    summary[symbol] = {
                        "status": "new",
                        "stored_asset_id": None,
                        "current_asset_id": current_id,
                    }
                    continue

                # Existing record — check for asset_id drift (ticker reuse!)
                if stored_meta.asset_id and stored_meta.asset_id != current_id:
                    summary[symbol] = {
                        "status": "reused",
                        "stored_asset_id": stored_meta.asset_id,
                        "current_asset_id": current_id,
                    }
                    if record_events:
                        db.add(SymbolMetadataEvent(
                            symbol=symbol,
                            event_type="asset_id_changed",
                            details_json=json.dumps({
                                "old_asset_id": stored_meta.asset_id,
                                "new_asset_id": current_id,
                            }),
                        ))
                    # Auto-quarantine for admin review
                    stored_meta.status = "quarantined"
                    stored_meta.quarantine_reason = "asset_id_changed"
                    stored_meta.quarantined_at = datetime.utcnow()
                    continue

                # Healthy: update asset_id (if unset) and last_verified_at
                if not stored_meta.asset_id:
                    stored_meta.asset_id = current_id
                stored_meta.last_verified_at = datetime.utcnow()
                summary[symbol] = {
                    "status": "ok",
                    "stored_asset_id": stored_meta.asset_id,
                    "current_asset_id": current_id,
                }

            await db.commit()

        return summary

    # ─────────────────────────── Corp-actions poll ───────────────────────────

    async def poll_corp_actions(
        self, since_hours: int = 36
    ) -> List[Dict]:
        """
        Query Alpaca's corporate-actions endpoint for events in the past
        N hours. Records each into SymbolMetadataEvent and returns a list
        of event dicts.

        Default window 36h covers a 24h nightly cadence with buffer.
        """
        from alpaca.data.requests import CorporateActionsRequest

        client = self._get_corp_actions_client()
        end = date.today()
        start = end - timedelta(days=max(2, since_hours // 24 + 1))

        try:
            req = CorporateActionsRequest(start=start, end=end)
            result = client.get_corporate_actions(req)
        except Exception as e:
            logger.error(f"corp-actions poll failed: {e}")
            return [{"error": str(e)[:300]}]

        events: List[Dict] = []
        raw_data = getattr(result, "data", {}) or {}

        async with async_session() as db:
            for action_type, actions in raw_data.items():
                for action in (actions or []):
                    # action is a pydantic model; extract fields generically
                    ad = getattr(action, "model_dump", lambda: dict(action))()
                    symbol = ad.get("symbol") or ad.get("target_symbol") or ad.get("initiating_symbol")
                    event_date_val = ad.get("ex_date") or ad.get("effective_date") or ad.get("process_date")
                    event = {
                        "symbol": symbol,
                        "event_type": str(action_type),
                        "event_date": event_date_val.isoformat() if hasattr(event_date_val, "isoformat") else event_date_val,
                        "details": ad,
                    }
                    events.append(event)
                    if symbol:
                        db.add(SymbolMetadataEvent(
                            symbol=symbol,
                            event_type=str(action_type),
                            event_date=event_date_val if hasattr(event_date_val, "year") else None,
                            details_json=json.dumps(ad, default=str)[:4000],
                        ))
            await db.commit()

        logger.info(f"corp-actions poll: {len(events)} events across {len(raw_data)} types")
        return events

    # ─────────────────────────── Admin utilities ───────────────────────────

    async def get_quarantined_symbols(self) -> List[Dict]:
        """Return all symbols currently in 'quarantined' status."""
        async with async_session() as db:
            result = await db.execute(
                select(SymbolMetadata).where(SymbolMetadata.status == "quarantined")
            )
            rows = result.scalars().all()
            return [{
                "symbol": r.symbol,
                "asset_id": r.asset_id,
                "reason": r.quarantine_reason,
                "quarantined_at": r.quarantined_at.isoformat() if r.quarantined_at else None,
            } for r in rows]

    async def get_excluded_symbols(self) -> List[str]:
        """List of symbols to exclude from signal generation (quarantined + inactive)."""
        async with async_session() as db:
            result = await db.execute(
                select(SymbolMetadata.symbol).where(
                    SymbolMetadata.status.in_(["quarantined", "inactive"])
                )
            )
            return [r[0] for r in result.all()]

    async def set_status(self, symbol: str, status: str, reason: Optional[str] = None) -> bool:
        """Manually set a symbol's status (admin override)."""
        assert status in {"active", "inactive", "quarantined"}
        async with async_session() as db:
            result = await db.execute(
                select(SymbolMetadata).where(SymbolMetadata.symbol == symbol)
            )
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.status = status
            if status == "quarantined":
                row.quarantine_reason = reason or "manual"
                row.quarantined_at = datetime.utcnow()
            else:
                row.quarantine_reason = None
                row.quarantined_at = None
            db.add(SymbolMetadataEvent(
                symbol=symbol,
                event_type="manual_override",
                details_json=json.dumps({"new_status": status, "reason": reason}),
            ))
            await db.commit()
            return True


symbol_metadata_service = SymbolMetadataService()
