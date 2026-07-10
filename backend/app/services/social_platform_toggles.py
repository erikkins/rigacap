"""Per-platform posting on/off toggles — admin-controlled, no deploy needed.

Backed by a single small S3 JSON object so both Lambdas and every publish path
share one source of truth. Default: every platform ENABLED (backward-compatible —
nothing changes until an admin flips one off in the Social tab). Added Jul 2026
after Meta flagged the IG/FB account: lets us pause a platform instantly instead
of blanking API credentials.
"""
import json
import logging
import time

logger = logging.getLogger(__name__)

PLATFORMS = ("twitter", "instagram", "threads", "tiktok")
_S3_KEY = "social/platform_toggles.json"
_cache = {"data": None, "ts": 0.0}
_TTL = 30.0  # seconds — short so an admin flip takes effect on the next scan


def _s3():
    import boto3
    return boto3.client("s3", region_name="us-east-1")


def _bucket():
    from app.services.data_export import S3_BUCKET
    return S3_BUCKET


def get_platform_toggles(force: bool = False) -> dict:
    """Return {platform: bool}. Missing config or read error -> all enabled
    (fail-open: never let a transient S3 issue silently kill a platform)."""
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["ts"] < _TTL:
        return dict(_cache["data"])
    state = {p: True for p in PLATFORMS}
    try:
        obj = _s3().get_object(Bucket=_bucket(), Key=_S3_KEY)
        saved = json.loads(obj["Body"].read())
        for p in PLATFORMS:
            if p in saved:
                state[p] = bool(saved[p])
    except Exception as e:
        logger.debug("platform_toggles read fell back to all-enabled: %s", e)
    _cache["data"] = state
    _cache["ts"] = now
    return dict(state)


def is_platform_enabled(platform: str) -> bool:
    return get_platform_toggles().get(platform, True)


def set_platform_toggles(updates: dict) -> dict:
    """Merge {platform: bool} updates, persist to S3, return the full new state."""
    state = get_platform_toggles(force=True)
    for p, v in (updates or {}).items():
        if p in PLATFORMS:
            state[p] = bool(v)
    _s3().put_object(
        Bucket=_bucket(), Key=_S3_KEY,
        Body=json.dumps(state).encode(), ContentType="application/json",
    )
    _cache["data"] = dict(state)
    _cache["ts"] = time.time()
    logger.info("platform_toggles updated -> %s", state)
    return dict(state)
