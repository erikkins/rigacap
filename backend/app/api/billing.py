"""Billing API endpoints for Stripe integration."""

import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db, User, Subscription
from app.core.config import settings
from app.core.security import get_current_user

router = APIRouter()

# Subscription statuses that count as an occupied founding seat (a started
# trial claims a seat; canceled/expired free it). Shared by the seat counter,
# the public status endpoint, and the admin founder pill.
_LIVE_SUB_STATUSES = ("trial", "trialing", "active", "past_due")


async def count_founding_seats(db: AsyncSession) -> int:
    """How many founding seats are taken — subscriptions on the FOUNDING ($59)
    price in a live status. Founder status is DERIVED from the price id (no
    schema change): once founding closes new signups go to the standard price,
    so this count stabilizes at the seat limit."""
    if not settings.STRIPE_PRICE_ID:
        return 0
    n = await db.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.stripe_price_id == settings.STRIPE_PRICE_ID,
            Subscription.status.in_(_LIVE_SUB_STATUSES),
        )
    )
    return int(n.scalar() or 0)


async def founding_status(db: AsyncSession) -> dict:
    limit = settings.FOUNDING_SEAT_LIMIT
    taken = await count_founding_seats(db)
    return {
        "taken": taken,
        "limit": limit,
        "remaining": max(0, limit - taken),
        "open": taken < limit,
    }


@router.get("/founding-status")
async def get_founding_status(db: AsyncSession = Depends(get_db)):
    """PUBLIC — drives the landing 'X of 100 seats left' teaser + grays the
    founding card once full. Also tells checkout which monthly price to use."""
    return await founding_status(db)


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionResponse(BaseModel):
    status: str
    is_valid: bool
    days_remaining: int
    trial_end: Optional[str] = None
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False


