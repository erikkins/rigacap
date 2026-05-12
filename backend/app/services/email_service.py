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


def get_email_failures() -> list[dict]:
    """Return accumulated email failures since last clear."""
    return list(_failure_log)


def clear_email_failures():
    """Clear the failure log (after admin report is sent)."""
    _failure_log.clear()


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


class EmailService:
    """
    Manages email sending for daily summaries and alerts
    """

    def __init__(self):
        self.enabled = bool(SMTP_USER and SMTP_PASS)
        if not self.enabled:
            logger.warning("Email service disabled - SMTP credentials not configured")

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
<td><img src="https://rigacap.com/email-header.png" alt="RigaCap." width="150" height="36" style="display:block;" /></td>
<td align="right" style="font-family:'Courier New',monospace;font-size:11px;color:#8A8279;letter-spacing:1px;text-transform:uppercase;">{label}</td>
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
                <p style="margin: 0 0 8px; font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; line-height: 1.8; text-align: center;">
                    RigaCap &middot; Disciplined Momentum Strategy<br>
                    <a href="https://rigacap.com/app" style="color: #7A2430; text-decoration: underline;">Dashboard</a>
                    &nbsp;&middot;&nbsp;
                    <a href="{manage_url}" style="color: #7A2430; text-decoration: underline;">Manage Alerts</a>
                    &nbsp;&middot;&nbsp;
                    <a href="{unsub_url}" style="color: #8A8279; text-decoration: underline;">Unsubscribe</a>
                </p>
                <p style="margin: 0; font-family: 'Courier New', monospace; font-size: 9px; color: #C9BFAC; line-height: 1.6; text-align: center;">
                    For information purposes only. Not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest.<br>
                    RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
                </p>
                <p style="margin: 8px 0 0; font-family: 'Courier New', monospace; font-size: 9px; color: #C9BFAC; text-align: center;">
                    &copy; {datetime.now().year} RigaCap, LLC
                </p>
            </td>
        </tr>'''

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        user_id: str = None,
        list_unsubscribe_url: Optional[str] = None,
        email_type: Optional[str] = None,
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
        market_context: str = None
    ) -> str:
        """
        Generate beautiful HTML for daily summary email

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
        fresh_signals = [s for s in signals if s.get('is_fresh')]
        watchlist = watchlist or []

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
                            <img src="https://rigacap.com/email-header.png" alt="RigaCap." width="150" height="36" style="display: block;" />
                        </td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; letter-spacing: 1px; text-transform: uppercase;">
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
                            <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;">{date_str}</div>
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

        <!-- Market Context -->
        {f'''<tr>
            <td style="padding: 0 24px 20px;">
                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0;">
                    <div style="font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.65;">{market_context}</div>
                </div>
            </td>
        </tr>''' if market_context else ''}

        <!-- Buy Signals Section (fresh only) -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 1px solid #DDD5C7; margin-bottom: 12px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Buy Signals <span style="font-style: italic; color: #8A8279; font-weight: 400;">({len(fresh_signals)})</span></td>
                            <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #7A2430;">Consider adding</td>
                        </tr>
                    </table>
                </div>
                {"".join(self._signal_row(s) for s in fresh_signals[:8]) if fresh_signals else f'''
                <div style="padding: 24px; text-align: center; font-family: Georgia, serif; font-style: italic; color: #5A544E;">
                    No fresh signals today.{f" {len(watchlist)} approaching trigger." if watchlist else ""}
                </div>
                '''}
            </td>
        </tr>

        <!-- Monitoring Section (non-fresh signals) -->
        {self._monitoring_section([s for s in signals if not s.get('is_fresh')]) if [s for s in signals if not s.get('is_fresh')] else ''}

        <!-- Watchlist Section -->
        {self._watchlist_section(watchlist) if watchlist else ''}

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

    def _signal_row(self, signal: Dict) -> str:
        """Generate HTML for a single signal row"""
        symbol = signal.get('symbol', 'N/A')
        price = signal.get('price', 0)
        pct_above = signal.get('pct_above_dwap', 0)
        mom_rank = signal.get('momentum_rank', 0)
        is_strong = signal.get('is_strong', False)
        is_fresh = signal.get('is_fresh', False)
        days_since = signal.get('days_since_crossover')

        strength_label = 'STRONG' if is_strong else ''
        age_label = ''
        if is_fresh and days_since is not None and days_since == 0:
            age_label = 'TODAY'
        elif is_fresh and days_since is not None:
            age_label = f'{days_since}D AGO'

        return f"""
        <div style="padding: 14px 0; border-bottom: 1px solid #DDD5C7; {('border-left: 3px solid #7A2430; padding-left: 14px;' if is_fresh else '')}">
            <table cellpadding="0" cellspacing="0" style="width: 100%;">
                <tr>
                    <td style="width: 40%;">
                        <div style="font-family: Georgia, serif; font-size: 18px; font-weight: 500; color: #141210;">
                            <a href="https://rigacap.com/app?chart={symbol}" style="color: #141210; text-decoration: none;">{symbol}</a>
                        </div>
                        <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; letter-spacing: 0.5px; margin-top: 2px;">
                            {age_label}
                        </div>
                    </td>
                    <td style="width: 25%; text-align: right; font-family: 'Courier New', monospace; font-size: 13px; color: #141210;">
                        ${price:.2f}
                    </td>
                    <td style="width: 20%; text-align: right; font-family: 'Courier New', monospace; font-size: 13px; color: #2D5F3F;">
                        +{pct_above:.1f}%
                    </td>
                    <td style="width: 15%; text-align: right; font-family: 'Courier New', monospace; font-size: 11px; color: #7A2430; letter-spacing: 1px; text-transform: uppercase;">
                        {strength_label}
                    </td>
                </tr>
            </table>
        </div>
        """

    def _monitoring_section(self, monitoring_signals: List[Dict], max_rows: int = 6) -> str:
        """Generate HTML for monitoring section (non-fresh signals above breakout trigger + top momentum)"""
        if not monitoring_signals:
            return ''

        total = len(monitoring_signals)
        shown = monitoring_signals[:max_rows]
        rows = "".join(self._signal_row(s) for s in shown)
        remaining = total - len(shown)
        more_note = f"""
                <tr>
                    <td colspan="4" style="padding: 8px 0; text-align: center; font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #8A8279;">
                        and {remaining} more on your <a href="https://rigacap.com/app" style="color: #7A2430; text-decoration: none;">dashboard</a>
                    </td>
                </tr>""" if remaining > 0 else ""
        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; padding-bottom: 8px; border-bottom: 1px solid #DDD5C7; margin-bottom: 8px;">
                    <tr>
                        <td style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Monitoring <span style="font-style: italic; color: #8A8279; font-weight: 400;">({total})</span></td>
                        <td align="right" style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #5A544E;">Watching for entry</td>
                    </tr>
                </table>
                {rows}{more_note}
            </td>
        </tr>
        """

    def _watchlist_section(self, watchlist: List[Dict]) -> str:
        """Generate HTML for watchlist (approaching trigger) section"""
        if not watchlist:
            return ''

        rows = ""
        for w in watchlist[:3]:
            symbol = w.get('symbol', 'N/A')
            price = w.get('price', 0)
            distance = w.get('distance_to_trigger', 0)

            rows += f"""
            <tr>
                <td style="width: 40%; padding: 10px 0; border-bottom: 1px solid #DDD5C7;">
                    <a href="https://rigacap.com/app?chart={symbol}" style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210; text-decoration: none;">{symbol}</a>
                </td>
                <td style="width: 25%; padding: 10px 0; text-align: right; border-bottom: 1px solid #DDD5C7; font-family: 'Courier New', monospace; font-size: 13px; color: #141210;">
                    ${price:.2f}
                </td>
                <td style="width: 35%; padding: 10px 0; text-align: right; border-bottom: 1px solid #DDD5C7; font-family: 'Courier New', monospace; font-size: 11px; color: #5A544E;">
                    +{distance:.1f}% to trigger
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="padding-bottom: 8px; border-bottom: 2px solid #141210; margin-bottom: 12px;">
                    <span style="font-family: Georgia, serif; font-size: 16px; font-weight: 500; color: #141210;">Watchlist</span>
                    <span style="font-family: Georgia, serif; font-style: italic; font-size: 13px; color: #5A544E;"> — Approaching trigger</span>
                </div>
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    {rows}
                </table>
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
        fresh_signals = [s for s in signals if s.get('is_fresh')]

        lines = [
            f"RIGACAP DAILY - {date_str}",
            "=" * 40,
            "",
            f"Market Regime: {market_regime.get('regime', 'N/A') if market_regime else 'N/A'}",
            f"S&P 500: ${market_regime.get('spy_price', 'N/A') if market_regime else 'N/A'}",
            f"Market Fear: {_vix_label(market_regime.get('vix_level')) if market_regime else 'N/A'}",
            "",
            f"BUY SIGNALS ({len(fresh_signals)})",
            "-" * 40,
        ]

        non_fresh = [s for s in signals if not s.get('is_fresh')]

        if fresh_signals:
            for s in fresh_signals[:8]:
                symbol = s.get('symbol', 'N/A')
                price = s.get('price', 0)
                pct = s.get('pct_above_dwap', 0)
                mom_rank = s.get('momentum_rank', 0)
                fresh_tag = " [NEW TODAY]" if s.get('days_since_crossover') == 0 else " [FRESH]"
                lines.append(f"  {symbol}: ${price:.2f} (Rank #{mom_rank}) - Breakout +{pct:.1f}%{fresh_tag}")
        else:
            lines.append(f"  No fresh buy signals today")

        if non_fresh:
            lines.extend(["", f"MONITORING ({len(non_fresh)})", "-" * 40])
            for s in non_fresh[:6]:
                symbol = s.get('symbol', 'N/A')
                price = s.get('price', 0)
                pct = s.get('pct_above_dwap', 0)
                mom_rank = s.get('momentum_rank', 0)
                lines.append(f"  {symbol}: ${price:.2f} (Rank #{mom_rank}) - Breakout +{pct:.1f}%")

        if not signals and watchlist:
            lines.append(f"  No fresh signals — {len(watchlist)} stock(s) on watchlist")

        if watchlist:
            lines.extend(["", "WATCHLIST — APPROACHING TRIGGER:", "-" * 40])
            for w in watchlist[:3]:
                lines.append(f"  {w.get('symbol', 'N/A')}: ${w.get('price', 0):.2f} — +{w.get('distance_to_trigger', 0):.1f}% to go")

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
        market_context: str = None
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

        fresh_count = len([s for s in signals if s.get('is_fresh')])
        # Include date in subject for historical (time-travel) emails
        is_historical = date and date.date() != _now_et().date()
        date_label = f" [{date.strftime('%b %d, %Y')}]" if is_historical else ""
        if fresh_count > 0:
            subject = f"📊 RigaCap Daily{date_label}: {fresh_count} Ensemble Signal{'s' if fresh_count != 1 else ''}"
        elif watchlist:
            subject = f"📊 Market Update{date_label} — {len(watchlist)} on Watchlist"
        else:
            subject = f"📊 RigaCap Daily{date_label}: Market Update"

        html = self.generate_daily_summary_html(
            signals=signals,
            market_regime=market_regime,
            positions=positions,
            missed_opportunities=missed_opportunities,
            watchlist=watchlist,
            regime_forecast=regime_forecast,
            date=date,
            user_id=user_id,
            market_context=market_context
        )

        text = self.generate_plain_text(signals, market_regime, date=date, watchlist=watchlist)

        return await self.send_email(to_email, subject, html, text, user_id=user_id, email_type="daily_digest")

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
                RigaCap is a disciplined momentum signal service built by a former Chief Innovation Officer with 15 years of quantitative research. Walk-forward validated. $129/month with a 7-day free trial.
                <a href="https://rigacap.com" style="color: #7A2430;">Start your trial &rarr;</a>
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

Start a 7-day trial: https://rigacap.com
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
                RigaCap is a disciplined momentum signal service. Walk-forward validated. $129/month with a 7-day free trial.
                <a href="https://rigacap.com" style="color: #7A2430;">Start your trial &rarr;</a>
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


    async def send_welcome_email(self, to_email: str, name: str, referral_code: str = None, user_id: str = None) -> bool:
        """
        Send a beautiful welcome email when a user signs up.
        """
        first_name = name.split()[0] if name else "there"

        referral_html = ""
        referral_text = ""
        if referral_code:
            referral_html = f'''
                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 28px 0; text-align: center;">
                    <p style="margin: 0 0 8px; font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Give a Month, Get a Month</p>
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
                        <td><img src="https://rigacap.com/email-header.png" alt="RigaCap." width="150" height="36" style="display: block;" /></td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; letter-spacing: 1px; text-transform: uppercase;">Welcome</td>
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
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    Welcome to RigaCap. I built this because I got tired of overriding my own rules — the system doesn't have that problem.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px; line-height: 1.65;">
                    You now have access to the Ensemble strategy — a disciplined momentum system combining breakout timing, momentum quality ranking, and adaptive risk management. Walk-forward validated across multiple start dates with no hindsight bias.
                </p>

                <!-- What You Get -->
                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 28px 0;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Ensemble buy signals (3-4 per month)</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Daily email digest at 6 PM ET</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— 7-regime market detection</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Trailing stop alerts (intraday)</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Portfolio tracking</td></tr>
                        <tr><td style="padding: 6px 0; font-size: 15px; color: #141210;">— Works with any broker</td></tr>
                    </table>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 24px 0; line-height: 1.65;">
                    Your <strong>7-day free trial</strong> starts now. Tomorrow you'll receive your first daily digest.
                </p>

                <!-- CTA -->
                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        View Today's Signals
                    </a>
                </div>

                <!-- Track Record -->
                <div style="border-left: 2px solid #7A2430; padding: 14px 18px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 15px; color: #141210; line-height: 1.6;">
                        ~21.5% annualized over 5 years, walk-forward validated.
                        <a href="https://rigacap.com/track-record" style="color: #7A2430; text-decoration: underline;">See the full track record.</a>
                    </p>
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
Welcome to RigaCap, {first_name}!

