"""Two-Factor Authentication (TOTP) API endpoints."""

import json
import secrets
from datetime import datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, User, Subscription
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_challenge_token,
    create_2fa_trust_token,
    decode_token,
    get_admin_user,
    get_client_ip,
    get_password_hash,
    verify_password,
    rate_limiter,
)

router = APIRouter()

# Characters excluding ambiguous ones (O/0/I/1/L)
BACKUP_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _generate_backup_codes(count: int = 10) -> list[str]:
    """Generate plaintext backup codes."""
    return ["".join(secrets.choice(BACKUP_CODE_CHARS) for _ in range(8)) for _ in range(count)]


def _hash_backup_codes(codes: list[str]) -> str:
    """Hash backup codes and return JSON array of hashes."""
    return json.dumps([get_password_hash(code) for code in codes])


def _verify_backup_code(code: str, hashed_codes_json: str) -> tuple[bool, str | None]:
    """Verify a backup code against stored hashes. Returns (valid, updated_json)."""
    hashes = json.loads(hashed_codes_json)
    for i, h in enumerate(hashes):
        if verify_password(code.upper().strip(), h):
            # Consume the code
            hashes.pop(i)
            return True, json.dumps(hashes)
    return False, None


def _count_backup_codes(hashed_codes_json: str | None) -> int:
    """Count remaining backup codes."""
    if not hashed_codes_json:
        return 0
    return len(json.loads(hashed_codes_json))


def _check_trusted_device(user: User, device_id: str | None) -> bool:
    """Check if device_id is in the user's trusted device list and not expired."""
    if not device_id or not user.totp_trusted_devices:
        return False
    try:
        devices = json.loads(user.totp_trusted_devices)
        now = datetime.utcnow().isoformat()
        for d in devices:
            if d.get("device_id") == device_id and d.get("expires_at", "") > now:
                return True
    except (json.JSONDecodeError, TypeError):
        pass
    return False


def _add_trusted_device(user: User, device_id: str) -> str:
    """Add a device to the trusted list (max 10, prune expired)."""
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=30)).isoformat()

    devices = []
    if user.totp_trusted_devices:
        try:
            devices = json.loads(user.totp_trusted_devices)
        except (json.JSONDecodeError, TypeError):
            devices = []

    # Prune expired and duplicates
    devices = [
        d for d in devices
        if d.get("expires_at", "") > now.isoformat() and d.get("device_id") != device_id
    ]

    devices.append({"device_id": device_id, "expires_at": expires_at})

    # Keep only last 10
    devices = devices[-10:]

    return json.dumps(devices)


# ============================================================================
# Request/Response schemas
# ============================================================================


class SetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class ConfirmSetupRequest(BaseModel):
    code: str


class VerifyRequest(BaseModel):
    challenge_token: str
    code: str
    device_id: str | None = None
    trust_device: bool = False
    is_backup_code: bool = False


class VerifyResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
    trust_token: str | None = None


class DisableRequest(BaseModel):
    code: str


class RegenerateRequest(BaseModel):
    code: str


class StatusResponse(BaseModel):
    totp_enabled: bool
    backup_codes_remaining: int


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/setup", response_model=SetupResponse)
async def setup_2fa(
    request: Request,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate TOTP secret and backup codes. Does NOT enable 2FA yet."""
    client_ip = get_client_ip(request) or "unknown"
    if not rate_limiter.check(f"2fa_setup:{client_ip}", max_requests=3, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")

    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled. Disable it first to reconfigure.",
        )

    # Generate secret
    secret = pyotp.random_base32(length=32)
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="RigaCap")

    # Generate backup codes
    backup_codes = _generate_backup_codes()

    # Store secret + hashed backup codes (not enabled yet)
    user.totp_secret = secret
    user.totp_backup_codes = _hash_backup_codes(backup_codes)
    await db.commit()

    return SetupResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        backup_codes=backup_codes,
    )


@router.post("/confirm-setup")
async def confirm_setup(
    body: ConfirmSetupRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify first TOTP code to finalize 2FA setup."""
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled.",
        )

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run /setup first.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code.strip(), valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code. Please try again.",
        )

    user.totp_enabled = True
    await db.commit()

    return {"message": "2FA enabled successfully."}


@router.post("/verify", response_model=VerifyResponse)
async def verify_2fa(
    body: VerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify TOTP or backup code during login. Returns full auth tokens."""
    from sqlalchemy import select

    client_ip = get_client_ip(request) or "unknown"
    if not rate_limiter.check(f"2fa_verify:{client_ip}", max_requests=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")

    # Decode challenge token
    payload = decode_token(body.challenge_token)
    if not payload or payload.get("type") != "2fa_challenge":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired challenge. Please log in again.",
        )

    user_id = payload.get("sub")
    import uuid as _uuid
    result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid challenge.",
        )

    code = body.code.strip()
    verified = False

    if body.is_backup_code:
        # Verify backup code
        if user.totp_backup_codes:
            valid, updated_json = _verify_backup_code(code, user.totp_backup_codes)
            if valid:
                verified = True
                user.totp_backup_codes = updated_json
    else:
        # Verify TOTP
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code, valid_window=1):
            verified = True

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid code. Please try again.",
        )

    # Update last login
    user.last_login = datetime.utcnow()

    # Trust device if requested
    trust_token = None
    if body.trust_device and body.device_id:
        user.totp_trusted_devices = _add_trusted_device(user, body.device_id)
        trust_token = create_2fa_trust_token(str(user.id), body.device_id)

    await db.commit()
    await db.refresh(user)

    # Load subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        user_dict["subscription"] = subscription.to_dict()

    # Generate auth tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return VerifyResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_dict,
        trust_token=trust_token,
    )


@router.post("/disable")
async def disable_2fa(
    body: DisableRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable 2FA. Requires current TOTP code."""
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code.strip(), valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code.",
        )

    user.totp_enabled = False
    user.totp_secret = None
    user.totp_backup_codes = None
    user.totp_trusted_devices = None
    await db.commit()

    return {"message": "2FA disabled."}


@router.get("/status", response_model=StatusResponse)
async def get_2fa_status(user: User = Depends(get_admin_user)):
    """Get 2FA status for the current admin user."""
    return StatusResponse(
        totp_enabled=bool(user.totp_enabled),
        backup_codes_remaining=_count_backup_codes(user.totp_backup_codes),
    )


@router.post("/regenerate-backup-codes")
async def regenerate_backup_codes(
    body: RegenerateRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate backup codes. Requires current TOTP code."""
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled.",
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(body.code.strip(), valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code.",
        )

    backup_codes = _generate_backup_codes()
    user.totp_backup_codes = _hash_backup_codes(backup_codes)
    await db.commit()

    return {"backup_codes": backup_codes}