class CheckoutRequest(BaseModel):
    plan: str = "monthly"  # "monthly" or "annual"


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe Checkout session for subscription.

    Args:
        plan: "monthly" ($10/month) or "annual" ($110/year, one month free)
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured"
        )

    # Determine which price ID to use.
    plan = request.plan if request else "monthly"
    if plan == "annual":
        price_id = settings.STRIPE_PRICE_ID_ANNUAL
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Annual plan not configured"
            )
    else:
        # Monthly: founding ($59) while seats remain, else standard ($129).
        # Server-side decision so the price can't be spoofed from the client,
        # and so 'founding'/'monthly' CTAs both resolve to the correct live
        # price. (Jun 23 2026 — replaces the single $39 STRIPE_PRICE_ID.)
        fstat = await founding_status(db)
        if fstat["open"] or not settings.STRIPE_PRICE_ID_STANDARD:
            price_id = settings.STRIPE_PRICE_ID            # founding $59
        else:
            price_id = settings.STRIPE_PRICE_ID_STANDARD   # standard $129
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Monthly plan not configured"
            )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # Create or get Stripe customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={"user_id": str(user.id)}
            )
            user.stripe_customer_id = customer.id
            await db.commit()

        # Check if user already had a subscription (prevent repeat trials)
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        existing_sub = result.scalar_one_or_none()

        # Create checkout session
        checkout_params = {
            "customer": user.stripe_customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{settings.FRONTEND_URL}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/pricing?checkout=canceled",
        }

        # Apply referral coupon if user was referred (and no existing subscription)
        if user.referred_by and not existing_sub and settings.STRIPE_REFERRAL_COUPON_ID:
            checkout_params["discounts"] = [{"coupon": settings.STRIPE_REFERRAL_COUPON_ID}]
        else:
            checkout_params["allow_promotion_codes"] = True

        # Only offer trial to users who have never had a subscription
        if not existing_sub:
            checkout_params["subscription_data"] = {"trial_period_days": 7}

        session = stripe.checkout.Session.create(**checkout_params)

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id
        )

    except stripe.StripeError as e:
        print(f"❌ Stripe error in create-checkout: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment service error"
        )
    except Exception as e:
        print(f"❌ Unexpected error in create-checkout: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checkout error: {type(e).__name__}"
        )


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe Customer Portal session for managing subscription."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured"
        )

    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found. Subscribe first to manage billing."
        )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard?portal_return=1"
        )
        return PortalResponse(portal_url=session.url)
    except stripe.InvalidRequestError as e:
        # Stale customer ID (e.g. sandbox/test-mode customer in live mode) — clear it
        print(f"⚠️ Stale Stripe customer for {user.email}: {e}")
        user.stripe_customer_id = None
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found. Subscribe first to manage billing."
        )
    except stripe.StripeError as e:
        print(f"❌ Stripe error in portal: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment service error"
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's subscription status."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )

    return SubscriptionResponse(
        status=subscription.status,
        is_valid=subscription.is_valid(),
        days_remaining=subscription.days_remaining(),
        trial_end=subscription.trial_end.isoformat() if subscription.trial_end else None,
        current_period_end=subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        cancel_at_period_end=subscription.cancel_at_period_end
    )


@router.post("/sync")
async def sync_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sync subscription status directly from Stripe (doesn't rely on webhooks)."""
    if not settings.STRIPE_SECRET_KEY or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # List active subscriptions for this customer
        subs = stripe.Subscription.list(
            customer=user.stripe_customer_id,
            status="all",
            limit=1,
        )

        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        subscription = result.scalar_one_or_none()
        _is_new_subscription = False
        if not subscription:
            # User may have just completed Stripe checkout before webhook fired
            if subs.data:
                subscription = Subscription(user_id=user.id)
                db.add(subscription)
                _is_new_subscription = True  # welcome fires below (deduped vs webhook by the new-row check)
            else:
                raise HTTPException(status_code=404, detail="No subscription record")

        if subs.data:
            stripe_sub = subs.data[0]
            status_map = {
                "active": "active",
                "past_due": "past_due",
                "canceled": "canceled",
                "unpaid": "past_due",
                "trialing": "trial",
            }
            period_start, period_end = _get_period_dates(stripe_sub)
            subscription.status = status_map.get(stripe_sub.status, stripe_sub.status)
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.stripe_price_id = stripe_sub.items.data[0].price.id if stripe_sub.items.data else None
            if period_start:
                subscription.current_period_start = datetime.fromtimestamp(period_start)
            if period_end:
                subscription.current_period_end = datetime.fromtimestamp(period_end)
            subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
            # Set trial dates if trialing
            if hasattr(stripe_sub, 'trial_start') and stripe_sub.trial_start:
                subscription.trial_start = datetime.fromtimestamp(stripe_sub.trial_start)
            if hasattr(stripe_sub, 'trial_end') and stripe_sub.trial_end:
                subscription.trial_end = datetime.fromtimestamp(stripe_sub.trial_end)
            await db.commit()

            # Welcome on first subscription (founder/standard by price). Deduped
            # vs the webhook: only the path that creates the row sends it.
            if _is_new_subscription:
                try:
                    is_founding = bool(settings.STRIPE_PRICE_ID and subscription.stripe_price_id == settings.STRIPE_PRICE_ID)
                    from app.services.email_service import email_service
                    await email_service.send_welcome_email(
                        to_email=user.email, name=user.name or "", referral_code=getattr(user, "referral_code", None),
                        user_id=str(user.id), is_founding=is_founding,
                    )
                    print(f"📧 Welcome ({'founder' if is_founding else 'standard'}) sent via sync to {user.email}")
                except Exception as we:
                    print(f"⚠️ Welcome email on sync failed (non-fatal): {we}")

            return {
                "synced": True,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            }

        return {"synced": True, "status": subscription.status, "message": "No Stripe subscription found"}

    except stripe.StripeError as e:
        print(f"❌ Stripe error in sync: {e}")
        raise HTTPException(status_code=502, detail="Payment service error")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhooks not configured"
        )

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = await request.body()

    # Verify signature using construct_event
    try:
        stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as sig_err:
        if "Signature" in type(sig_err).__name__ or "signature" in str(sig_err).lower():
            raise HTTPException(status_code=400, detail="Invalid signature")
        raise

    # Parse as plain dict to avoid StripeObject attribute access issues
    event = json.loads(payload)
    event_type = event.get("type", "")
    sub_data = event.get("data", {}).get("object", {})

    print(f"📩 Webhook received: {event_type}, sub={sub_data.get('id')}")

    try:
        if event_type == "customer.subscription.created":
            await handle_subscription_created(sub_data, db)
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(sub_data, db)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(sub_data, db)
        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(sub_data, db)
    except Exception as e:
        print(f"❌ Webhook handler error for {event_type}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing error")

    return {"received": True}


def _get_period_dates(sub: dict):
    """Extract current_period_start/end from subscription dict.

    Stripe API 2026-01-28+ moved these from subscription to items.data[0].
    """
    start = sub.get("current_period_start")
    end = sub.get("current_period_end")
    if not start or not end:
        items = sub.get("items", {}).get("data", [])
        if items:
            start = start or items[0].get("current_period_start")
            end = end or items[0].get("current_period_end")
    if not start:
        start = sub.get("start_date") or sub.get("created")
    return start, end


def _get_price_id(sub: dict) -> Optional[str]:
    """Extract price ID from subscription dict."""
    items = sub.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("id")
    return None


async def handle_subscription_created(sub: dict, db: AsyncSession):
    """Handle new Stripe subscription created."""
    customer_id = sub.get("customer")

    result = await db.execute(
        select(User).where(User.stripe_customer_id == customer_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        print(f"⚠️ No user found for Stripe customer {customer_id}")
        return

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()

    # Brand-new subscription row = first time this user subscribed → welcome.
    # Natural dedup (no new column): a re-delivered webhook finds the existing
    # row and won't re-send.
    _is_new_subscription = subscription is None
    if not subscription:
        subscription = Subscription(user_id=user.id)
        db.add(subscription)

    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "trialing": "trial",
    }

    period_start, period_end = _get_period_dates(sub)
    subscription.status = status_map.get(sub.get("status", ""), sub.get("status", ""))
    subscription.stripe_subscription_id = sub.get("id")
    subscription.stripe_price_id = _get_price_id(sub)
    if period_start:
        subscription.current_period_start = datetime.fromtimestamp(period_start)
    if period_end:
        subscription.current_period_end = datetime.fromtimestamp(period_end)
    subscription.cancel_at_period_end = sub.get("cancel_at_period_end", False)

    # Set trial dates if trialing
    if sub.get("trial_start"):
        subscription.trial_start = datetime.fromtimestamp(sub["trial_start"])
    if sub.get("trial_end"):
        subscription.trial_end = datetime.fromtimestamp(sub["trial_end"])

    await db.commit()
    print(f"✅ Webhook: subscription created for user {user.id}, status={subscription.status}")

    # Welcome email fires HERE (not at registration) so it knows founder vs
    # standard — non-founders never get founding-rate language (Erik Jun 23).
    if _is_new_subscription:
        try:
            is_founding = bool(settings.STRIPE_PRICE_ID and subscription.stripe_price_id == settings.STRIPE_PRICE_ID)
            from app.services.email_service import email_service
            await email_service.send_welcome_email(
                to_email=user.email, name=user.name or "", referral_code=getattr(user, "referral_code", None),
                user_id=str(user.id), is_founding=is_founding,
            )
            print(f"📧 Welcome ({'founder' if is_founding else 'standard'}) sent to {user.email}")
        except Exception as we:
            print(f"⚠️ Welcome email on subscription-created failed (non-fatal): {we}")


async def handle_subscription_updated(sub: dict, db: AsyncSession):
    """Handle Stripe subscription updated."""
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub.get("id"))
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        customer_id = sub.get("customer")
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()

        if user:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = result.scalar_one_or_none()

    if not subscription:
        print(f"⚠️ No subscription found for Stripe sub {sub.get('id')}")
        return

    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "trialing": "trial",
    }

    old_status = subscription.status
    period_start, period_end = _get_period_dates(sub)
    new_status = status_map.get(sub.get("status", ""), sub.get("status", ""))
    subscription.status = new_status
    subscription.stripe_subscription_id = sub.get("id")
    if period_start:
        subscription.current_period_start = datetime.fromtimestamp(period_start)
    if period_end:
        subscription.current_period_end = datetime.fromtimestamp(period_end)
    subscription.cancel_at_period_end = sub.get("cancel_at_period_end", False)

    await db.commit()
    print(f"✅ Webhook: subscription updated, status={new_status}")

    # Reward referrer when referred user converts trial → active
    if old_status == "trial" and new_status == "active":
        await _reward_referrer(subscription.user_id, db)


