"""SnapTrade brokerage-connection client — read-only holdings for the Mirror.

Manual HMAC-SHA256 request signing (verified live against api.snaptrade.com — no SDK
dependency). Reads SNAPTRADE_CLIENT_ID / SNAPTRADE_CONSUMER_KEY from env; if unset,
is_configured() is False and endpoints return a clean "not configured" response.

Flow (all paths verified working):
  registerUser  POST /api/v1/snapTrade/registerUser   {userId} -> {userId, userSecret}
  login         POST /api/v1/snapTrade/login          {customRedirect} -> {redirectURI}
  accounts      GET  /api/v1/accounts                 -> [account, ...]   (the old /holdings is 410)
  positions     GET  /api/v1/accounts/{id}/positions  -> [position, ...]

We use OUR user's UUID as the SnapTrade userId (deterministic, no extra mapping); only
the returned userSecret is persisted (snaptrade_users table).
"""
import os
import time
import json
import hmac
import hashlib
import base64
import logging
from urllib.parse import urlencode
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HOST = "https://api.snaptrade.com"


def _creds(env: str = "prod"):
    """Resolve (clientId, consumerKey) for a SnapTrade environment. 'test' = the demo key
    (5-connection cap — used for admin demos); 'prod' = the production key (real subscribers).
    Each SnapTrade userSecret is issued by ONE key, so a connection's env is fixed at register
    time (snaptrade_users.st_env) and every later call must use the same env. Test falls back to
    the unprefixed SNAPTRADE_CLIENT_ID/CONSUMER_KEY so the existing (test) env keeps working
    without renaming; prod reads the dedicated SNAPTRADE_PROD_* pair."""
    if (env or "prod").lower() == "test":
        cid = os.environ.get("SNAPTRADE_TEST_CLIENT_ID") or os.environ.get("SNAPTRADE_CLIENT_ID")
        key = os.environ.get("SNAPTRADE_TEST_CONSUMER_KEY") or os.environ.get("SNAPTRADE_CONSUMER_KEY")
    else:
        cid = os.environ.get("SNAPTRADE_PROD_CLIENT_ID")
        key = os.environ.get("SNAPTRADE_PROD_CONSUMER_KEY")
    return cid, key


def is_configured(env: str = "prod") -> bool:
    cid, key = _creds(env)
    return bool(cid and key)


# --- At-rest encryption for the per-user userSecret (KMS-backed) -----------------------------
# The userSecret is a credential. When SNAPTRADE_KMS_KEY_ID is set (production), it's encrypted
# with KMS before it touches Postgres; without it (dev/test) we store plaintext. The "kms:"
# prefix records the scheme, so decrypt is unambiguous and backward-compatible with existing
# plaintext rows (they simply pass through). To activate: create a KMS key, grant the Lambda
# role kms:Encrypt/Decrypt on it, and set SNAPTRADE_KMS_KEY_ID.

_ENC_PREFIX = "kms:"


def _kms_client():
    import boto3
    return boto3.client("kms", region_name="us-east-1")


def encrypt_secret(plaintext: str) -> str:
    key_id = os.environ.get("SNAPTRADE_KMS_KEY_ID")
    if not key_id or not plaintext:
        return plaintext                       # dev/test: inert pass-through
    blob = _kms_client().encrypt(KeyId=key_id, Plaintext=plaintext.encode())["CiphertextBlob"]
    return _ENC_PREFIX + base64.b64encode(blob).decode()


def decrypt_secret(stored: str) -> str:
    if not stored or not stored.startswith(_ENC_PREFIX):
        return stored                          # legacy/plaintext row
    blob = base64.b64decode(stored[len(_ENC_PREFIX):])
    return _kms_client().decrypt(CiphertextBlob=blob)["Plaintext"].decode()


def _sign(consumer_key: str, path: str, query: str, body) -> str:
    # Signature covers {content, path, query} in that key order, compact-serialized.
    msg = json.dumps({"content": body, "path": path, "query": query}, separators=(",", ":"))
    return base64.b64encode(hmac.new(consumer_key.encode(), msg.encode(), hashlib.sha256).digest()).decode()


async def _call(method: str, path: str, env: str = "prod", query_extra: Optional[dict] = None, body=None):
    client_id, consumer_key = _creds(env)
    if not (client_id and consumer_key):
        raise RuntimeError(f"snaptrade env '{env}' is not configured")
    q = {"clientId": client_id, "timestamp": str(int(time.time()))}
    if query_extra:
        q.update(query_extra)
    qs = urlencode(sorted(q.items()))
    headers = {"Signature": _sign(consumer_key, path, qs, body), "Content-Type": "application/json"}
    url = f"{HOST}{path}?{qs}"
    data = json.dumps(body, separators=(",", ":")) if body is not None else None
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.request(method, url, content=data, headers=headers)
    if r.status_code >= 400:
        # SECURITY: never let httpx's own error propagate — its message includes the full
        # request URL, whose query string carries userSecret. Log status + path only, and
        # raise a clean error so callers can't accidentally log the credential.
        logger.warning(f"snaptrade {method} {path} -> {r.status_code}: {r.text[:200]}")
        raise RuntimeError(f"snaptrade {method} {path} -> {r.status_code}")
    return r.json() if r.content else None


