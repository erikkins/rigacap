"""Circuit Breaker / Cascade Guard production state.

Mirrors the WF backtester's circuit-breaker logic in production so subscribers
get the same protection the published WF numbers reflect (the WITH-CB variant).
The b-full validation showed CB adds ~3.7 pp ann to total return; without it,
production was leaving that uplift on the table.

Trigger semantics (matches CustomBacktester):
  - Threshold: N trailing-stop fires on the SAME DAY (not consecutive across days).
  - Default: 3 stops same day → pause new entries for 10 days.
  - "Longer-pause-wins": new requests only extend pause if the new expiry is
    further out than the current one. Shadowed events still get logged for
    telemetry.

Storage: S3 JSON, one file per portfolio at
  s3://<PRICE_DATA_BUCKET>/cb-state/<portfolio_type>.json

State schema:
  {
    "pause_until":      "2026-05-13",       # ISO date or null
    "pause_source":     "circuit_breaker",  # or "regime_exit", "manual", null
    "last_triggered_at": "2026-05-03T20:30:00Z",
    "events":           [...]               # last 50 events for post-hoc analysis
  }

Feature flag: CIRCUIT_BREAKER_ENABLED env var (default "false" for safe deploy).
When unset/false, all functions are no-ops — production behavior unchanged.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# ---- Defaults (mirror CustomBacktester defaults) -------------------------
DEFAULT_THRESHOLD_STOPS = 3       # circuit_breaker_stops
DEFAULT_PAUSE_DAYS = 10           # circuit_breaker_pause_days
MAX_EVENT_HISTORY = 50            # how many events we keep in state file


def is_enabled() -> bool:
    """CB feature flag — default OFF for safe deploys."""
    return os.environ.get("CIRCUIT_BREAKER_ENABLED", "false").lower() == "true"


def threshold_stops() -> int:
    return int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD_STOPS", DEFAULT_THRESHOLD_STOPS))


def pause_days() -> int:
    return int(os.environ.get("CIRCUIT_BREAKER_PAUSE_DAYS", DEFAULT_PAUSE_DAYS))


# ---- S3 backing store ----------------------------------------------------

_S3_BUCKET = os.environ.get("PRICE_DATA_BUCKET")
_IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _state_key(portfolio_type: str) -> str:
    return f"cb-state/{portfolio_type}.json"


def _get_s3():
    import boto3
    return boto3.client("s3")


def _read_state_file(portfolio_type: str) -> Dict:
    """Load CB state from S3. Returns empty dict if missing."""
    if not (_IS_LAMBDA and _S3_BUCKET):
        return {}
    try:
        s3 = _get_s3()
        obj = s3.get_object(Bucket=_S3_BUCKET, Key=_state_key(portfolio_type))
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey if hasattr(_get_s3(), "exceptions") else Exception:
        return {}
    except Exception as e:
        logger.warning(f"CB state read failed for {portfolio_type}: {e}")
        return {}


def _write_state_file(portfolio_type: str, state: Dict) -> None:
    if not (_IS_LAMBDA and _S3_BUCKET):
        return
    try:
        s3 = _get_s3()
        s3.put_object(
            Bucket=_S3_BUCKET,
            Key=_state_key(portfolio_type),
            Body=json.dumps(state, default=str).encode(),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error(f"CB state write FAILED for {portfolio_type}: {e}")


# ---- Public API ----------------------------------------------------------

def get_state(portfolio_type: str) -> Dict:
    """Public read — caller can inspect pause_until / events for telemetry."""
    return _read_state_file(portfolio_type)


def is_paused(portfolio_type: str, today: Optional[date] = None) -> bool:
    """Check if a portfolio is currently in CB pause.

    Returns False unconditionally when feature flag is disabled — keeps
    production behavior unchanged until explicitly flipped on.
    """
    if not is_enabled():
        return False
    today = today or date.today()
    state = _read_state_file(portfolio_type)
    pu = state.get("pause_until")
    if not pu:
        return False
    try:
        pause_until = date.fromisoformat(pu) if isinstance(pu, str) else pu
    except Exception:
        return False
    return today <= pause_until


def request_pause(
    portfolio_type: str,
    source: str,
    days: int,
    today: Optional[date] = None,
    context: Optional[Dict] = None,
) -> Dict:
    """Atomic state update with longer-pause-wins semantics.

    Mirrors CustomBacktester._request_pause. Always logs the event (even if
    shadowed by a longer existing pause) for post-hoc analysis.

    Returns the resulting event record.
    """
    today = today or date.today()
    new_until = today + timedelta(days=days)
    state = _read_state_file(portfolio_type)

    cur_until_str = state.get("pause_until")
    cur_until = (
        date.fromisoformat(cur_until_str) if isinstance(cur_until_str, str)
        else cur_until_str if isinstance(cur_until_str, date)
        else None
    )

    currently_paused = cur_until is not None and today <= cur_until
    extends = cur_until is None or new_until > cur_until

    event = {
        "trigger_date": today.isoformat(),
        "source": source,
        "days": days,
        "until_date": new_until.isoformat(),
        "extended_active_pause": currently_paused and extends,
        "shadowed_by_longer_pause": not extends,
        "prior_until_date": cur_until.isoformat() if cur_until else None,
        "prior_source": state.get("pause_source"),
        "context": context or {},
    }

    events = state.get("events", [])
    events.append(event)
    if len(events) > MAX_EVENT_HISTORY:
        events = events[-MAX_EVENT_HISTORY:]

    if extends:
        state["pause_until"] = new_until.isoformat()
        state["pause_source"] = source
        state["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
    state["events"] = events
    _write_state_file(portfolio_type, state)

    return event


def record_eod_trailing_stops(
    portfolio_type: str,
    today: date,
    stopped_symbols: List[str],
) -> Optional[Dict]:
    """Called by daily scan after EOD exits processed.

    Counts today's trailing-stop closures and triggers CB pause if the count
    meets the threshold. Returns the event dict if a pause was triggered,
    otherwise None.

    No-op when feature flag is off.
    """
    if not is_enabled():
        return None
    count = len(stopped_symbols)
    threshold = threshold_stops()
    if count < threshold:
        return None
    # Don't re-trigger while already paused
    if is_paused(portfolio_type, today):
        logger.info(
            f"CB threshold hit ({count}>={threshold}) for {portfolio_type} "
            f"but already in pause — no new trigger."
        )
        return None
    return request_pause(
        portfolio_type=portfolio_type,
        source="circuit_breaker",
        days=pause_days(),
        today=today,
        context={
            "stops_today": count,
            "threshold": threshold,
            "stopped_symbols": stopped_symbols,
        },
    )
