"""CloudFront origin verification middleware.

Closes the direct-execute-api WAF bypass: every legitimate request reaches
us via CloudFront, which injects a shared secret in the `X-Origin-Verify`
header. Requests that hit the API Gateway URL directly (bypassing
CloudFront and therefore WAF) won't carry the header and get rejected.

The secret comes from the `CLOUDFRONT_ORIGIN_SECRET` env var, set in the
API Lambda env via Terraform alongside the matching CloudFront
`custom_header`. If the env var is empty/unset, the middleware is a
no-op — supports gradual rollout and local dev without ceremony.

Exemptions:
- OPTIONS preflight (CORS) — browsers don't carry custom headers on
  preflight, must be allowed unconditionally.
- /health — used by uptime monitoring that may hit the API directly.
"""
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class OriginVerifyMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health"}

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS" or request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        expected = os.environ.get("CLOUDFRONT_ORIGIN_SECRET", "")
        if not expected:
            # Guard disabled — env var missing or empty
            return await call_next(request)

        supplied = request.headers.get("X-Origin-Verify", "")
        if not supplied or not hmac.compare_digest(expected, supplied):
            return PlainTextResponse("Forbidden", status_code=403)

        return await call_next(request)