async def register_user(user_id: str, env: str = "prod") -> str:
    """Register (idempotent-ish) a SnapTrade user; returns the userSecret to persist."""
    res = await _call("POST", "/api/v1/snapTrade/registerUser", env, body={"userId": user_id})
    return (res or {}).get("userSecret")


async def login_redirect_uri(user_id: str, user_secret: str, custom_redirect: str, env: str = "prod") -> Optional[str]:
    """Connection-portal URL. `custom_redirect` = where the user returns after connecting."""
    res = await _call(
        "POST", "/api/v1/snapTrade/login", env,
        query_extra={"userId": user_id, "userSecret": user_secret},
        body={"customRedirect": custom_redirect},
    )
    return (res or {}).get("redirectURI")


async def list_accounts(user_id: str, user_secret: str, env: str = "prod") -> list:
    res = await _call("GET", "/api/v1/accounts", env, query_extra={"userId": user_id, "userSecret": user_secret})
    return res or []


async def account_positions(user_id: str, user_secret: str, account_id: str, env: str = "prod") -> list:
    # The legacy /positions and /holdings are 410 for accounts created after 2026-05-11.
    # Current endpoint = /positions/all (equity + ETF + options + …); positions under "results".
    res = await _call(
        "GET", f"/api/v1/accounts/{account_id}/positions/all", env,
        query_extra={"userId": user_id, "userSecret": user_secret},
    )
    if isinstance(res, dict):
        return res.get("results") or []
    return res or []


def _extract_symbol(pos: dict) -> Optional[str]:
    """positions/all shape (verified live): {"instrument": {"kind","symbol","raw_symbol",…},
    "units", "price", …}. The ticker is instrument.raw_symbol (fallback instrument.symbol)."""
    inst = pos.get("instrument") or {}
    sym = inst.get("raw_symbol") or inst.get("symbol")
    return sym.upper() if isinstance(sym, str) and sym else None


async def remove_authorization(user_id: str, user_secret: str, authorization_id: str, env: str = "prod") -> None:
    """Disconnect a brokerage CONNECTION (removes all its accounts). The legacy
    DELETE /authorizations/{id} is 410; the current path is DELETE /connection/{id}
    (connectionId == the authorization id). Async: 200 = queued for deletion."""
    await _call(
        "DELETE", f"/api/v1/connection/{authorization_id}", env,
        query_extra={"userId": user_id, "userSecret": user_secret},
    )


async def delete_user(user_id: str, env: str = "prod") -> None:
    """Deregister a SnapTrade user entirely — removes the user AND all their brokerage
    connections. THIS is what stops SnapTrade's per-connected-user daily billing; removing
    individual authorizations is not guaranteed to. Authenticated at the client level
    (clientId + signature), so no userSecret is required. Idempotent from our side: a 404
    (already gone) is swallowed so cleanup/reconcile can run repeatedly without erroring."""
    try:
        await _call("DELETE", "/api/v1/snapTrade/deleteUser", env, query_extra={"userId": user_id})
    except RuntimeError as e:
        if "404" in str(e):
            logger.info(f"snaptrade deleteUser {user_id}: already absent (404) — treating as done")
            return
        raise


async def list_users(env: str = "prod") -> list:
    """All SnapTrade userIds registered under this env's key. GET /snapTrade/listUsers → [userId,...].
    Diagnostic — lets us see the true server-side state (which env a user actually lives under)."""
    res = await _call("GET", "/api/v1/snapTrade/listUsers", env)
    return res or []


async def all_holdings(user_id: str, user_secret: str, env: str = "prod") -> dict:
    """Union of position tickers across EVERY connected account (multi-brokerage), plus the
    connected brokerages GROUPED BY CONNECTION (authorization) — so two accounts at one
    broker show as one entry, and each carries the authorization_id used to disconnect it."""
    import asyncio
    accounts = await list_accounts(user_id, user_secret, env)
    brokers = {}       # authorization_id (or institution) -> {institution, authorization_id, accounts}
    account_ids = []
    for acct in accounts:
        aid = acct.get("id")
        auth = acct.get("brokerage_authorization")           # this API returns the auth id as a string
        auth_id = auth if isinstance(auth, str) else (auth or {}).get("id") if isinstance(auth, dict) else None
        inst = acct.get("institution_name") or "Brokerage"
        key = auth_id or inst
        b = brokers.setdefault(key, {"institution": inst, "authorization_id": auth_id, "accounts": []})
        # E-Trade obscures the real account number (opaque token), so the NAME is the reliable
        # human differentiator between two accounts at one broker.
        b["accounts"].append(acct.get("name") or "Account")
        if aid:
            account_ids.append(aid)
    # Fetch positions across accounts IN PARALLEL — each broker sync is ~1-2s; sequential stacks up.
    results = await asyncio.gather(
        *[account_positions(user_id, user_secret, aid, env) for aid in account_ids],
        return_exceptions=True,
    )
    symbols = set()
    for res in results:
        if isinstance(res, Exception):
            logger.warning(f"snaptrade positions failed: {res}")
            continue
        for p in res:
            sym = _extract_symbol(p)
            if sym:
                symbols.add(sym)
    return {"symbols": sorted(symbols), "sources": list(brokers.values()), "account_count": len(accounts)}