async def _reward_referrer(user_id, db: AsyncSession):
    """Apply referral coupon to referrer's subscription when referred user converts."""
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        referred_user = result.scalar_one_or_none()
        if not referred_user or not referred_user.referred_by:
            return

        result = await db.execute(select(User).where(User.id == referred_user.referred_by))
        referrer = result.scalar_one_or_none()
        if not referrer:
            return

        # Apply coupon to referrer's Stripe subscription
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == referrer.id)
        )
        referrer_sub = result.scalar_one_or_none()
        if referrer_sub and referrer_sub.stripe_subscription_id and settings.STRIPE_REFERRAL_COUPON_ID:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                stripe.Subscription.modify(
                    referrer_sub.stripe_subscription_id,
                    coupon=settings.STRIPE_REFERRAL_COUPON_ID,
                )
                print(f"✅ Referral: applied coupon to referrer {referrer.id}")
            except Exception as e:
                print(f"⚠️ Referral: failed to apply coupon to referrer {referrer.id}: {e}")

        # Increment referrer's count
        referrer.referral_count = (referrer.referral_count or 0) + 1
        await db.commit()

        # Send reward email to referrer
        from app.services.email_service import email_service
        import asyncio
        asyncio.create_task(
            email_service.send_referral_reward_email(
                to_email=referrer.email,
                name=referrer.name or referrer.email,
                friend_name=referred_user.name or referred_user.email,
                user_id=str(referrer.id),
            )
        )
        print(f"✅ Referral: rewarded referrer {referrer.id}, count={referrer.referral_count}")
    except Exception as e:
        print(f"⚠️ Referral reward error: {e}")


