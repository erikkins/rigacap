"""
Email Service - Daily summary emails for subscribers

Sends beautiful HTML emails with:
- Top signals of the day
- Market regime summary
- Open positions P&L
- Missed opportunities
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import pytz

_ET = pytz.timezone('US/Eastern')


def _now_et() -> datetime:
    """Current time in US/Eastern (naive, for display formatting)."""
    return datetime.now(_ET).replace(tzinfo=None)

logger = logging.getLogger(__name__)

# Email configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'daily@rigacap.com')
FROM_NAME = os.getenv('FROM_NAME', 'RigaCap Signals')

# Admin emails - only these addresses can receive internal/admin notifications
ADMIN_EMAILS = set(
    e.strip().lower()
    for e in os.getenv('ADMIN_EMAILS', 'erik@rigacap.com').split(',')
    if e.strip()
)

# Module-level failure log (per Lambda container lifetime)
_failure_log: list[dict] = []

# Permanent (5xx) bounces recorded during a send batch. The caller (e.g. the daily-email job)
# drains these after the batch and marks those users unsendable so we stop retrying dead addresses.
_permanent_bounces: list[dict] = []


def get_email_failures() -> list[dict]:
    """Return accumulated email failures since last clear."""
    return list(_failure_log)


def clear_email_failures():
    """Clear the failure log (after admin report is sent)."""
    _failure_log.clear()


def pop_permanent_bounces() -> list[dict]:
    """Return and clear the permanent-bounce list [{to_email, code, reason}, ...]."""
    out = list(_permanent_bounces)
    _permanent_bounces.clear()
    return out


def _permanent_smtp_code(exc) -> Optional[int]:
    """Extract a permanent 5xx SMTP code from an aiosmtplib exception, else None.
    Handles SMTPResponseException(.code) and SMTPRecipientsRefused(.recipients={addr: resp})."""
    code = getattr(exc, "code", None)
    if code is None:
        recips = getattr(exc, "recipients", None)
        if isinstance(recips, dict) and recips:
            codes = []
            for v in recips.values():
                c = getattr(v, "code", None)
                if c is None and isinstance(v, (tuple, list)) and v:
                    c = v[0]
                if isinstance(c, int):
                    codes.append(c)
            code = max(codes) if codes else None
    return code if (isinstance(code, int) and 500 <= code < 600) else None


def _vix_label(vix) -> str:
    """Convert VIX number to human-readable fear label."""
    if vix is None or vix == 'N/A':
        return 'N/A'
    try:
        v = float(vix)
    except (ValueError, TypeError):
        return 'N/A'
    if v < 15:
        return f'Calm (VIX: {v:.1f})'
    if v < 20:
        return f'Normal (VIX: {v:.1f})'
    if v < 25:
        return f'Elevated (VIX: {v:.1f})'
    if v < 35:
        return f'High Fear (VIX: {v:.1f})'
    return f'Extreme Fear (VIX: {v:.1f})'


# Bulk / marketing email types that MUST be suppressed for hard-bounced (email_unsendable)
# addresses. This is an ALLOWLIST on purpose: anything NOT listed here — transactional/recovery
# mail (email verification, password reset, welcome, goodbye) and admin/operational alerts
# (email_type=None) — is NEVER auto-suppressed, so a false-positive unsendable flag can't lock a
# real user out of account recovery. Onboarding steps are matched by the "onboarding_step" prefix.
_SUPPRESS_EMAIL_TYPES = {
    "daily_digest", "newsletter", "market_measured", "weekly_regime",
    "sell_alert", "intraday_signal_alert", "double_signal", "winback",
    "tier_announcement", "trial_ending", "referral_reward",
}


class EmailService:
    """
    Manages email sending for daily summaries and alerts
    """

    def __init__(self):
        self.enabled = bool(SMTP_USER and SMTP_PASS)
        if not self.enabled:
            logger.warning("Email service disabled - SMTP credentials not configured")
        # Suppression cache: lowercased emails flagged email_unsendable. Loaded lazily on the
        # first bulk send and refreshed every 5 min, so one warm Lambda invocation running a bulk
        # job does a single lookup that covers all recipients. See _is_suppressed / send_email.
        self._suppress_set: Optional[set] = None
        self._suppress_loaded_at: float = 0.0

    async def _is_suppressed(self, to_email: str) -> bool:
        """True if this address is flagged email_unsendable (hard bounce / bogus). Fail-open on a
        load error — we'd rather risk one send than silently drop ALL mail if the DB hiccups."""
        import time
        now = time.time()
        if self._suppress_set is None or (now - self._suppress_loaded_at) > 300:
            try:
                from app.core.database import async_session, User
                from sqlalchemy import select
                async with async_session() as db:
                    res = await db.execute(select(User.email).where(User.email_unsendable.is_(True)))
                    self._suppress_set = {e.lower() for (e,) in res.all() if e}
                self._suppress_loaded_at = now
            except Exception as e:
                logger.warning(f"[suppress] failed to load unsendable set: {e}")
                if self._suppress_set is None:
                    self._suppress_set = set()
        return (to_email or "").lower() in self._suppress_set

    def _generate_email_token(self, user_id: str, purpose: str = "email_manage") -> str:
        """Generate JWT token for email footer links (30-day expiry)."""
        from jose import jwt as jose_jwt
        from datetime import timedelta
        from app.core.config import settings
        payload = {
            "sub": str(user_id),
            "purpose": purpose,
            "exp": datetime.utcnow() + timedelta(days=30),
        }
        return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def _email_wrapper(self, label: str, content: str, user_id: str = None) -> str:
        """Wrap email content in the editorial header + footer."""
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;background-color:#F5F1E8;-webkit-font-smoothing:antialiased;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;">
<tr><td style="padding:32px 32px 0;">
<table cellpadding="0" cellspacing="0" style="width:100%;border-bottom:2px solid #141210;padding-bottom:20px;">
<tr>
<td><img src="https://rigacap.com/email-header.png" alt="RigaCap." width="240" height="58" style="display:block; width:240px; height:auto;" /></td>
<td align="right" style="font-family:'Courier New',monospace;font-size:11px;font-weight:700;color:#3A342E;letter-spacing:1.2px;text-transform:uppercase;">{label}</td>
</tr></table>
</td></tr>
<tr><td style="padding:32px;">{content}</td></tr>
{self._email_footer_html(user_id)}
</table></body></html>"""

    def _email_footer_html(self, user_id: str = None) -> str:
        """Generate the standard email footer with manage/unsubscribe links."""
        if user_id:
            token = self._generate_email_token(str(user_id))
            manage_url = f"https://rigacap.com/app?emailPrefs=1&token={token}"
            unsub_url = f"https://rigacap.com/app?unsubscribe=1&token={token}"
        else:
            manage_url = "https://rigacap.com/app"
            unsub_url = "#"

        return f'''<tr>
            <td style="border-top: 1px solid #DDD5C7; padding: 24px 24px;">
                <p style="margin: 0 0 8px; font-family: 'Courier New', monospace; font-size: 12px; color: #5A544E; line-height: 1.8; text-align: center;">
                    RigaCap &middot; Disciplined Momentum Strategy<br>
                    <a href="https://rigacap.com/app" style="color: #7A2430; text-decoration: underline;">Dashboard</a>
                    &nbsp;&middot;&nbsp;
                    <a href="{manage_url}" style="color: #7A2430; text-decoration: underline;">Manage Alerts</a>
                    &nbsp;&middot;&nbsp;
                    <a href="{unsub_url}" style="color: #7A2430; text-decoration: underline;">Unsubscribe</a>
                </p>
                <p style="margin: 0; font-family: 'Courier New', monospace; font-size: 11px; color: #6B6356; line-height: 1.6; text-align: center;">
                    For information purposes only. Not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.<br>
                    RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
                </p>
                <p style="margin: 8px 0 0; font-family: 'Courier New', monospace; font-size: 11px; color: #6B6356; text-align: center;">
                    &copy; {datetime.now().year} RigaCap, LLC
                </p>
            </td>
        </tr>'''

    async def send_tier_announcement(self, to_email: str, first_name: str = "there",
                                     user_id: str = None) -> bool:
        """Beta-tester announcement of the two product tiers (Preserver / Maximizer) so they can
        self-select. Brand-styled (paper/claret), thesis-led (no hard return numbers — the app's
        Simulated Portfolio carries the live walk-forward)."""
        first_name = (first_name or "there").split()[0]
        subject = "RigaCap now comes in two settings — pick the one that fits you"
        footer = self._email_footer_html(user_id)
        card = ("border-left: 3px solid #7A2430; background: #FAF7F0; padding: 18px 20px; "
                "margin: 0 0 20px;")
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;background-color:#F5F1E8;-webkit-font-smoothing:antialiased;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">Same engine, two temperaments. Here's how to choose.</span>
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;">
  <tr><td style="padding:32px 32px 0;">
    <table cellpadding="0" cellspacing="0" style="width:100%;border-bottom:2px solid #141210;padding-bottom:20px;">
      <tr>
        <td><img src="https://rigacap.com/email-header.png" alt="RigaCap." width="240" height="58" style="display:block; width:240px; height:auto;" /></td>
        <td align="right" style="font-family:'Courier New',monospace;font-size:11px;font-weight:700;color:#3A342E;letter-spacing:1.2px;text-transform:uppercase;">Two Settings</td>
      </tr>
    </table>
  </td></tr>
  <tr><td style="padding:32px;">
    <p style="font-size:17px;color:#141210;margin:0 0 24px;line-height:1.65;">Hi {first_name},</p>
    <p style="font-size:17px;color:#141210;margin:0 0 24px;line-height:1.65;">
      When you joined the beta, RigaCap was one strategy. Your feedback pushed us somewhere better:
      <strong>one engine, two settings</strong> &mdash; so the signals match <em>your</em> temperament, not the other way around.
    </p>
    <p style="font-size:17px;color:#141210;margin:0 0 24px;line-height:1.65;">
      Both tiers run the same underlying ensemble &mdash; the momentum, regime-detection, and risk discipline
      you've been watching. The difference is how aggressively they lean in, and what they optimize for.
    </p>
    <div style="text-align:center;margin:8px 0 28px;">
      <img src="https://rigacap.com/email-knob-v3.png" alt="One knob — Preserve to Maximize" width="280" style="display:inline-block;max-width:100%;height:auto;border:1px solid #141210;" />
      <p style="margin:8px 0 0;font-family:'Courier New',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#8A8279;">One knob &mdash; Preserve to Maximize</p>
    </div>
    <div style="{card}">
      <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#7A2430;">&#9670; Preserver</p>
      <p style="margin:0 0 10px;font-size:15px;font-style:italic;color:#5A544E;">for the investor who never wants a reason to panic-sell.</p>
      <p style="margin:0;font-size:16px;color:#141210;line-height:1.6;">
        Participate in the upside, but cut the gut-punch drawdowns that make people bail at the worst
        possible moment. In a genuine capitulation, Preserver raises cash and gets defensive automatically.
        You won't beat a raging bull every quarter &mdash; that's the premium you pay &mdash; but you'll stay in
        the seat through the parts that shake other people out. <strong>Choose this if your bigger fear is
        losing your nerve, not missing a rally.</strong>
      </p>
    </div>
    <div style="{card}">
      <p style="margin:0 0 6px;font-family:'Courier New',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#7A2430;">&#9670; Maximizer</p>
      <p style="margin:0 0 10px;font-size:15px;font-style:italic;color:#5A544E;">for the investor with a long horizon and the stomach for it.</p>
      <p style="margin:0;font-size:16px;color:#141210;line-height:1.6;">
        Chases momentum breakouts hard when the regime rewards it, then throttles its own exposure with a
        volatility brake when things get choppy &mdash; aggressive, but not reckless. Higher-variance by design:
        some stretches it flies, some its risk-management deliberately leaves upside on the table to protect
        you from a momentum crash. Over full cycles that trade has paid off handsomely. <strong>Choose this if
        your bigger fear is missing the big move &mdash; and you won't bail during the quiet stretches.</strong>
      </p>
    </div>
    <p style="font-size:17px;color:#141210;margin:24px 0;line-height:1.65;">
      <strong>How this is priced:</strong> Preserver is the base plan &mdash; that's where everyone starts.
      Maximizer is a <strong>+$100/mo add-on</strong> (+$79/mo at the introductory rate) that runs on top of it,
      and you can toggle it on or off anytime. So the question isn't which one instead of the other &mdash; it's
      whether Preserver alone fits you, or whether you'd want the offense switched on too. What keeps you up at
      night: drawdowns, or missing out? If it's drawdowns, Preserver is plenty. If it's missing the run and you can
      ride out the flat patches, add Maximizer. You can see both live books and their walk-forward track record in
      the app before you decide.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <p style="font-size:16px;color:#141210;margin:0 0 4px;">Just reply <strong>"Preserver"</strong> (the base) or <strong>"Preserver + Maximizer"</strong> and I'll get you set up.</p>
      <p style="font-size:14px;color:#5A544E;margin:0;">You're a beta member &mdash; first in line, and you keep your beta standing either way.</p>
    </div>
    <p style="font-size:17px;color:#141210;margin:24px 0 0;line-height:1.65;">Thanks for being here from the start,<br>Erik<br><span style="color:#5A544E;font-size:14px;">Founder, RigaCap</span></p>
  </td></tr>
  {footer}
</table>
</body></html>"""
        text = (
            f"Hi {first_name},\n\n"
            "When you joined the beta, RigaCap was one strategy. Your feedback pushed us somewhere better: "
            "one engine, two settings — so the signals match your temperament.\n\n"
            "PRESERVER — for the investor who never wants a reason to panic-sell. Participate in the upside, "
            "but cut the gut-punch drawdowns; in a real capitulation it raises cash automatically. Choose this "
            "if your bigger fear is losing your nerve, not missing a rally.\n\n"
            "MAXIMIZER — for the long-horizon investor with the stomach for it. Chases momentum breakouts, then "
            "throttles exposure with a volatility brake when things get choppy. Higher-variance; over full cycles "
            "it's paid off handsomely. Choose this if your bigger fear is missing the big move and you won't bail "
            "during the quiet stretches.\n\n"
            "How this is priced: Preserver is the base plan — that's where everyone starts. Maximizer is a "
            "+$100/mo add-on (+$79/mo at the introductory rate) that runs on top of it; toggle it on or off "
            "anytime. So it's not one instead of the other — it's whether Preserver alone fits you, or whether "
            "you'd want the offense switched on too. Drawdowns your worry? Preserver is plenty. Missing out (and "
            "you can ride the flat patches)? Add Maximizer. See both live books + track record in the app.\n\n"
            "Just reply \"Preserver\" (the base) or \"Preserver + Maximizer\" and I'll set you up. You keep your "
            "beta standing either way.\n\n"
            "Thanks for being here from the start,\nErik\nFounder, RigaCap\n\n"
            "Signals only — you execute through your own broker. Past performance is not a guarantee of future returns."
        )
        return await self.send_email(to_email, subject, html, text, user_id=user_id,
                                     email_type="tier_announcement")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        user_id: str = None,
        list_unsubscribe_url: Optional[str] = None,
        email_type: Optional[str] = None,
        inline_images: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Send an email to a single recipient with retry + exponential backoff.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML body of the email
            text_content: Plain text fallback (optional)
            user_id: User ID for List-Unsubscribe header (omit for transactional emails)
            email_type: Email-tracking category (e.g. 'daily_digest', 'signal_alert',
                'welcome', 'newsletter'). When provided, the HTML is instrumented
                with a 1x1 tracking pixel + click-redirect-wrapped links, and a
                'sent' row is recorded in email_events. Omit for operational/admin
                emails that shouldn't be tracked.

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email service disabled, would have sent to: {to_email}")
            return False

        # Central suppression chokepoint: never send BULK/marketing mail to a hard-bounced
        # (email_unsendable) address, regardless of which job built the recipient list. This is
        # the single guard that covers ALL email processes — the reason wonderboy stopped getting
        # the daily digest but still got the weekly regime report (that job had no flag check).
        # Transactional/recovery + admin mail is exempt (not in _SUPPRESS_EMAIL_TYPES).
        _et = email_type or ""
        if (_et in _SUPPRESS_EMAIL_TYPES or _et.startswith("onboarding_step")) and await self._is_suppressed(to_email):
            logger.info(f"[suppress] skipping {_et} to unsendable address: {to_email}")
            return False

        # Email engagement tracking — opt-in per call via email_type. Returns
        # the original html unchanged if instrumentation fails so the actual
        # send never breaks on a tracking issue.
        if email_type:
            try:
                from app.services.email_tracking_service import prepare_tracked_email
                html_content, _tok = await prepare_tracked_email(
                    html=html_content,
                    email_address=to_email,
                    email_type=email_type,
                    user_id=user_id,
                )
            except Exception as _te:
                logger.warning(f"Email tracking instrumentation failed for {email_type} -> {to_email}: {_te}")

        try:
            import aiosmtplib
        except ImportError:
            logger.error("aiosmtplib not installed. Run: pip install aiosmtplib")
            return False

        # Build message once, retry only the send
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Reply-To'] = f"{FROM_NAME} <{FROM_EMAIL}>"

        # An explicit unsubscribe URL (e.g. newsletter one-click link) wins
        # over the user_id-derived paid-user unsubscribe.
        if list_unsubscribe_url:
            msg['List-Unsubscribe'] = f"<{list_unsubscribe_url}>"
            msg['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"
        elif user_id:
            token = self._generate_email_token(str(user_id), purpose="email_unsubscribe")
            unsub_url = f"https://api.rigacap.com/auth/unsubscribe?token={token}"
            msg['List-Unsubscribe'] = f"<{unsub_url}>"
            msg['List-Unsubscribe-Post'] = "List-Unsubscribe=One-Click"

        if text_content:
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            msg.attach(text_part)

        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)

        # Inline images (cid:) — wrap the alternative body in a 'related' container so email
        # clients render embedded <img src="cid:..."> (e.g. the digest hero). Backward-compatible:
        # with no inline_images, msg stays a plain 'alternative' exactly as before.
        if inline_images:
            from email.mime.image import MIMEImage
            related = MIMEMultipart('related')
            for _h in ('Subject', 'From', 'To', 'Reply-To', 'List-Unsubscribe', 'List-Unsubscribe-Post'):
                if msg.get(_h) is not None:
                    related[_h] = msg[_h]
                    del msg[_h]
            related.attach(msg)
            for _cid, _path in inline_images.items():
                try:
                    with open(_path, 'rb') as _f:
                        _img = MIMEImage(_f.read(), _subtype='png')
                    _img.add_header('Content-ID', f'<{_cid}>')
                    _img.add_header('Content-Disposition', 'inline', filename=f'{_cid}.png')
                    related.attach(_img)
                except Exception as _ie:
                    logger.warning(f"inline image '{_cid}' ({_path}) attach failed: {_ie}")
            msg = related

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                await aiosmtplib.send(
                    msg,
                    hostname=SMTP_HOST,
                    port=SMTP_PORT,
                    username=SMTP_USER,
                    password=SMTP_PASS,
                    start_tls=True
                )
                logger.info(f"Email sent to {to_email}: {subject}")
                return True
            except Exception as e:
                # Permanent (5xx) rejection — e.g. Yahoo 552, mailbox doesn't exist. Retrying is
                # futile (it fails identically every time), so record it as a hard bounce and stop.
                # The daily-email job drains _permanent_bounces and marks the user unsendable.
                perm_code = _permanent_smtp_code(e)
                if perm_code is not None:
                    logger.error(f"Email to {to_email} PERMANENTLY rejected ({perm_code}) — marking unsendable: {e}")
                    _permanent_bounces.append({"to_email": to_email, "code": perm_code, "reason": f"smtp_{perm_code}"})
                    _failure_log.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "to_email": to_email, "subject": subject,
                        "error": str(e), "attempts": attempt, "permanent": True,
                    })
                    return False
                if attempt < max_retries:
                    delay = 2 ** attempt  # 2s, 4s
                    logger.warning(
                        f"Email to {to_email} failed (attempt {attempt}/{max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Email to {to_email} failed after {max_retries} attempts: {e}")
                    _failure_log.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "to_email": to_email,
                        "subject": subject,
                        "error": str(e),
                        "attempts": max_retries,
                    })
                    return False

    def _market_read_block(self, label: str, text: str) -> str:
        """A small labeled market-read block. Used to sit a read directly above the book it
        describes when a Maximizer email carries BOTH books (each gets its own read)."""
        if not text:
            return ''
        return f'''<tr>
            <td style="padding: 0 24px 14px;">
                <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #7A2430; margin-bottom: 6px;">{label}</div>
                <div style="border-left: 2px solid #DDD5C7; padding: 10px 16px; background: #FAF7F0;">
                    <div style="font-family: Georgia, serif; font-style: italic; font-size: 14px; color: #141210; line-height: 1.6;">{text}</div>
                </div>
            </td>
        </tr>'''

    def _bar(self, pct: float, color: str, track: str = '#E5DFD2', height: int = 5) -> str:
        """A horizontal progress bar that survives email clients — nested table with bgcolor
        cells (no CSS positioning, which Gmail/Outlook strip). `pct` (0–100) is filled in `color`,
        the remainder in `track`."""
        pct = max(0.0, min(100.0, pct))
        fill = (f'<td width="{pct:.0f}%" bgcolor="{color}" style="background:{color}; font-size:1px; '
                f'line-height:1px; height:{height}px; mso-line-height-rule:exactly;">&nbsp;</td>') if pct > 0 else ''
        rest = (f'<td bgcolor="{track}" style="background:{track}; font-size:1px; line-height:1px; '
                f'height:{height}px; mso-line-height-rule:exactly;">&nbsp;</td>') if pct < 100 else ''
        return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-collapse:collapse; table-layout:fixed;"><tr>{fill}{rest}</tr></table>')

    def _holding_row(self, h: Dict, scale: float = 1.0) -> str:
        """One book holding as an email row — symbol/price, a meta line (weight · whole shares ·
        $ value scaled to the recipient's capital), P&L, a NEW tag, and a visual GAUGE matching
        the portal: the Maximizer day-clock (progress to the 29-day time-stop) or the Preserver
        cushion-to-stop bar. Shared by both books. Bars only — the portal's entry/now marker dots
        need CSS positioning email can't do, so those are omitted; the bar + labels carry it."""
        sym = h.get('symbol', '')
        price = h.get('price') or 0
        wt = h.get('weight_pct')
        pnl = h.get('pnl_pct')
        pnl_txt = ''
        if pnl is not None:
            _pc = '#245232' if pnl >= 0 else '#7A2430'
            pnl_txt = (f'<span style="font-family: \'Courier New\', monospace; font-size: 14px; '
                       f'color: {_pc};">{"+" if pnl >= 0 else ""}{pnl:.1f}%</span>')
        new_tag = ('&nbsp;<span style="font-family: \'Courier New\', monospace; font-size: 11px; '
                   'letter-spacing: 1px; color: #7A2430;">NEW</span>') if h.get('is_new') else ''
        wt_txt = f"{wt:.0f}% of book" if wt is not None else ""
        # Capital-scaled holding: how much to actually hold at the recipient's capital.
        _ish = h.get('implied_shares'); _iv = h.get('implied_value')
        hold_txt = ""
        if _ish is not None and _iv is not None:
            _shn = _ish * scale
            _sh_txt = "&lt;1" if 0 < _shn < 1 else f"{round(_shn):,}"
            hold_txt = f"{_sh_txt} sh &middot; ${(_iv * scale):,.0f}"

        # Gauge — day-clock (breakout) or cushion-to-stop (Preserver). It carries the exit info,
        # so the text exit label is dropped from the meta line when a gauge renders.
        gauge = ''; g_l = ''; g_r = ''
        if h.get('exit_rule') == 'hold':
            hd = int(h.get('days_held') or 0); hold = int(h.get('hold_days') or 29)
            _dl = h.get('days_left'); dl = (hold - hd) if _dl is None else int(_dl)
            color = '#7A2430' if dl <= 5 else '#B98A92'          # near-exit → solid claret
            gauge = self._bar((hd / hold * 100) if hold else 0, color)
            g_l, g_r = f"day {hd}/{hold}", f"~{dl}d to time-stop"
        elif h.get('trailing_stop_level') is not None and h.get('high_water_mark') is not None:
            stop = float(h.get('trailing_stop_level') or 0)
            hwm = max(float(h.get('high_water_mark') or 0), stop + 0.01)
            now = float(price or stop)
            nowpct = ((now - stop) / (hwm - stop) * 100) if (hwm - stop) else 0   # cushion fill: stop→now
            cushion = ((now - stop) / now * 100) if now else 0                    # % above the stop
            color = '#7A2430' if cushion <= 8 else '#245232'     # thin cushion → claret, else green
            gauge = self._bar(nowpct, color)
            g_l, g_r = f"stop ${stop:,.0f}", f"{cushion:.0f}% to stop &middot; high ${hwm:,.0f}"

        meta_bits = [wt_txt, hold_txt]
        if not gauge:  # fallback text exit label only when no gauge rendered
            if h.get('exit_rule') == 'hold':
                meta_bits.append(f"day {h.get('days_held', 0)}/{h.get('hold_days', 29)}")
            else:
                meta_bits.append(f"{(h.get('trailing_stop_pct') or 30):.0f}% trail")
        meta = " &middot; ".join([x for x in meta_bits if x])

        gauge_row = ''
        if gauge:
            gauge_row = f'''
                        <tr>
                            <td colspan="2" style="padding-top: 8px;">
                                {gauge}
                                <table cellpadding="0" cellspacing="0" style="width:100%; margin-top:3px;"><tr>
                                    <td style="font-family:'Courier New',monospace; font-size:10px; color:#8A8279;">{g_l}</td>
                                    <td style="text-align:right; font-family:'Courier New',monospace; font-size:10px; color:#8A8279;">{g_r}</td>
                                </tr></table>
                            </td>
                        </tr>'''
        return f'''
                <div style="padding: 14px 0; border-bottom: 1px solid #DDD5C7;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="vertical-align: baseline; padding-right: 12px;">
                                <span style="font-family: Georgia, serif; font-size: 20px; font-weight: 500; color: #141210;">{sym}</span>{new_tag}
                            </td>
                            <td style="text-align: right; vertical-align: baseline; white-space: nowrap;">
                                <span style="font-family: 'Courier New', monospace; font-size: 17px; font-weight: bold; color: #141210;">${price:.2f}</span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding-top: 5px; font-family: 'Courier New', monospace; font-size: 13px; color: #5A544E; letter-spacing: 0.2px;">{meta}</td>
                            <td style="padding-top: 5px; text-align: right; white-space: nowrap;">{pnl_txt}</td>
                        </tr>{gauge_row}
                    </table>
                </div>'''

    def _book_section(self, book: Dict, market_regime: Dict = None, capital: float = None) -> str:
        """'Our Book' — the mirror that IS the product: current model holdings + a
        one-line posture + the mirroring rule. Leads the Preserver digest so the book
        (what to hold to match us) comes before the bonus 'Other Signals' list.

        capital: the recipient's portfolio size. When given, each row shows the implied
        shares + $ value AT THEIR CAPITAL (linear rescale of the book's implied_* which
        were computed at book['capital']) — so an email-only subscriber can mirror exactly."""
        if not book or not book.get('holdings'):
            return ''
        holdings = sorted(book['holdings'], key=lambda h: -(h.get('weight_pct') or 0))
        # Linear rescale factor: the book's implied_shares/implied_value were built at
        # book['capital']; scale to the recipient's capital. 1.0 if either is missing.
        _book_cap = book.get('capital') or 0
        _scale = (capital / _book_cap) if (capital and _book_cap) else 1.0
        n = len(holdings)
        new_ct = book.get('new_today') or 0
        exposure = book.get('exposure')
        bits = [f"Holding {n} position{'s' if n != 1 else ''}"]
        if new_ct:
            bits.append(f"{new_ct} new today")
        if exposure is not None and exposure < 0.99:
            bits.append(f"~{round(exposure * 100)}% invested &mdash; cash raised (defensive)")
        posture = " &middot; ".join(bits)
        rows = "".join(self._holding_row(h, _scale) for h in holdings)   # ALL holdings — never truncated
        return f'''
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #141210; margin-bottom: 8px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 18px; font-weight: 500; color: #141210;">Preserver Book</td>
                            <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 14px; color: #7A2430;">Preserve &middot; 30% trailing</td>
                        </tr>
                    </table>
                </div>
                <div style="font-family: Georgia, serif; font-size: 15px; color: #5A544E; margin-bottom: 4px;">{posture}.</div>
                <div style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #8A8279; line-height: 1.55; margin-bottom: 6px;">Mirror at today&rsquo;s price &mdash; the trailing stop rides the high, not your entry, so a late fill just widens your cushion.</div>
                {rows}
            </td>
        </tr>'''

    def generate_daily_summary_html(
        self,
        signals: List[Dict],
        market_regime: Dict,
        positions: List[Dict],
        missed_opportunities: List[Dict],
        date: Optional[datetime] = None,
        watchlist: List[Dict] = None,
        regime_forecast: Dict = None,
        user_id: str = None,
        market_context: str = None,
        tier: str = 'preserver',
        book: Dict = None,
        breakout_book: List[Dict] = None,
        breakout_tier_book: Dict = None,
        breakout_radar: List[Dict] = None,
        capital: float = None,
        secondary_market_context: str = None,
        todays_actions: Dict = None,
        preserver_todays_actions: Dict = None,
    ) -> str:
        """
        Generate beautiful HTML for daily summary email

        breakout_book: additive Maximizer serving — when provided, the recipient sees the
        Preserver base (book + signals) AND a delineated breakout-book section. None = legacy
        (Preserver, or the old Maximizer swap where signals ARE the book).

        Args:
            signals: List of today's signals
            market_regime: Market regime info (regime, spy_price, vix_level)
            positions: User's open positions with P&L
            missed_opportunities: Recent missed opportunities
            date: Date for the summary (default: today)

        Returns:
            HTML string for email body
        """
        if date is None:
            date = _now_et()

        date_str = date.strftime("%A, %B %d, %Y")

        # Cascade Guard (circuit breaker) — email-only users won't see the portal badge, so if
        # new entries are paused, say it plainly. Self-contained + best-effort.
        cascade_notice = ''
        try:
            from app.services import circuit_breaker_state as _cb
            _cbst = _cb.get_state('live') or {}
            _pu = _cbst.get('pause_until')
            if _pu and _cb.is_paused('live'):
                cascade_notice = f'''
        <tr><td style="padding: 0 24px 16px;">
            <div style="border-left: 3px solid #7A2430; background: #FAF7F0; padding: 10px 14px; font-family: Georgia, serif; font-size: 13px; color: #7A2430; line-height: 1.5;">
                <strong>Cascade Guard active</strong> &mdash; new entries are paused through {_pu} after a cluster of same-day stops. Existing holdings ride their stops as normal.
            </div>
        </td></tr>'''
        except Exception:
            cascade_notice = ''

        # Today's moves — same-day fills for the book(s) this subscriber mirrors. A Maximizer sub
        # holds BOTH books, so show a per-book line: Preserver (t30v entries / 30% trailing / regime)
        # AND Maximizer (breakout entries / 29-day time-stop). Only render a line that has moves; if
        # neither book traded today there's nothing to render.
        moves_banner = ''

        def _moves_line(ta, label, sell_note):
            b = [x.get('symbol') for x in ((ta or {}).get('buys') or []) if x.get('symbol')]
            s = [x.get('symbol') for x in ((ta or {}).get('sells') or []) if x.get('symbol')]
            if not (b or s):
                return None
            segs = []
            if b:
                segs.append("BUY " + ", ".join(b))
            if s:
                segs.append("SELL " + ", ".join(s) + sell_note)
            return (
                '<div style="font-family: Georgia, serif; font-size: 15px; color: #141210; '
                'line-height: 1.5; margin-top: 3px;">'
                '<span style="font-family: \'Courier New\', monospace; font-size: 11px; '
                'text-transform: uppercase; letter-spacing: 1px; color: #7A2430;">' + label + ':</span> '
                '&nbsp;' + " &nbsp;&middot;&nbsp; ".join(segs) + '</div>'
            )

        _move_lines = [ln for ln in (
            _moves_line(preserver_todays_actions, "Preserver", " (trailing / regime exit)"),
            _moves_line(todays_actions, "Maximizer", " (29-day exit)"),
        ) if ln]
        if _move_lines:
            moves_banner = f'''
        <tr><td style="padding: 0 24px 18px;">
            <div style="border: 1px solid #7A2430; background: #FFFFFF; padding: 12px 16px;">
                <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #7A2430; margin-bottom: 6px;">Today's moves &mdash; sync your broker</div>
                {"".join(_move_lines)}
            </div>
        </td></tr>'''
        # Bucket taxonomy — MUST match the dashboard (App.jsx) exactly:
        #   New today    = is_fresh signals ("Buy Signals" bucket on the site)
        #   Open         = non-fresh signals still in the buy zone ("Monitoring")
        #   Approaching  = watchlist, within striking distance of trigger
        # The subject line in send_daily_summary derives its counts from the
        # same is_fresh split — keep these definitions in lockstep.
        # Freshness is AGE-based (see _effective_fresh) — never the stored flag,
        # which persists at write time and never ages. Also dedupe by symbol
        # (broken invalidation left duplicate active rows), keep highest score.
        _effective_fresh = self._effective_fresh
        _seen, _deduped = set(), []
        for s_ in sorted(signals, key=lambda x: -(x.get('ensemble_score') or 0)):
            if s_.get('symbol') in _seen:
                continue
            _seen.add(s_.get('symbol'))
            _deduped.append(s_)
        signals = _deduped
        fresh_signals = [s for s in signals if _effective_fresh(s)]
        open_signals = [s for s in signals if not _effective_fresh(s)]
        watchlist = watchlist or []

        # "Our Book" (mirror) leads for served Preserver — the book is the product
        # promise; signals are the bonus. The signal list below is then framed as
        # "Other Signals — not in our book" so a subscriber running their OWN book
        # off our signals (different entries = their own diversification) still gets
        # them, without ever reading as a book holding. Maximizer's signals ARE its
        # breakout book, so that section stays the book. Legacy (no book) keeps the
        # historical "New Today / Consider adding".
        # Additive Maximizer (breakout_book provided): render the Preserver base like a served
        # Preserver (book + "Other Signals"), then append the breakout book as its own section.
        # Legacy Maximizer (no breakout_book): signals ARE the breakout book (the old swap).
        served_preserver = ((tier != 'maximizer' or breakout_book is not None) and book is not None)
        book_section = self._book_section(book, market_regime, capital) if served_preserver else ''
        if tier == 'maximizer' and not breakout_book:
            sig_header, sig_subhead = 'Your Maximizer Book', 'Held 29 days'
            sig_framing = ("Mirror at today&rsquo;s price. Each breakout is held 29 trading days then "
                           "sold on time &mdash; a late entry just gets fewer of those days, so favor the fresh names.")
        elif served_preserver:
            sig_header, sig_subhead = 'Other Signals', 'Not in our book'
            sig_framing = ("These pass our screen but aren&rsquo;t in our book right now &mdash; shown for your "
                           "own allocation. Running your own entries is its own diversification; the tags show "
                           "whether each is still near its entry.")
        else:
            # DEFENSIVE FALLBACK ONLY — reached when the tier book failed to build (book is None),
            # NOT a normal served send. Real subscribers hit the served-Preserver / Maximizer
            # branches above (lead with the book + Today's Actions). Never surface the retired
            # self-managed "Consider adding" framing here — keep it book-neutral. (Deleting the
            # branch outright would NameError sig_header if a book build ever fails.)
            sig_header, sig_subhead = 'Today&rsquo;s Signals', ''
            sig_framing = ("Mirror at today&rsquo;s price &mdash; the trailing stop rides the high, not your entry, "
                           "so a late fill just widens your cushion. Don&rsquo;t chase names already well past their signal.")

        # New-Today section (Jun 17 2026 rework): LEAD with the active set.
        # When nothing is fresh but signals are still active, don't headline a
        # flat "New Today (0) / No new signals" empty block — that reads like a
        # dead day. Show a slim one-liner here and let the Open (active) section
        # carry the email. Only the truly-empty day gets the centered notice.
        def _wrap(header_html, subhead, framing, rows_html):
            return f'''
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 1px solid #DDD5C7; margin-bottom: 12px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">{header_html}</td>
                            <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #7A2430;">{subhead}</td>
                        </tr>
                    </table>
                </div>
                <div style="font-family: Georgia, serif; font-style: italic; font-size: 12px; color: #8A8279; line-height: 1.5; margin-bottom: 12px;">{framing}</div>
                {rows_html}
            </td>
        </tr>'''

        def _count(n):
            return f'<span style="font-style: italic; color: #8A8279; font-weight: 400;">({n})</span>'

        if tier == 'maximizer' and not breakout_book:
            # LEGACY swap: the breakout book IS the content — show ALL cards (new first, then
            # holdings), always, no truncation, no "no new entries" headline. Posture line up top.
            book_cards = signals  # already new-first from build_maximizer_breakout_view
            _new_ct = len([s for s in book_cards if s.get('status') == 'new' or s.get('is_fresh')])
            _held_ct = len(book_cards) - _new_ct
            if book_cards:
                _posture = (f"{_held_ct} breakout{'s' if _held_ct != 1 else ''} in play"
                            + (f" &middot; {_new_ct} entered today" if _new_ct else " &middot; none entered today") + ". ")
                _rows = "".join(self._signal_row(s) for s in book_cards)
                new_today_section = _wrap(f"{sig_header} {_count(len(book_cards))}", sig_subhead, _posture + sig_framing, _rows)
            else:
                new_today_section = _wrap(sig_header, 'In cash', "Your book is in cash right now &mdash; breakout hunting resumes when momentum broadens.", '')
        elif served_preserver:
            # ONE "Other Signals — not in our book" list = all not-held ensemble names
            # (fresh first); the old separate "Open" section is folded in here.
            other = fresh_signals + open_signals
            if other:
                _rows = "".join(self._signal_row(s) for s in other)
                new_today_section = _wrap(f"{sig_header} {_count(len(other))}", sig_subhead, sig_framing, _rows)
            else:
                new_today_section = _wrap(sig_header, sig_subhead, "Nothing outside the book today &mdash; the book above is the full picture.", '')
        else:
            if fresh_signals:
                _nt_rows = "".join(self._signal_row(s) for s in fresh_signals[:8])
                new_today_section = _wrap(f"{sig_header} {_count(len(fresh_signals))}", sig_subhead, sig_framing, _nt_rows)
            elif open_signals:
                _n = len(open_signals)
                new_today_section = f'''
        <tr>
            <td style="padding: 0 24px 12px;">
                <div style="font-family: Georgia, serif; font-style: italic; font-size: 14px; color: #5A544E; line-height: 1.5;">No new entries today &mdash; {_n} signal{"s" if _n != 1 else ""} still active in the buy zone, below.</div>
            </td>
        </tr>'''
            else:
                new_today_section = '''
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding: 24px; text-align: center; font-family: Georgia, serif; font-style: italic; color: #5A544E;">No new signals today. The system is watching.</div>
            </td>
        </tr>'''

        # Calculate totals
        total_positions_pnl = sum(
            (p.get('current_price', 0) - p.get('entry_price', 0)) * p.get('shares', 0)
            for p in positions
        )
        total_missed = sum(m.get('would_be_pnl', 0) for m in missed_opportunities[:5])

        # Regime styling — editorial density palette
        regime = market_regime.get('regime', 'range_bound') if market_regime else 'range_bound'
        regime_labels = {
            'strong_bull': 'Strong Bull', 'weak_bull': 'Weak Bull', 'rotating_bull': 'Rotating Bull',
            'range_bound': 'Range-Bound', 'weak_bear': 'Weak Bear', 'panic_crash': 'Panic/Crash', 'recovery': 'Recovery',
        }
        regime_label = regime_labels.get(regime, regime.replace('_', ' ').title())

        # --- Middle section ordering -----------------------------------------------------------
        # Maximizer ("both" books): LEAD with the breakout book (what they upgraded for — matches
        # the Maximizer-branded subject), then the Preserver base. Mirror the portal's two
        # deviation layers (Preserver signals via new_today_section + the breakout radar) and DROP
        # the generic ensemble "Approaching" watchlist here — the served portal doesn't show it and
        # the word collides with the radar's "approaching a breakout trigger".
        _is_both = breakout_book is not None
        _top_ctx = (f'''<tr>
            <td style="padding: 0 24px 20px;">
                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0;">
                    <div style="font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.65;">{market_context}</div>
                </div>
            </td>
        </tr>''' if (market_context and not _is_both) else '')
        _pres_read = self._market_read_block('Preserver market read', secondary_market_context) if (_is_both and secondary_market_context) else ''
        _max_read = self._market_read_block('Maximizer breakout read', market_context) if (_is_both and market_context) else ''
        _breakout = self._breakout_book_section(breakout_book, capital=capital, tier_book=breakout_tier_book) if _is_both else ''
        _radar = self._breakout_radar_section(breakout_radar) if (_is_both and breakout_radar) else ''
        _open = self._open_signals_section(open_signals) if (open_signals and tier != 'maximizer' and not served_preserver) else ''
        _watch = self._watchlist_section(watchlist) if (watchlist and not _is_both) else ''
        if _is_both:
            _middle = _max_read + _breakout + _radar + _pres_read + book_section + new_today_section
        else:
            _middle = _top_ctx + _pres_read + book_section + new_today_section + _open + _watch

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #F5F1E8; -webkit-font-smoothing: antialiased;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto;">
        <!-- Header -->
        <tr>
            <td style="padding: 24px 24px 0;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; border-bottom: 2px solid #141210; padding-bottom: 16px;">
                    <tr>
                        <td>
                            <img src="https://rigacap.com/email-header.png" alt="RigaCap." width="240" height="58" style="display: block; width:240px; height:auto;" />
                        </td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; color: #3A342E; letter-spacing: 1.2px; text-transform: uppercase;">
                            Daily Digest
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Date + Regime -->
        <tr>
            <td style="padding: 20px 24px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    <tr>
                        <td>
                            <div style="font-family: 'Courier New', monospace; font-size: 13px; font-weight: bold; color: #5A544E; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 8px;">{date_str}</div>
                            <div style="font-family: Georgia, serif; font-size: 22px; color: #141210; line-height: 1.2;">{regime_label} Market</div>
                        </td>
                        <td align="right" valign="top" style="font-family: 'Courier New', monospace; font-size: 12px; color: #5A544E; line-height: 1.6;">
                            <strong style="color: #141210;">SPY ${market_regime.get('spy_price', 0):.0f}</strong><br>
                            VIX: {market_regime.get('vix_level', 0):.1f}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Tier label — premium cue distinguishing Maximizer from Preserver emails -->
        {f'''<tr>
            <td style="padding: 0 24px 12px;">
                <span style="display: inline-block; font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; {'background:#7A2430;color:#F5F1E8;' if tier == 'maximizer' else 'border:1px solid #DDD5C7;color:#5A544E;'} padding: 3px 8px;">{'&#9670; Maximizer' if tier == 'maximizer' else 'Preserver'}</span>
            </td>
        </tr>''' if tier else ''}

        <!-- Cascade Guard notice (entries paused) — only when active -->
        {cascade_notice}

        <!-- Today's moves — same-day book fills; empty when the book didn't trade today -->
        {moves_banner}

        <!-- Ordered middle: Maximizer leads with breakout book + radar, then Preserver base;
             Preserver-only keeps context → book → signals → open → watchlist. Assembled above. -->
        {_middle}

        <!-- Open Positions -->
        {self._positions_section(positions, total_positions_pnl) if positions else ''}

        <!-- Missed Opportunities -->
        {self._missed_section(missed_opportunities[:5], total_missed) if missed_opportunities else ''}

        <!-- Footer -->
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>
"""
        return html

    @staticmethod
    def _signal_strength(signal: Dict) -> tuple:
        """Ensemble score (0-100) + strength label — the SAME indicator pair
        the dashboard renders for every signal card. Label thresholds are
        identical to signals.py get_signal_strength_label and the App.jsx
        fallback (>=88 Very Strong, >=75 Strong, >=61 Moderate, else Weak).
        DB-sourced email signals don't carry signal_strength_label, so the
        fallback is the common path here."""
        score = int(round(signal.get('ensemble_score') or 0))
        label = signal.get('signal_strength_label')
        if not label:
            if score >= 88:
                label = 'Very Strong'
            elif score >= 75:
                label = 'Strong'
            elif score >= 61:
                label = 'Moderate'
            else:
                label = 'Weak'
        return score, label

    @staticmethod
    def _effective_fresh(sig: Dict) -> bool:
        """Age-based freshness — the ONE definition used for section split, the
        New/Open routing, the 'NEW' vs 'STILL QUALIFIES' label, AND the claret
        'new pick' border. Never the stored is_fresh flag (it persists at write
        time and never ages → stale 'NEW · 88D AGO' rows + a border that lit up
        on old signals, which read as arbitrary). Fresh = crossed/entered within
        5 days; falls back to the stored flag only when no age is present."""
        ages = [a for a in (sig.get('days_since_crossover'), sig.get('days_since_entry')) if a is not None]
        if ages:
            return min(ages) <= 5
        return bool(sig.get('is_fresh'))

    def _breakout_book_section(self, breakout_book: List[Dict], capital: float = None,
                               tier_book: Dict = None) -> str:
        """Delineated Maximizer breakout-book block for the additive digest — rendered below
        the Preserver base. Held names (day X/29) + any fresh breakouts; empty => a one-line
        'paused' note. Claret top-border to set it apart from the Preserver sections.

        tier_book: the capital-scaled build_tier_book('maximizer') dict (same object the portal
        renders). When present, each name shows weight · whole shares · $ value at the recipient's
        capital (via the shared _holding_row) + a book-level vol-target exposure line — so an
        email-only subscriber can mirror the breakout book exactly. Falls back to the plain
        signal-card rows (no shares) when only the legacy card list is available."""
        holdings = (tier_book or {}).get('holdings') or []
        vol_line = ''
        if holdings:
            # Rich, capital-scaled render (portal parity).
            _bcap = tier_book.get('capital') or 0
            _scale = (capital / _bcap) if (capital and _bcap) else 1.0
            holdings = sorted(holdings, key=lambda h: -(h.get('weight_pct') or 0))
            new_ct = tier_book.get('new_today') or sum(1 for h in holdings if h.get('is_new'))
            held_ct = len(holdings) - new_ct
            body = "".join(self._holding_row(h, _scale) for h in holdings)
            posture = (f"{held_ct} breakout{'s' if held_ct != 1 else ''} in play"
                       + (f" &middot; {new_ct} entered today" if new_ct else " &middot; none entered today")
                       + ". Each is held 29 trading days then sold on time &mdash; no trailing stop.")
            # Vol-target exposure gauge: the Barroso vol-brake dials the book's exposure down in
            # choppy markets. None (older snapshots) → omit the line rather than guess.
            _vs = tier_book.get('vol_scale')
            if _vs is not None:
                _pct = round(_vs * 100)
                _state = 'full exposure' if _vs >= 0.99 else 'dialed back when the market turns choppy'
                vol_line = (f'<div style="font-family: \'Courier New\', monospace; font-size: 12px; '
                            f'color: #5A544E; letter-spacing: 0.3px; margin-bottom: 12px;">'
                            f'Volatility target: <strong style="color:#7A2430;">{_pct}% exposure</strong> '
                            f'&mdash; {_state}.</div>')
        else:
            # Fallback: legacy card list (no per-name shares), or the paused empty-state.
            cards = breakout_book or []
            new_ct = len([c for c in cards if c.get('status') == 'new' or c.get('is_fresh')])
            held_ct = len(cards) - new_ct
            if cards:
                body = "".join(self._signal_row(c) for c in cards)
                posture = (f"{held_ct} breakout{'s' if held_ct != 1 else ''} in play"
                           + (f" &middot; {new_ct} entered today" if new_ct else " &middot; none entered today")
                           + ". Each is held 29 trading days then sold on time &mdash; no trailing stop.")
            else:
                body = ''
                posture = ("Breakout hunting is paused &mdash; not a rotating-bull regime. "
                           "Your breakout book resumes when momentum broadens.")
        return f'''
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #7A2430; margin-bottom: 12px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #7A2430;">&#9670; Maximizer Breakout Book</td>
                            <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #7A2430;">Grow &middot; held 29d</td>
                        </tr>
                    </table>
                </div>
                <div style="font-family: Georgia, serif; font-style: italic; font-size: 12px; color: #8A8279; line-height: 1.5; margin-bottom: 12px;">{posture}</div>
                {vol_line}
                {body}
            </td>
        </tr>'''

    def _breakout_radar_section(self, radar: List[Dict]) -> str:
        """Maximizer breakout RADAR — names approaching a 50-day-high breakout, not yet in the
        book. Mirrors the portal's '◆ Maximizer breakout candidates · Approaching a breakout
        trigger' card, so the email's 'approaching' layer matches the site (and no longer collides
        with the old ensemble watchlist, which is dropped for the two-book view)."""
        cards = radar or []
        if not cards:
            return ''
        rows = ""
        for r in cards[:8]:
            sym = r.get('symbol', '')
            pct = r.get('pct_below_50d_high')
            vol = r.get('vol_ratio')
            meta_bits = []
            if pct is not None:
                meta_bits.append(f"{pct}% below high")
            if vol is not None:
                meta_bits.append(f"vol {vol}&times;")
            meta = " &middot; ".join(meta_bits)
            rows += f'''
                <div style="padding: 12px 0; border-bottom: 1px solid #DDD5C7;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 18px; font-weight: 500; color: #141210;">{sym}</td>
                            <td align="right" style="font-family: 'Courier New', monospace; font-size: 12px; color: #5A544E; white-space: nowrap;">{meta}</td>
                        </tr>
                    </table>
                </div>'''
        return f'''
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 1px solid #7A2430; margin-bottom: 10px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 15px; font-weight: 500; color: #7A2430;">&#9670; Approaching a breakout trigger</td>
                            <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 12px; color: #8A8279;">not yet in the book</td>
                        </tr>
                    </table>
                </div>
                {rows}
            </td>
        </tr>'''

    def _breakout_signal_row(self, signal: Dict) -> str:
        """Breakout (Maximizer) row — NO ensemble score / "% above trend" (those are t30v
        concepts). Shows the BREAKOUT tag, new-vs-holding state with the day-X/29 hold
        countdown, price, and hold P&L. Same block-anchor layout as _signal_row."""
        symbol = signal.get('symbol', 'N/A')
        price = signal.get('price', 0) or 0
        status = signal.get('status')
        hold = signal.get('hold_days') or 29
        days_held = signal.get('days_held')
        days_left = signal.get('days_left')
        pnl = signal.get('pnl_pct')
        is_new = status == 'new' or bool(signal.get('is_fresh'))
        # One short meta line (no per-row "NO TRAILING STOP" — it's true of every breakout
        # and just bloated the row; the 29-day clock is the distinctive fact). Jul 30: the
        # old 2-col stack collided/wrapped on phones (Erik) → symbol/price on line 1, a single
        # full-width meta line + P&L on line 2.
        if is_new:
            meta = f'New breakout · enter today · holds {hold} days'
        else:
            parts = []
            if days_held is not None:
                parts.append(f'Day {days_held}/{hold}')
            if days_left is not None:
                parts.append(f'{days_left}d to exit')
            meta = ' · '.join(parts) if parts else 'Holding'
            if signal.get('entry_status') == 'extended':
                meta += ' · late to initiate'
        pnl_cell = ''
        if pnl is not None and not is_new:
            pnl_color = '#245232' if pnl >= 0 else '#7A2430'
            pnl_cell = (f'<span style="font-family: \'Courier New\', monospace; font-size: 14px; '
                        f'color: {pnl_color};">{"+" if pnl >= 0 else ""}{pnl:.1f}%</span>')
        border = 'border-left: 3px solid #7A2430; padding-left: 14px;' if is_new else ''
        return f"""
        <a href="https://rigacap.com/app?chart={symbol}" style="display: block; color: inherit; text-decoration: none;">
        <div style="padding: 14px 0; border-bottom: 1px solid #DDD5C7; {border}">
            <table cellpadding="0" cellspacing="0" style="width: 100%;">
                <tr>
                    <td style="vertical-align: baseline; padding-right: 12px;">
                        <span style="font-family: Georgia, serif; font-size: 20px; font-weight: 500; color: #141210; text-decoration: underline;">{symbol}</span>
                        &nbsp;<span style="font-family: 'Courier New', monospace; font-size: 11px; letter-spacing: 1px; color: #7A2430;">BREAKOUT</span>
                    </td>
                    <td style="text-align: right; vertical-align: baseline; white-space: nowrap;">
                        <span style="font-family: 'Courier New', monospace; font-size: 17px; font-weight: bold; color: #141210;">${price:.2f}</span>
                    </td>
                </tr>
                <tr>
                    <td style="padding-top: 6px; font-family: 'Courier New', monospace; font-size: 13px; color: #5A544E; letter-spacing: 0.2px;">{meta}</td>
                    <td style="padding-top: 6px; text-align: right; white-space: nowrap;">{pnl_cell}</td>
                </tr>
            </table>
        </div>
        </a>
        """

    def _signal_row(self, signal: Dict) -> str:
        """Generate HTML for a single signal row — mirrors the dashboard card:
        symbol, price, ensemble score + strength label, and the trend distance
        explicitly labeled ("+x.x% above trend" — never a bare percentage).
        The whole row is a block anchor to the dashboard (inline styles only,
        color inherit, no underline on the block; symbol carries the underline)."""
        # Breakout (Maximizer) signals carry none of the t30v fields (score / % above trend) —
        # render the breakout-specific row instead of showing 0 / 0% above trend.
        if signal.get('source') == 'breakout' or signal.get('exit_rule') == 'hold':
            return self._breakout_signal_row(signal)
        symbol = signal.get('symbol', 'N/A')
        price = signal.get('price', 0)
        pct_above = signal.get('pct_above_dwap') or 0
        # AGE-based freshness — drives BOTH the age label and the claret border,
        # so the border means "genuinely new pick" and is consistent with the
        # section split (was the raw stored flag → border lit up on 88-day-old
        # signals; Erik Jun 22: "isn't clear why it's there and others don't").
        is_fresh = self._effective_fresh(signal)
        # Use the age that ACTUALLY drove freshness (min of crossover/entry) for the
        # label — not the raw crossover. A name fresh-by-ENTRY but that crossed DWAP
        # 50d ago was showing "New · 50d ago" under a "New Today" header (Erik Aug 5:
        # "the market message and New Today aren't jiving"). The effective age is honest.
        _ages = [a for a in (signal.get('days_since_crossover'), signal.get('days_since_entry')) if a is not None]
        eff_age = min(_ages) if _ages else None
        days_since = eff_age if eff_age is not None else signal.get('days_since_crossover')

        score, label = self._signal_strength(signal)

        # Sentence case (Erik Jul 30): all-caps monospace was the hardest style to scan;
        # descriptor lines read as normal prose now (eyebrow labels stay uppercase).
        if is_fresh:
            if days_since == 0:
                age_label = 'New today'
            elif days_since is not None:
                age_label = f'New · {days_since}d ago'
            else:
                age_label = 'New'
        else:
            # Non-fresh = older signal still qualifying. NEVER present these
            # without age context (Erik, Jun 11 — "Consider adding" on a 57d
            # signal misleads).
            if days_since is not None:
                age_label = f'Signaled {days_since}d ago · still qualifies'
            else:
                age_label = 'Still qualifies'

        # Actionability ("did I miss the window?"). The 30% stop trails the HIGH, not
        # your entry, so a late fill just widens the cushion — the only real risk is
        # chasing a name that has run well past where it signaled. entry_status is set
        # upstream (fresh | actionable | extended) off move-since-signal.
        _status = signal.get('entry_status')
        _move = signal.get('move_since_signal_pct')
        if _status == 'extended' and _move is not None:
            action_label = f'Extended +{_move:.0f}% past its signal — size down or wait for a pullback'
            action_color = '#7A2430'
        elif _status == 'actionable':
            action_label = 'Still near its entry — clean to mirror at today&rsquo;s price'
            action_color = '#245232'
        else:
            action_label = ''
            action_color = ''
        action_row = (
            f'''<tr><td colspan="2" style="padding-top: 3px; font-family: Georgia, serif; font-style: italic; font-size: 12px; color: {action_color}; letter-spacing: 0.1px;">{action_label}</td></tr>'''
            if action_label else ''
        )

        # Symbol/price on line 1, then full-width meta lines (strength+trend, then age).
        # Was a 3-item nowrap right column beside a left age label — collided/wrapped on
        # phones once the fonts were bumped (Erik Jul 30). Stacking full-width can't collide.
        return f"""
        <a href="https://rigacap.com/app?chart={symbol}" style="display: block; color: inherit; text-decoration: none;">
        <div style="padding: 14px 0; border-bottom: 1px solid #DDD5C7; {('border-left: 3px solid #7A2430; padding-left: 14px;' if is_fresh else '')}">
            <table cellpadding="0" cellspacing="0" style="width: 100%;">
                <tr>
                    <td style="vertical-align: baseline; padding-right: 12px;">
                        <span style="font-family: Georgia, serif; font-size: 20px; font-weight: 500; color: #141210; text-decoration: underline;">{symbol}</span>
                    </td>
                    <td style="text-align: right; vertical-align: baseline; white-space: nowrap;">
                        <span style="font-family: 'Courier New', monospace; font-size: 17px; font-weight: bold; color: #141210;">${price:.2f}</span>
                    </td>
                </tr>
                <tr>
                    <td colspan="2" style="padding-top: 6px; font-family: 'Courier New', monospace; font-size: 13px; letter-spacing: 0.2px;">
                        <span style="color: #7A2430;">{score}&nbsp;·&nbsp;{label}</span>&nbsp;·&nbsp;<span style="color: #245232;">+{pct_above:.0f}% above trend</span>
                    </td>
                </tr>
                <tr>
                    <td colspan="2" style="padding-top: 4px; font-family: 'Courier New', monospace; font-size: 12px; color: #8A8279; letter-spacing: 0.2px;">{age_label}</td>
                </tr>
                {action_row}
            </table>
        </div>
        </a>
        """

    def _open_signals_section(self, open_signals: List[Dict], max_rows: int = 10) -> str:
        """Generate HTML for the Open section — non-fresh signals still in the
        buy zone (the dashboard's "Monitoring" bucket). Every row carries its
        age context via _signal_row's "signaled Nd ago · still qualifies"."""
        if not open_signals:
            return ''

        total = len(open_signals)
        shown = open_signals[:max_rows]
        rows = "".join(self._signal_row(s) for s in shown)
        remaining = total - len(shown)
        more_note = f"""
                <div style="padding: 8px 0; text-align: center; font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #8A8279;">
                    and {remaining} more on your <a href="https://rigacap.com/app" style="color: #7A2430; text-decoration: none;">dashboard</a>
                </div>""" if remaining > 0 else ""
        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; padding-bottom: 8px; border-bottom: 1px solid #DDD5C7; margin-bottom: 8px;">
                    <tr>
                        <td style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Open <span style="font-style: italic; color: #8A8279; font-weight: 400;">({total})</span></td>
                        <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #5A544E;">Still in buy zone</td>
                    </tr>
                </table>
                {rows}{more_note}
            </td>
        </tr>
        """

    def _watchlist_section(self, watchlist: List[Dict], max_rows: int = 5) -> str:
        """Generate HTML for the Approaching section (watchlist nearing trigger).
        Each row is a block anchor to the dashboard; the distance is labeled
        "+x.x% to trigger" — never a bare percentage."""
        if not watchlist:
            return ''

        total = len(watchlist)
        shown = watchlist[:max_rows]
        rows = ""
        for w in shown:
            symbol = w.get('symbol', 'N/A')
            price = w.get('price', 0)
            distance = w.get('distance_to_trigger', 0)

            rows += f"""
            <a href="https://rigacap.com/app?chart={symbol}" style="display: block; color: inherit; text-decoration: none;">
            <div style="padding: 10px 0; border-bottom: 1px solid #DDD5C7;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    <tr>
                        <td style="vertical-align: top; padding-right: 12px; font-family: Georgia, serif; font-size: 17px; font-weight: 500; color: #141210;">
                            <span style="text-decoration: underline;">{symbol}</span>
                        </td>
                        <!-- price + distance STACKED right (was side-by-side, overlapped on mobile) -->
                        <td style="text-align: right; vertical-align: top; white-space: nowrap;">
                            <div style="font-family: 'Courier New', monospace; font-size: 15px; font-weight: bold; color: #141210;">${price:.2f}</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 12px; color: #5A544E; margin-top: 4px;">+{distance:.1f}% to trigger</div>
                        </td>
                    </tr>
                </table>
            </div>
            </a>
            """

        remaining = total - len(shown)
        more_note = f"""
                <div style="padding: 8px 0; text-align: center; font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #8A8279;">
                    and {remaining} more on your <a href="https://rigacap.com/app" style="color: #7A2430; text-decoration: none;">dashboard</a>
                </div>""" if remaining > 0 else ""

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #141210; margin-bottom: 12px;">
                    <span style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Approaching <span style="font-style: italic; color: #8A8279; font-weight: 400;">({total})</span></span>
                    <span style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #5A544E;"> — Nearing trigger</span>
                </div>
                {rows}{more_note}
            </td>
        </tr>
        """

    def _positions_section(self, positions: List[Dict], total_pnl: float) -> str:
        """Generate HTML for positions section"""
        pnl_color = '#2D5F3F' if total_pnl >= 0 else '#8F2D3D'
        pnl_sign = '+' if total_pnl >= 0 else ''

        rows = ""
        for p in positions[:5]:
            symbol = p.get('symbol', 'N/A')
            shares = p.get('shares', 0)
            entry = p.get('entry_price', 0)
            current = p.get('current_price', entry)
            pnl = (current - entry) * shares
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            color = '#2D5F3F' if pnl >= 0 else '#8F2D3D'
            sign = '+' if pnl >= 0 else ''

            rows += f"""
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #DDD5C7;">
                    <span style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">{symbol}</span>
                    <span style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279;"> {int(shares)} shares</span>
                </td>
                <td style="padding: 10px 0; text-align: right; border-bottom: 1px solid #DDD5C7;">
                    <span style="font-family: 'Courier New', monospace; font-size: 14px; color: {color};">{sign}{pnl_pct:.1f}%</span>
                    <span style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279;"> ({sign}${abs(pnl):.0f})</span>
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #141210; margin-bottom: 12px;">
                    <span style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Open Positions</span>
                </div>
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    {rows}
                    <tr>
                        <td style="padding: 14px 0 0; font-family: Georgia, serif; font-size: 14px; font-weight: 500; color: #141210;">Total P&L</td>
                        <td style="padding: 14px 0 0; text-align: right; font-family: 'Courier New', monospace; font-size: 18px; color: {pnl_color};">
                            {pnl_sign}${abs(total_pnl):,.0f}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """

    def _missed_section(self, missed: List[Dict], total_missed: float) -> str:
        """Generate HTML for missed opportunities section"""
        rows = ""
        for m in missed:
            symbol = m.get('symbol', 'N/A')
            would_be = m.get('would_be_return', 0)
            would_be_pnl = m.get('would_be_pnl', 0)
            date = m.get('signal_date', '')

            rows += f"""
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #DDD5C7;">
                    <a href="https://rigacap.com/app?chart={symbol}" style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210; text-decoration: none;">{symbol}</a>
                    <span style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279;"> {date}</span>
                </td>
                <td style="padding: 10px 0; text-align: right; border-bottom: 1px solid #DDD5C7; font-family: 'Courier New', monospace; font-size: 13px; color: #2D5F3F;">
                    +{would_be:.1f}% (+${would_be_pnl:.0f})
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #141210; margin-bottom: 12px;">
                    <span style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Missed Opportunities</span>
                </div>
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    {rows}
                </table>
                <div style="margin-top: 14px; font-family: 'Courier New', monospace; font-size: 13px; color: #141210;">
                    Total missed: +${total_missed:,.0f}
                </div>
            </td>
        </tr>
        """

    def generate_plain_text(
        self,
        signals: List[Dict],
        market_regime: Dict,
        date: Optional[datetime] = None,
        watchlist: List[Dict] = None
    ) -> str:
        """Generate plain text fallback for email"""
        if date is None:
            date = _now_et()
        watchlist = watchlist or []

        date_str = date.strftime("%A, %B %d, %Y")
        # Same bucket taxonomy as the HTML builder + the dashboard:
        # New today (is_fresh) / Open (non-fresh, still in buy zone) / Approaching.
        # Freshness is AGE-based (see _effective_fresh) — never the stored flag,
        # which persists at write time and never ages. Also dedupe by symbol
        # (broken invalidation left duplicate active rows), keep highest score.
        _effective_fresh = self._effective_fresh
        _seen, _deduped = set(), []
        for s_ in sorted(signals, key=lambda x: -(x.get('ensemble_score') or 0)):
            if s_.get('symbol') in _seen:
                continue
            _seen.add(s_.get('symbol'))
            _deduped.append(s_)
        signals = _deduped
        fresh_signals = [s for s in signals if _effective_fresh(s)]
        open_signals = [s for s in signals if not _effective_fresh(s)]

        def _signal_line(s: Dict, fresh: bool) -> str:
            symbol = s.get('symbol', 'N/A')
            price = s.get('price', 0)
            # Breakout (Maximizer): no score / "% above trend" — show the hold countdown.
            if s.get('source') == 'breakout' or s.get('exit_rule') == 'hold':
                hold = s.get('hold_days') or 29
                if s.get('status') == 'new' or s.get('is_fresh'):
                    return f"  {symbol}: ${price:.2f} - BREAKOUT, enter today, hold {hold} trading days [NEW]"
                dh, dl = s.get('days_held'), s.get('days_left')
                pnl = s.get('pnl_pct')
                pnl_s = f", {'+' if (pnl or 0) >= 0 else ''}{pnl:.1f}%" if pnl is not None else ""
                return (f"  {symbol}: ${price:.2f} - BREAKOUT, day {dh}/{hold}"
                        f"{f', {dl}d to exit' if dl is not None else ''}{pnl_s} [holding]")
            pct = s.get('pct_above_dwap') or 0
            days_since = s.get('days_since_crossover')
            score, label = self._signal_strength(s)
            if fresh:
                tag = "[NEW TODAY]" if days_since == 0 else (
                    f"[NEW - {days_since}d ago]" if days_since is not None else "[NEW]")
            else:
                tag = (f"[signaled {days_since}d ago, still qualifies]"
                       if days_since is not None else "[still qualifies]")
            return (f"  {symbol}: ${price:.2f} - Strength {score}/100 ({label}) "
                    f"- +{pct:.1f}% above trend {tag}")

        lines = [
            f"RIGACAP DAILY - {date_str}",
            "=" * 40,
            "",
            f"Market Regime: {market_regime.get('regime', 'N/A') if market_regime else 'N/A'}",
            f"S&P 500: ${market_regime.get('spy_price', 'N/A') if market_regime else 'N/A'}",
            f"Market Fear: {_vix_label(market_regime.get('vix_level')) if market_regime else 'N/A'}",
            "",
            f"NEW TODAY ({len(fresh_signals)})",
            "-" * 40,
        ]

        if fresh_signals:
            for s in fresh_signals[:8]:
                lines.append(_signal_line(s, fresh=True))
        else:
            lines.append("  No new signals today.")

        if open_signals:
            lines.extend(["", f"OPEN - STILL IN BUY ZONE ({len(open_signals)})", "-" * 40])
            for s in open_signals[:6]:
                lines.append(_signal_line(s, fresh=False))
            if len(open_signals) > 6:
                lines.append(f"  ...and {len(open_signals) - 6} more on your dashboard")

        if watchlist:
            lines.extend(["", f"APPROACHING ({len(watchlist)})", "-" * 40])
            for w in watchlist[:5]:
                lines.append(f"  {w.get('symbol', 'N/A')}: ${w.get('price', 0):.2f} - +{w.get('distance_to_trigger', 0):.1f}% to trigger")
            if len(watchlist) > 5:
                lines.append(f"  ...and {len(watchlist) - 5} more on your dashboard")

        lines.extend([
            "",
            "View full details at: https://rigacap.com/app",
            "",
            "---",
            "RigaCap - Ensemble Trading Signals",
            "For information purposes only. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results."
        ])

        return "\n".join(lines)

    async def send_daily_summary(
        self,
        to_email: str,
        signals: List[Dict],
        market_regime: Dict,
        positions: List[Dict] = None,
        missed_opportunities: List[Dict] = None,
        watchlist: List[Dict] = None,
        regime_forecast: Dict = None,
        date: Optional[datetime] = None,
        user_id: str = None,
        market_context: str = None,
        tier: str = 'preserver',
        book: Dict = None,
        breakout_book: List[Dict] = None,
        breakout_tier_book: Dict = None,
        breakout_radar: List[Dict] = None,
        capital: float = None,
        secondary_market_context: str = None,
        todays_actions: Dict = None,
        preserver_todays_actions: Dict = None,
    ) -> bool:
        """
        Send daily summary email to a subscriber

        Args:
            to_email: Subscriber email
            signals: Today's ensemble signals
            market_regime: Current market regime info
            positions: User's open positions
            missed_opportunities: Recent missed opportunities
            watchlist: Stocks approaching trigger
            regime_forecast: Regime forecast data
            date: Date for the summary (default: today). Used for time-travel emails.

        Returns:
            True if sent successfully
        """
        positions = positions or []
        missed_opportunities = missed_opportunities or []
        watchlist = watchlist or []

        # Subject counts use the SAME age-based freshness the HTML uses
        # (_effective_fresh), so subject/headers/rows never disagree.
        def _eff_fresh(sig):
            ages = [a for a in (sig.get('days_since_crossover'), sig.get('days_since_entry')) if a is not None]
            return (min(ages) <= 5) if ages else bool(sig.get('is_fresh'))
        fresh_count = len([s for s in signals if _eff_fresh(s)])
        active_count = len(signals)
        approaching_count = len(watchlist)
        # Include date in subject for historical (time-travel) emails
        is_historical = date and date.date() != _now_et().date()
        date_label = f" [{date.strftime('%b %d, %Y')}]" if is_historical else ""
        # "new" MUST match the body's "Today's moves" — BUY = the instruction, so it counts actual
        # new book entries today (preserver_todays_actions.buys), NOT the fresh-signal bucket, which
        # diverges from what the book did (Sep 12 2026: subject said "2 new" while the book made 1
        # move). Sells are exits, not "new". LEAD with the active count — NEVER open with "0 new"
        # when signals are live (Jun 17 2026: "0 new …" read exactly like the empty-bug).
        todays_new = len(((preserver_todays_actions or {}).get('buys')) or [])
        if todays_new > 0:
            subject = (f"📊 RigaCap Daily{date_label}: {todays_new} new · "
                       f"{active_count} active · {approaching_count} approaching")
        elif active_count > 0:
            subject = (f"📊 RigaCap Daily{date_label}: {active_count} signal"
                       f"{'s' if active_count != 1 else ''} active · {approaching_count} approaching")
        else:
            subject = f"📊 RigaCap Daily{date_label}: watching the market · {approaching_count} approaching"

        # Maximizer subscribers get a book-posture subject (breakouts in play + new today).
        # Additive mode: counts come from the breakout_book (signals are now the Preserver base).
        if tier == 'maximizer':
            _bk = breakout_book if breakout_book is not None else signals
            new_ct = len([s for s in _bk if s.get('status') == 'new' or s.get('is_fresh')])
            held_ct = len([s for s in _bk if s.get('status') == 'holding'])
            if new_ct > 0:
                subject = f"◆ RigaCap Maximizer{date_label}: {new_ct} new breakout{'s' if new_ct != 1 else ''} · {held_ct} in play"
            else:
                subject = f"◆ RigaCap Maximizer{date_label}: {held_ct} breakout{'s' if held_ct != 1 else ''} in play"

        # v3 = dashboard-sourced editorial redesign (both tiers). Old generate_daily_summary_html
        # is kept intact above as an instant one-line revert if needed.
        from app.services import digest_v3
        html = digest_v3.build_digest_v3(
            tier=tier,
            signals=signals,
            market_regime=market_regime,
            watchlist=watchlist,
            market_context=market_context,
            regime_forecast=regime_forecast,
            date=date,
            breakout_book=breakout_book,
            breakout_radar=breakout_radar,
            secondary_market_context=secondary_market_context,
        )
        hero_path = digest_v3.digest_hero_path(market_regime, tier)
        dawn_path = digest_v3.digest_dawn_path()
        inline_hero = {}
        if hero_path:
            inline_hero['hero'] = hero_path
        if dawn_path:
            inline_hero['dawn'] = dawn_path
        inline_hero = inline_hero or None

        text = self.generate_plain_text(signals, market_regime, date=date, watchlist=watchlist)

        return await self.send_email(to_email, subject, html, text, user_id=user_id,
                                     email_type="daily_digest", inline_images=inline_hero)

    async def send_newsletter_confirmation(
        self,
        to_email: str,
        report_type: str = "market_measured",
    ) -> bool:
        """Courtesy opt-in confirmation sent the moment someone subscribes to a
        free newsletter (market_measured / regime_report). Not a click-to-confirm
        gate — the subscription is already active. Its job is to (a) confirm the
        signup and (b) give an instant one-click out for anyone whose address was
        entered by someone else. Reuses the segmented newsletter-unsubscribe token
        so the footer link + List-Unsubscribe header target only this report."""
        report_labels = {
            "market_measured": ("Market Measured",
                                 "a weekly read of what the system is seeing, delivered Sundays"),
            "regime_report": ("Weekly Regime Report",
                              "our weekly market-regime briefing"),
        }
        label, tagline = report_labels.get(
            report_type, ("RigaCap newsletter", "our weekly briefing"))

        from jose import jwt as _jose_jwt
        from app.core.config import settings as _settings
        _unsub_tok = _jose_jwt.encode(
            {"email": to_email.strip().lower(), "report_type": report_type,
             "purpose": "newsletter_unsubscribe"},
            _settings.JWT_SECRET_KEY,
            algorithm=_settings.JWT_ALGORITHM,
        )
        unsub_url = f"https://api.rigacap.com/api/public/newsletter/unsubscribe?token={_unsub_tok}"

        subject = f"You're on the list — RigaCap {label}"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F5F1E8;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F5F1E8;">
    <tr><td align="center" style="padding:40px 20px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#F5F1E8;">
        <tr><td style="padding:0 0 28px;">
          <span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;color:#141210;letter-spacing:0.02em;">RigaCap</span>
        </td></tr>
        <tr><td style="border-top:1px solid #E0D9CB;padding:28px 0 0;">
          <h1 style="margin:0 0 16px;font-family:Georgia,'Times New Roman',serif;font-weight:400;font-size:26px;line-height:1.25;color:#141210;">You're on the list.</h1>
          <p style="margin:0 0 16px;font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.6;color:#141210;">
            Thanks for signing up for RigaCap's <strong style="font-weight:600;">{label}</strong> — {tagline}. Your first issue will land in your inbox on the next send.
          </p>
          <p style="margin:0 0 28px;font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.6;color:#5A544E;">
            <strong style="color:#7A2430;font-weight:600;">If you didn't sign up</strong> for this, you can ignore this email or remove yourself instantly below — you won't hear from us again.
          </p>
          <p style="margin:0 0 32px;">
            <a href="{unsub_url}" style="font-family:Georgia,serif;font-size:14px;color:#7A2430;text-decoration:underline;">Unsubscribe with one click</a>
          </p>
          <p style="margin:0;padding-top:24px;border-top:1px solid #E0D9CB;font-family:Georgia,serif;font-size:12px;line-height:1.6;color:#8A847C;">
            RigaCap · Signals only — you execute at your own broker. Not investment advice.<br>
            Questions? Just reply to this email.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""
        text = (
            f"You're on the list.\n\n"
            f"Thanks for signing up for RigaCap's {label} — {tagline}. "
            f"Your first issue will land on the next send.\n\n"
            f"If you didn't sign up for this, you can ignore this email or unsubscribe "
            f"instantly here: {unsub_url}\n\n"
            f"RigaCap · Signals only — you execute at your own broker. Not investment advice.\n"
            f"Questions? Just reply to this email."
        )
        return await self.send_email(
            to_email, subject, html, text,
            list_unsubscribe_url=unsub_url,
            email_type="newsletter",
        )

    async def send_market_measured(
        self,
        to_email: str,
        dashboard_data: Dict,
        date: Optional[datetime] = None,
        user_id: str = None,
        show_symbols: bool = False,
        last_weeks_fresh: Optional[List[Dict]] = None,
    ) -> bool:
        """
        Send the weekly 'Market, Measured.' top-of-funnel email.

        Reads directly from dashboard_data (same structure as dashboard.json).
        Calm, observational, non-urgent — positions RigaCap as the adult voice.
        No strategy mechanics revealed (no DWAP, MA thresholds, stop pcts).

        Args:
            show_symbols: If False (default, for free list), watchlist and
                this-week's fresh signals are anonymized (count-only) to
                preserve paid value. If True (for paid subscribers), full
                tickers are shown.
            last_weeks_fresh: List of dicts with at least {symbol, entry_date,
                entry_price, current_price, pnl_pct}. Used for the delayed-
                reveal track-record section in free-list emails. Ignored if
                show_symbols is True (paid users see live signals instead).
        """
        if date is None:
            date = _now_et()
        date_str = date.strftime("%B %d, %Y")
        subject_date = date.strftime("%B %-d")

        # Segmented unsubscribe token — shared between List-Unsubscribe header
        # (one-click) and the visible footer link so the footer matches the
        # header exactly and both target only market_measured for this email.
        from jose import jwt as _jose_jwt
        from app.core.config import settings as _settings
        _unsub_tok = _jose_jwt.encode(
            {"email": to_email.strip().lower(), "report_type": "market_measured",
             "purpose": "newsletter_unsubscribe"},
            _settings.JWT_SECRET_KEY,
            algorithm=_settings.JWT_ALGORITHM,
        )
        unsub_url = f"https://api.rigacap.com/api/public/newsletter/unsubscribe?token={_unsub_tok}"

        market_stats = dashboard_data.get('market_stats') or {}
        regime_name = market_stats.get('regime_name', 'Unknown')
        spy_price = market_stats.get('spy_price')
        spy_change = market_stats.get('spy_change_pct')
        vix_level = market_stats.get('vix_level')

        market_context = dashboard_data.get('market_context') or ''

        buy_signals = dashboard_data.get('buy_signals') or []
        fresh_signals = [s for s in buy_signals if s.get('is_fresh')]
        fresh_count = len(fresh_signals)
        watchlist = dashboard_data.get('watchlist') or []

        # Build The Reading line — plain-English first, jargon in context.
        regime_glosses = {
            "Strong Bull": "broad rally across most sectors",
            "Weak Bull": "advancing, but leadership is narrow",
            "Rotating Bull": "broad market healthy, but sector leadership is churning",
            "Range Bound": "sideways, no clear trend commitment",
            "Weak Bear": "drifting lower on weak breadth",
            "Panic Crash": "sharp sell-off — system is defensive",
            "Recovery": "bouncing from the lows, rebuilding trend",
        }
        gloss = regime_glosses.get(regime_name, "")
        regime_line = (
            f"<strong>Regime: {regime_name}</strong>"
            + (f" — {gloss}." if gloss else ".")
        )
        reading_bits = [regime_line]

        if spy_price is not None:
            if spy_change is not None:
                direction = "up" if spy_change >= 0 else "down"
                reading_bits.append(
                    f"The S&amp;P 500 closed {direction} {abs(spy_change):.2f}% at ${spy_price:,.0f}."
                )
            else:
                reading_bits.append(f"The S&amp;P 500 closed at ${spy_price:,.0f}.")

        if vix_level is not None:
            if vix_level < 15:
                vix_label = "low"
            elif vix_level < 20:
                vix_label = "moderate"
            elif vix_level < 30:
                vix_label = "elevated"
            else:
                vix_label = "high"
            reading_bits.append(
                f"Market anxiety (the VIX) sits at {vix_level:.0f} — {vix_label}."
            )

        reading_line = " ".join(reading_bits)

        # Build watchlist line
        if watchlist:
            wl_count = len(watchlist)
            if show_symbols:
                wl_names = [w.get('symbol', '') for w in watchlist[:5]]
                wl_sentence = (
                    f"{wl_count} name{'s are' if wl_count != 1 else ' is'} "
                    f"approaching entry territory ({', '.join(wl_names)}). "
                    f"Any of them could fire in the coming days if the move confirms."
                )
            else:
                wl_sentence = (
                    f"{wl_count} name{'s are' if wl_count != 1 else ' is'} "
                    f"approaching entry territory right now. Subscribers see which "
                    f"ones — and get alerted the moment they fire."
                )
        else:
            wl_sentence = (
                "The watchlist is quiet this week — no names are within breakout range yet."
            )

        # Fresh-buy sentence — paid subscribers see symbols, free list sees counts
        if fresh_count == 0:
            buy_sentence = (
                "<strong>Fresh buy signals this week: 0.</strong><br><br>"
                "That's not a bug — it's the strategy working as designed. "
                f"{regime_name}s mean fewer stocks are in a genuine breakout at "
                "any given moment. Our algorithm requires multiple conditions "
                "to align simultaneously before firing, and this week, they didn't."
            )
        elif show_symbols:
            if fresh_count == 1:
                sym = fresh_signals[0].get('symbol', '')
                buy_sentence = (
                    f"<strong>Fresh buy signal this week: {sym}.</strong><br><br>"
                    "The conditions aligned for a single name — a genuine breakout "
                    "that cleared every gate our system requires before firing."
                )
            else:
                syms = ", ".join(s.get('symbol', '') for s in fresh_signals[:4])
                buy_sentence = (
                    f"<strong>Fresh buy signals this week: {fresh_count}.</strong><br><br>"
                    f"Multiple names aligned — {syms}. Each cleared every gate our "
                    "system requires before firing."
                )
        else:
            # Free list: reveal count only, conversion line
            word = "signal" if fresh_count == 1 else "signals"
            buy_sentence = (
                f"<strong>Fresh buy {word} this week: {fresh_count}.</strong><br><br>"
                f"{'A stock' if fresh_count == 1 else 'Multiple names'} cleared "
                "every gate our system requires before firing. Subscribers got "
                "the alerts at market open."
            )

        # Delayed-reveal track record block (free list only; paid already
        # sees live signals on the dashboard and doesn't need this)
        proof_block = ""
        if not show_symbols and last_weeks_fresh:
            rows = []
            for s in last_weeks_fresh[:3]:
                sym = s.get('symbol', '')
                entry = s.get('entry_price')
                curr = s.get('current_price')
                pnl = s.get('pnl_pct')
                entry_date = s.get('entry_date') or ''
                if pnl is None or entry is None or curr is None:
                    continue
                pnl_str = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
                pnl_color = "#059669" if pnl >= 0 else "#dc2626"
                rows.append(
                    f'<tr><td style="padding: 8px 12px; font-weight: 600;">{sym}</td>'
                    f'<td style="padding: 8px 12px; color: #6b7280;">{entry_date}</td>'
                    f'<td style="padding: 8px 12px; text-align: right;">${entry:.2f}</td>'
                    f'<td style="padding: 8px 12px; text-align: right;">${curr:.2f}</td>'
                    f'<td style="padding: 8px 12px; text-align: right; color: {pnl_color}; font-weight: 700;">{pnl_str}</td></tr>'
                )
            if rows:
                proof_block = f"""
        <tr><td style="padding: 28px 40px 0 40px;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 1px;">
                Recent Signals — How They're Doing
            </h2>
            <p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.6; color: #6b7280; font-style: italic;">
                The signals we called over the last couple of weeks, with how they've performed since entry. Subscribers got these in real time.
            </p>
            <table cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; font-size: 15px;">
                <thead><tr style="border-bottom: 2px solid #e5e7eb; color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">
                    <th style="padding: 8px 12px; text-align: left;">Ticker</th>
                    <th style="padding: 8px 12px; text-align: left;">Entered</th>
                    <th style="padding: 8px 12px; text-align: right;">Entry</th>
                    <th style="padding: 8px 12px; text-align: right;">Now</th>
                    <th style="padding: 8px 12px; text-align: right;">Since</th>
                </tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </td></tr>"""

        # § 01 · The Week in Focus
        s1_title = "What the system sees."
        s1_body = reading_line
        if market_context:
            s1_body += f"</p><p style=\"margin: 16px 0 0 0; font-size: 16px; line-height: 1.75; color: #141210;\">{market_context}"

        # § 02 · What the System is Doing
        s2_title = "What the system is doing."
        s2_body = buy_sentence
        s2_body += f"</p><p style=\"margin: 16px 0 0 0; font-size: 16px; line-height: 1.75; color: #141210;\"><strong>On the watchlist:</strong> {wl_sentence}"
        s2_body += "</p><p style=\"margin: 16px 0 0 0; font-size: 16px; line-height: 1.75; color: #141210;\"><strong>Still holding:</strong> existing positions continue to be managed by our standard risk discipline."

        # § 03 · The Anti-Pitch
        s3_title = "What the system is <em>not</em> doing."
        s3_items = [
            f"<strong>Chasing headlines.</strong> If a stock is in the news, it's usually too late for our system. We catch breakouts before they're obvious — that's the point of running math instead of reading Twitter.",
            f"<strong>Forcing trades.</strong> {fresh_count} signal{'s' if fresh_count != 1 else ''} this week. If it were zero, that would be fine. Quiet weeks are the system working as designed, not broken.",
            f"<strong>Predicting the macro.</strong> We don't forecast recessions, rate cuts, or elections. The regime detector reads what's happening now. When conditions change, so do we — but not before.",
        ]
        s3_list = "".join(
            f'<tr><td style="padding: 12px 0 12px 20px; border-top: 1px solid #DDD5C7; font-size: 16px; line-height: 1.75; color: #141210; position: relative;">'
            f'<span style="position: absolute; left: 0; color: #7A2430;">—</span>{item}</td></tr>'
            for item in s3_items
        )
        s3_list_html = f'<table cellpadding="0" cellspacing="0" style="width: 100%; margin: 16px 0;">{s3_list}<tr><td style="border-top: 1px solid #DDD5C7;"></td></tr></table>'

        # Section break helper
        section_break = '''
        <tr><td style="padding: 24px 40px;">
            <table cellpadding="0" cellspacing="0" style="width: 100%;"><tr>
                <td style="border-bottom: 1px solid #DDD5C7; width: 45%;"></td>
                <td style="text-align: center; font-size: 12px; color: #C4BAA9; letter-spacing: 6px; padding: 0 12px; white-space: nowrap;">···</td>
                <td style="border-bottom: 1px solid #DDD5C7; width: 45%;"></td>
            </tr></table>
        </td></tr>'''

        # Section number style
        sn = 'font-size: 12px; font-weight: 500; letter-spacing: 2px; color: #7A2430; text-transform: uppercase; margin: 0 0 10px 0;'
        sh = 'margin: 0 0 20px 0; font-size: 22px; font-weight: 500; letter-spacing: -0.3px; line-height: 1.2; color: #141210;'

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Georgia, 'Times New Roman', serif; background-color: #F5F1E8; color: #141210;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 640px; margin: 0 auto; background-color: #FAF7F0;">
        <!-- Masthead -->
        <tr>
            <td style="padding: 48px 40px 20px 40px; text-align: center; border-bottom: 2px solid #141210;">
                <p style="margin: 0 0 12px 0; font-size: 12px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #5A544E;">The Weekly Letter &middot; From RigaCap</p>
                <h1 style="margin: 0; font-size: 36px; font-weight: 400; color: #141210; letter-spacing: -0.5px;">
                    The Market, <em style="color: #7A2430;">Measured.</em>
                </h1>
                <p style="margin: 10px 0 0 0; font-size: 15px; color: #5A544E; font-style: italic;">
                    A weekly read of what the system is seeing, and why.
                </p>
            </td>
        </tr>

        <!-- Issue bar -->
        <tr>
            <td style="padding: 14px 40px; border-bottom: 1px solid #DDD5C7; font-size: 12px; letter-spacing: 1px; color: #8A8279;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;"><tr>
                    <td style="font-weight: 500; color: #141210;">{date_str.upper()}</td>
                    <td align="right">~5 min read</td>
                </tr></table>
            </td>
        </tr>

        <!-- § 01 · The Week in Focus -->
        <tr><td style="padding: 36px 40px 0 40px;">
            <p style="{sn}">&sect; 01 &middot; The Week in Focus</p>
            <h2 style="{sh}">{s1_title}</h2>
            <p style="margin: 0; font-size: 16px; line-height: 1.75; color: #141210;">
                {s1_body}
            </p>
        </td></tr>

        {section_break}

        <!-- § 02 · What the System is Doing -->
        <tr><td style="padding: 0 40px;">
            <p style="{sn}">&sect; 02 &middot; Signal Report</p>
            <h2 style="{sh}">{s2_title}</h2>
            <p style="margin: 0; font-size: 16px; line-height: 1.75; color: #141210;">
                {s2_body}
            </p>
        </td></tr>

        {proof_block}

        {section_break}

        <!-- § 03 · The Anti-Pitch -->
        <tr><td style="padding: 0 40px;">
            <p style="{sn}">&sect; 03 &middot; The Anti-Pitch</p>
            <h2 style="{sh}">{s3_title}</h2>
            <p style="margin: 0 0 4px 0; font-size: 16px; line-height: 1.75; color: #141210;">Right now, the system is:</p>
            {s3_list_html}
            <p style="margin: 0; font-size: 16px; line-height: 1.75; color: #141210; font-style: italic;">
                If you're looking for a system that does all of those things, this isn't it. What you're getting instead is a system that tries to do one thing very well and is transparent about what it won't do.
            </p>
        </td></tr>

        {section_break}

        <!-- § 04 · Signoff -->
        <tr><td style="padding: 0 40px;">
            <p style="{sn}">&sect; 04 &middot; A Note From Erik</p>
            <p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.75; color: #141210;">
                See you next Sunday.
            </p>
            <p style="margin: 0; font-size: 20px; font-style: italic; color: #7A2430;">
                &mdash; Erik
            </p>
        </td></tr>

        <!-- Subscribe box -->
        <tr><td style="padding: 36px 40px 0 40px;">
            <div style="background: #FAF7F0; border: 1px solid #C4BAA9; padding: 28px 24px; text-align: center;">
                <p style="margin: 0 0 6px 0; font-size: 18px; font-weight: 500; color: #141210;">
                    The Market, Measured. <em style="color: #7A2430;">Delivered Sundays.</em>
                </p>
                <p style="margin: 0 0 16px 0; font-size: 14px; color: #5A544E;">
                    Free. No spam. Unsubscribe anytime.
                </p>
                <a href="https://rigacap.com/newsletter" style="display: inline-block; background-color: #141210; color: #F5F1E8; text-decoration: none; padding: 12px 24px; font-size: 14px; font-weight: 500;">
                    Subscribe
                </a>
            </div>
        </td></tr>

        <!-- Product pitch -->
        <tr><td style="padding: 28px 40px 0 40px; border-top: 1px solid #DDD5C7; margin-top: 24px;">
            <p style="margin: 0; font-size: 15px; line-height: 1.65; color: #5A544E; font-style: italic;">
                RigaCap is a disciplined momentum signal service built by a former Chief Innovation Officer with 15 years of quantitative research. Walk-forward validated. Start free — no credit card, with full access for your first two weeks.
                <a href="https://rigacap.com" style="color: #7A2430;">Start free &rarr;</a>
            </p>
        </td></tr>

        {'' if show_symbols else '''<tr><td style="padding: 20px 40px 0 40px;">
            <div style="background: #ECE6D9; border-left: 3px solid #7A2430; padding: 14px 18px;">
                <p style="margin: 0; font-size: 13px; color: #5A544E;">
                    <em>Was this forwarded to you?</em>
                    &nbsp;<a href="https://rigacap.com/newsletter" style="color: #7A2430; font-weight: 500; text-decoration: none;">Subscribe — free, Sundays only&nbsp;&rarr;</a>
                </p>
            </div>
        </td></tr>'''}

        <tr><td style="padding: 32px 40px 32px 40px;">
            <p style="margin: 0; font-size: 12px; color: #8A8279; line-height: 1.6; font-style: italic; border-top: 1px solid #DDD5C7; padding-top: 16px;">
                <em>Market, Measured.</em> is a weekly reading from RigaCap. Data-backed, noise-free. Reply anytime — we read every response.
            </p>
            <p style="margin: 12px 0 0 0; font-size: 11px; color: #8A8279;">
                &copy; {date.year} RigaCap, LLC &middot; For information purposes only
                &nbsp;&middot;&nbsp;
                <a href="{unsub_url}" style="color:#8A8279;text-decoration:underline;">Unsubscribe</a>
            </p>
        </td></tr>
    </table>
</body>
</html>"""

        if spy_price is not None and spy_change is not None:
            spy_txt = f"up {abs(spy_change):.2f}% at ${spy_price:,.0f}" if spy_change >= 0 else f"down {abs(spy_change):.2f}% at ${spy_price:,.0f}"
        elif spy_price is not None:
            spy_txt = f"at ${spy_price:,.0f}"
        else:
            spy_txt = "—"
        vix_txt = f"{vix_level:.0f}" if vix_level is not None else "?"
        regime_txt = f"{regime_name}" + (f" — {gloss}" if gloss else "")
        text = f"""MARKET, MEASURED.
{date_str}

THE READING
Regime: {regime_txt}.
The S&P 500 closed {spy_txt}.
Market anxiety (the VIX) sits at {vix_txt}.

{('WHAT THE SYSTEM SEES' + chr(10) + market_context + chr(10) + chr(10)) if market_context else ''}
WHAT THE SYSTEM IS DOING
Fresh buy signals this week: {fresh_count}.
Watchlist: {len(watchlist)} names approaching entry territory.

WHAT WOULD CHANGE THINGS
— For more buys: broader rally conditions.
— For defensive: a broad-market breakdown would flip the regime.
— For now: stay patient.

Three-to-four signals a month, sometimes zero. We trade when the math is clear — not when the news is loud.

Start free — no credit card, full access for your first two weeks: https://rigacap.com
{('' if show_symbols else chr(10) + 'Was this forwarded to you? Subscribe — free, Sundays only: https://rigacap.com/?subscribe=market_measured#newsletter' + chr(10))}

---
Market, Measured. is a weekly reading from RigaCap.
"""

        subject = f"Market, Measured — {subject_date}"

        # Archive to S3 (once per date, keyed by date for web archive)
        try:
            import boto3, json as _json
            s3 = boto3.client("s3", region_name="us-east-1")
            archive_key = f"newsletter/issues/{date.strftime('%Y-%m-%d')}.json"
            s3.put_object(
                Bucket="rigacap-prod-price-data-149218244179",
                Key=archive_key,
                Body=_json.dumps({
                    "date": date_str,
                    "subject": subject,
                    "html": html,
                    "regime": regime_name,
                    "spy_price": spy_price,
                    "spy_change": spy_change,
                    "vix_level": vix_level,
                    "fresh_count": fresh_count,
                    "watchlist_count": len(watchlist),
                    "sections": [
                        {"num": "01", "label": "The Week in Focus", "title": s1_title, "body": s1_body},
                        {"num": "02", "label": "Signal Report", "title": s2_title, "body": s2_body},
                        {"num": "03", "label": "The Anti-Pitch", "title": "What the system is not doing.", "items": s3_items},
                        {"num": "04", "label": "A Note From Erik", "body": "See you next Sunday."},
                    ],
                }).encode(),
                ContentType="application/json",
            )
        except Exception as e:
            logger.warning(f"Newsletter archive failed: {e}")

        return await self.send_email(
            to_email, subject, html, text,
            user_id=user_id,
            list_unsubscribe_url=unsub_url,
            email_type="market_measured",
        )

    async def send_newsletter_from_draft(
        self, to_email: str, draft: dict, user_id: str = None
    ) -> bool:
        """Send a newsletter email built from the editor draft sections."""
        from jose import jwt as _jose_jwt
        from app.core.config import settings as _settings

        date = draft.get("date_display", draft.get("date", ""))
        subject_date = date
        sections = draft.get("sections", [])

        _unsub_tok = _jose_jwt.encode(
            {"email": to_email.strip().lower(), "report_type": "market_measured",
             "purpose": "newsletter_unsubscribe"},
            _settings.JWT_SECRET_KEY, algorithm=_settings.JWT_ALGORITHM,
        )
        unsub_url = f"https://api.rigacap.com/api/public/newsletter/unsubscribe?token={_unsub_tok}"

        sn = 'font-size: 12px; font-weight: 500; letter-spacing: 2px; color: #7A2430; text-transform: uppercase; margin: 0 0 10px 0;'
        sh = 'margin: 0 0 20px 0; font-size: 22px; font-weight: 500; letter-spacing: -0.3px; line-height: 1.2; color: #141210;'
        section_break = '''
        <tr><td style="padding: 24px 40px;">
            <table cellpadding="0" cellspacing="0" style="width: 100%;"><tr>
                <td style="border-bottom: 1px solid #DDD5C7; width: 45%;"></td>
                <td style="text-align: center; font-size: 12px; color: #C4BAA9; letter-spacing: 6px; padding: 0 12px; white-space: nowrap;">···</td>
                <td style="border-bottom: 1px solid #DDD5C7; width: 45%;"></td>
            </tr></table>
        </td></tr>'''

        # Build section HTML from draft
        section_html_parts = []
        for i, sec in enumerate(sections):
            num = sec.get("num", str(i + 1).zfill(2))
            label = sec.get("label", "")
            title = sec.get("title", "")
            body = sec.get("body", "")
            items = sec.get("items", [])

            part = f'<tr><td style="padding: {"36px" if i == 0 else "0"} 40px 0 40px;">'
            part += f'<p style="{sn}">&sect; {num} &middot; {label}</p>'
            if title:
                part += f'<h2 style="{sh}">{title}</h2>'

            if items:
                part += '<p style="margin: 0 0 4px 0; font-size: 16px; line-height: 1.75; color: #141210;">Right now, the system is:</p>'
                for item in items:
                    part += f'''<table cellpadding="0" cellspacing="0" style="width: 100%;"><tr>
                        <td style="padding: 12px 0 12px 20px; border-top: 1px solid #DDD5C7; font-size: 16px; line-height: 1.75; color: #141210; position: relative;">
                        <span style="position: absolute; left: 0; color: #7A2430;">&mdash;</span>{item}</td>
                    </tr></table>'''
                part += '<table cellpadding="0" cellspacing="0" style="width: 100%;"><tr><td style="border-top: 1px solid #DDD5C7;"></td></tr></table>'
                part += '<p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.75; color: #141210; font-style: italic;">If you\'re looking for a system that does all of those things, this isn\'t it. What you\'re getting instead is a system that tries to do one thing very well and is transparent about what it won\'t do.</p>'
            elif num == '04':
                part += f'<p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.75; color: #141210;">{body}</p>'
                part += '<div style="border-top: 1px solid #DDD5C7; padding-top: 16px; margin-top: 16px;">'
                part += '<p style="margin: 0; font-size: 20px; font-style: italic; color: #7A2430;">&mdash; Erik</p></div>'
            else:
                for para in body.split("\n\n"):
                    para = para.strip()
                    if para:
                        part += f'<p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.75; color: #141210;">{para}</p>'

            part += '</td></tr>'
            section_html_parts.append(part)

        sections_html = section_break.join(section_html_parts)

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; font-family: Georgia, 'Times New Roman', serif; background-color: #F5F1E8; color: #141210;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 640px; margin: 0 auto; background-color: #FAF7F0;">
        <tr>
            <td style="padding: 48px 40px 20px 40px; text-align: center; border-bottom: 2px solid #141210;">
                <p style="margin: 0 0 12px 0; font-size: 12px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #5A544E;">The Weekly Letter &middot; From RigaCap</p>
                <h1 style="margin: 0; font-size: 36px; font-weight: 400; color: #141210; letter-spacing: -0.5px;">
                    The Market, <em style="color: #7A2430;">Measured.</em>
                </h1>
                <p style="margin: 10px 0 0 0; font-size: 15px; color: #5A544E; font-style: italic;">
                    A weekly read of what the system is seeing, and why.
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding: 14px 40px; border-bottom: 1px solid #DDD5C7; font-size: 12px; letter-spacing: 1px; color: #8A8279;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;"><tr>
                    <td style="font-weight: 500; color: #141210;">{date.upper()}</td>
                    <td align="right">~5 min read</td>
                </tr></table>
            </td>
        </tr>

        {sections_html}

        <tr><td style="padding: 36px 40px 0 40px;">
            <div style="background: #FAF7F0; border: 1px solid #C4BAA9; padding: 28px 24px; text-align: center;">
                <p style="margin: 0 0 6px 0; font-size: 18px; font-weight: 500; color: #141210;">
                    The Market, Measured. <em style="color: #7A2430;">Delivered Sundays.</em>
                </p>
                <p style="margin: 0 0 16px 0; font-size: 14px; color: #5A544E;">Free. No spam. Unsubscribe anytime.</p>
                <a href="https://rigacap.com/newsletter" style="display: inline-block; background-color: #141210; color: #F5F1E8; text-decoration: none; padding: 12px 24px; font-size: 14px; font-weight: 500;">Subscribe</a>
            </div>
        </td></tr>

        <tr><td style="padding: 28px 40px 0 40px; border-top: 1px solid #DDD5C7; margin-top: 24px;">
            <p style="margin: 0; font-size: 15px; line-height: 1.65; color: #5A544E; font-style: italic;">
                RigaCap is a disciplined momentum signal service. Walk-forward validated. Start free — no credit card, with full access for your first two weeks.
                <a href="https://rigacap.com" style="color: #7A2430;">Start free &rarr;</a>
            </p>
        </td></tr>

        <tr><td style="padding: 32px 40px 32px 40px;">
            <p style="margin: 0; font-size: 12px; color: #8A8279; line-height: 1.6; font-style: italic; border-top: 1px solid #DDD5C7; padding-top: 16px;">
                <em>Market, Measured.</em> is a weekly reading from RigaCap. Data-backed, noise-free. Reply anytime — we read every response.
            </p>
            <p style="margin: 12px 0 0 0; font-size: 11px; color: #8A8279;">
                &copy; 2026 RigaCap, LLC &middot; For information purposes only
                &nbsp;&middot;&nbsp;
                <a href="{unsub_url}" style="color:#8A8279;text-decoration:underline;">Unsubscribe</a>
            </p>
        </td></tr>
    </table>
</body>
</html>"""

        subject = f"Market, Measured — {subject_date}"
        return await self.send_email(
            to_email, subject, html, "",
            user_id=user_id,
            list_unsubscribe_url=unsub_url,
            email_type="newsletter",
        )

    async def send_bulk_daily_summary(
        self,
        subscribers: List[str],
        signals: List[Dict],
        market_regime: Dict
    ) -> Dict:
        """
        Send daily summary to all subscribers

        Args:
            subscribers: List of subscriber emails
            signals: Today's signals
            market_regime: Current market regime

        Returns:
            Summary of sent/failed emails
        """
        sent = 0
        failed = 0

        for email in subscribers:
            try:
                # TODO: Fetch user-specific positions and missed opportunities
                success = await self.send_daily_summary(
                    to_email=email,
                    signals=signals,
                    market_regime=market_regime
                )
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to send to {email}: {e}")
                failed += 1

            # Rate limiting - don't spam SMTP server
            await asyncio.sleep(0.5)

        logger.info(f"Bulk email complete: {sent} sent, {failed} failed")
        return {"sent": sent, "failed": failed, "total": len(subscribers)}


    async def send_welcome_email(self, to_email: str, name: str, referral_code: str = None, user_id: str = None, is_founding: bool = False) -> bool:
        """
        Welcome email — fired on subscription creation (we know founder vs
        standard by then). is_founding gates the founding-member acknowledgment;
        the rest (capital-preservation thesis) is shared. NON-founders must never
        see founding-rate language (Erik Jun 23 — there's a full-price route that
        is NOT founding).
        """
        first_name = name.split()[0] if name else "there"

        # Founder-only acknowledgment block (top of the email).
        founder_html = ""
        founder_text = ""
        if is_founding:
            founder_html = """
                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0; margin: 0 0 24px;">
                    <p style="margin: 0; font-size: 16px; color: #141210; line-height: 1.6;">
                        You're in &mdash; and you're a <strong>founding member</strong>. Your rate is locked at <strong>$59/month for a full year</strong>, while everyone after the first 100 pays $129. Thank you for betting early.
                    </p>
                </div>"""
            founder_text = "You're a FOUNDING MEMBER — your rate is locked at $59/month for a year (everyone after the first 100 pays $129). Thank you for betting early.\n\n"

        referral_html = ""
        referral_text = ""
        if referral_code:
            referral_html = f'''
                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 28px 0; text-align: center;">
                    <p style="margin: 0 0 8px; font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">Give a Month, Get a Month</p>
                    <p style="margin: 0 0 12px; font-size: 14px; color: #141210; line-height: 1.5;">
                        Share your link with a friend. They get their first month free, you get a free month when they subscribe.
                    </p>
                    <div style="background: #FAF7F0; border: 1px solid #DDD5C7; padding: 10px; margin: 0 auto; max-width: 400px;">
                        <p style="margin: 0; font-family: 'Courier New', monospace; font-size: 13px; color: #141210; word-break: break-all;">
                            rigacap.com/?ref={referral_code}
                        </p>
                    </div>
                </div>
'''
            referral_text = f"""
--- GIVE A MONTH, GET A MONTH ---
Share your referral link: rigacap.com/?ref={referral_code}
Your friend gets their first month free, and you get a free month when they subscribe!
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #F5F1E8; -webkit-font-smoothing: antialiased;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto;">
        <!-- Header -->
        <tr>
            <td style="padding: 32px 32px 0;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; border-bottom: 2px solid #141210; padding-bottom: 20px;">
                    <tr>
                        <td><img src="https://rigacap.com/email-header.png" alt="RigaCap." width="240" height="58" style="display: block; width:240px; height:auto;" /></td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; color: #3A342E; letter-spacing: 1.2px; text-transform: uppercase;">Welcome</td>
                    </tr>
                </table>
            </td>
        </tr>

        <!-- Welcome Message -->
        <tr>
            <td style="padding: 32px;">
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    {first_name},
                </p>

                {founder_html}

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Here's what you actually bought, and it isn't a hot-stock newsletter: RigaCap is built to do one thing exceptionally well &mdash; <strong>keep you invested through the part of the cycle where most people sell at the bottom.</strong> I built it because I got tired of overriding my own rules in a drawdown. The system doesn't have that problem.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Here's the whole point in one line: <strong>market-beating-or-matching returns, at a fraction of the pain.</strong> In 2008, the S&amp;P 500 fell about 37%. <strong>RigaCap finished roughly flat — about +0.1% — while the market halved.</strong> That's the asymmetry the engine is built for, on both settings.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    It's not a one-year fluke. In the modern era (2021&ndash;26), <strong>Preserver</strong> compounded about <strong>13.0% a year with a &minus;12.9% worst drawdown</strong>; the <strong>Maximizer add-on</strong> ran <strong>~31.4% a year at &minus;14.9%</strong>. Over the full 21-year walk-forward record, Maximizer's worst drawdown was <strong>&minus;20.8%</strong> at <strong>13.5% a year</strong> &mdash; roughly the return of raw momentum, but with about two-thirds of the drawdown cut away. Preserver held its worst drawdown to <strong>&minus;13.7%</strong> while the S&amp;P lost more than half its value <em>twice</em>. When the market has a bad month, these barely flinch: Preserver falls about &minus;1.0% and Maximizer &minus;1.0% for every &minus;3.9% the S&amp;P drops.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    That's <strong>Preserver</strong>, your base plan &mdash; the gentle path, built so <strong>you never get a reason to sell at the bottom.</strong> When you want more offense, <strong>Maximizer</strong> is a <strong>+$100/mo add-on</strong> (+$79 at the introductory rate) you can toggle on anytime &mdash; the same engine, dialed up. One knob, your call.
                    <a href="https://rigacap.com/track-record" style="color: #7A2430; text-decoration: underline;">See the full track record.</a>
                </p>

                <!-- What You Get -->
                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 28px 0;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Signals after every close: ticker, entry, and a trailing stop that only rises</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Daily 6 PM ET digest: the market read and the model's positions</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— A regime filter that steps to cash when the market turns hostile</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Portfolio tracking · quiet when nothing qualifies</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Works with any broker — you execute, we signal</td></tr>
                    </table>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 24px 0; line-height: 1.65;">
                    <strong>You're subscribed — full access is live.</strong> Your daily digest lands around 6 PM ET on every trading day, and you're covered by a <strong>30-day money-back guarantee</strong> — if it's not for you, just reply and I'll refund you, no friction.
                </p>

                <!-- CTA -->
                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        View Today's Signals
                    </a>
                </div>

                {referral_html}

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">
                    Reply to this email anytime — it comes straight to me. — Erik
                </p>
            </td>
        </tr>

        <!-- Footer -->
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>
"""

        text = f"""
{first_name},

{founder_text}Here's what you actually bought, and it isn't a hot-stock newsletter: RigaCap is built to do one thing exceptionally well — keep you invested through the part of the cycle where most people sell at the bottom. I built it because I got tired of overriding my own rules in a drawdown. The system doesn't have that problem.

Here's the whole point in one line: market-beating-or-matching returns, at a fraction of the pain. In 2008, the S&P 500 fell about 37%. RigaCap finished roughly flat — about +0.1% — while the market halved. That's the asymmetry the engine is built for, on both settings.

It's not a one-year fluke. In the modern era (2021-26), Preserver compounded about 13.0% a year with a -12.9% worst drawdown; the Maximizer add-on ran ~31.4% a year at -14.9%. Over the full 21-year walk-forward record, Maximizer's worst drawdown was -20.8% at 13.5% a year — roughly the return of raw momentum, but with about two-thirds of the drawdown cut away. Preserver held its worst drawdown to -13.7% while the S&P lost more than half its value twice. When the market has a bad month, these barely flinch: Preserver falls about -1.0% and Maximizer -1.0% for every -3.9% the S&P drops.

That's Preserver, your base plan — the gentle path, built so you never get a reason to sell at the bottom. When you want more offense, Maximizer is a +$100/mo add-on (+$79 at the introductory rate) you can toggle on anytime — the same engine, dialed up. One knob, your call. See the full track record: https://rigacap.com/track-record

What you get:
- Signals after every close: ticker, entry, and a trailing stop that only rises
- Daily 6 PM ET digest: the market read and the model's positions
- A regime filter that steps to cash when the market turns hostile
- Portfolio tracking; quiet when nothing qualifies
- Works with any broker — you execute, we signal

You're subscribed — full access is live. Your daily digest lands around 6 PM ET on every trading day, and you're covered by a 30-day money-back guarantee — if it's not for you, just reply and I'll refund you, no friction. Visit https://rigacap.com/app to see today's signals.
{referral_text}
Reply to this anytime — it comes straight to me. — Erik

---
For information purposes only. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
"""

        return await self.send_email(
            to_email=to_email,
            subject="Welcome to RigaCap",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="welcome",
        )

    async def send_free_welcome_email(self, to_email: str, name: str = "", user_id: str = None) -> bool:
        """At-signup 'you're in' confirmation — fires the instant a free-first account is created
        (all 3 register paths), BEFORE any Stripe conversion. Distinct from:
          - send_welcome_email  → the PAID welcome (fires on subscription-created), and
          - send_onboarding_email step 1 → the meaty how-to-act note that lands ~10 AM ET next day.
        This one is deliberately short: an immediate receipt that says access is live now, one CTA
        to open the dashboard, light expectations, and the honest day-14 shape. No card, no fabrication."""
        first_name = name.split()[0] if name else "there"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Welcome &mdash; your RigaCap account is live, and so is your full access. No card, nothing to set up: for the <strong>next two weeks</strong> you can see everything the paid product shows &mdash; every live signal, both settings (<strong>Preserver</strong> and the <strong>Maximizer</strong> add-on), the daily market read, and the model's positions.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0 0 4px; font-family: 'Courier New', monospace; font-size: 10px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #5A544E;">What Happens Next</p>
                    <ul style="margin: 12px 0 0; padding: 0 0 0 20px; color: #141210; line-height: 1.9; font-size: 15px;">
                        <li><strong>Right now</strong> &mdash; open your dashboard and see exactly what the model is holding today.</li>
                        <li><strong>~6 PM ET, every trading day</strong> &mdash; your daily digest lands: the market read, the model's moves, and any new signals. When nothing qualifies, it says so.</li>
                        <li><strong>Over the next few days</strong> &mdash; I'll send a short series of notes on how to actually act on a signal at your own broker. RigaCap sends signals; it never touches your money.</li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Open Your Dashboard
                    </a>
                </div>

                <p style="font-size: 15px; color: #5A544E; margin: 0 0 24px; line-height: 1.6;">
                    One thing worth knowing now: your full live access runs through <strong>day 14</strong>. After that your view settles onto the proof floor &mdash; the full track record and closed results, minus the live names &mdash; and you can unlock the full product anytime. I'll remind you before anything changes; nothing disappears without warning.
                </p>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">
                    Reply to this email anytime &mdash; it comes straight to me. &mdash; Erik
                </p>"""
        html = self._email_wrapper("Welcome", content, user_id)

        text = f"""{first_name},

Welcome — your RigaCap account is live, and so is your full access. No card, nothing to set up: for the next two weeks you can see everything the paid product shows — every live signal, both settings (Preserver and the Maximizer add-on), the daily market read, and the model's positions.

WHAT HAPPENS NEXT
- Right now — open your dashboard and see exactly what the model is holding today: https://rigacap.com/app
- ~6 PM ET, every trading day — your daily digest lands: the market read, the model's moves, and any new signals. When nothing qualifies, it says so.
- Over the next few days — I'll send a short series of notes on how to actually act on a signal at your own broker. RigaCap sends signals; it never touches your money.

One thing worth knowing now: your full live access runs through day 14. After that your view settles onto the proof floor — the full track record and closed results, minus the live names — and you can unlock the full product anytime. I'll remind you before anything changes; nothing disappears without warning.

Reply to this email anytime — it comes straight to me. — Erik
"""

        return await self.send_email(
            to_email=to_email,
            subject="Welcome to RigaCap — you're in",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="free_welcome",
        )

    async def send_verification_email(self, to_email: str, name: str, verify_url: str) -> bool:
        """Confirm-your-email link. Verifying unlocks live brokerage connect for trial users."""
        first_name = name.split()[0] if name else "there"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    One quick step to confirm this is really you. Verifying your email unlocks
                    connecting your brokerage so the Mirror can show how your holdings line up with
                    the book.
                </p>
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{verify_url}"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Verify Email
                    </a>
                </div>
                <p style="font-size: 14px; color: #8A8279; margin: 0 0 16px; line-height: 1.5;">
                    This link expires in 48 hours. If you didn't create a RigaCap account, you can
                    safely ignore this email.
                </p>
                <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 16px 0 0; word-break: break-all;">
                    {verify_url}
                </p>"""
        html = self._email_wrapper("Confirm your email", content)

        text = f"""Confirm your email

Hey {first_name}, one quick step to confirm this is really you. Verifying unlocks connecting your brokerage to the Mirror.

Verify here:
{verify_url}

This link expires in 48 hours. If you didn't create a RigaCap account, you can safely ignore this email.

— The RigaCap Team"""

        return await self.send_email(
            to_email=to_email,
            subject="Confirm your email for RigaCap",
            html_content=html,
            text_content=text,
        )

    async def send_password_reset_email(self, to_email: str, name: str, reset_url: str) -> bool:
        """Send a password reset email with a time-limited link."""
        first_name = name.split()[0] if name else "there"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    We received a request to reset your password. Click below to choose a new one:
                </p>
                <div style="text-align: center; margin: 32px 0;">
                    <a href="{reset_url}"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Reset Password
                    </a>
                </div>
                <p style="font-size: 14px; color: #8A8279; margin: 0 0 16px; line-height: 1.5;">
                    This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
                </p>
                <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 16px 0 0; word-break: break-all;">
                    {reset_url}
                </p>"""
        html = self._email_wrapper("Password Reset", content)

        text = f"""Reset Your Password

Hey {first_name}, we received a request to reset your password.

Click this link to choose a new one:
{reset_url}

This link expires in 1 hour. If you didn't request this, you can safely ignore this email.

— The RigaCap Team"""

        return await self.send_email(
            to_email=to_email,
            subject="Reset your RigaCap password",
            html_content=html,
            text_content=text
        )

    async def send_trial_ending_email(
        self,
        to_email: str,
        name: str,
        days_remaining: int = 2,
        signals_generated: int = 0,
        strong_signals_seen: int = 0,
        user_id: str = None
    ) -> bool:
        """
        Send a 'your trial is ending soon' email to nudge conversion.

        Args:
            to_email: User email
            name: User's full name
            days_remaining: Days left in trial (typically 2 or 1)
            signals_generated: Total signals generated during their trial
            strong_signals_seen: Strong signals they received
        """
        first_name = name.split()[0] if name else "there"
        urgency = "tomorrow" if days_remaining == 1 else f"in {days_remaining} days"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">{first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Your free trial ends <strong>{urgency}</strong>. After that, you'll lose access to signals, regime detection, and position guidance.
                </p>

                {f'''<table cellpadding="0" cellspacing="0" style="width:100%; border-top:1px solid #141210; border-bottom:1px solid #DDD5C7; margin:28px 0;">
                <tr>
                    <td style="width:50%; padding:16px 0; text-align:center; border-right:1px solid #DDD5C7;">
                        <div style="font-family:Georgia,serif; font-size:32px; color:#141210;">{signals_generated}</div>
                        <div style="font-family:'Courier New',monospace; font-size:10px; color:#8A8279; margin-top:4px; letter-spacing:2px; text-transform:uppercase;">Signals generated</div>
                    </td>
                    <td style="width:50%; padding:16px 0; text-align:center;">
                        <div style="font-family:Georgia,serif; font-size:32px; color:#141210;">{strong_signals_seen}</div>
                        <div style="font-family:'Courier New',monospace; font-size:10px; color:#8A8279; margin-top:4px; letter-spacing:2px; text-transform:uppercase;">Strong signals</div>
                    </td>
                </tr></table>''' if signals_generated > 0 else ''}

                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.6;">
                        Preserver, the base plan, compounded 7.7% a year across a 21-year walk-forward — worst drawdown just 13.7% while the index lost half its value twice. Add the Maximizer setting (+$100/mo, +$79 introductory) and the same engine ran 13.5% a year at a -20.8% worst drawdown. The live record began June 2026.
                        <a href="https://rigacap.com/track-record" style="color: #7A2430; text-decoration: underline;">Full track record.</a>
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Subscribe — $59/month founding
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">Founding rate while seats remain · $129/month standard · or $1,099/year</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">
                    Reply to this email if you have questions. — Erik
                </p>"""

        html = self._email_wrapper(f"Trial ends {urgency}", content, user_id)

        text = f"""{first_name}, your RigaCap free trial ends {urgency}. Subscribe at rigacap.com/#pricing to keep access. $129/month or $1,099/year. Reply with questions. — Erik"""

        day_word = "Tomorrow" if days_remaining == 1 else f"in {days_remaining} Days"
        return await self.send_email(
            to_email=to_email,
            subject=f"RigaCap — Your trial ends {urgency}",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="trial_ending",
        )

    async def send_goodbye_email(self, to_email: str, name: str, user_id: str = None) -> bool:
        """
        Send a 'sorry to see you go' email when a user cancels or trial expires.
        """
        first_name = name.split()[0] if name else "there"

        import secrets
        promo_code = f"WELCOME-{secrets.token_hex(3).upper()}"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">{first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Your subscription has ended. The system is still running — signals, regime detection, trailing stops — all operating without you.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    If something wasn't right, reply and tell me. I read every response.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.6;">
                        The hardest work of investing isn't the analysis. It's executing boring rules consistently. That's what you were paying for.
                    </p>
                </div>



                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Reactivate
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">— Erik</p>"""

        html = self._email_wrapper("We'll be here", content, user_id)

        text = f"""{first_name}, your RigaCap subscription has ended. The door stays open — same price as everyone. Reply if something wasn't right. — Erik"""

        return await self.send_email(
            to_email=to_email,
            subject="RigaCap — the system is still running",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="goodbye",
        )


    async def send_onboarding_email(self, step: int, to_email: str, name: str, user_id: str = None) -> bool:
        """
        Send an onboarding drip email for the free-first lifecycle.

        New signup = 30-day no-card trial with FULL live access (both books)
        for the first 14 days (TRIAL_FULL_DAYS), then access decays to the
        proof floor (record + closed winners, no live names). Users
        auto-mirror the model book — there is no manual record-entry
        workflow. Signals only; subscribers execute at their own broker.

        Day-based schedule (see scheduler.send_onboarding_drip_emails):
          Step 1 (Day 1):  Welcome — you're in, full access, how to act + sync your broker
          Step 2 (Day 3):  One engine, two settings — Preserver vs Maximizer
          Step 3 (Day 7):  Your first week, graded — value reinforcement, still full access
          Step 4 (Day 12): CONVERSION (urgency) — full access winds down in 2 days, subscribe to keep it
          Step 5 (Day 15): Access wound down — you're on the proof view now, unlock to get live back
          Step 6 (Day 22): Proof + last nudge — a real closed winner, 30-day money-back, final ask

        Steps 1-3 send regardless of subscription status; steps 4-6 are
        upgrade asks and skip already-converted (active) subscribers.
        """
        first_name = name.split()[0] if name else "there"

        # Day/time-aware first-digest timing: the daily digest sends ~6 PM ET on trading days, so a
        # welcome landing on a weekday morning means the first digest is THIS evening, not "tomorrow".
        def _next_digest_phrase():
            from datetime import datetime as _dt, timedelta as _td
            from zoneinfo import ZoneInfo as _ZI
            now = _dt.now(_ZI("America/New_York"))
            if now.weekday() <= 4 and now.hour < 18:   # weekday before the 6 PM send
                return "This evening"
            d = now + _td(days=1)
            while d.weekday() > 4:                       # skip to the next weekday
                d += _td(days=1)
            return "Tomorrow evening" if (d.date() - now.date()).days == 1 else d.strftime("%A") + " evening"
        digest_when = _next_digest_phrase()

        subjects = {
            1: "You're in — full access starts now",
            2: "One engine, two settings",
            3: "Your first week, graded",
            4: "Your live access winds down in 2 days",
            5: "You're on the proof view now",
            6: "We called it — proof, and one last door",
        }

        subject = f"RigaCap — {subjects.get(step, 'RigaCap')}"

        content_blocks = {
            1: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    You're in. From today you have <strong>full access to both books</strong> — every live signal, both settings — for your trial. No card, nothing to configure. This first note is the only one you really need to read closely, because it tells you how to act on what you see.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0 0 4px; font-family: 'Courier New', monospace; font-size: 10px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #5A544E;">The Daily Rhythm</p>
                    <ol style="margin: 12px 0 0; padding: 0 0 0 20px; color: #141210; line-height: 2; font-size: 15px;">
                        <li><strong>4:30 PM ET, every market day</strong> — the system scans after the close</li>
                        <li><strong>Every evening</strong> — you get the daily digest: the market read, the model's positions, and any new moves</li>
                        <li><strong>If a stock qualifies</strong> — it's in that email in full, and a signal card appears on your dashboard</li>
                        <li><strong>If nothing qualifies</strong> — the digest says so, and the model holds cash. "Nothing today" is an output, stated out loud.</li>
                    </ol>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Here's the part that surprises people: <strong>there's no manual bookkeeping.</strong> Your view auto-mirrors the model book — when the model enters or exits, your dashboard updates. You never mark a trade "done" or key in a fill. The system keeps the record; you keep the returns.
                </p>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    What you <em>do</em> is act at your own broker — RigaCap sends signals, it never touches your money. Say tomorrow's scan flags ABC at $42. The email lands that evening with the entry, the current stop level, and the position weight. At your broker — next morning is fine, this isn't a race — you place the buy and close the laptop. You don't set stop orders and there's nothing to watch intraday: <em>the system</em> tracks the trailing stop, ratcheting it up as the stock rises. If price ever breaches it, you get a sell alert that says so plainly — sell ABC, here's why. Dial toward Maximizer and the breakout book runs the same way at your broker — you just place the buys it flags; the only difference is the exit, which comes on a 29-day time-stop rather than a trailing stop, with the same plain sell alert when the clock's up. That's the whole judgment call. There isn't one.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">Entry Signal</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Ticker, entry price, current stop level, position weight — you place it at your broker</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">Sell Alert</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Stop breached — exit, no second-guessing</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    A note on the shape of your trial, so nothing catches you off guard: you have full live access — every current name, both books — through <strong>day 14</strong>. I'll remind you before it changes. For now, open the dashboard and see what the model is actually holding today.
                </p>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Open Your Dashboard
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    {digest_when} you'll get your first daily digest (it lands ~6 PM ET on trading days). In a couple of days I'll explain how the two settings work — Preserver's the base, Maximizer's the add-on when you want more.
                </p>
            """,
            2: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    You've seen a digest or two by now. Here's how the product is built: it's <strong>one engine, two settings</strong> — the same signal machinery, tuned for two different jobs. <strong>Preserver is the base plan.</strong> Maximizer is a <strong>+$100/mo add-on</strong> (+$79/mo at the introductory rate) you can toggle on or off anytime — it's not an either/or you pick for the same price. Both are open to you during the trial so you can feel the difference before you decide.
                </p>

                <div style="border-top: 1px solid #DDD5C7; padding: 20px 0;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #7A2430; margin: 0 0 8px;">Preserver &middot; the base plan</p>
                    <p style="font-family: Georgia, serif; font-size: 18px; color: #141210; margin: 0 0 8px; font-weight: 500;">Built to protect capital first.</p>
                    <p style="font-size: 15px; color: #5A544E; margin: 0; line-height: 1.6;">A wide 30% trailing stop lets positions breathe through normal noise and gets you out before a real break turns into a rout. It gives up bull-market bragging rights to almost never hand you a reason to panic. If your instinct is "don't lose the money," this is where you start.</p>
                </div>

                <div style="border-top: 1px solid #DDD5C7; padding: 20px 0;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #7A2430; margin: 0 0 8px;">Maximizer &middot; a +$100/mo add-on</p>
                    <p style="font-family: Georgia, serif; font-size: 18px; color: #141210; margin: 0 0 8px; font-weight: 500;">Built to grow — with a seatbelt.</p>
                    <p style="font-size: 15px; color: #5A544E; margin: 0; line-height: 1.6;">Leans into breakouts and adds a volatility brake that pulls in when conditions get rough, plus a 29-day time-stop so capital doesn't sit dead in a name that stalls. More drawdown than Preserver, more upside in trending markets. It's an add-on that runs on top of Preserver — <strong>+$100/mo (+$79/mo at the introductory rate), toggle it on or off anytime.</strong> If your instinct is "put it to work," add this.</p>
                </div>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.6;">
                        Same product, graded two ways: an F for someone trying to beat the market every year, an A for someone trying to preserve and compound. The grade depends on who's holding it — which is exactly why Preserver is the base, and the offense is an add-on you switch on only if it fits you.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Reading the digest is simple once you know this. <strong>"Today's Moves"</strong> is just the sync list: what the model bought, what it sold. You mirror those at your broker to stay in step. Green means a new entry to place; a sell alert means close a position. Nothing listed means nothing to do — hold.
                </p>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        See Both Books
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    You don't have to decide today — both are live for you this week. Start noticing whether Preserver alone is enough, or whether you'd want the Maximizer add-on switched on too.
                </p>
            """,
            3: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    One week in. This note is just a checkpoint — no ask attached. You still have <strong>full live access to both books</strong>, and I want you to get the most out of the days that are left.
                </p>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Look back at what actually happened this week rather than what a chart might have tempted you to do. A few honest questions worth sitting with:
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">The Regime</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">What did the market read say each evening — was the model leaning in, or holding cash?</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">The Book</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Did any signals fire? Did a stop move up under a position you were watching?</div>
                        </td>
                    </tr>
                </table>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.6;">
                        If your week was quiet, that's not a dead product — it's the discipline showing. The system only buys when its conditions are met and holds cash otherwise. Learning to sit still through a quiet stretch is most of what you're here to practice.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    The most useful thing you can do with the rest of your full-access window is watch how the model behaves and check it against your own instincts. When did you feel the itch to override it? Note that. That gap — between what you'd have done and what the system did — is the whole reason this exists.
                </p>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Review Your Week
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Anything unclear about what you're seeing? Reply — it comes straight to me. — Erik
                </p>
            """,
            4: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Straight to it: <strong>your full live access winds down in 2 days.</strong> On day 14 the live signals switch off. After that you keep an honest proof view — the record and the closed winners — but the current names, both books, and the exit alerts go quiet unless you subscribe.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 17px; color: #141210; line-height: 1.65;">
                        The signals only help if you can see them the evening they fire — not a week later as a case study. That's the whole thing you'd be keeping: today's moves, in real time, while there's still time to act on them.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Subscribe before day 14 and nothing changes — the live signals, both books, and the sell alerts stay on without a gap. Wait, and you'll be looking at yesterday's winners instead of today's setups.
                </p>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E; margin: 0 0 8px;">What You Keep</p>
                    <p style="font-family: Georgia, serif; font-size: 22px; color: #141210; margin: 0 0 6px;">Live signals · both books · exit alerts</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0; line-height: 1.7;">Introductory rate, locked 12 months · 30-day money-back<br>Preserver is the base · add Maximizer for +$100/mo (+$79 introductory), toggle anytime</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 16px 40px; text-decoration: none;">
                        Keep My Access
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">Introductory pricing · 12-month lock · 30-day money-back guarantee</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    If you're on the fence, reply and tell me what's holding you up — it comes straight to me. — Erik
                </p>
            """,
            5: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Your full-access window closed, so I'll be straight about what changed. <strong>You're on the proof view now.</strong> Not a lockout — you can still open the dashboard, still see the live record as it posts, still see the closed winners the model has booked. What you can't see anymore are the live calls: today's entries, the current positions in each book, and the sell alerts.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 17px; color: #141210; line-height: 1.65;">
                        The proof view is there so you can keep checking our homework — the record posts publicly, good or bad. But a record you can only read after the fact doesn't help your account. The live signals do.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    If the two weeks were enough to tell you this isn't your product, let it rest here — no hard feelings, and the proof view stays open if you want to keep watching from a distance. If they told you the opposite, one click puts the live signals, both books, and the exit alerts back on.
                </p>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E; margin: 0 0 8px;">Unlock The Live Calls</p>
                    <p style="font-family: Georgia, serif; font-size: 22px; color: #141210; margin: 0 0 6px;">Introductory rate, locked 12 months</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0;">30-day money-back · Preserver base, add Maximizer for +$100/mo (+$79 introductory)</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Get The Live Signals Back
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    If something specific didn't land during the trial, reply and tell me. I read every response. — Erik
                </p>
            """,
            6: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Last note from me on this. Rather than argue, I'll just show you one. Since your access wound down, the model closed a position the way it's supposed to — let a winner run, then booked it when the trail said so. This is the kind of call the live signals put in front of subscribers the evening it happens.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 2px solid #141210; border-bottom: 1px solid #141210; margin: 28px 0;">
                    <tr>
                        <td style="padding: 16px 16px 16px 0; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">We Called It</div>
                            <div style="font-family: Georgia, serif; font-size: 22px; color: #141210; margin-top: 4px;">Closed Winner</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; color: #6B6356; margin-top: 2px;">On the public record</div>
                        </td>
                        <td style="padding: 16px; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">Entered</div>
                            <div style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin-top: 4px;">On signal</div>
                        </td>
                        <td style="padding: 16px 0 16px 16px; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E;">Exited</div>
                            <div style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin-top: 4px;">On the trail</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 15px; color: #5A544E; margin: 0 0 24px 0; line-height: 1.6;">
                    You can see the closed winners on your proof view right now — that part never left. What the proof view can't give you is the next one, in time to act on it. That's the only thing behind the subscription.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.65;">
                        And if you subscribe and it turns out I'm wrong for you — you have 30 days to get every dollar back. The whole risk of trying it is a couple of clicks. The risk of the alternative is being the person who read the record and still watched the next call from the sidelines.
                    </p>
                </div>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E; margin: 0 0 8px;">The Offer, Plainly</p>
                    <p style="font-family: Georgia, serif; font-size: 22px; color: #141210; margin: 0 0 6px;">Introductory rate, locked 12 months</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0;">30-day money-back · Preserver base, add Maximizer for +$100/mo (+$79 introductory)</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 16px 40px; text-decoration: none;">
                        Turn The Live Signals Back On
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">30-day money-back guarantee · cancel anytime</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Whatever you decide, thank you for giving it a real look. If it's a no, this is the last you'll hear on it. — Erik
                </p>
            """,
        }

        content = content_blocks.get(step, "")
        if not content:
            logger.warning(f"Unknown onboarding step: {step}")
            return False

        header_title = subjects.get(step, 'RigaCap')

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #F5F1E8; -webkit-font-smoothing: antialiased;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto;">
        <tr>
            <td style="padding: 32px 32px 0;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; border-bottom: 2px solid #141210; padding-bottom: 20px;">
                    <tr>
                        <td>
                            <img src="https://rigacap.com/email-header.png" alt="RigaCap." width="240" height="58" style="display: block; width:240px; height:auto;" />
                        </td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; color: #3A342E; letter-spacing: 1.2px; text-transform: uppercase;">
                            {header_title}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding: 32px 32px;">
                {content}
                <p style="font-size: 16px; color: #141210; margin: 24px 0 0 0; line-height: 1.6;">
                    Happy trading,<br>
                    <strong>Erik</strong><br>
                    <span style="font-size: 13px; color: #6b7280;">Founder, RigaCap</span>
                </p>
            </td>
        </tr>
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>"""

        return await self.send_email(to_email, subject, html, user_id=user_id, email_type=f"onboarding_step{step}")

    async def send_sell_alert(
        self,
        to_email: str,
        user_name: str,
        symbol: str,
        action: str,
        reason: str,
        current_price: float,
        entry_price: float,
        stop_price: float = None,
        user_id: str = None,
    ) -> bool:
        """
        Send a sell or warning alert for an open position.

        Args:
            to_email: Subscriber email
            user_name: User's full name
            symbol: Stock symbol
            action: "sell" or "warning"
            reason: Human-readable reason for the alert
            current_price: Current live price
            entry_price: Position entry price
            stop_price: Trailing stop price (if applicable)

        Returns:
            True if sent successfully
        """
        first_name = user_name.split()[0] if user_name else "there"
        pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        pnl_color = "#2D5F3F" if pnl_pct >= 0 else "#8F2D3D"
        pnl_sign = "+" if pnl_pct >= 0 else ""
        is_sell = action.lower() == "sell"
        action_label = "Record Exit" if is_sell else "Watch"

        stop_html = f"""<tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Trailing Stop</td>
                            <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#141210;">${stop_price:.2f}</td></tr>""" if stop_price else ""

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 20px; line-height: 1.65;">Hi {first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 20px; line-height: 1.65;">
                    Your position in <strong>{symbol}</strong> {'has hit its trailing stop' if is_sell else 'is approaching its trailing stop'}.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; margin:24px 0;">
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Symbol</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:Georgia,serif; font-size:18px; font-weight:500; color:#141210;">{symbol}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Current Price</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#141210;">${current_price:.2f}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Entry Price</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#8A8279;">${entry_price:.2f}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">P&L</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:{pnl_color};">{pnl_sign}{pnl_pct:.1f}%</td></tr>
                    {stop_html}
                </table>

                <div style="border-left: 2px solid #7A2430; padding: 12px 16px; background: #FAF7F0; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px; color: #141210;">
                        <strong>{'Record Exit' if is_sell else 'Monitor'}:</strong> {reason}
                    </p>
                </div>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        View Dashboard
                    </a>
                </div>"""

        label = "Sell Alert" if is_sell else "Position Alert"
        html = self._email_wrapper(label, content, user_id)
        subject = f"RigaCap — {symbol}: {reason}"

        text = f"{symbol}: {reason}. Price ${current_price:.2f}, entry ${entry_price:.2f}, P/L {pnl_sign}{pnl_pct:.1f}%. View: rigacap.com/app"

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="sell_alert",
        )

    async def send_intraday_signal_alert(
        self,
        to_email: str,
        user_name: str,
        symbol: str,
        live_price: float,
        dwap: float,
        pct_above_dwap: float,
        momentum_rank: int = None,
        sector: str = None,
        user_id: str = None,
    ) -> bool:
        """
        Send alert when a watchlist stock crosses the breakout trigger intraday.

        Distinct amber/orange styling to differentiate from daily buy/sell emails.
        """
        first_name = user_name.split()[0] if user_name else "there"
        mom_row = f'<tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Momentum Rank</td><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:\'Courier New\',monospace; font-size:14px; color:#141210;">#{momentum_rank}</td></tr>' if momentum_rank else ""
        sector_row = f'<tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Sector</td><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-size:14px; color:#141210;">{sector}</td></tr>' if sector else ""

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 20px; line-height: 1.65;">{first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 20px; line-height: 1.65;">
                    <strong>{symbol}</strong> just crossed the breakout threshold during market hours. This was on your watchlist.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; margin:24px 0;">
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Symbol</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:Georgia,serif; font-size:18px; font-weight:500; color:#141210;">{symbol}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Live Price</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#141210;">${live_price:.2f}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Wtd Avg (200d)</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#8A8279;">${dwap:.2f}</td></tr>
                    <tr><td style="padding:10px 0; border-bottom:1px solid #DDD5C7; font-size:14px; color:#5A544E;">Breakout</td>
                        <td style="padding:10px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:14px; color:#2D5F3F;">+{pct_above_dwap:.1f}%</td></tr>
                    {mom_row}{sector_row}
                </table>

                <div style="border-left: 2px solid #7A2430; padding: 12px 16px; background: #FAF7F0; margin: 20px 0;">
                    <p style="margin: 0; font-size: 14px; color: #141210;">
                        <strong>Intraday signal</strong> — detected during market hours. Will be confirmed in tonight's full scan.
                    </p>
                </div>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="https://rigacap.com/app" style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">View Dashboard</a>
                </div>"""

        html = self._email_wrapper("Live Signal", content, user_id)

        text_lines = [f"LIVE: {symbol} breakout +{pct_above_dwap:.1f}%", f"Price: ${live_price:.2f}, Wtd Avg: ${dwap:.2f}"]
        if momentum_rank:
            text_lines.append(f"Rank: #{momentum_rank}")
        if sector:
            text_lines.append(f"  Sector: {sector}")
        text_lines.extend([
            "",
            "This signal was detected intraday and will be confirmed in tonight's full scan.",
            "",
            "View dashboard: https://rigacap.com/app",
            "",
            "---",
            "For information purposes only. Not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.",
            "RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.",
        ])

        return await self.send_email(
            to_email=to_email,
            subject=f"🔔 LIVE SIGNAL: {symbol} breakout +{pct_above_dwap:.1f}%",
            html_content=html,
            text_content="\n".join(text_lines),
            user_id=user_id,
            email_type="intraday_signal_alert",
        )

    async def send_referral_reward_email(self, to_email: str, name: str, friend_name: str, user_id: str = None) -> bool:
        """Send a reward notification when a referred friend converts to paid."""
        first_name = name.split()[0] if name else "there"
        friend_first = friend_name.split()[0] if friend_name else "Your friend"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">{first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    <strong>{friend_first}</strong> just became a paying subscriber. Your next invoice is <strong>$0</strong> — one full month on us.
                </p>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E; margin: 0 0 8px;">Your Reward</p>
                    <p style="font-family: Georgia, serif; font-size: 28px; color: #141210; margin: 0;">1 Month Free</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 4px 0 0;">Applied to your next invoice</p>
                </div>

                <p style="font-size: 15px; color: #5A544E; margin: 24px 0; line-height: 1.6;">
                    Keep sharing — every friend who subscribes earns you another free month.
                </p>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="https://rigacap.com/app" style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">View Dashboard</a>
                </div>"""

        html = self._email_wrapper("Referral Reward", content, user_id)
        text = f"{first_name}, {friend_first} subscribed! Your next month is free. Keep sharing at rigacap.com/app"

        return await self.send_email(
            to_email=to_email,
            subject=f"RigaCap — You earned a free month",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="referral_reward",
        )


    # ========================================================================
    # Weekly Regime Report (free subscribers + paid users)
    # ========================================================================

    def _generate_regime_unsubscribe_token(self, subscriber_id: int) -> str:
        """Generate JWT token for regime report unsubscribe link."""
        from jose import jwt as jose_jwt
        from datetime import timedelta
        from app.core.config import settings
        payload = {
            "sub": str(subscriber_id),
            "purpose": "regime_unsubscribe",
            "exp": datetime.utcnow() + timedelta(days=90),
        }
        return jose_jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def generate_regime_report_html(self, history: list, subscriber_id: int = None, user_id: str = None) -> str:
        """
        Generate HTML for the weekly market regime report email.

        Args:
            history: List of regime snapshots (most recent first) from get_forecast_history()
            subscriber_id: For free subscribers (regime_unsubscribe token)
            user_id: For paid users (standard email_manage token)
        """
        import json

        regime_colors = {
            'strong_bull': ('#2D5F3F', '#E8F0EB', 'Strong Bull'),
            'weak_bull': ('#5A7F5F', '#EDF2EE', 'Weak Bull'),
            'rotating_bull': ('#7A6F3F', '#F0EDE4', 'Rotating Bull'),
            'range_bound': ('#8A8279', '#EDEBE7', 'Range-Bound'),
            'weak_bear': ('#8F6D3D', '#F0ECE4', 'Weak Bear'),
            'panic_crash': ('#8F2D3D', '#F0E8E8', 'Panic/Crash'),
            'recovery': ('#3D6F8F', '#E4ECF0', 'Recovery'),
        }

        now = _now_et()
        date_str = now.strftime('%B %d, %Y')

        if not history:
            return f"<p>No regime data available for {date_str}.</p>"

        # history is ascending (oldest first), latest is last element
        latest = history[-1]
        regime_key = latest.get('regime', 'range_bound')
        color, bg_color, regime_name = regime_colors.get(regime_key, ('#F59E0B', '#fef3c7', 'Unknown'))

        outlook = latest.get('outlook', 'neutral')
        recommended_action = latest.get('recommended_action', 'hold')
        spy_close = latest.get('spy_close')
        vix_close = latest.get('vix_close')

        # Week-over-week change (7 days back from end)
        week_ago_idx = max(0, len(history) - 7)
        week_ago = history[week_ago_idx]
        prev_regime = week_ago.get('regime', '')
        if prev_regime == regime_key:
            wow_text = f"Held at <strong>{regime_name}</strong> for the week"
        else:
            prev_name = regime_colors.get(prev_regime, ('', '', prev_regime))[2]
            wow_text = f"Shifted: {prev_name} → <strong>{regime_name}</strong>"

        # SPY/VIX deltas
        prev_spy = week_ago.get('spy_close')
        prev_vix = week_ago.get('vix_close')
        spy_delta = ""
        if spy_close and prev_spy and prev_spy > 0:
            pct = (spy_close / prev_spy - 1) * 100
            arrow = "↑" if pct >= 0 else "↓"
            spy_delta = f' <span style="color:{"#2D5F3F" if pct >= 0 else "#8F2D3D"}">{arrow}{abs(pct):.1f}%</span>'
        vix_delta = ""
        if vix_close and prev_vix and prev_vix > 0:
            pct = (vix_close / prev_vix - 1) * 100
            arrow = "↑" if pct >= 0 else "↓"
            vix_delta = f' <span style="color:{"#8F2D3D" if pct >= 0 else "#2D5F3F"}">{arrow}{abs(pct):.1f}%</span>'

        # Pre-format values for HTML template (avoid nested f-string issues on Lambda)
        spy_display = f"${spy_close:.2f}" if spy_close else "N/A"
        vix_display = f"{vix_close:.1f}" if vix_close else "N/A"

        # Transition probabilities
        probs_raw = latest.get('probabilities')
        probs = {}
        if probs_raw:
            probs = probs_raw if isinstance(probs_raw, dict) else json.loads(probs_raw) if isinstance(probs_raw, str) else {}

        top_transitions = sorted(probs.items(), key=lambda x: -x[1])[:3]
        trans_rows = ""
        for regime, prob in top_transitions:
            r_color, _, r_name = regime_colors.get(regime, ('#6b7280', '#f3f4f6', regime))
            pct = round(prob, 1)
            bar_width = min(pct, 100)
            trans_rows += f'''
            <tr>
              <td style="padding:6px 12px;font-size:14px;color:#5A544E;width:140px;">{r_name}</td>
              <td style="padding:6px 12px;">
                <div style="background:#ECE6D9;overflow:hidden;height:18px;">
                  <div style="background:{r_color};width:{bar_width}%;height:100%;"></div>
                </div>
              </td>
              <td style="padding:6px 12px;font-size:14px;color:#141210;text-align:right;width:60px;font-weight:500;">{pct}%</td>
            </tr>'''

        # 30-day regime timeline (compact)
        timeline_blocks = ""
        for snap in history:  # already ascending (oldest first)
            r = snap.get('regime', 'range_bound')
            c = regime_colors.get(r, ('#F59E0B', '#fef3c7', 'Unknown'))[0]
            d = snap.get('date', '')[-5:]  # MM-DD
            timeline_blocks += f'<td style="background:{c};width:10px;height:24px;border-radius:2px;" title="{d}: {regime_colors.get(r, ("","",""))[2]}"></td>'

        # Action text
        action_display = recommended_action.replace('_', ' ').title() if recommended_action else 'Hold'

        # Unsubscribe footer
        if subscriber_id:
            token = self._generate_regime_unsubscribe_token(subscriber_id)
            unsub_url = f"https://api.rigacap.com/api/public/unsubscribe?token={token}"
            footer = f'''<tr>
                <td style="background-color: #ECE6D9; padding: 24px; text-align: center; border-top: 1px solid #DDD5C7;">
                    <p style="margin: 0 0 8px 0; font-size: 12px; color: #8A8279;">
                        You're receiving this because you subscribed at rigacap.com.
                    </p>
                    <p style="margin: 0; font-size: 12px; color: #8A8279;">
                        <a href="{unsub_url}" style="color: #5A544E; text-decoration: underline;">Unsubscribe</a>
                    </p>
                    <p style="margin: 8px 0 0 0; font-size: 12px; color: #8A8279;">
                        For information purposes only. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
                    </p>
                </td>
            </tr>'''
        elif user_id:
            footer = self._email_footer_html(user_id)
        else:
            footer = '''<tr>
                <td style="background-color: #ECE6D9; padding: 24px; text-align: center; border-top: 1px solid #DDD5C7;">
                    <p style="margin: 0; font-size: 12px; color: #8A8279;">
                        For information purposes only. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
                    </p>
                </td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#F5F1E8;font-family:Georgia,'Times New Roman',serif;color:#141210;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background-color:#FAF7F0;">
  <!-- Header -->
  <tr>
    <td style="padding: 32px 24px 20px 24px; border-bottom: 2px solid #141210;">
      <h1 style="margin:0;color:#141210;font-size:22px;font-weight:400;">Weekly Regime Report</h1>
      <p style="margin:8px 0 0 0;color:#8A8279;font-size:13px;font-style:italic;">{date_str}</p>
    </td>
  </tr>

  <!-- Regime Badge -->
  <tr>
    <td style="padding:28px 24px 20px 24px;text-align:center;">
      <div style="display:inline-block;background:{bg_color};border:1px solid {color};padding:10px 28px;">
        <span style="font-size:22px;font-weight:500;color:{color};">{regime_name}</span>
      </div>
      <p style="margin:10px 0 0 0;font-size:14px;color:#5A544E;">{wow_text}</p>
    </td>
  </tr>

  <!-- SPY & VIX -->
  <tr>
    <td style="padding:0 24px 24px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td width="50%" style="text-align:center;padding:14px;background:#ECE6D9;border-right:1px solid #DDD5C7;">
            <p style="margin:0;font-size:11px;color:#8A8279;text-transform:uppercase;letter-spacing:1px;">S&amp;P 500</p>
            <p style="margin:6px 0 0 0;font-size:20px;font-weight:500;color:#141210;">{spy_display}{spy_delta}</p>
          </td>
          <td width="50%" style="text-align:center;padding:14px;background:#ECE6D9;">
            <p style="margin:0;font-size:11px;color:#8A8279;text-transform:uppercase;letter-spacing:1px;">Market Fear</p>
            <p style="margin:6px 0 0 0;font-size:20px;font-weight:500;color:#141210;">{_vix_label(vix_close)}{vix_delta}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Outlook & Action -->
  <tr>
    <td style="padding:0 24px 24px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="border-left:3px solid #7A2430;">
        <tr>
          <td style="padding:16px 20px;">
            <p style="margin:0 0 6px 0;font-size:11px;color:#8A8279;text-transform:uppercase;letter-spacing:1px;">Outlook</p>
            <p style="margin:0 0 14px 0;font-size:16px;font-weight:500;color:#141210;">{outlook.replace('_', ' ').title()}</p>
            <p style="margin:0 0 6px 0;font-size:11px;color:#8A8279;text-transform:uppercase;letter-spacing:1px;">Recommended Action</p>
            <p style="margin:0;font-size:16px;font-weight:500;color:#141210;">{action_display}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Transition Probabilities -->
  <tr>
    <td style="padding:0 24px 24px 24px;">
      <p style="margin:0 0 12px 0;font-size:13px;font-weight:500;color:#141210;text-transform:uppercase;letter-spacing:1px;">Transition Probabilities</p>
      <table width="100%" cellpadding="0" cellspacing="0">
        {trans_rows}
      </table>
    </td>
  </tr>

  <!-- 30-Day Timeline -->
  <tr>
    <td style="padding:0 24px 24px 24px;">
      <p style="margin:0 0 12px 0;font-size:13px;font-weight:500;color:#141210;text-transform:uppercase;letter-spacing:1px;">30-Day Timeline</p>
      <table cellpadding="1" cellspacing="1" style="width:100%;">
        <tr>{timeline_blocks}</tr>
      </table>
    </td>
  </tr>

  <!-- CTA -->
  <tr>
    <td style="padding:0 24px 32px 24px;text-align:center;border-top:1px solid #DDD5C7;">
      <p style="margin:20px 0 16px 0;font-size:14px;color:#5A544E;font-style:italic;">
        RigaCap subscribers see daily signals informed by this regime intelligence.
      </p>
      <a href="https://rigacap.com?utm_source=regime_report&utm_medium=email&utm_campaign=weekly"
         style="display:inline-block;padding:12px 28px;background:#141210;color:#F5F1E8;text-decoration:none;font-weight:500;font-size:14px;">
        Start Your Trial
      </a>
    </td>
  </tr>

  <!-- Footer -->
  {footer}
</table>
</body>
</html>'''
        return html

    async def send_weekly_regime_report(self, to_email: str, html: str,
                                         subscriber_id: int = None, user_id: str = None) -> bool:
        """Send the weekly regime report email."""
        subject = f"Weekly Regime Report — {_now_et().strftime('%B %d, %Y')}"
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            user_id=user_id,  # For List-Unsubscribe header (paid users only)
            email_type="weekly_regime",
        )


    async def send_winback_email(
        self,
        to_email: str,
        user_name: str,
        user_id: str = None,
    ) -> bool:
        """
        Send win-back email to a paid subscriber who just cancelled.

        Sent 24 hours after cancellation — door-stays-open note, no discount (Erik, Jun 12 2026: no shared discount codes; serialized one-time coupons only if data ever justifies).
        Different from the D8 trial drip — this targets paying customers who churned.
        """
        first_name = user_name.split()[0] if user_name else "there"
        import secrets
        promo_code = f"RETURN-{secrets.token_hex(3).upper()}"

        content = f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">{first_name},</p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Your subscription was cancelled. If something wasn't working, reply and tell me — I read every response.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.6;">
                        The system is still finding 3-4 signals per month, still going to cash when conditions deteriorate, still cutting losers at the trailing stop. That discipline doesn't stop when you leave.
                    </p>
                </div>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: #3A342E; margin: 0 0 8px;">Come Back</p>
                    <p style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin: 0;">The door stays open &mdash; same price as everyone.</p>
                </div>

                <div style="text-align: center; margin: 28px 0;">
                    <a href="https://rigacap.com/#pricing" style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">Reactivate</a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">— Erik</p>"""

        html = self._email_wrapper("We'll be here", content, user_id)

        return await self.send_email(to_email, f"RigaCap — the system is still running", html, user_id=user_id, email_type="winback")


# Singleton instance
email_service = EmailService()


class AdminEmailService(EmailService):
    """
    Email service for admin-only notifications.

    Enforces that emails can only be sent to addresses in the ADMIN_EMAILS
    allowlist. This prevents internal system emails (ticker alerts, strategy
    analysis, switch notifications, AI generation reports) from ever being
    sent to subscribers.
    """

    def _validate_admin_recipient(self, to_email: str) -> bool:
        """Check that the recipient is a configured admin."""
        if to_email.lower().strip() not in ADMIN_EMAILS:
            logger.error(
                f"BLOCKED: Attempted to send admin email to non-admin address: {to_email}. "
                f"Allowed admins: {ADMIN_EMAILS}"
            )
            return False
        return True

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Override send_email to enforce admin-only recipients."""
        if not self._validate_admin_recipient(to_email):
            return False
        return await super().send_email(to_email, subject, html_content, text_content)

    async def send_ticker_alert(
        self,
        to_email: str,
        issues: list,
        check_type: str = "position"
    ) -> bool:
        """
        Send alert email when ticker issues are detected.

        Args:
            to_email: Admin email to alert
            issues: List of dicts with 'symbol', 'issue', 'last_price', 'last_date'
            check_type: 'position' or 'universe'

        Returns:
            True if sent successfully
        """
        if not issues:
            return True

        issue_rows = ""
        for issue in issues:
            symbol = issue.get('symbol', 'N/A')
            problem = issue.get('issue', 'Unknown issue')
            last_price = issue.get('last_price', 'N/A')
            last_date = issue.get('last_date', 'N/A')
            suggestion = issue.get('suggestion', 'Research ticker change or delisting')

            issue_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #fee2e2; font-weight: 600; color: #dc2626;">
                    {symbol}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #fee2e2; color: #374151;">
                    {problem}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #fee2e2; color: #6b7280; font-size: 13px;">
                    Last: ${last_price} on {last_date}
                </td>
            </tr>
            <tr>
                <td colspan="3" style="padding: 8px 12px 16px; color: #92400e; font-size: 13px; background-color: #fef3c7;">
                    {suggestion}
                </td>
            </tr>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <!-- Header -->
        <tr>
            <td style="background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                    Ticker Health Alert
                </h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    {len(issues)} issue(s) detected in {"open positions" if check_type == "position" else "stock universe"}
                </p>
            </td>
        </tr>

        <!-- Issues Table -->
        <tr>
            <td style="padding: 24px;">
                <p style="margin: 0 0 16px 0; font-size: 14px; color: #374151;">
                    The following tickers failed to return data during the daily health check.
                    This may indicate a ticker change, delisting, or merger.
                </p>

                <table cellpadding="0" cellspacing="0" style="width: 100%; border: 1px solid #fecaca; border-radius: 8px; overflow: hidden;">
                    <tr style="background-color: #fef2f2;">
                        <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #991b1b;">Symbol</th>
                        <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #991b1b;">Issue</th>
                        <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #991b1b;">Last Known</th>
                    </tr>
                    {issue_rows}
                </table>
            </td>
        </tr>

        <!-- Action Items -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: #f0f9ff; border-radius: 12px; padding: 20px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #0369a1; border-left: 4px solid #172554; padding-left: 12px;">
                        Recommended Actions
                    </h3>
                    <ol style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 1.8;">
                        <li>Search for recent news about the affected ticker(s)</li>
                        <li>Check if ticker changed (e.g., SQ → XYZ for Block Inc)</li>
                        <li>If delisted/acquired, close any open positions manually</li>
                        <li>Update MUST_INCLUDE list in stock_universe.py if needed</li>
                    </ol>
                </div>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    This is an automated alert from RigaCap Health Monitor
                </p>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #9ca3af;">
                    Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ET
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        text_lines = [
            "TICKER HEALTH ALERT",
            "=" * 40,
            f"{len(issues)} issue(s) detected in {'open positions' if check_type == 'position' else 'stock universe'}",
            "",
        ]

        for issue in issues:
            text_lines.append(f"• {issue.get('symbol')}: {issue.get('issue')}")
            text_lines.append(f"  Last: ${issue.get('last_price', 'N/A')} on {issue.get('last_date', 'N/A')}")
            text_lines.append(f"  → {issue.get('suggestion', 'Research ticker change')}")
            text_lines.append("")

        text_lines.extend([
            "RECOMMENDED ACTIONS:",
            "1. Search for recent news about the ticker(s)",
            "2. Check if ticker changed (e.g., SQ → XYZ)",
            "3. Close positions manually if delisted",
            "4. Update MUST_INCLUDE list if needed",
        ])

        return await self.send_email(
            to_email=to_email,
            subject=f"⚠️ RigaCap Alert: {len(issues)} Ticker Issue(s) Detected",
            html_content=html,
            text_content="\n".join(text_lines)
        )

    async def send_admin_alert(
        self,
        to_email: str,
        subject: str,
        message: str,
    ) -> bool:
        """
        Send a generic admin alert email.

        Args:
            to_email: Admin email address
            subject: Email subject line
            message: Plain-text message body
        """
        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f3f4f6;">
<table cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;margin:0 auto;background:#fff;">
<tr><td style="background:linear-gradient(135deg,#dc2626 0%,#b91c1c 100%);padding:32px 24px;text-align:center;">
<h1 style="margin:0;color:#fff;font-size:22px;">Admin Alert</h1>
</td></tr>
<tr><td style="padding:24px;">
<pre style="white-space:pre-wrap;font-family:inherit;color:#374151;line-height:1.6;margin:0;">{message}</pre>
</td></tr>
<tr><td style="background:#f9fafb;padding:16px 24px;text-align:center;border-top:1px solid #e5e7eb;">
<p style="margin:0;font-size:12px;color:#9ca3af;">RigaCap Admin Alert &mdash; {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ET</p>
</td></tr>
</table>
</body></html>"""

        ok = await self.send_email(
            to_email=to_email,
            subject=f"⚠️ {subject}",
            html_content=html,
            text_content=message,
        )

        # Mirror the alert to the admin's phone (admin mobile app). Pushes to
        # THIS to_email only — send_admin_alert is sometimes called once per
        # admin in a loop, so a fan-out-to-all here would duplicate. Best-effort.
        try:
            from app.services.push_notification_service import push_notification_service
            await push_notification_service.send_to_admin_email(
                to_email, f"⚠️ {subject}", message, data={"screen": "glance"}
            )
        except Exception:
            pass

        return ok

    async def send_strategy_analysis_email(
        self,
        to_email: str,
        analysis_results: dict,
        recommendation: str,
        switch_executed: bool = False,
        switch_reason: str = ""
    ) -> bool:
        """
        Send biweekly strategy analysis summary email.

        Args:
            to_email: Admin email
            analysis_results: Dict with evaluations and recommendation
            recommendation: Recommendation text
            switch_executed: Whether a switch was executed
            switch_reason: Reason for switch or why blocked
        """
        evaluations = analysis_results.get("evaluations", [])
        analysis_date = analysis_results.get("analysis_date", datetime.now().isoformat())
        lookback_days = analysis_results.get("lookback_days", 90)

        # Sort by score
        sorted_evals = sorted(evaluations, key=lambda x: x.get("recommendation_score", 0), reverse=True)

        eval_rows = ""
        for i, e in enumerate(sorted_evals[:5]):
            rank_badge = f'<span style="display:inline-block;background:#172554;color:#c9a94e;font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;">#{i+1}</span>'
            score_color = "#059669" if e.get("recommendation_score", 0) >= 60 else "#f59e0b" if e.get("recommendation_score", 0) >= 40 else "#6b7280"
            return_color = "#059669" if e.get("total_return_pct", 0) >= 0 else "#dc2626"

            eval_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                    {rank_badge} <strong>{e.get('name', 'Unknown')}</strong>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                    <span style="color: {score_color}; font-weight: 600;">{e.get('recommendation_score', 0):.0f}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">
                    {e.get('sharpe_ratio', 0):.2f}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right; color: {return_color};">
                    {'+' if e.get('total_return_pct', 0) >= 0 else ''}{e.get('total_return_pct', 0):.1f}%
                </td>
            </tr>
            """

        status_color = "#059669" if switch_executed else "#f59e0b"
        status_text = "Switch Executed" if switch_executed else "No Switch"

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px;">Strategy Analysis Report</h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    {lookback_days}-day rolling walk-forward
                </p>
            </td>
        </tr>

        <!-- Status Banner -->
        <tr>
            <td style="padding: 24px;">
                <div style="background-color: {'#ecfdf5' if switch_executed else '#fef3c7'}; border-radius: 12px; padding: 16px; border-left: 4px solid {status_color};">
                    <div style="font-weight: 600; color: {status_color};">
                        {status_text}
                    </div>
                    <div style="color: #374151; margin-top: 4px;">
                        {switch_reason}
                    </div>
                </div>
            </td>
        </tr>

        <!-- Strategy Rankings -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 16px; font-size: 18px; color: #111827; border-left: 4px solid #172554; padding-left: 12px;">Strategy Rankings</h2>
                <table cellpadding="0" cellspacing="0" style="width: 100%; border: 1px solid #e5e7eb; border-radius: 8px;">
                    <tr style="background-color: #f9fafb;">
                        <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #6b7280;">Strategy</th>
                        <th style="padding: 12px; text-align: right; font-size: 12px; text-transform: uppercase; color: #6b7280;">Score</th>
                        <th style="padding: 12px; text-align: right; font-size: 12px; text-transform: uppercase; color: #6b7280;">Sharpe</th>
                        <th style="padding: 12px; text-align: right; font-size: 12px; text-transform: uppercase; color: #6b7280;">Return</th>
                    </tr>
                    {eval_rows}
                </table>
            </td>
        </tr>

        <!-- Recommendation -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: #f0f9ff; border-radius: 12px; padding: 16px;">
                    <h3 style="margin: 0 0 8px; font-size: 14px; color: #0369a1; border-left: 4px solid #172554; padding-left: 12px;">Recommendation</h3>
                    <p style="margin: 0; color: #374151; white-space: pre-line;">{recommendation}</p>
                </div>
            </td>
        </tr>

        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Analysis completed at {analysis_date}<br>
                    RigaCap Strategy Management
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        return await self.send_email(
            to_email=to_email,
            subject=f"📊 Strategy Analysis: {status_text}",
            html_content=html
        )

    async def send_switch_notification_email(
        self,
        to_email: str,
        from_strategy: str,
        to_strategy: str,
        reason: str,
        metrics: dict
    ) -> bool:
        """
        Send notification when an automatic strategy switch occurs.

        Args:
            to_email: Admin email
            from_strategy: Previous strategy name
            to_strategy: New strategy name
            reason: Reason for the switch
            metrics: Dict with score_before, score_after, score_diff
        """
        score_before = metrics.get("score_before", 0)
        score_after = metrics.get("score_after", 0)
        score_diff = metrics.get("score_diff", 0)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #059669 0%, #10b981 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px;">Strategy Switch Executed</h1>
            </td>
        </tr>

        <tr>
            <td style="padding: 32px 24px;">
                <!-- Switch Visual -->
                <div style="display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 24px;">
                    <div style="background-color: #fee2e2; padding: 16px 24px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 12px; color: #991b1b; text-transform: uppercase; margin-bottom: 4px;">From</div>
                        <div style="font-size: 18px; font-weight: 600; color: #dc2626;">{from_strategy or 'None'}</div>
                        <div style="font-size: 14px; color: #6b7280; margin-top: 4px;">Score: {score_before:.0f}</div>
                    </div>
                    <div style="font-size: 24px;">→</div>
                    <div style="background-color: #d1fae5; padding: 16px 24px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 12px; color: #065f46; text-transform: uppercase; margin-bottom: 4px;">To</div>
                        <div style="font-size: 18px; font-weight: 600; color: #059669;">{to_strategy}</div>
                        <div style="font-size: 14px; color: #6b7280; margin-top: 4px;">Score: {score_after:.0f}</div>
                    </div>
                </div>

                <!-- Score Improvement -->
                <div style="background-color: #f0fdf4; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
                    <div style="font-size: 14px; color: #065f46; margin-bottom: 8px;">Score Improvement</div>
                    <div style="font-size: 36px; font-weight: 700; color: #059669;">+{score_diff:.1f}</div>
                </div>

                <!-- Reason -->
                <div style="background-color: #f3f4f6; border-radius: 8px; padding: 16px;">
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px;">Reason</div>
                    <div style="color: #6b7280;">{reason}</div>
                </div>
            </td>
        </tr>

        <tr>
            <td style="padding: 0 24px 24px;">
                <p style="margin: 0; font-size: 14px; color: #6b7280;">
                    The new strategy is now active and will be used for all trading signals.
                    You can review and override this in the Admin Dashboard.
                </p>
            </td>
        </tr>

        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Switch executed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC<br>
                    RigaCap Strategy Management
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        return await self.send_email(
            to_email=to_email,
            subject=f"🔄 Strategy Switch: {from_strategy or 'None'} → {to_strategy}",
            html_content=html
        )

    async def send_generation_complete_email(
        self,
        to_email: str,
        best_params: dict,
        expected_metrics: dict,
        market_regime: str,
        created_strategy_name: str = None
    ) -> bool:
        """
        Send notification when AI strategy generation completes.

        Args:
            to_email: Admin email
            best_params: Best parameters found
            expected_metrics: Expected sharpe, return, drawdown
            market_regime: Detected market regime
            created_strategy_name: Name of created strategy (if auto_create was True)
        """
        params_html = ""
        for key, value in best_params.items():
            params_html += f"""
            <tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">{key.replace('_', ' ').title()}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #111827;">{value}</td>
            </tr>
            """

        regime_colors = {
            "strong_bull": ("#10B981", "#d1fae5"),
            "weak_bull": ("#84CC16", "#ecfdf5"),
            "rotating_bull": ("#8B5CF6", "#ede9fe"),
            "range_bound": ("#F59E0B", "#fef3c7"),
            "weak_bear": ("#F97316", "#fff7ed"),
            "panic_crash": ("#EF4444", "#fee2e2"),
            "recovery": ("#06B6D4", "#cffafe"),
        }
        market_regime = market_regime or "unknown"
        regime_color, regime_bg = regime_colors.get(market_regime, ("#6b7280", "#f3f4f6"))

        created_section = ""
        if created_strategy_name:
            created_section = f"""
            <tr>
                <td style="padding: 0 24px 24px;">
                    <div style="background-color: #d1fae5; border-radius: 12px; padding: 16px; border-left: 4px solid #059669;">
                        <div style="font-weight: 600; color: #065f46;">Strategy Created</div>
                        <div style="color: #374151; margin-top: 4px;">
                            "{created_strategy_name}" has been added to your strategy library.
                        </div>
                    </div>
                </td>
            </tr>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px;">AI Strategy Generation Complete</h1>
            </td>
        </tr>

        <!-- Market Regime -->
        <tr>
            <td style="padding: 24px;">
                <div style="background-color: {regime_bg}; border-radius: 12px; padding: 16px; text-align: center;">
                    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase; margin-bottom: 4px;">Market Regime Detected</div>
                    <div style="font-size: 24px; font-weight: 700; color: {regime_color};">{market_regime.upper()}</div>
                </div>
            </td>
        </tr>

        <!-- Expected Metrics -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 16px; font-size: 18px; color: #111827; border-left: 4px solid #172554; padding-left: 12px;">Expected Performance</h2>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
                    <div style="background-color: #f0fdf4; border-radius: 8px; padding: 16px; text-align: center;">
                        <div style="font-size: 12px; color: #065f46; margin-bottom: 4px;">Sharpe Ratio</div>
                        <div style="font-size: 24px; font-weight: 700; color: #059669;">{expected_metrics.get('sharpe', 0):.2f}</div>
                    </div>
                    <div style="background-color: #f0fdf4; border-radius: 8px; padding: 16px; text-align: center;">
                        <div style="font-size: 12px; color: #065f46; margin-bottom: 4px;">Expected Return</div>
                        <div style="font-size: 24px; font-weight: 700; color: #059669;">+{expected_metrics.get('return', 0):.1f}%</div>
                    </div>
                    <div style="background-color: #fef2f2; border-radius: 8px; padding: 16px; text-align: center;">
                        <div style="font-size: 12px; color: #991b1b; margin-bottom: 4px;">Max Drawdown</div>
                        <div style="font-size: 24px; font-weight: 700; color: #dc2626;">-{expected_metrics.get('drawdown', 0):.1f}%</div>
                    </div>
                </div>
            </td>
        </tr>

        <!-- Best Parameters -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 16px; font-size: 18px; color: #111827; border-left: 4px solid #172554; padding-left: 12px;">Optimal Parameters</h2>
                <table cellpadding="0" cellspacing="0" style="width: 100%; border: 1px solid #e5e7eb; border-radius: 8px;">
                    {params_html}
                </table>
            </td>
        </tr>

        {created_section}

        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Generation completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC<br>
                    RigaCap AI Strategy Generator
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        return await self.send_email(
            to_email=to_email,
            subject="🤖 AI Strategy Generation Complete",
            html_content=html
        )


    async def send_post_approval_notification(
        self,
        to_email: str,
        post,
        hours_before: int,
        cancel_url: str,
        publish_url: str = "",
    ) -> bool:
        """
        Send admin notification for an upcoming scheduled social post.

        Shows post preview, platform badge, scheduled time, cancel + post-now buttons.

        Args:
            to_email: Admin email
            post: SocialPost object
            hours_before: 24 or 1
            cancel_url: JWT-signed one-click cancel link
            publish_url: JWT-signed one-click publish link
        """
        _pnames = {"twitter": "Twitter/X", "instagram": "Instagram", "threads": "Threads", "tiktok": "TikTok"}
        _pcolors = {"twitter": "#1DA1F2", "instagram": "#E4405F", "threads": "#000000", "tiktok": "#000000"}
        platform_display = _pnames.get(post.platform, (post.platform or "Post").title())
        platform_color = _pcolors.get(post.platform, "#141210")
        scheduled_str = post.scheduled_for.strftime('%B %d at %I:%M %p UTC') if post.scheduled_for else "Soon"
        urgency = "in 1 hour" if hours_before <= 1 else f"in ~{hours_before} hours"
        header_bg = "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)" if hours_before <= 1 else "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"

        # Full post text in email so admin can review before it goes live
        preview_text = post.text_content or ""
        import html as _html
        preview_html = _html.escape(preview_text).replace("\n", "<br>")

        ai_badge = ""
        if getattr(post, "ai_generated", False):
            ai_badge = '<span style="display:inline-block;background:#8b5cf6;color:#fff;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-left:8px;">AI Generated</span>'

        # Chart card image (if post has one). image_s3_key may be a full public URL
        # (launch cards on CloudFront) OR an S3 key (generated cards) — mirror publish_post:
        # use full URLs directly, presign only real keys. (Presigning a full URL mangled it,
        # which is why the launch-card previews showed a broken image.)
        chart_img_html = ""
        image_s3_key = getattr(post, "image_s3_key", None)
        if image_s3_key:
            try:
                if image_s3_key.startswith("http://") or image_s3_key.startswith("https://"):
                    img_url = image_s3_key
                else:
                    from app.services.chart_card_generator import chart_card_generator
                    img_url = chart_card_generator.get_presigned_url(image_s3_key, expires_in=86400)
                if img_url:
                    chart_img_html = f'<img src="{img_url}" alt="Chart card" style="width:100%; border-radius:8px; margin-bottom:16px;" />'
            except Exception:
                pass

        html = f"""<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:#f9fafb; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto;">
        <tr>
            <td style="background:{header_bg}; padding:32px 24px; text-align:center;">
                <h1 style="margin:0; color:#ffffff; font-size:24px;">
                    Post Goes Live {urgency.title()}
                </h1>
                <p style="margin:8px 0 0 0; color:rgba(255,255,255,0.9); font-size:14px;">
                    Scheduled for {scheduled_str}
                </p>
            </td>
        </tr>
        <tr>
            <td style="background:#ffffff; padding:32px 24px;">
                <div style="margin-bottom:20px;">
                    <span style="display:inline-block;background:{platform_color};color:#fff;font-size:12px;font-weight:600;padding:4px 12px;border-radius:99px;">
                        {platform_display}
                    </span>
                    <span style="display:inline-block;background:#e5e7eb;color:#374151;font-size:12px;font-weight:500;padding:4px 12px;border-radius:99px;margin-left:8px;">
                        {(post.post_type or '').replace('_', ' ').title()}
                    </span>
                    {ai_badge}
                </div>

                <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:12px; padding:20px; margin-bottom:24px;">
                    {chart_img_html}
                    <p style="margin:0; font-size:14px; color:#374151; line-height:1.6;">{preview_html}</p>
                    {f'<p style="margin:12px 0 0 0; font-size:13px; color:#6366f1;">{post.hashtags}</p>' if post.hashtags else ''}
                </div>

                <div style="text-align:center; margin:32px 0;">
                    <a href="{publish_url}"
                       style="display:inline-block; background:#059669; color:#ffffff; font-size:16px; font-weight:600; padding:16px 32px; border-radius:12px; text-decoration:none; margin-right:12px;">
                        Post Now
                    </a>
                    <a href="{cancel_url}"
                       style="display:inline-block; background:#dc2626; color:#ffffff; font-size:16px; font-weight:600; padding:16px 32px; border-radius:12px; text-decoration:none;">
                        Cancel
                    </a>
                </div>

                <p style="margin:0; font-size:13px; color:#6b7280; text-align:center;">
                    If you do nothing, this post will be published automatically at {scheduled_str}.
                </p>
            </td>
        </tr>
        <tr>
            <td style="background-color:#f9fafb; padding:24px; text-align:center; border-top:1px solid #e5e7eb;">
                <p style="margin:0; font-size:12px; color:#9ca3af;">
                    RigaCap Social Post Scheduler
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""

        text = f"""Post Goes Live {urgency}

Platform: {platform_display}
Type: {(post.post_type or '').replace('_', ' ').title()}
Scheduled: {scheduled_str}

--- Post Preview ---
{preview_text}
{f'Hashtags: {post.hashtags}' if post.hashtags else ''}
---

To post now, visit:
{publish_url}

To cancel this post, visit:
{cancel_url}

If you do nothing, it will be published automatically."""

        subject = f"{'🔴' if hours_before <= 1 else '🟡'} Post goes live {urgency}: {platform_display} — {(post.post_type or '').replace('_', ' ').title()}"

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            text_content=text,
        )


    async def send_reply_approval_email(
        self,
        to_email: str,
        post,
        approve_url: str,
    ) -> bool:
        """
        Send admin email for a contextual reply draft with one-click Approve & Post button.

        Shows: who we're replying to, their tweet text, our generated reply, and an approve button.
        """
        import html as _html

        username = getattr(post, "reply_to_username", None) or "unknown"
        source_text = getattr(post, "source_tweet_text", None) or ""
        reply_text = (post.text_content or "")[:300]

        source_html = _html.escape(source_text).replace("\n", "<br>")
        reply_html = _html.escape(reply_text).replace("\n", "<br>")

        # Extract trade return from source_trade_json
        trade_return = ""
        try:
            import json
            trade = json.loads(post.source_trade_json) if post.source_trade_json else {}
            pnl = trade.get("pnl_pct", 0)
            symbol = trade.get("symbol", "")
            if pnl and symbol:
                trade_return = f'<span style="display:inline-block;background:#059669;color:#fff;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-left:8px;">${symbol} {pnl:+.1f}%</span>'
        except Exception:
            pass

        html = f"""<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:#f9fafb; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto;">
        <tr>
            <td style="background:linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); padding:32px 24px; text-align:center;">
                <h1 style="margin:0; color:#ffffff; font-size:22px;">
                    Reply Draft for @{_html.escape(username)}
                </h1>
                <p style="margin:8px 0 0 0; color:rgba(255,255,255,0.9); font-size:14px;">
                    Approve to post immediately
                </p>
            </td>
        </tr>
        <tr>
            <td style="background:#ffffff; padding:32px 24px;">
                <div style="margin-bottom:20px;">
                    <span style="display:inline-block;background:#1DA1F2;color:#fff;font-size:12px;font-weight:600;padding:4px 12px;border-radius:99px;">
                        Twitter/X Reply
                    </span>
                    <span style="display:inline-block;background:#8b5cf6;color:#fff;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-left:8px;">
                        AI Generated
                    </span>
                    {trade_return}
                </div>

                <div style="background:#f0f9ff; border:1px solid #bae6fd; border-radius:12px; padding:16px; margin-bottom:16px;">
                    <p style="margin:0 0 4px 0; font-size:12px; color:#0369a1; font-weight:600;">
                        @{_html.escape(username)}'s tweet:
                    </p>
                    <p style="margin:0; font-size:14px; color:#374151; line-height:1.5;">{source_html}</p>
                </div>

                <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:12px; padding:16px; margin-bottom:24px;">
                    <p style="margin:0 0 4px 0; font-size:12px; color:#15803d; font-weight:600;">
                        Our reply:
                    </p>
                    <p style="margin:0; font-size:14px; color:#374151; line-height:1.5;">{reply_html}</p>
                </div>

                <div style="text-align:center; margin:32px 0;">
                    <a href="{approve_url}"
                       style="display:inline-block; background:#059669; color:#ffffff; font-size:16px; font-weight:600; padding:16px 40px; border-radius:12px; text-decoration:none;">
                        Approve &amp; Post Now
                    </a>
                </div>

                <p style="margin:0; font-size:13px; color:#6b7280; text-align:center;">
                    This reply will NOT be posted unless you click approve.<br>
                    The link expires in 72 hours.
                </p>
            </td>
        </tr>
        <tr>
            <td style="background-color:#f9fafb; padding:24px; text-align:center; border-top:1px solid #e5e7eb;">
                <p style="margin:0; font-size:12px; color:#9ca3af;">
                    RigaCap Reply Scanner
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""

        text = f"""Reply Draft for @{username}

--- Their tweet ---
{source_text}
---

--- Our reply ---
{reply_text}
---

Approve & post now: {approve_url}

This reply will NOT be posted unless you click approve.
The link expires in 72 hours."""

        subject = f"Reply draft for @{username} — approve to post"

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            text_content=text,
        )

    async def send_reply_approval_batch(self, to_email: str, items: list) -> bool:
        """ONE digest email with all of a scan's contextual-reply drafts, each with its own
        one-click Approve & Post button. items = [{"post": SocialPost, "approve_url": str}].
        Batched so a 4x/day scan cadence doesn't spam N separate emails per run."""
        import html as _html, json as _json
        if not items:
            return False
        cards = []
        for it in items:
            post = it.get("post")
            approve_url = it.get("approve_url", "")
            if not post:
                continue
            username = getattr(post, "reply_to_username", None) or "unknown"
            source_text = getattr(post, "source_tweet_text", None) or ""
            reply_text = (post.text_content or "")
            source_html = _html.escape(source_text).replace("\n", "<br>")
            reply_html = _html.escape(reply_text).replace("\n", "<br>")
            flag = ""
            try:
                trade = _json.loads(post.source_trade_json) if post.source_trade_json else {}
                pnl = trade.get("pnl_pct", 0)
                symbol = trade.get("symbol", "")
                if symbol:
                    flag = f'<span style="display:inline-block;background:#eef2f7;color:#334155;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-left:6px;">${symbol} {pnl:+.1f}%</span>'
            except Exception:
                pass
            plat = (getattr(post, "platform", "") or "twitter").title()
            tier = (it.get("tier") or "preserver").lower()
            if tier == "maximizer":
                tier_chip = '<span style="display:inline-block;background:#ecfdf5;color:#047857;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:6px;">Maximizer angle</span>'
            else:
                tier_chip = '<span style="display:inline-block;background:#fbeaec;color:#7A2430;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:6px;">Preserver angle</span>'
            cards.append(f"""
                <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:16px;">
                    <div style="font-size:12px;color:#64748b;margin-bottom:8px;">Reply to <strong>@{_html.escape(username)}</strong> &middot; {plat}{tier_chip}{flag}</div>
                    <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:10px;font-size:13px;color:#475569;line-height:1.5;">{source_html or '<em style="color:#94a3b8;">(their post)</em>'}</div>
                    <div style="font-size:14px;color:#141210;line-height:1.55;margin-bottom:14px;">{reply_html}</div>
                    <a href="{approve_url}" style="display:inline-block;background:#059669;color:#ffffff;font-size:14px;font-weight:600;padding:10px 22px;border-radius:8px;text-decoration:none;">Open in X &mdash; reply ready &rarr;</a>
                    <div style="font-size:11px;color:#9ca3af;margin-top:8px;">Opens the X composer as a reply, text pre-filled. Review, then hit Post.</div>
                </div>""")
        n = len([c for c in cards])
        cards_html = "".join(cards)
        html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
        <tr><td style="padding:28px 24px 8px;">
            <h1 style="margin:0;font-size:20px;color:#141210;">{n} reply draft{'s' if n != 1 else ''} ready</h1>
            <p style="margin:6px 0 0;font-size:13px;color:#64748b;">Tap the ones that sound like you &mdash; each opens X with the reply pre-filled, you just hit Post. Nothing posts on its own. Links expire in 72h.</p>
        </td></tr>
        <tr><td style="padding:16px 24px 24px;">{cards_html}</td></tr>
        <tr><td style="background:#f9fafb;padding:20px 24px;text-align:center;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">RigaCap Reply Scanner</p>
        </td></tr>
    </table></body></html>"""
        text_lines = [f"{n} reply draft{'s' if n != 1 else ''} ready — tap to open X with the reply pre-filled, then hit Post:", ""]
        for it in items:
            p = it.get("post")
            if not p:
                continue
            u = getattr(p, "reply_to_username", None) or "unknown"
            text_lines += [f"@{u}: {(p.text_content or '').strip()}", f"Open in X: {it.get('approve_url','')}", ""]
        subject = f"{n} reply draft{'s' if n != 1 else ''} ready to approve"
        return await self.send_email(to_email=to_email, subject=subject, html_content=html, text_content="\n".join(text_lines))


    async def send_autopost_notice(self, to_email: str, post, kill_url: str, tier: str, post_when: str, platforms=None, edit_url: str = None) -> bool:
        """Heads-up that an own-social post is scheduled to AUTO-PUBLISH, with a one-click
        KILL link. Autopost + kill model — the feed stays alive with zero effort; Erik only
        acts if he wants to stop one. `platforms` lists all targets (kill cancels all)."""
        import html as _html
        text = (getattr(post, "text_content", None) or "")
        text_html = _html.escape(text).replace("\n", "<br>")
        _names = {"twitter": "X", "threads": "Threads", "instagram": "Instagram"}
        if platforms:
            labs = [_names.get(p, p.title()) for p in platforms]
            plat = " & ".join([", ".join(labs[:-1]), labs[-1]]) if len(labs) > 1 else labs[0]
        else:
            plat = _names.get((getattr(post, "platform", "") or "twitter"), "X")
        tier = (tier or "preserver").lower()
        if tier == "maximizer":
            chip = '<span style="display:inline-block;background:#ecfdf5;color:#047857;font-size:12px;font-weight:700;padding:3px 10px;border-radius:99px;">Maximizer angle</span>'
        else:
            chip = '<span style="display:inline-block;background:#fbeaec;color:#7A2430;font-size:12px;font-weight:700;padding:3px 10px;border-radius:99px;">Preserver angle</span>'
        html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
        <tr><td style="padding:28px 24px 8px;">
            <h1 style="margin:0;font-size:20px;color:#141210;">Posting to {plat} {post_when}</h1>
            <p style="margin:6px 0 0;font-size:13px;color:#64748b;">This auto-publishes unless you kill it. {chip}</p>
        </td></tr>
        <tr><td style="padding:14px 24px 6px;">
            <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;">
                <div style="font-size:15px;color:#141210;line-height:1.6;">{text_html}</div>
            </div>
        </td></tr>
        <tr><td style="padding:12px 24px 26px;">
            <a href="{kill_url}" style="display:inline-block;background:#8F2D3D;color:#ffffff;font-size:14px;font-weight:600;padding:10px 22px;border-radius:8px;text-decoration:none;">Kill this post</a>
            {f'<a href="{edit_url}" style="display:inline-block;background:#FAF7F0;color:#7A2430;border:1px solid #DDD5C7;font-size:14px;font-weight:600;padding:10px 22px;border-radius:8px;text-decoration:none;margin-left:10px;">Edit &amp; tweak</a>' if edit_url else ''}
            <div style="font-size:11px;color:#9ca3af;margin-top:8px;">Do nothing and it posts as scheduled. Kill or edit any time before then. Links expire in 48h.</div>
        </td></tr>
        <tr><td style="background:#f9fafb;padding:18px 24px;text-align:center;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">RigaCap Auto-Social</p>
        </td></tr>
    </table></body></html>"""
        text_body = (
            f"Posting to {plat} {post_when} ({tier} angle) — auto-publishes unless you kill it:\n\n"
            f"{text.strip()}\n\nKill it: {kill_url}\n\n(Do nothing and it posts as scheduled.)"
        )
        subject = f"Posting {post_when}: {text.strip()[:48]}{'…' if len(text.strip()) > 48 else ''}"
        return await self.send_email(to_email=to_email, subject=subject, html_content=html, text_content=text_body)

    async def send_email_failure_report(self, to_email: str, failures: list[dict]) -> bool:
        """Send a summary report of email delivery failures to an admin."""
        if not failures:
            return True

        def mask_email(email: str) -> str:
            local, domain = email.split("@", 1) if "@" in email else (email, "")
            if len(local) <= 2:
                masked = local[0] + "***"
            else:
                masked = local[:2] + "***"
            return f"{masked}@{domain}" if domain else masked

        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        count = len(failures)

        rows_html = ""
        for f in failures:
            ts = f.get("timestamp", "")
            # Convert UTC ISO to ET display
            try:
                from pytz import timezone as _tz
                dt = datetime.fromisoformat(ts)
                dt_et = dt.replace(tzinfo=_tz("UTC")).astimezone(_tz("US/Eastern"))
                time_str = dt_et.strftime("%I:%M %p ET")
            except Exception:
                time_str = ts[:19] if ts else "unknown"

            recipient = mask_email(f.get("to_email", "unknown"))
            subj = f.get("subject", "")[:80]
            error = f.get("error", "")[:100]
            attempts = f.get("attempts", "?")

            rows_html += f"""<tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #374151;">{time_str}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #374151;">{recipient}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #374151;">{subj}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #dc2626;">{error}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px; color: #374151; text-align: center;">{attempts}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width: 700px; margin: 0 auto;">
<tr>
    <td style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding: 24px; text-align: center;">
        <h1 style="margin: 0; color: #f59e0b; font-size: 20px; font-weight: 700;">Email Failure Report</h1>
        <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 14px;">{count} failed delivery{'s' if count != 1 else ''} on {date_str}</p>
    </td>
</tr>
<tr>
    <td style="background-color: #ffffff; padding: 24px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
            <thead>
                <tr style="background-color: #f9fafb;">
                    <th style="padding: 10px 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Time</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Recipient</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Subject</th>
                    <th style="padding: 10px 12px; text-align: left; font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Error</th>
                    <th style="padding: 10px 12px; text-align: center; font-size: 12px; color: #6b7280; font-weight: 600; text-transform: uppercase;">Tries</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <p style="margin: 16px 0 0 0; font-size: 12px; color: #9ca3af;">
            Each email was retried 3 times with exponential backoff before being marked as failed.
            Recipient emails are masked for privacy.
        </p>
    </td>
</tr>
<tr>
    <td style="background-color: #f9fafb; padding: 16px; text-align: center; border-top: 1px solid #e5e7eb;">
        <p style="margin: 0; font-size: 12px; color: #9ca3af;">&copy; {datetime.now().year} RigaCap — Admin Notification</p>
    </td>
</tr>
</table>
</body></html>"""

        subject = f"[RigaCap] Email Failure Report — {count} failed ({date_str})"
        return await self.send_email(to_email=to_email, subject=subject, html_content=html)


    async def send_health_report(self, to_email: str, report) -> bool:
        """
        Send daily pipeline health report email.

        Args:
            to_email: Admin email address
            report: HealthReport instance from health_monitor_service

        Only sends when there are warnings/errors (unless always_send=True at caller).
        """
        from app.services.health_monitor_service import HealthStatus

        total = len(report.checks)
        green = report.green_count
        yellow = report.yellow_count
        red = report.red_count

        # Subject line varies by severity
        if red > 0:
            subject = f"ALERT Pipeline Health: {red} Error(s)"
            if yellow > 0:
                subject += f", {yellow} Warning(s)"
        elif yellow > 0:
            names = ", ".join(report.yellow_names[:3])
            subject = f"Pipeline Health: {yellow} Warning(s) -- {names}"
        else:
            subject = f"Pipeline Health: All Clear ({green}/{total} green)"

        # Header color based on overall status
        if report.overall_status == HealthStatus.RED:
            header_bg = "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)"
            header_label = "ERRORS DETECTED"
        elif report.overall_status == HealthStatus.YELLOW:
            header_bg = "linear-gradient(135deg, #d97706 0%, #b45309 100%)"
            header_label = "WARNINGS"
        else:
            header_bg = "linear-gradient(135deg, #172554 0%, #1e3a5f 100%)"
            header_label = "ALL SYSTEMS HEALTHY"

        # Status icons
        status_icons = {
            HealthStatus.GREEN: "&#9989;",   # green checkmark
            HealthStatus.YELLOW: "&#9888;&#65039;",  # warning
            HealthStatus.RED: "&#10060;",    # red X
        }

        # Build rows grouped by category
        check_rows = ""
        current_category = None
        for check in report.checks:
            if check.category != current_category:
                current_category = check.category
                check_rows += f"""
                <tr>
                    <td colspan="4" style="padding: 8px 12px 2px; font-size: 10px; font-weight: 700;
                        text-transform: uppercase; color: #6b7280; letter-spacing: 0.05em;
                        border-top: 1px solid #e5e7eb;">
                        {current_category}
                    </td>
                </tr>"""

            row_bg = "#ffffff"
            if check.status == HealthStatus.RED:
                row_bg = "#fef2f2"
            elif check.status == HealthStatus.YELLOW:
                row_bg = "#fffbeb"

            icon = status_icons.get(check.status, "")
            check_rows += f"""
                <tr style="background-color: {row_bg};">
                    <td style="padding: 3px 10px; border-bottom: 1px solid #f3f4f6; font-size: 13px; width: 24px;">
                        {icon}
                    </td>
                    <td style="padding: 3px 10px; border-bottom: 1px solid #f3f4f6; font-size: 13px; font-weight: 600; color: #111827;">
                        {check.name}
                    </td>
                    <td style="padding: 3px 10px; border-bottom: 1px solid #f3f4f6; font-size: 13px; color: #374151;">
                        {check.value}
                    </td>
                    <td style="padding: 3px 10px; border-bottom: 1px solid #f3f4f6; font-size: 12px; color: #6b7280;">
                        {check.message}
                    </td>
                </tr>"""

            # Resolution row for non-green checks
            if check.status != HealthStatus.GREEN and check.resolution:
                res_bg = "#fef3c7" if check.status == HealthStatus.YELLOW else "#fee2e2"
                res_color = "#92400e" if check.status == HealthStatus.YELLOW else "#991b1b"
                check_rows += f"""
                <tr>
                    <td colspan="4" style="padding: 2px 12px 4px 36px; font-size: 12px;
                        color: {res_color}; background-color: {res_bg};">
                        &#8594; {check.resolution}
                    </td>
                </tr>"""

        # Summary banner
        summary_parts = []
        if green > 0:
            summary_parts.append(f'<span style="color: #16a34a; font-weight: 700;">{green} green</span>')
        if yellow > 0:
            summary_parts.append(f'<span style="color: #d97706; font-weight: 700;">{yellow} yellow</span>')
        if red > 0:
            summary_parts.append(f'<span style="color: #dc2626; font-weight: 700;">{red} red</span>')
        summary_text = " &bull; ".join(summary_parts)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 650px; margin: 0 auto; background-color: #ffffff;">
        <!-- Header -->
        <tr>
            <td style="background: {header_bg}; padding: 14px 20px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 17px; font-weight: 700;">
                    Pipeline Health &middot; <span style="font-weight: 500; opacity: 0.9;">{header_label}</span>
                </h1>
            </td>
        </tr>

        <!-- Summary Banner -->
        <tr>
            <td style="padding: 8px 20px; background-color: #f9fafb; border-bottom: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 13px; text-align: center;">
                    {summary_text} &mdash; {total} checks
                </p>
            </td>
        </tr>

        <!-- Check Table -->
        <tr>
            <td style="padding: 0 12px 8px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    {check_rows}
                </table>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f9fafb; padding: 10px 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 11px; color: #9ca3af;">
                    RigaCap Admin &middot; {report.timestamp.strftime('%Y-%m-%d %H:%M')} ET
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""

        # Plain text fallback
        text_lines = [
            "PIPELINE HEALTH REPORT",
            "=" * 40,
            f"{green} green, {yellow} yellow, {red} red ({total} checks)",
            "",
        ]
        for check in report.checks:
            icon = {"green": "OK", "yellow": "WARN", "red": "FAIL"}.get(check.status.value, "??")
            text_lines.append(f"[{icon}] {check.name}: {check.value} - {check.message}")
            if check.status != HealthStatus.GREEN and check.resolution:
                text_lines.append(f"     -> {check.resolution}")
        text_lines.append("")
        text_lines.append(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M')} ET")

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            text_content="\n".join(text_lines),
        )


admin_email_service = AdminEmailService()
