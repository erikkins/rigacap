"""Authentication API endpoints."""

import secrets
import time
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db, User, Subscription
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_challenge_token,
    decode_token,
    get_client_ip,
    get_current_user,
    rate_limiter,
)
from app.services.turnstile import verify_turnstile
from app.services.email_service import email_service

# Apple JWKS cache
_apple_jwks: Optional[dict] = None
_apple_jwks_fetched_at: float = 0
_APPLE_JWKS_TTL = 3600  # 1 hour


async def _get_apple_public_keys() -> dict:
    """Fetch and cache Apple's public signing keys (JWKS)."""
    global _apple_jwks, _apple_jwks_fetched_at

    if _apple_jwks and (time.time() - _apple_jwks_fetched_at) < _APPLE_JWKS_TTL:
        return _apple_jwks

    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://appleid.apple.com/auth/keys")
        resp.raise_for_status()
        _apple_jwks = resp.json()
        _apple_jwks_fetched_at = time.time()
        return _apple_jwks


async def _verify_apple_token(id_token: str) -> dict:
    """Verify an Apple Sign In JWT and return its claims."""
    from jose import jwt, jwk, JWTError

    # Get the key ID from the token header
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Token missing kid header")

    # Find the matching public key from Apple's JWKS
    jwks = await _get_apple_public_keys()
    matching_key = None
    for key_data in jwks.get("keys", []):
        if key_data["kid"] == kid:
            matching_key = key_data
            break

    if not matching_key:
        # Key not found — maybe Apple rotated keys, clear cache and retry once
        global _apple_jwks_fetched_at
        _apple_jwks_fetched_at = 0
        jwks = await _get_apple_public_keys()
        for key_data in jwks.get("keys", []):
            if key_data["kid"] == kid:
                matching_key = key_data
                break

    if not matching_key:
        raise ValueError("No matching Apple public key found")

    # Construct the RSA public key and verify the token
    public_key = jwk.construct(matching_key)
    claims = jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=settings.APPLE_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )
    return claims

router = APIRouter()


def generate_referral_code(length=8):
    """Generate a unique referral code (no ambiguous chars O/0/I/1/L)."""
    chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return ''.join(secrets.choice(chars) for _ in range(length))


# Request/Response schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    turnstile_token: str
    referral_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    turnstile_token: Optional[str] = None
    referral_code: Optional[str] = None


class AppleAuthRequest(BaseModel):
    id_token: str
    user_data: Optional[dict] = None
    turnstile_token: Optional[str] = None
    referral_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None
    requires_2fa: bool = False
    challenge_token: Optional[str] = None


def _check_2fa_required(user: User, trust_token: Optional[str] = None) -> bool:
    """Check if 2FA verification is needed for this login."""
    if not user.totp_enabled:
        return False

    # Check trust token
    if trust_token:
        payload = decode_token(trust_token)
        if (
            payload
            and payload.get("type") == "2fa_trust"
            and payload.get("sub") == str(user.id)
        ):
            device_id = payload.get("device_id")
            # Verify device is still in trusted list
            from app.api.two_factor import _check_trusted_device
            if _check_trusted_device(user, device_id):
                return False

    return True


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with email/password."""
    client_ip = get_client_ip(req) or "unknown"

    # Rate limit: 3 registrations per minute per IP
    if not rate_limiter.check(f"register:{client_ip}", max_requests=3, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")

    # Verify Turnstile
    if not await verify_turnstile(request.turnstile_token, client_ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot verification failed"
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    # Create user
    user = User(
        email=request.email,
        password_hash=get_password_hash(request.password),
        name=request.name,
        role="admin" if request.email == "erik@rigacap.com" else "user",
        referral_code=generate_referral_code(),
    )

    # Link referrer if referral code provided
    if request.referral_code:
        referrer_result = await db.execute(
            select(User).where(User.referral_code == request.referral_code.upper().strip())
        )
        referrer = referrer_result.scalar_one_or_none()
        if referrer:
            user.referred_by = referrer.id

    db.add(user)
    await db.flush()

    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    # Send welcome email (don't wait for it, fire and forget)
    import asyncio
    asyncio.create_task(
        email_service.send_welcome_email(
            user.email, user.name or user.email,
            referral_code=user.referral_code,
            user_id=str(user.id),
        )
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict()
    )


@router.post("/login")
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Login with email/password."""
    client_ip = get_client_ip(req) or "unknown"

    # Rate limit: 5 login attempts per minute per IP
    if not rate_limiter.check(f"login:{client_ip}", max_requests=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")

    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Check 2FA
    trust_token = req.headers.get("X-2FA-Trust")
    if _check_2fa_required(user, trust_token):
        challenge = create_challenge_token(str(user.id))
        return LoginResponse(requires_2fa=True, challenge_token=challenge)

    # Update last login
    user.last_login = datetime.utcnow()
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

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_dict
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    payload = decode_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled"
        )

    # Load subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        user_dict["subscription"] = subscription.to_dict()

    # Generate new tokens
    access_token = create_access_token(str(user.id))
    new_refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=user_dict
    )


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user."""
    # Load subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        sub_dict = subscription.to_dict()
        # Admins always have a valid subscription
        if user.is_admin():
            sub_dict["is_valid"] = True
            sub_dict["status"] = "active"
        user_dict["subscription"] = sub_dict
    elif user.is_admin():
        # Admin with no subscription record at all — synthesize one
        user_dict["subscription"] = {
            "status": "active",
            "is_valid": True,
            "days_remaining": 999,
            "has_stripe_subscription": False,
        }

    return user_dict


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout current user (client should delete tokens)."""
    return {"message": "Logged out successfully"}