async def handle_subscription_deleted(sub: dict, db: AsyncSession):
    """Handle Stripe subscription canceled/deleted."""
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub.get("id"))
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = "canceled"
        subscription.cancel_at_period_end = False
        await db.commit()
        print(f"✅ Webhook: subscription deleted/canceled")

        # Send win-back email to the cancelled subscriber
        try:
            user_result = await db.execute(
                select(User).where(User.id == subscription.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user and user.email:
                from app.services.email_service import email_service
                await email_service.send_winback_email(
                    to_email=user.email,
                    user_name=user.full_name or user.email,
                    user_id=str(user.id),
                )
                print(f"📧 Win-back email sent to {user.email}")
        except Exception as e:
            print(f"⚠️ Win-back email failed: {e}")


async def handle_payment_failed(invoice: dict, db: AsyncSession):
    """Handle failed payment."""
    subscription_id = invoice.get("subscription")

    if subscription_id:
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.status = "past_due"
            await db.commit()
            print(f"✅ Webhook: payment failed, status=past_due")


# === Cancel Survey ===

class CancelSurveyRequest(BaseModel):
    reason: str  # "too_expensive", "not_enough_signals", "confusing", "not_useful", "other"
    detail: Optional[str] = None  # Free-text elaboration
    would_return: Optional[bool] = None  # "Would you come back if we improved?"


@router.post("/cancel-survey")
async def submit_cancel_survey(
    survey: CancelSurveyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store cancel survey response. Called from frontend after Stripe portal return."""
    from sqlalchemy import text

    await db.execute(
        text("""
            INSERT INTO cancel_surveys (user_id, email, reason, detail, would_return, created_at)
            VALUES (:user_id, :email, :reason, :detail, :would_return, NOW())
        """),
        {
            "user_id": str(user.id),
            "email": user.email,
            "reason": survey.reason,
            "detail": survey.detail,
            "would_return": survey.would_return,
        }
    )
    await db.commit()
    print(f"📋 Cancel survey from {user.email}: reason={survey.reason}")
    return {"status": "ok"}