Your journey to smarter trading starts now.

Here's what you get:
- Ensemble signals — 3-4 high-conviction picks per month, delivered before market open
- Simple & Advanced views — clear actions or full technical details
- Smart watchlist — alerts when stocks approach buy triggers
- Trailing stop protection — adaptive risk management
- Market regime analysis — 7-regime detection
- Daily email digest
- Portfolio tracking
- Works with any broker — Schwab, Fidelity, IBKR — you execute, we signal

Your 7-day free trial starts now. Visit https://rigacap.com/app to see today's signals!

Our Track Record: ~21.5% annualized over 5 years, walk-forward validated. See the details: https://rigacap.com/track-record

Pro Tip: Look for signals with the green BUY badge — these are fresh breakouts with the highest conviction.
{referral_text}
Happy trading!
The RigaCap Team

---
For information purposes only. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
"""

        return await self.send_email(
            to_email=to_email,
            subject="🚀 Welcome to RigaCap — Your Trading Edge Starts Now!",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="welcome",
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
                        ~21.5% annualized over 5 years, walk-forward validated. Every start date stayed positive in 2022 (avg ~+8%) while the S&amp;P fell 20%.
                        <a href="https://rigacap.com/track-record" style="color: #7A2430; text-decoration: underline;">Full track record.</a>
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Subscribe — $129/month
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">Or $1,099/year (three months free)</p>
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

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E; margin: 0 0 8px;">Come Back</p>
                    <p style="font-family: Georgia, serif; font-size: 24px; color: #141210; margin: 0 0 4px;">20% off your first month</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0;">Code: {promo_code}</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Reactivate
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0; line-height: 1.5;">— Erik</p>"""

        html = self._email_wrapper("We'll be here", content, user_id)

        text = f"""{first_name}, your RigaCap subscription has ended. Come back with 20% off — code {promo_code}. Reply if something wasn't right. — Erik"""

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
        Send an onboarding drip email.

        Time-based (lifecycle, fired by day count from signup):
          Step 1 (Day 1): How Your Signals Work
          Step 2 (Day 3): Pro Tips for Better Returns
          Step 3 (Day 5): Your Trial Ends in 2 Days
          Step 4 (Day 6): Last Day of Your Free Trial
          Step 5 (Day 8): We Miss You (win-back)

        Event-triggered for subscribers (per marketing doc §14 — fire when
        the named event occurs, not on a calendar):
          Step 6: First trailing-stop hit (DR-005 in marketing doc)
          Step 7: First profitable exit (DR-006)
          Step 8: 7-day no-signal streak (DR-008)

        Re-engagement for trial-exited (no longer subscribers):
          Step 9: Worked-example after a signal fires post-trial (RE-001)
                  Renders {symbol}, {signal_date}, {entry_price},
                  {trail_stop}, {regime_context} placeholders — caller
                  supplies via str.format() before send. 24-48h delayed
                  delivery per Marketing Rule guidance.
          Step 10: 30-day "still here" check-in (RE-002)
          Step 11: 90-day quarterly summary (RE-003)
                   Renders {signal_count}, {cash_days}, {current_regime}.

        ATTORNEY REVIEW REQUIRED before steps 9-11 fire publicly: the
        worked-example mechanism in step 9 has Marketing Rule
        implications. Per project_marketing_strategy_doc.md §14: "Run
        by Juris (legal counsel) before shipping."

        Step-6+ triggering is event-driven, not day-based — see scheduler
        hooks (TODO) for when each one fires. Each is one-shot per
        recipient (tracked separately for steps 6-8 vs 9-11 since
        9-11 fire to former subscribers, not active ones).
        """
        first_name = name.split()[0] if name else "there"

        subjects = {
            1: "How Your Signals Work",
            2: "Three things most traders get wrong",
            3: "Your trial ends in 2 days",
            4: "Last day of your free trial",
            5: "What you've been missing",
            6: "About that trailing stop",
            7: "Locked in",
            8: "Quiet week",
            9: "A signal you missed (worked example)",
            10: "Still here",
            11: "Quarterly check-in",
        }

        subject = f"RigaCap — {subjects.get(step, 'RigaCap')}"

        content_blocks = {
            1: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    I built RigaCap because I got tired of overriding my own rules. The system doesn't have that problem. Here's how it works.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0 0 4px; font-family: 'Courier New', monospace; font-size: 10px; font-weight: 500; letter-spacing: 3px; text-transform: uppercase; color: #5A544E;">Three Factors, Every Signal</p>
                    <ol style="margin: 12px 0 0; padding: 0 0 0 20px; color: #141210; line-height: 2; font-size: 15px;">
                        <li><strong>Breakout detection</strong> — spots stocks breaking out of their long-term range</li>
                        <li><strong>Momentum ranking</strong> — only the top-ranked names make the cut</li>
                        <li><strong>Confirmation</strong> — volume spike + near recent highs. All three must align.</li>
                    </ol>
                </div>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Fresh Signals</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">New breakouts — high conviction entries</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Monitoring</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Strong momentum — approaching entry</div>
                        </td>
                    </tr>
                </table>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        View Today's Signals
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Tomorrow you'll receive your first daily digest — a summary of fresh signals delivered to your inbox each evening.
                </p>
            """,
            2: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Most retail investors are reasonably good at finding ideas and reliably bad at three specific things. Here's how the system handles each one.
                </p>

                <div style="border-top: 1px solid #DDD5C7; padding: 20px 0;">
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #7A2430; margin: 0 0 8px;">Ⅰ / Sitting in Cash</p>
                    <p style="font-family: Georgia, serif; font-size: 18px; color: #141210; margin: 0 0 8px; font-weight: 500;">The system knows when not to trade.</p>
                    <p style="font-size: 15px; color: #5A544E; margin: 0; line-height: 1.6;">Seven-regime market detection moves to cash when conditions deteriorate. Most months, few or no signals. That discipline is the product.</p>
                </div>

                <div style="border-top: 1px solid #DDD5C7; padding: 20px 0;">
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #7A2430; margin: 0 0 8px;">Ⅱ / Honoring Stops</p>
                    <p style="font-family: Georgia, serif; font-size: 18px; color: #141210; margin: 0 0 8px; font-weight: 500;">Trailing stops close positions without the argument.</p>
                    <p style="font-size: 15px; color: #5A544E; margin: 0; line-height: 1.6;">When a stop hits, you get an alert. No second-guessing, no "maybe it'll bounce back." The system already decided.</p>
                </div>

                <div style="border-top: 1px solid #DDD5C7; padding: 20px 0;">
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #7A2430; margin: 0 0 8px;">Ⅲ / Not Doubling Down</p>
                    <p style="font-family: Georgia, serif; font-size: 18px; color: #141210; margin: 0 0 8px; font-weight: 500;">No averaging down. No bag-holding.</p>
                    <p style="font-size: 15px; color: #5A544E; margin: 0; line-height: 1.6;">The ensemble ranks every stock fresh. A losing position doesn't get more capital — it gets replaced by whatever's strongest now.</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Open Dashboard
                    </a>
                </div>
            """,
            3: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Your free trial ends in <strong>2 days</strong>. Here's what the system has delivered during that time — and what you'll keep with a subscription.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 2px solid #141210; border-bottom: 1px solid #141210; margin: 28px 0;">
                    <tr>
                        <td style="padding: 16px 16px 16px 0; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Annualized</div>
                            <div style="font-family: Georgia, serif; font-size: 32px; color: #2D5F3F; margin-top: 4px;">~21.5%</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; margin-top: 2px;">Friction-adjusted</div>
                        </td>
                        <td style="padding: 16px; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Sharpe</div>
                            <div style="font-family: Georgia, serif; font-size: 32px; color: #141210; margin-top: 4px;">0.95</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; margin-top: 2px;">Risk-adjusted</div>
                        </td>
                        <td style="padding: 16px 0 16px 16px; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Validated</div>
                            <div style="font-family: Georgia, serif; font-size: 32px; color: #141210; margin-top: 4px;">5 yr</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; margin-top: 2px;">Walk-forward</div>
                        </td>
                    </tr>
                </table>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.6;">
                        Every start date in our 5-year walk-forward stayed positive in 2022 (averaging ~+8%) while the S&amp;P fell 20%. That behavior — not the headline return — is what you're paying for.
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Subscribe — $129/month
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">Or $1,099/year (three months free)</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Questions? Reply to this email — it comes straight to me.
                </p>
            """,
            4: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Your free trial ends today. After this, you'll lose access to signals, regime detection, and position guidance.
                </p>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0;">
                    <p style="font-family: Georgia, serif; font-size: 17px; color: #141210; margin: 0; line-height: 1.65;">
                        The value proposition is simple: on a $100K portfolio, the strategy's ~21.5% annualized vs SPY's ~13% historical
                        is roughly <strong>$8,500/year of potential excess return</strong>. A subscription at $1,548/year captures less than 20% of that value.
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 16px 40px; text-decoration: none;">
                        Subscribe Now
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">$129/month · $1,099/year · Cancel anytime</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Reply to this email if you have questions. — Erik
                </p>
            """,
            5: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Your trial ended, but the system is still running. The ensemble generates 3–4 high-conviction signals per month — and stays quiet when conditions aren't right.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.6;">
                        The hardest work of investing isn't the analysis. It's executing boring rules consistently. That's what you were paying for — and what's waiting if you come back.
                    </p>
                </div>

                <div style="border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; padding: 20px 0; margin: 24px 0; text-align: center;">
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E; margin: 0 0 8px;">Come Back</p>
                    <p style="font-family: Georgia, serif; font-size: 28px; color: #141210; margin: 0 0 4px;">20% off your first month</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0;">Use code COMEBACK20 at checkout</p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app?promo=COMEBACK20"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Reactivate
                    </a>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    If something wasn't right, reply and tell me. I read every response. — Erik
                </p>
            """,
            6: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    A trailing stop just fired on one of your positions. That can feel like a loss — and on this trade, financially, it was. But the stop firing isn't the system failing. It's the system doing the hardest job in trading.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 17px; color: #141210; line-height: 1.65;">
                        Discretionary traders override stops constantly. "It'll come back." "Just one more day." That's how a 12% loss becomes a 30% loss. The system doesn't have that conversation.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Trailing stops aren't designed to maximize a single trade. They're designed to keep losses bounded across hundreds of trades. The math only works if every stop fires — including this one. The next signal already ranks fresh; that's where capital goes next.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">What You Avoided</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">A 12% loss capped before it became 25%</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">What's Next</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Capital redeploys to the strongest current signal</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    If you're tempted to override the next one, reply and tell me — I'll talk you out of it. — Erik
                </p>
            """,
            7: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    One of your positions just closed at a profit. The trailing stop did its other job — letting a winner run, then closing it before the gain evaporated. Worth pausing on what happened, because most retail traders never see this trade end this way.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 17px; color: #141210; line-height: 1.65;">
                        The instinct on a winner is to take it early — "lock it in before it gives back." That instinct is exactly why most retail underperforms. Winners need room to compound; losers need to be cut.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    The system doesn't care that you "had a feeling" about exiting earlier. It tracks the high water mark and only closes when the trail breaches. The trade ended where the math said it should end — not where your emotions wanted it to.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Win/Loss Ratio</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Winners average 1.7× the size of losers</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Why It Works</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">Asymmetric outcomes, executed without flinching</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Worth a small celebration. Not a strategy change. — Erik
                </p>
            """,
            9: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Your trial ended quiet. Most of it landed in a stretch where the system stayed in cash, so you never saw a signal fire — and that's a tough way to evaluate something. I get it.
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    But yesterday, the system did fire. Here's what subscribers saw — delivered as a worked example, not a trade idea. The window has closed; this is what happened.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 2px solid #141210; border-bottom: 1px solid #141210; margin: 28px 0;">
                    <tr>
                        <td style="padding: 16px 16px 16px 0; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Signal</div>
                            <div style="font-family: Georgia, serif; font-size: 22px; color: #141210; margin-top: 4px;">{{symbol}}</div>
                            <div style="font-family: 'Courier New', monospace; font-size: 10px; color: #8A8279; margin-top: 2px;">{{signal_date}}</div>
                        </td>
                        <td style="padding: 16px; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Entry</div>
                            <div style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin-top: 4px;">${{entry_price}}</div>
                        </td>
                        <td style="padding: 16px 0 16px 16px; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Trail</div>
                            <div style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin-top: 4px;">${{trail_stop}}</div>
                        </td>
                    </tr>
                </table>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.65;">
                        {{regime_context}} — that's why the breakout passed every filter. The system was waiting; this was the entry it was waiting for.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    If you'd been a subscriber, you would have received this signal in real-time, with the entry price, the stop level, and the regime context. Subscribers act on it; trial-exits see it 24 hours later as a worked example, like this one.
                </p>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app?promo=COMEBACK20"
                       style="display: inline-block; background: #141210; color: #F5F1E8; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; padding: 14px 36px; text-decoration: none;">
                        Reactivate — 20% off
                    </a>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin-top: 8px;">Use code COMEBACK20</p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    No pressure. The next signal will fire when the system says it should — could be days, could be weeks. — Erik
                </p>
            """,
            10: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    It's been about a month since your trial ended. No pitch, no urgency — I just wanted to say I'm still here, and the system is still working.
                </p>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    A handful of signals fired since you left. A couple of trailing stops triggered. Mostly the system has been doing what it usually does: waiting for the conditions it likes, and staying in cash when it doesn't see them.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 16px 20px; background: #FAF7F0; margin: 24px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 16px; color: #141210; line-height: 1.65;">
                        If you tried RigaCap and it wasn't right for where you are, that's fine. If you're still curious but the timing wasn't right then, the door's open whenever it is.
                    </p>
                </div>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Reply if you want to talk through anything specific. — Erik
                </p>
            """,
            11: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    A quarter has passed since your trial. Here's what the system has done in that time — not a sales pitch, just the honest summary I'd want if I were where you are.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 2px solid #141210; border-bottom: 1px solid #141210; margin: 28px 0;">
                    <tr>
                        <td style="padding: 16px 16px 16px 0; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Signals Fired</div>
                            <div style="font-family: Georgia, serif; font-size: 28px; color: #141210; margin-top: 4px;">{{signal_count}}</div>
                        </td>
                        <td style="padding: 16px; border-right: 1px solid #DDD5C7; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Days In Cash</div>
                            <div style="font-family: Georgia, serif; font-size: 28px; color: #141210; margin-top: 4px;">{{cash_days}}</div>
                        </td>
                        <td style="padding: 16px 0 16px 16px; text-align: center;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Active Regime</div>
                            <div style="font-family: Georgia, serif; font-size: 20px; color: #141210; margin-top: 4px;">{{current_regime}}</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    Whether or not RigaCap is for you, I hope your trading's been going well this quarter. If you want to come back, the door's still open.
                </p>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    No reply needed. — Erik
                </p>
            """,
            8: f"""
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    {first_name},
                </p>
                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    The system has been quiet for a week — no fresh signals, no entries. If you're wondering whether something's broken, it isn't. Quiet is one of the system's outputs.
                </p>

                <div style="border-left: 2px solid #7A2430; padding: 20px 24px; background: #FAF7F0; margin: 28px 0;">
                    <p style="margin: 0; font-family: Georgia, serif; font-style: italic; font-size: 17px; color: #141210; line-height: 1.65;">
                        When the system stays quiet, that's the discipline working. Most active traders force trades during quiet weeks — and most of those trades lose money. The hardest skill in this business is sitting still.
                    </p>
                </div>

                <p style="font-size: 17px; color: #141210; margin: 0 0 24px 0; line-height: 1.65;">
                    The seven-regime detector is reading current conditions and finding none of the criteria are met: breakouts aren't confirming, momentum is mid-pack, or breadth is thin. Any one of those alone might still produce a signal. All three together — silence.
                </p>

                <table cellpadding="0" cellspacing="0" style="width:100%; border-top: 1px solid #141210; border-bottom: 1px solid #DDD5C7; margin: 28px 0;">
                    <tr>
                        <td style="padding: 14px 16px 14px 0; border-right: 1px solid #DDD5C7;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">Typical Cadence</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">3–4 signals per month in healthy markets</div>
                        </td>
                        <td style="padding: 14px 16px;">
                            <div style="font-family: 'Courier New', monospace; font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E;">When Conditions Improve</div>
                            <div style="font-family: Georgia, serif; font-size: 13px; color: #141210; margin-top: 4px;">You'll see fresh signals back in the dashboard</div>
                        </td>
                    </tr>
                </table>

                <p style="font-size: 14px; color: #8A8279; margin: 24px 0 0 0; line-height: 1.5;">
                    Boring is the price of consistent. — Erik
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
                            <img src="https://rigacap.com/email-header.png" alt="RigaCap." width="150" height="36" style="display: block;" />
                        </td>
                        <td align="right" style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; letter-spacing: 1px; text-transform: uppercase;">
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

    async def send_double_signal_alert(
        self,
        to_email: str,
        new_signals: List[Dict],
        approaching: List[Dict] = None,
        market_regime: Dict = None,
        user_id: str = None
    ) -> bool:
        """
        Send alert when momentum stocks hit the breakout signal trigger.

        Args:
            to_email: Recipient email
            new_signals: List of newly triggered breakout signals
            approaching: Optional list of stocks approaching trigger (watchlist)
            market_regime: Current market regime info (regime, spy_price)

        Returns:
            True if sent successfully
        """
        if not new_signals:
            return True  # Nothing to send

        approaching = approaching or []

        # Build signal rows
        signal_rows = ""
        for s in new_signals[:10]:
            sym = s.get('symbol', 'N/A')
            price = s.get('price', 0)
            pct_above = s.get('pct_above_dwap', 0)
            mom_rank = s.get('momentum_rank', 0)
            days_since = s.get('days_since_crossover')
            age = 'TODAY' if days_since == 0 else (f'{days_since}D AGO' if days_since else '')

            signal_rows += f"""
                <tr>
                    <td style="width:40%; padding:12px 0; border-bottom:1px solid #DDD5C7;">
                        <span style="font-family:Georgia,serif; font-size:18px; font-weight:500; color:#141210;">{sym}</span>
                        <span style="display:block; font-family:'Courier New',monospace; font-size:10px; color:#8A8279; margin-top:2px;">{age}</span>
                    </td>
                    <td style="width:25%; padding:12px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:13px; color:#141210;">${price:.2f}</td>
                    <td style="width:20%; padding:12px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:13px; color:#2D5F3F;">+{pct_above:.1f}%</td>
                    <td style="width:15%; padding:12px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:11px; color:#7A2430;">#{mom_rank}</td>
                </tr>"""

        # Approaching watchlist
        watch_rows = ""
        if approaching:
            for a in approaching[:5]:
                watch_rows += f"""<tr>
                    <td style="width:40%; padding:8px 0; border-bottom:1px solid #DDD5C7; font-family:Georgia,serif; font-size:15px; color:#141210;">{a.get('symbol','')}</td>
                    <td style="width:25%; padding:8px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:12px; color:#141210;">${a.get('price',0):.2f}</td>
                    <td style="width:35%; padding:8px 0; border-bottom:1px solid #DDD5C7; text-align:right; font-family:'Courier New',monospace; font-size:11px; color:#5A544E;">+{a.get('distance_to_trigger',0):.1f}% to trigger</td>
                </tr>"""

        regime_line = f"""<p style="font-family:'Courier New',monospace; font-size:12px; color:#5A544E; margin:0 0 20px;">
            Market: {market_regime.get('regime','').replace('_',' ').title()} &middot; SPY ${market_regime.get('spy_price','N/A')}</p>""" if market_regime else ""

        watchlist_section = f"""
                <div style="padding-bottom:8px; border-bottom:1px solid #DDD5C7; margin:24px 0 12px;">
                    <span style="font-family:Georgia,serif; font-size:14px; font-weight:500; color:#141210;">Approaching Trigger</span>
                    <span style="font-family:Georgia,serif; font-style:italic; font-size:12px; color:#5A544E;"> ({len(approaching)})</span>
                </div>
                <table cellpadding="0" cellspacing="0" style="width:100%;">{watch_rows}</table>""" if approaching else ""

        content = f"""
                {regime_line}
                <div style="padding-bottom:8px; border-bottom:2px solid #141210; margin-bottom:12px;">
                    <table cellpadding="0" cellspacing="0" style="width:100%;">
                        <tr>
                            <td style="font-family:Georgia,serif; font-size:16px; font-weight:500; color:#141210;">New Signals <span style="font-style:italic; color:#8A8279; font-weight:400;">({len(new_signals)})</span></td>
                            <td align="right" style="font-family:Georgia,serif; font-style:italic; font-size:13px; color:#7A2430;">Consider adding</td>
                        </tr>
                    </table>
                </div>
                <table cellpadding="0" cellspacing="0" style="width:100%;">{signal_rows}</table>
                {watchlist_section}
                <div style="text-align:center; margin:28px 0;">
                    <a href="https://rigacap.com/app" style="display:inline-block; background:#141210; color:#F5F1E8; font-size:13px; font-weight:500; letter-spacing:2px; text-transform:uppercase; padding:14px 36px; text-decoration:none;">View Dashboard</a>
                </div>"""

        html = self._email_wrapper("New Signals", content, user_id)

        symbols_text = ", ".join(s.get('symbol','') for s in new_signals[:5])
        text = f"New breakout signals: {symbols_text}. View at rigacap.com/app"

        return await self.send_email(
            to_email=to_email,
            subject=f"RigaCap — {len(new_signals)} new signal{'s' if len(new_signals) > 1 else ''}",
            html_content=html,
            text_content=text,
            user_id=user_id,
            email_type="double_signal_alert",
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
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E; margin: 0 0 8px;">Your Reward</p>
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

        Sent 24 hours after cancellation with 20% off comeback offer.
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
                    <p style="font-family: 'Courier New', monospace; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #5A544E; margin: 0 0 8px;">Come Back</p>
                    <p style="font-family: Georgia, serif; font-size: 24px; color: #141210; margin: 0 0 4px;">20% off your next month</p>
                    <p style="font-family: 'Courier New', monospace; font-size: 11px; color: #8A8279; margin: 0;">Code: {promo_code} · Valid 30 days</p>
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

        return await self.send_email(
            to_email=to_email,
            subject=f"⚠️ {subject}",
            html_content=html,
            text_content=message,
        )

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
                    {lookback_days}-day rolling backtest
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
        platform_display = "Twitter/X" if post.platform == "twitter" else "Instagram"
        platform_color = "#1DA1F2" if post.platform == "twitter" else "#E4405F"
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

        # Chart card image (if post has one)
        chart_img_html = ""
        image_s3_key = getattr(post, "image_s3_key", None)
        if image_s3_key:
            try:
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