@router.post("/google")
async def google_auth(
    request: GoogleAuthRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate with Google OAuth."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={request.id_token}"
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token"
                )
            google_data = response.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to verify Google token"
        )

    email = google_data.get("email")
    google_id = google_data.get("sub")
    name = google_data.get("name")

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token data"
        )

    # Check if user exists by Google ID or email
    result = await db.execute(
        select(User).where((User.google_id == google_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()

    is_new_user = False
    if user:
        # Update Google ID if not set
        if not user.google_id:
            user.google_id = google_id
        user.last_login = datetime.utcnow()
    else:
        # Verify Turnstile for new users (mandatory)
        client_ip = get_client_ip(req)
        if not request.turnstile_token or not await verify_turnstile(request.turnstile_token, client_ip):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot verification failed"
            )

        # Create new user
        user = User(
            email=email,
            name=name,
            google_id=google_id,
            role="admin" if email == "erik@rigacap.com" else "user",
            referral_code=generate_referral_code(),
            last_login=datetime.utcnow(),
        )

        # Link referrer if referral code provided
        if request.referral_code:
            referrer_result = await db.execute(
                select(User).where(User.referral_code == request.referral_code.upper().strip())
            )
            referrer = referrer_result.scalar_one_or_none()
            if referrer:
                user.referred_by = referrer.id

        db.add(user)
        await db.flush()
        is_new_user = True

    await db.commit()
    await db.refresh(user)

    # Send welcome email to new users
    if is_new_user:
        import asyncio
        asyncio.create_task(
            email_service.send_welcome_email(
                user.email, user.name or user.email,
                referral_code=user.referral_code,
                user_id=str(user.id),
            )
        )

    # Check 2FA (skip for brand-new users)
    if not is_new_user:
        trust_token = req.headers.get("X-2FA-Trust")
        if _check_2fa_required(user, trust_token):
            challenge = create_challenge_token(str(user.id))
            return LoginResponse(requires_2fa=True, challenge_token=challenge)

    # Load subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        user_dict["subscription"] = subscription.to_dict()

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_dict
    )


@router.post("/apple")
async def apple_auth(
    request: AppleAuthRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Authenticate with Apple Sign In."""
    try:
        verified = await _verify_apple_token(request.id_token)
        apple_id = verified.get("sub")
        email = verified.get("email")

        # Apple only sends user info (name/email) on first auth, use user_data if provided
        if not email and request.user_data:
            email = request.user_data.get("email")

        if request.user_data and request.user_data.get("name"):
            name = request.user_data["name"]
            full_name = f"{name.get('firstName', '')} {name.get('lastName', '')}".strip()
        else:
            full_name = None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Apple token"
        )

    if not apple_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token data"
        )

    # Check if user exists by Apple ID
    result = await db.execute(select(User).where(User.apple_id == apple_id))
    user = result.scalar_one_or_none()

    # Also check by email if we have one
    if not user and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    is_new_user = False
    if user:
        # Update Apple ID if not set
        if not user.apple_id:
            user.apple_id = apple_id
        user.last_login = datetime.utcnow()
    else:
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email required for new accounts"
            )

        # Verify Turnstile for new users (mandatory)
        client_ip = get_client_ip(req)
        if not request.turnstile_token or not await verify_turnstile(request.turnstile_token, client_ip):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bot verification failed"
            )

        # Create new user
        user = User(
            email=email,
            name=full_name,
            apple_id=apple_id,
            role="admin" if email == "erik@rigacap.com" else "user",
            referral_code=generate_referral_code(),
            last_login=datetime.utcnow(),
        )

        # Link referrer if referral code provided
        if request.referral_code:
            referrer_result = await db.execute(
                select(User).where(User.referral_code == request.referral_code.upper().strip())
            )
            referrer = referrer_result.scalar_one_or_none()
            if referrer:
                user.referred_by = referrer.id

        db.add(user)
        await db.flush()
        is_new_user = True

    await db.commit()
    await db.refresh(user)

    # Send welcome email to new users
    if is_new_user:
        import asyncio
        asyncio.create_task(
            email_service.send_welcome_email(
                user.email, user.name or user.email,
                referral_code=user.referral_code,
                user_id=str(user.id),
            )
        )

    # Check 2FA (skip for brand-new users)
    if not is_new_user:
        trust_token = req.headers.get("X-2FA-Trust")
        if _check_2fa_required(user, trust_token):
            challenge = create_challenge_token(str(user.id))
            return LoginResponse(requires_2fa=True, challenge_token=challenge)

    # Load subscription
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    user_dict = user.to_dict()
    if subscription:
        user_dict["subscription"] = subscription.to_dict()

    # Generate tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_dict
    )


# ============================================================================
# Password Reset
# ============================================================================

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Send a password reset email. Always returns 200 to prevent email enumeration."""
    client_ip = get_client_ip(req) or "unknown"

    # Rate limit: 3 reset requests per minute per IP
    if not rate_limiter.check(f"forgot:{client_ip}", max_requests=3, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user and user.password_hash:
        # Only send reset for email/password accounts (not OAuth-only)
        from jose import jwt as jose_jwt
        reset_token = jose_jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.utcnow() + timedelta(hours=1),
                "type": "password_reset",
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        import asyncio
        asyncio.create_task(
            email_service.send_password_reset_email(user.email, user.name or user.email, reset_url)
        )

    return {"message": "If that email is registered, you'll receive a reset link shortly."}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using a valid reset token."""
    payload = decode_token(request.token)

    if payload is None or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link"
        )

    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset link"
        )

    user.password_hash = get_password_hash(request.password)
    await db.commit()

    return {"message": "Password reset successfully. You can now sign in."}


# ============================================================================
# Email Preferences
# ============================================================================

ALLOWED_EMAIL_PREFS = {"daily_digest", "sell_alerts", "double_signals", "intraday_signals", "market_measured"}


@router.patch("/me/email-preferences")
async def update_email_preferences(
    prefs: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update email preferences for the current user."""
    # Validate keys
    invalid_keys = set(prefs.keys()) - ALLOWED_EMAIL_PREFS
    if invalid_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preference keys: {', '.join(invalid_keys)}"
        )

    # Validate values are booleans
    for key, value in prefs.items():
        if not isinstance(value, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Preference '{key}' must be a boolean"
            )

    # Merge with existing
    existing = user.email_preferences or {}
    merged = {**existing, **prefs}
    user.email_preferences = merged
    await db.commit()
    await db.refresh(user)

    defaults = {k: True for k in ALLOWED_EMAIL_PREFS}
    return {"email_preferences": {**defaults, **merged}}


@router.get("/email-preferences")
async def get_email_preferences_by_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get email preferences using a JWT token (from email footer links)."""
    payload = decode_token(token)
    if payload is None or payload.get("purpose") != "email_manage":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid link"
        )

    defaults = {k: True for k in ALLOWED_EMAIL_PREFS}
    prefs = {**defaults, **(user.email_preferences or {})}
    return {"email_preferences": prefs, "email": user.email}


@router.post("/unsubscribe")
async def unsubscribe_by_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """One-click unsubscribe from all emails (from email footer)."""
    payload = decode_token(token)
    if payload is None or payload.get("purpose") not in ("email_manage", "email_unsubscribe"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link"
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid link"
        )

    user.email_preferences = {k: False for k in ALLOWED_EMAIL_PREFS}
    await db.commit()

    return {"message": "You have been unsubscribed from all emails.", "email": user.email}


# ============================================================================
# Referral Program
# ============================================================================

@router.get("/referral")
async def get_referral_info(
    user: User = Depends(get_current_user),
):
    """Get the current user's referral code, link, and count."""
    return {
        "referral_code": user.referral_code,
        "referral_link": f"https://rigacap.com/?ref={user.referral_code}" if user.referral_code else None,
        "referral_count": user.referral_count or 0,
    }
