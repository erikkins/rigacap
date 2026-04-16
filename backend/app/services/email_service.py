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
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280;">
                    <a href="https://rigacap.com/app" style="color: #172554; text-decoration: none;">View Dashboard</a>
                    &nbsp;&bull;&nbsp;
                    <a href="{manage_url}" style="color: #172554; text-decoration: none;">Manage Alerts</a>
                    &nbsp;&bull;&nbsp;
                    <a href="{unsub_url}" style="color: #6b7280; text-decoration: none;">Unsubscribe</a>
                </p>
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Trading involves risk. Past performance does not guarantee future results.
                </p>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
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
    ) -> bool:
        """
        Send an email to a single recipient with retry + exponential backoff.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML body of the email
            text_content: Plain text fallback (optional)
            user_id: User ID for List-Unsubscribe header (omit for transactional emails)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email service disabled, would have sent to: {to_email}")
            return False

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

        # Regime styling - matches 7 regimes from market_regime.py REGIME_DEFINITIONS
        regime = market_regime.get('regime', 'range_bound') if market_regime else 'range_bound'
        regime_colors = {
            'strong_bull': ('#10B981', '#d1fae5', 'Strong Bull'),
            'weak_bull': ('#84CC16', '#ecfdf5', 'Weak Bull'),
            'rotating_bull': ('#8B5CF6', '#ede9fe', 'Rotating Bull'),
            'range_bound': ('#F59E0B', '#fef3c7', 'Range-Bound'),
            'weak_bear': ('#F97316', '#fff7ed', 'Weak Bear'),
            'panic_crash': ('#EF4444', '#fee2e2', 'Panic/Crash'),
            'recovery': ('#06B6D4', '#cffafe', 'Recovery'),
        }
        regime_color, regime_bg, regime_label = regime_colors.get(regime, ('#6b7280', '#f3f4f6', regime.replace('_', ' ').title()))

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
            <td style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="48" height="48" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    RigaCap Daily
                </h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    {date_str}
                </p>
            </td>
        </tr>

        <!-- Market Summary -->
        <tr>
            <td style="padding: 24px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    <tr>
                        <td style="background-color: {regime_bg}; border-radius: 12px; padding: 20px;">
                            <div style="font-size: 12px; text-transform: uppercase; color: #6b7280; font-weight: 600; margin-bottom: 8px;">
                                Market Regime
                            </div>
                            <div style="font-size: 24px; font-weight: 700; color: {regime_color};">
                                {regime_label}
                            </div>
                            <div style="margin-top: 12px; font-size: 14px; color: #374151;">
                                S&amp;P 500: ${market_regime.get('spy_price', 'N/A') if market_regime else 'N/A'} &nbsp;•&nbsp;
                                Market Fear: {_vix_label(market_regime.get('vix_level')) if market_regime else 'N/A'}
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>

        {f'''<!-- Market Context -->
        <tr>
            <td style="padding: 0 24px 16px;">
                <div style="background-color: #f0f9ff; border-left: 3px solid #3b82f6; border-radius: 6px; padding: 12px 16px;">
                    <div style="font-size: 13px; color: #1e40af; line-height: 1.5;">
                        {market_context}
                    </div>
                </div>
            </td>
        </tr>''' if market_context else ''}

        <!-- Buy Signals Section (fresh only) -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 4px 0; font-size: 18px; color: #111827; border-left: 4px solid #059669; padding-left: 12px;">
                    Ensemble Buy Signals{f' ({len(fresh_signals)})' if fresh_signals else ''}
                </h2>
                <p style="margin: 0 0 16px 16px; font-size: 13px; color: #6b7280;">
                    Recent breakout + top momentum — consider adding
                </p>
                {"".join(self._signal_row(s) for s in fresh_signals[:8]) if fresh_signals else f'''
                <div style="background-color: #f9fafb; border-radius: 8px; padding: 24px; text-align: center; color: #6b7280;">
                    No fresh buy signals today{f" — {len(watchlist)} stock{'s' if len(watchlist) != 1 else ''} approaching trigger" if watchlist else ". Check back tomorrow!"}
                </div>
                '''}
            </td>
        </tr>

        <!-- Monitoring Section (non-fresh signals) -->
        {self._monitoring_section([s for s in signals if not s.get('is_fresh')][:6]) if [s for s in signals if not s.get('is_fresh')] else ''}

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

        # Rank badge: Top 5 = green, Top 10 = blue, 11+ = gray
        if mom_rank and mom_rank <= 5:
            rank_color = '#059669'
            rank_label = f'#{mom_rank} Top 5'
        elif mom_rank and mom_rank <= 10:
            rank_color = '#2563eb'
            rank_label = f'#{mom_rank} Top 10'
        else:
            rank_color = '#6b7280'
            rank_label = f'Rank #{mom_rank}'

        badge = '<span style="display:inline-block;background:#172554;color:#c9a94e;font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;vertical-align:middle;">STRONG</span>' if is_strong else ''

        fresh_chip = ''
        if is_fresh and days_since is not None and days_since == 0:
            fresh_chip = '<span style="display: inline-block; background-color: #059669; color: #ffffff; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 99px; margin-left: 8px;">NEW TODAY</span>'
        elif is_fresh:
            fresh_chip = f'<span style="display: inline-block; background-color: #d1fae5; color: #065f46; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 99px; margin-left: 8px;">FRESH</span>'

        return f"""
        <div style="background-color: {'#f0fdf4' if is_fresh else '#f9fafb'}; border-radius: 8px; padding: 16px; margin-bottom: 8px; {('border-left: 4px solid #059669;' if is_fresh else '')}">
            <table cellpadding="0" cellspacing="0" style="width: 100%;">
                <tr>
                    <td>
                        <div style="font-size: 16px; font-weight: 600; color: #111827;">
                            <a href="https://rigacap.com/dashboard?chart={symbol}" style="color: #111827; text-decoration: none;">{symbol}</a> {badge}{fresh_chip}
                        </div>
                        <div style="font-size: 14px; color: #6b7280; margin-top: 4px;">
                            ${price:.2f} &nbsp;•&nbsp; Breakout +{pct_above:.1f}%
                        </div>
                    </td>
                    <td style="text-align: right;">
                        <div style="display: inline-block; background-color: {rank_color}; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 99px;">
                            {rank_label}
                        </div>
                    </td>
                </tr>
            </table>
        </div>
        """

    def _monitoring_section(self, monitoring_signals: List[Dict]) -> str:
        """Generate HTML for monitoring section (non-fresh signals above breakout trigger + top momentum)"""
        if not monitoring_signals:
            return ''

        rows = "".join(self._signal_row(s) for s in monitoring_signals)
        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 4px 0; font-size: 18px; color: #111827; border-left: 4px solid #6b7280; padding-left: 12px;">
                    Monitoring ({len(monitoring_signals)})
                </h2>
                <p style="margin: 0 0 16px 16px; font-size: 13px; color: #6b7280;">
                    Strong momentum, watching for fresh entry signal
                </p>
                {rows}
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
                <td style="padding: 8px 0; border-bottom: 1px solid #fef3c7;">
                    <a href="https://rigacap.com/dashboard?chart={symbol}" style="font-weight: 600; color: #111827; text-decoration: none;">{symbol}</a>
                    <span style="color: #6b7280; font-size: 12px;"> ${price:.2f}</span>
                </td>
                <td style="padding: 8px 0; text-align: right; border-bottom: 1px solid #fef3c7;">
                    <span style="display: inline-block; background-color: #fbbf24; color: #78350f; font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 99px;">
                        +{distance:.1f}% to go
                    </span>
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                        Watchlist — Approaching Trigger
                    </h3>
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        {rows}
                    </table>
                </div>
            </td>
        </tr>
        """

    def _positions_section(self, positions: List[Dict], total_pnl: float) -> str:
        """Generate HTML for positions section"""
        pnl_color = '#059669' if total_pnl >= 0 else '#dc2626'
        pnl_sign = '+' if total_pnl >= 0 else ''

        rows = ""
        for p in positions[:5]:
            symbol = p.get('symbol', 'N/A')
            shares = p.get('shares', 0)
            entry = p.get('entry_price', 0)
            current = p.get('current_price', entry)
            pnl = (current - entry) * shares
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            color = '#059669' if pnl >= 0 else '#dc2626'
            sign = '+' if pnl >= 0 else ''

            rows += f"""
            <tr>
                <td style="padding: 8px 0; border-bottom: 1px solid #e5e7eb;">
                    <span style="font-weight: 600;">{symbol}</span>
                    <span style="color: #6b7280; font-size: 12px;"> ({shares} shares)</span>
                </td>
                <td style="padding: 8px 0; text-align: right; border-bottom: 1px solid #e5e7eb;">
                    <span style="color: {color}; font-weight: 600;">{sign}${abs(pnl):.0f}</span>
                    <span style="color: {color}; font-size: 12px;"> ({sign}{pnl_pct:.1f}%)</span>
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827; border-left: 4px solid #172554; padding-left: 12px;">
                    Open Positions
                </h2>
                <table cellpadding="0" cellspacing="0" style="width: 100%;">
                    {rows}
                    <tr>
                        <td style="padding: 12px 0 0 0; font-weight: 600;">Total P&L</td>
                        <td style="padding: 12px 0 0 0; text-align: right; font-weight: 700; font-size: 18px; color: {pnl_color};">
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
                <td style="padding: 8px 0; border-bottom: 1px solid #fef3c7;">
                    <a href="https://rigacap.com/dashboard?chart={symbol}" style="font-weight: 600; color: #111827; text-decoration: none;">{symbol}</a>
                    <span style="color: #92400e; font-size: 12px;"> ({date})</span>
                </td>
                <td style="padding: 8px 0; text-align: right; border-bottom: 1px solid #fef3c7; color: #b45309;">
                    +{would_be:.1f}% (+${would_be_pnl:.0f})
                </td>
            </tr>
            """

        return f"""
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px;">
                    <h2 style="margin: 0 0 12px 0; font-size: 16px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                        Missed Opportunities
                    </h2>
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        {rows}
                    </table>
                    <div style="margin-top: 12px; font-size: 14px; color: #b45309; font-weight: 600;">
                        Total missed: +${total_missed:,.0f}
                    </div>
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
            "Trading involves risk. Past performance does not guarantee future results."
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

        return await self.send_email(to_email, subject, html, text, user_id=user_id)

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

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Georgia, serif; background-color: #f5f5f0; color: #1f2937;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 640px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="padding: 48px 40px 24px 40px; border-bottom: 1px solid #e5e7eb;">
                <h1 style="margin: 0; font-size: 32px; font-weight: 700; color: #172554; letter-spacing: -0.5px;">
                    Market, Measured.
                </h1>
                <p style="margin: 8px 0 0 0; font-size: 14px; color: #6b7280; font-style: italic;">
                    {date_str}
                </p>
            </td>
        </tr>

        <tr><td style="padding: 32px 40px 0 40px;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 1px;">
                The Reading
            </h2>
            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #1f2937;">
                {reading_line}
            </p>
        </td></tr>

        {f'''<tr><td style="padding: 28px 40px 0 40px;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 1px;">
                What the System Sees
            </h2>
            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #1f2937;">
                {market_context}
            </p>
        </td></tr>''' if market_context else ''}

        <tr><td style="padding: 28px 40px 0 40px;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 1px;">
                What the System is Doing
            </h2>
            <p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.7; color: #1f2937;">
                {buy_sentence}
            </p>
            <p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.7; color: #1f2937;">
                <strong>On the watchlist:</strong> {wl_sentence}
            </p>
            <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #1f2937;">
                <strong>Still holding:</strong> existing positions continue to be managed by our standard risk discipline.
            </p>
        </td></tr>

        {proof_block}

        <tr><td style="padding: 28px 40px 0 40px;">
            <h2 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 700; color: #92400e; text-transform: uppercase; letter-spacing: 1px;">
                What Would Change Things
            </h2>
            <ul style="margin: 0; padding: 0 0 0 20px; font-size: 16px; line-height: 1.8; color: #1f2937;">
                <li><strong>For more buys:</strong> we'd need broader rally conditions where many stocks break out simultaneously.</li>
                <li><strong>For defensive posture:</strong> a meaningful broad-market breakdown would flip the regime and move us to cash.</li>
                <li><strong>For now:</strong> stay patient. Quiet weeks are normal. The system is measuring, not reacting.</li>
            </ul>
        </td></tr>

        <tr><td style="padding: 36px 40px 0 40px;">
            <div style="border-top: 1px solid #e5e7eb; padding-top: 28px;">
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.7; color: #1f2937; font-style: italic;">
                    Three-to-four signals a month, sometimes zero.<br>
                    We trade when the math is clear — not when the news is loud.
                </p>
                <p style="margin: 0 0 8px 0; font-size: 15px; color: #374151;">
                    Want the signals when they fire?
                </p>
                <a href="https://rigacap.com" style="display: inline-block; background-color: #172554; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-size: 15px; font-weight: 600;">
                    Start a 7-day trial →
                </a>
            </div>
        </td></tr>

        {'' if show_symbols else '''<tr><td style="padding: 24px 40px 0 40px;">
            <div style="background: #f9fafb; border-left: 3px solid #172554; padding: 14px 18px; border-radius: 4px;">
                <p style="margin: 0; font-size: 13px; color: #6b7280;">
                    <em>Was this forwarded to you?</em>
                    &nbsp;<a href="https://rigacap.com/?subscribe=market_measured#newsletter" style="color: #172554; font-weight: 600; text-decoration: none;">Subscribe — free, Sundays only&nbsp;→</a>
                </p>
            </div>
        </td></tr>'''}

        <tr><td style="padding: 36px 40px 32px 40px;">
            <p style="margin: 0; font-size: 12px; color: #9ca3af; line-height: 1.6; font-style: italic; border-top: 1px solid #f3f4f6; padding-top: 16px;">
                <em>Market, Measured.</em> is a weekly reading from RigaCap. Data-backed, noise-free. Reply anytime — we read every response.
            </p>
            <p style="margin: 12px 0 0 0; font-size: 11px; color: #9ca3af;">
                &copy; {date.year} RigaCap, LLC. Not investment advice.
                &nbsp;·&nbsp;
                <a href="{unsub_url}" style="color:#9ca3af;text-decoration:underline;">Unsubscribe</a>
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
        return await self.send_email(
            to_email, subject, html, text,
            user_id=user_id,
            list_unsubscribe_url=unsub_url,
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
                <div style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 8px 0; font-size: 18px; color: #c9a84c; font-weight: 700;">
                        Give a Month, Get a Month
                    </p>
                    <p style="margin: 0 0 16px 0; font-size: 14px; color: rgba(255,255,255,0.9); line-height: 1.5;">
                        Share your referral link with a friend. They get their first month free,
                        and when they subscribe, you get a free month too!
                    </p>
                    <div style="background: rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; margin: 0 auto; max-width: 400px;">
                        <p style="margin: 0; font-size: 14px; color: #ffffff; font-family: monospace; word-break: break-all;">
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
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <!-- Header -->
        <tr>
            <td style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding: 48px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="64" height="64" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700;">
                    Welcome to RigaCap!
                </h1>
                <p style="margin: 12px 0 0 0; color: rgba(255,255,255,0.9); font-size: 18px;">
                    Your journey to smarter trading starts now
                </p>
            </td>
        </tr>

        <!-- Welcome Message -->
        <tr>
            <td style="padding: 40px 32px;">
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name}!
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Thank you for joining RigaCap! We're thrilled to have you on board.
                    You've just unlocked access to our AI-powered <strong>Ensemble signals</strong> —
                    combining timing, momentum quality, and adaptive risk management to
                    find the best opportunities in any market.
                </p>

                <!-- What You Get Box -->
                <div style="background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #059669; border-left: 4px solid #172554; padding-left: 12px;">
                        Here's what you get:
                    </h2>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li><strong>Ensemble signals</strong> — 3-4 high-conviction picks per month, delivered before market open</li>
                        <li><strong>Simple & Advanced views</strong> — See clear buy/sell actions or dive into technical details</li>
                        <li><strong>Smart watchlist</strong> — Get alerted when stocks approach buy triggers</li>
                        <li><strong>Trailing stop protection</strong> — Adaptive risk management</li>
                        <li><strong>Market regime analysis</strong> — 7-regime detection across bull, bear, and recovery</li>
                        <li><strong>Daily email digest</strong> — Signals delivered to your inbox</li>
                        <li><strong>Portfolio tracking</strong> — See your P&L in real-time</li>
                        <li><strong>Works with any broker</strong> — Schwab, Fidelity, IBKR — you execute, we signal</li>
                    </ul>
                </div>

                <p style="font-size: 16px; color: #374151; margin: 24px 0; line-height: 1.6;">
                    Your <strong>7-day free trial</strong> starts now. Explore the dashboard,
                    check out today's signals, and see the Ensemble algorithm in action!
                </p>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                        View Today's Signals →
                    </a>
                </div>

                <!-- Track Record -->
                <div style="background-color: #eff6ff; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <p style="margin: 0; font-size: 14px; color: #1e3a5f;">
                        <strong>Our Track Record:</strong> +240% over 5 years, walk-forward validated with no hindsight bias.
                        <a href="https://rigacap.com/track-record" style="color: #1e40af; text-decoration: underline;">See the full year-by-year results →</a>
                    </p>
                </div>

                <!-- Pro Tip -->
                <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px; margin: 24px 0;">
                    <p style="margin: 0; font-size: 14px; color: #92400e;">
                        <strong>Pro Tip:</strong> Look for signals with the green BUY badge —
                        these are fresh breakouts with the highest conviction. Toggle Advanced mode
                        in the dashboard for full technical details.
                    </p>
                </div>

                {referral_html}

                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    If you have any questions, just reply to this email — we're always here to help.
                </p>

                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    Happy trading!<br>
                    <strong>The RigaCap Team</strong>
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Trading involves risk. Past performance does not guarantee future results.
                </p>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
                </p>
            </td>
        </tr>
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

Our Track Record: +240% over 5 years, walk-forward validated. See the details: https://rigacap.com/track-record

Pro Tip: Look for signals with the green BUY badge — these are fresh breakouts with the highest conviction.
{referral_text}
Happy trading!
The RigaCap Team

---
Trading involves risk. Past performance does not guarantee future results.
"""

        return await self.send_email(
            to_email=to_email,
            subject="🚀 Welcome to RigaCap — Your Trading Edge Starts Now!",
            html_content=html,
            text_content=text,
            user_id=user_id
        )

    async def send_password_reset_email(self, to_email: str, name: str, reset_url: str) -> bool:
        """Send a password reset email with a time-limited link."""
        first_name = name.split()[0] if name else "there"

        html = f"""<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:#f9fafb; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto;">
        <tr>
            <td style="background:linear-gradient(135deg,#172554 0%,#1e3a5f 100%); padding:24px; text-align:center;">
                <h1 style="margin:0; color:#c9a84c; font-size:24px; letter-spacing:1px;">RigaCap</h1>
            </td>
        </tr>
        <tr>
            <td style="background:#ffffff; padding:32px 24px;">
                <h2 style="margin:0 0 16px; font-size:20px; color:#1f2937;">Reset Your Password</h2>
                <p style="font-size:16px; color:#374151; line-height:1.6; margin:0 0 24px;">
                    Hey {first_name}, we received a request to reset your password. Click the button below to choose a new one:
                </p>
                <div style="text-align:center; margin:32px 0;">
                    <a href="{reset_url}"
                       style="display:inline-block; background:linear-gradient(135deg,#172554 0%,#1e3a5f 100%); color:#ffffff; font-size:16px; font-weight:600; padding:14px 36px; border-radius:10px; text-decoration:none;">
                        Reset Password
                    </a>
                </div>
                <p style="font-size:14px; color:#6b7280; line-height:1.6; margin:0 0 16px;">
                    This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
                </p>
                <p style="font-size:12px; color:#9ca3af; line-height:1.6; margin:16px 0 0; word-break:break-all;">
                    Or copy this link: {reset_url}
                </p>
            </td>
        </tr>
        <tr>
            <td style="background-color:#f9fafb; padding:24px; text-align:center; border-top:1px solid #e5e7eb;">
                <p style="margin:0; font-size:12px; color:#9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""

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
            <td style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 48px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="48" height="48" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    Your Trial Ends {urgency.title()}
                </h1>
                <p style="margin: 12px 0 0 0; color: rgba(255,255,255,0.9); font-size: 18px;">
                    Don't lose access to your trading edge
                </p>
            </td>
        </tr>

        <!-- Message -->
        <tr>
            <td style="padding: 40px 32px;">
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Just a heads up — your free trial ends <strong>{urgency}</strong>.
                    After that, you'll lose access to daily signals, portfolio tracking,
                    and market regime alerts.
                </p>

                <!-- Trial Stats -->
                {f'''
                <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #1e40af; border-left: 4px solid #172554; padding-left: 12px;">
                        Your Trial So Far
                    </h2>
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="padding: 8px 0; text-align: center; width: 50%;">
                                <div style="font-size: 36px; font-weight: 700; color: #1e40af;">{signals_generated}</div>
                                <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">Signals Generated</div>
                            </td>
                            <td style="padding: 8px 0; text-align: center; width: 50%;">
                                <div style="font-size: 36px; font-weight: 700; color: #059669;">{strong_signals_seen}</div>
                                <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">Strong Signals</div>
                            </td>
                        </tr>
                    </table>
                </div>
                ''' if signals_generated > 0 else ''}

                <!-- What You'll Lose -->
                <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #dc2626; border-left: 4px solid #172554; padding-left: 12px;">
                        What You'll Lose
                    </h2>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li>Daily AI-powered buy signals</li>
                        <li>Market regime alerts (bull/bear detection)</li>
                        <li>Momentum rankings across 6,500+ stocks</li>
                        <li>Portfolio P&L tracking</li>
                        <li>Missed opportunity alerts</li>
                    </ul>
                </div>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app/subscribe"
                       style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 18px; font-weight: 600; padding: 18px 48px; border-radius: 12px; text-decoration: none;">
                        Subscribe Now →
                    </a>
                </div>

                <!-- Social Proof -->
                <div style="background-color: #f0fdf4; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 4px 0; font-size: 14px; color: #065f46; text-transform: uppercase; font-weight: 600;">
                        Latest Year Performance
                    </p>
                    <p style="margin: 0; font-size: 42px; font-weight: 700; color: #059669;">
                        87.5%
                    </p>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #374151;">
                        Walk-forward return (2025-2026) &bull; 2.32 Sharpe ratio
                    </p>
                </div>

                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    Questions? Just reply to this email — we're happy to help.
                </p>

                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    Happy trading!<br>
                    <strong>The RigaCap Team</strong>
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0 0 8px 0; font-size: 14px; color: #6b7280;">
                    <a href="https://rigacap.com/app" style="color: #172554; text-decoration: none;">View Dashboard</a>
                </p>
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    Trading involves risk. Past performance does not guarantee future results.
                </p>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        text = f"""
Hey {first_name},

Your RigaCap free trial ends {urgency}!

After that, you'll lose access to:
- Daily AI-powered buy signals
- Market regime alerts
- Momentum rankings across 6,500+ stocks
- Portfolio P&L tracking
- Missed opportunity alerts

Subscribe now to keep your trading edge: https://rigacap.com/app/subscribe

Our walk-forward simulation returned 87.5% in the latest year (2025-2026) with a 2.32 Sharpe ratio.

Questions? Just reply to this email.

Happy trading!
The RigaCap Team

---
Trading involves risk. Past performance does not guarantee future results.
"""

        day_word = "Tomorrow" if days_remaining == 1 else f"in {days_remaining} Days"
        return await self.send_email(
            to_email=to_email,
            subject=f"⏰ Your Trial Ends {day_word} — Subscribe to Keep Your Edge",
            html_content=html,
            text_content=text,
            user_id=user_id
        )

    async def send_goodbye_email(self, to_email: str, name: str, user_id: str = None) -> bool:
        """
        Send a 'sorry to see you go' email when a user cancels or trial expires.
        """
        first_name = name.split()[0] if name else "there"

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
            <td style="background: linear-gradient(135deg, #1f2937 0%, #374151 100%); padding: 48px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="48" height="48" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    We're Sad to See You Go
                </h1>
            </td>
        </tr>

        <!-- Message -->
        <tr>
            <td style="padding: 40px 32px;">
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    We noticed your RigaCap subscription has ended. We're truly sorry to see you go!
                    Before you leave completely, we wanted to share what you might be missing...
                </p>

                <!-- What You're Missing -->
                <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #dc2626; border-left: 4px solid #172554; padding-left: 12px;">
                        What You're Missing Today:
                    </h2>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li>Fresh daily signals from 6,500+ stocks</li>
                        <li>Real-time market regime updates</li>
                        <li>Buy signals before they surge</li>
                        <li>Stop-loss alerts to protect your capital</li>
                    </ul>
                </div>

                <!-- Stats -->
                <div style="background-color: #f0fdf4; border-radius: 16px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #059669; text-transform: uppercase; font-weight: 600;">
                        Latest Year Performance
                    </p>
                    <p style="margin: 8px 0 0 0; font-size: 48px; font-weight: 700; color: #059669;">
                        87.5%
                    </p>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #374151;">
                        Walk-forward return (2025-2026) &bull; 2.32 Sharpe ratio
                    </p>
                </div>

                <p style="font-size: 16px; color: #374151; margin: 24px 0; line-height: 1.6;">
                    We'd love to have you back. If you left because something wasn't working,
                    please reply to this email and let us know — we're always improving based on feedback.
                </p>

                <!-- Special Offer -->
                <div style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); border-radius: 16px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 8px 0; font-size: 14px; color: rgba(255,255,255,0.9); text-transform: uppercase; font-weight: 600;">
                        Come Back Offer
                    </p>
                    <p style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: #ffffff;">
                        Get 20% Off Your First Month
                    </p>
                    <a href="https://rigacap.com/app?promo=COMEBACK20"
                       style="display: inline-block; background-color: #ffffff; color: #172554; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 10px; text-decoration: none;">
                        Reactivate Now →
                    </a>
                </div>

                <p style="font-size: 16px; color: #374151; margin: 24px 0; line-height: 1.6;">
                    Whatever you decide, we wish you the best with your trading journey.
                    The markets will always be here, and so will we if you ever want to come back.
                </p>

                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    All the best,<br>
                    <strong>The RigaCap Team</strong>
                </p>
            </td>
        </tr>

        <!-- Footer -->
        <tr>
            <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        text = f"""
Hey {first_name},

We noticed your RigaCap subscription has ended. We're sad to see you go!

What you're missing:
- Fresh daily signals from 6,500+ stocks
- Real-time market regime updates
- Buy signals before they surge
- Stop-loss alerts to protect your capital

Our walk-forward simulation returned 87.5% in the latest year with a 2.32 Sharpe ratio. We'd love to have you back.

SPECIAL OFFER: Get 20% off your first month when you reactivate.
Visit: https://rigacap.com/app?promo=COMEBACK20

If something wasn't working for you, please reply and let us know — we're always improving.

All the best,
The RigaCap Team

---
Unsubscribe: https://rigacap.com/unsubscribe
"""

        return await self.send_email(
            to_email=to_email,
            subject="💔 We Miss You at RigaCap — Here's a Special Offer",
            html_content=html,
            text_content=text,
            user_id=user_id
        )


    async def send_onboarding_email(self, step: int, to_email: str, name: str, user_id: str = None) -> bool:
        """
        Send an onboarding drip email (steps 1-5).

        Step 1 (Day 1): How Your Signals Work
        Step 2 (Day 3): Pro Tips for Better Returns
        Step 3 (Day 5): Your Trial Ends in 2 Days
        Step 4 (Day 6): Last Day of Your Free Trial
        Step 5 (Day 8): We Miss You (win-back)
        """
        first_name = name.split()[0] if name else "there"

        subjects = {
            1: "How Your Signals Work",
            2: "Pro Tips for Better Returns",
            3: "Your Trial Ends in 2 Days",
            4: "Last Day of Your Free Trial",
            5: "We Miss You — Come Back to RigaCap",
        }

        emojis = {1: "📊", 2: "💡", 3: "⏰", 4: "🚨", 5: "💔"}

        subject = f"{emojis.get(step, '📧')} {subjects.get(step, 'RigaCap')}"

        content_blocks = {
            1: f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name}!
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Welcome to Day 1! Let's make sure you get the most out of your trial.
                    Here's how RigaCap finds the best trades:
                </p>

                <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #1e40af; border-left: 4px solid #172554; padding-left: 12px;">
                        The Ensemble Algorithm
                    </h2>
                    <ol style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li><strong>Breakout Timing</strong> — We detect when a stock clears its long-term accumulation zone. This catches early breakouts before the crowd.</li>
                        <li><strong>Momentum Quality</strong> — We rank stocks by 10-day and 60-day momentum. Only top-ranked stocks make the cut.</li>
                        <li><strong>Confirmation</strong> — Volume surge + near 50-day high = triple-confirmed entry.</li>
                    </ol>
                </div>

                <div style="background-color: #f0fdf4; border-radius: 12px; padding: 20px; margin: 24px 0;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #059669;">Reading Your Dashboard</h3>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li><strong style="color: #059669;">Green BUY badge</strong> — Fresh breakout, highest conviction</li>
                        <li><strong>Momentum Rank</strong> — Top 5 = best opportunities</li>
                        <li><strong>Signal Strength</strong> — STRONG badge = all 3 factors aligned</li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                        Check Today's Signals →
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; margin: 24px 0 0 0;">
                    Tomorrow you'll start receiving daily email digests with fresh signals — no need to check the dashboard manually.
                </p>
            """,
            2: f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name}!
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    You've been with us a few days — here are some tips to maximize your returns:
                </p>

                <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                        Pro Tip #1: Watch the Watchlist
                    </h2>
                    <p style="margin: 0; color: #374151; line-height: 1.6;">
                        Stocks on the <strong>Watchlist</strong> are approaching the breakout trigger.
                        When they cross, you'll get an alert — often before they show up as full signals.
                        This gives you a head start.
                    </p>
                </div>

                <div style="background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #6d28d9; border-left: 4px solid #172554; padding-left: 12px;">
                        Pro Tip #2: Know Your Market Regime
                    </h2>
                    <p style="margin: 0; color: #374151; line-height: 1.6;">
                        RigaCap detects <strong>7 market regimes</strong> — from Strong Bull to Panic/Crash.
                        In bearish regimes, the algorithm reduces exposure automatically.
                        Check the regime badge at the top of your dashboard.
                    </p>
                </div>

                <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #059669; border-left: 4px solid #172554; padding-left: 12px;">
                        Pro Tip #3: Trailing Stops Protect You
                    </h2>
                    <p style="margin: 0; color: #374151; line-height: 1.6;">
                        Every position has a <strong>12% trailing stop</strong> from its high water mark.
                        You'll get an email alert when a stock approaches the stop —
                        no need to watch prices all day.
                    </p>
                </div>

                <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <p style="margin: 0; font-size: 14px; color: #374151;">
                        <strong>Simple vs Advanced mode:</strong> Toggle in the top-right corner of your dashboard.
                        Simple mode shows clear buy/sell actions. Advanced mode reveals full technical details
                        (breakout levels, momentum scores, regime analysis).
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                        Open Dashboard →
                    </a>
                </div>
            """,
            3: f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Just a heads up — your free trial ends in <strong>2 days</strong>.
                    Here's what you've been getting access to:
                </p>

                <div style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 16px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 4px 0; font-size: 14px; color: #059669; text-transform: uppercase; font-weight: 600;">
                        5-Year Walk-Forward Performance
                    </p>
                    <p style="margin: 0; font-size: 48px; font-weight: 700; color: #059669;">
                        +240%
                    </p>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #374151;">
                        ~28% annualized &bull; 0.89 Sharpe &bull; 24% max drawdown &bull; No hindsight bias
                    </p>
                </div>

                <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #172554;">How we trade</h3>
                    <p style="margin: 0 0 8px 0; font-size: 15px; color: #374151; line-height: 1.6;">
                        <strong style="color: #059669;">Winners run ~3 weeks at +20%.</strong>
                        <strong style="color: #92400e;">Losers get cut in 12 days at &minus;9%.</strong>
                    </p>
                    <p style="margin: 0; font-size: 13px; color: #6b7280; line-height: 1.5;">
                        No bag-holding for months. The system knows when to let a trade work and when to admit it isn't.
                    </p>
                </div>

                <div style="background-color: #eff6ff; border-radius: 12px; padding: 20px; margin: 24px 0;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #1e40af;">What you'll keep with a subscription:</h3>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li>Daily ensemble buy signals (breakout + momentum + volume)</li>
                        <li>7-regime market detection with adaptive exposure</li>
                        <li>Trailing stop alerts — sell signals delivered to your inbox</li>
                        <li>Watchlist alerts when stocks approach buy triggers</li>
                        <li>Full track record — <a href="https://rigacap.com/track-record" style="color: #1e40af;">see year-by-year results</a></li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 18px; font-weight: 600; padding: 18px 48px; border-radius: 12px; text-decoration: none;">
                        Subscribe Now →
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; margin: 24px 0 0 0;">
                    Questions? Just reply to this email — we're always here to help.
                </p>
            """,
            4: f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    This is your <strong>last day</strong> of free access to RigaCap signals.
                    After today, you'll lose access to:
                </p>

                <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2.2;">
                        <li>Daily AI-powered ensemble buy signals</li>
                        <li>Sell alerts and trailing stop notifications</li>
                        <li>Market regime detection (7 regimes)</li>
                        <li>Momentum rankings across 6,500+ stocks</li>
                        <li>Watchlist alerts and missed opportunity tracking</li>
                        <li>Portfolio P&L tracking</li>
                    </ul>
                </div>

                <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #172554;">How we trade</h3>
                    <p style="margin: 0 0 8px 0; font-size: 15px; color: #374151; line-height: 1.6;">
                        <strong style="color: #059669;">Winners run ~3 weeks at +20%.</strong>
                        <strong style="color: #92400e;">Losers get cut in 12 days at &minus;9%.</strong>
                    </p>
                    <p style="margin: 0; font-size: 13px; color: #6b7280; line-height: 1.5;">
                        No bag-holding for months. The system knows when to let a trade work and when to admit it isn't.
                    </p>
                </div>

                <div style="text-align: center; margin: 32px 0;">
                    <a href="https://rigacap.com/#pricing"
                       style="display: inline-block; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); color: #ffffff; font-size: 18px; font-weight: 600; padding: 18px 48px; border-radius: 12px; text-decoration: none;">
                        Don't Lose Access — Subscribe Now →
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; margin: 24px 0 0 0;">
                    Questions? Just reply to this email.
                </p>
            """,
            5: f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Your trial ended, but we're still finding signals every day.
                    Here's what you've been missing:
                </p>

                <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                        While You Were Away
                    </h2>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li>The ensemble generates <strong>3-4 high-conviction signals per month</strong> — and zero when conditions aren't right</li>
                        <li>Walk-forward tested: <strong>+240% over 5 years</strong>, no hindsight bias</li>
                        <li>The S&amp;P 500 returned just <strong>+84%</strong> over the same 5 years — nearly <strong>3&times; the market</strong></li>
                    </ul>
                </div>

                <div style="background-color: #eff6ff; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <p style="margin: 0; font-size: 14px; color: #1e3a5f;">
                        <strong>See our full track record:</strong>
                        Year-by-year walk-forward results with zero hindsight bias.
                        <a href="https://rigacap.com/track-record" style="color: #1e40af; text-decoration: underline;">View Track Record →</a>
                    </p>
                </div>

                <div style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); border-radius: 16px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 8px 0; font-size: 14px; color: rgba(255,255,255,0.9); text-transform: uppercase; font-weight: 600;">
                        Come Back Offer
                    </p>
                    <p style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: #ffffff;">
                        Get 20% Off Your First Month
                    </p>
                    <a href="https://rigacap.com/app?promo=COMEBACK20"
                       style="display: inline-block; background-color: #ffffff; color: #172554; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 10px; text-decoration: none;">
                        Reactivate Now →
                    </a>
                </div>

                <p style="font-size: 14px; color: #6b7280; margin: 24px 0 0 0;">
                    If something wasn't right, reply to this email and let us know — we're always improving.
                </p>
            """,
        }

        content = content_blocks.get(step, "")
        if not content:
            logger.warning(f"Unknown onboarding step: {step}")
            return False

        # Header gradient varies by step type
        if step <= 2:
            header_gradient = "linear-gradient(135deg, #172554 0%, #1e3a5f 100%)"
            header_title = subjects[step]
        elif step <= 4:
            header_gradient = "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
            header_title = subjects[step]
        else:
            header_gradient = "linear-gradient(135deg, #1f2937 0%, #374151 100%)"
            header_title = "We Miss You"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: {header_gradient}; padding: 48px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="48" height="48" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    {header_title}
                </h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 32px;">
                {content}
                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    Happy trading!<br>
                    <strong>The RigaCap Team</strong>
                </p>
            </td>
        </tr>
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>"""

        return await self.send_email(to_email, subject, html, user_id=user_id)

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
        pnl_color = "#059669" if pnl_pct >= 0 else "#dc2626"
        pnl_sign = "+" if pnl_pct >= 0 else ""

        is_sell = action.lower() == "sell"
        subject_prefix = "SELL ALERT" if is_sell else "WARNING"
        header_gradient = "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)" if is_sell else "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
        action_label = "SELL" if is_sell else "WATCH"

        stop_row = ""
        if stop_price is not None:
            stop_row = f"""
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Trailing Stop</td>
                            <td style="padding: 8px 0; text-align: right; font-weight: 600; color: #dc2626;">${stop_price:.2f}</td>
                        </tr>"""

        subject = f"[RigaCap] {subject_prefix}: {symbol} — {reason}"

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
            <td style="background: {header_gradient}; padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                    {subject_prefix}: {symbol}
                </h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    {reason}
                </p>
            </td>
        </tr>

        <!-- Greeting -->
        <tr>
            <td style="padding: 24px 24px 0;">
                <p style="margin: 0; font-size: 16px; color: #374151;">
                    Hey {first_name}, your position in <strong>{symbol}</strong> needs attention.
                </p>
            </td>
        </tr>

        <!-- Position Details -->
        <tr>
            <td style="padding: 24px;">
                <div style="background-color: #f9fafb; border-radius: 12px; padding: 20px;">
                    <table cellpadding="0" cellspacing="0" style="width: 100%;">
                        <tr>
                            <td style="padding: 8px 0; color: #6b7280;">Symbol</td>
                            <td style="padding: 8px 0; text-align: right; font-weight: 700; font-size: 18px; color: #111827;">{symbol}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; color: #6b7280;">Current Price</td>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; text-align: right; font-weight: 600; color: #111827;">${current_price:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; color: #6b7280;">Entry Price</td>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; text-align: right; color: #6b7280;">${entry_price:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; color: #6b7280;">P&L</td>
                            <td style="padding: 8px 0; border-top: 1px solid #e5e7eb; text-align: right; font-weight: 600; color: {pnl_color};">{pnl_sign}{pnl_pct:.1f}%</td>
                        </tr>{stop_row}
                    </table>
                </div>
            </td>
        </tr>

        <!-- Action Box -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: {'#fef2f2' if is_sell else '#fef3c7'}; border-radius: 12px; padding: 20px; border-left: 4px solid {'#dc2626' if is_sell else '#f59e0b'};">
                    <div style="font-weight: 700; color: {'#dc2626' if is_sell else '#92400e'}; font-size: 16px; margin-bottom: 8px;">
                        {'Recommended: Sell this position' if is_sell else 'Monitor closely'}
                    </div>
                    <div style="color: #374151; font-size: 14px;">
                        {reason}
                    </div>
                </div>
            </td>
        </tr>

        <!-- CTA -->
        <tr>
            <td style="padding: 0 24px 24px; text-align: center;">
                <a href="https://rigacap.com/app"
                   style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                    View Dashboard →
                </a>
            </td>
        </tr>

        <!-- Disclaimer -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <p style="margin: 0; font-size: 12px; color: #6b7280; text-align: center;">
                    This is not financial advice. Always do your own research before trading.
                    <br>Past performance does not guarantee future results.
                </p>
            </td>
        </tr>

        <!-- Footer -->
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>
"""

        text_lines = [
            f"{subject_prefix}: {symbol}",
            "=" * 40,
            f"Reason: {reason}",
            "",
            f"Symbol: {symbol}",
            f"Current Price: ${current_price:.2f}",
            f"Entry Price: ${entry_price:.2f}",
            f"P&L: {pnl_sign}{pnl_pct:.1f}%",
        ]
        if stop_price is not None:
            text_lines.append(f"Trailing Stop: ${stop_price:.2f}")
        text_lines.extend([
            "",
            f"Action: {'SELL this position' if is_sell else 'Monitor closely'}",
            "",
            "View dashboard: https://rigacap.com/app",
            "",
            "---",
            "This is not financial advice. Always do your own research before trading.",
            "Past performance does not guarantee future results.",
        ])

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            text_content="\n".join(text_lines),
            user_id=user_id
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

        # Build signal rows HTML
        signal_rows = ""
        for s in new_signals[:10]:  # Max 10 signals
            symbol = s.get('symbol', 'N/A')
            price = s.get('price', 0)
            pct_above = s.get('pct_above_dwap', 0)
            mom_rank = s.get('momentum_rank', 0)
            short_mom = s.get('short_momentum', 0)
            crossover_date = s.get('dwap_crossover_date', 'Today')

            days_since = s.get('days_since_crossover')
            new_badge = '<span style="display: inline-block; background-color: #059669; color: #ffffff; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 99px; margin-left: 8px; vertical-align: middle;">NEW TODAY</span>' if days_since is not None and days_since == 0 else ''

            signal_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #d1fae5;">
                    <div style="font-size: 18px; font-weight: 700; color: #059669;">
                        {symbol}{new_badge}
                    </div>
                    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
                        Signal triggered on {crossover_date}
                    </div>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #d1fae5; text-align: right;">
                    <div style="font-size: 16px; font-weight: 600;">${price:.2f}</div>
                    <div style="font-size: 12px; color: #059669;">Breakout +{pct_above:.1f}%</div>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #d1fae5; text-align: center;">
                    <div style="background-color: #fef3c7; color: #92400e; font-size: 14px; font-weight: 600; padding: 4px 12px; border-radius: 99px; display: inline-block;">
                        #{mom_rank}
                    </div>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #d1fae5; text-align: right; color: {'#059669' if short_mom > 0 else '#dc2626'};">
                    {'+' if short_mom > 0 else ''}{short_mom:.1f}%
                </td>
            </tr>
            """

        # Build approaching watchlist HTML
        watchlist_html = ""
        if approaching:
            watchlist_rows = ""
            for a in approaching[:5]:  # Max 5 approaching
                symbol = a.get('symbol', 'N/A')
                price = a.get('price', 0)
                pct_above = a.get('pct_above_dwap', 0)
                distance = a.get('distance_to_trigger', 0)

                watchlist_rows += f"""
                <tr>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #fef3c7; font-weight: 600;">{symbol}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #fef3c7; text-align: right;">${price:.2f}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #fef3c7; text-align: right; color: #92400e;">+{pct_above:.1f}%</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #fef3c7; text-align: right; color: #b45309;">+{distance:.1f}% to go</td>
                </tr>
                """

            watchlist_html = f"""
            <tr>
                <td style="padding: 0 24px 24px;">
                    <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px;">
                        <h3 style="margin: 0 0 12px 0; font-size: 16px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                            Approaching Trigger ({len(approaching)} stocks)
                        </h3>
                        <p style="margin: 0 0 12px 0; font-size: 13px; color: #92400e;">
                            These momentum stocks are approaching the signal trigger:
                        </p>
                        <table cellpadding="0" cellspacing="0" style="width: 100%;">
                            <tr style="background-color: rgba(0,0,0,0.05);">
                                <th style="padding: 8px 12px; text-align: left; font-size: 11px; text-transform: uppercase; color: #92400e;">Symbol</th>
                                <th style="padding: 8px 12px; text-align: right; font-size: 11px; text-transform: uppercase; color: #92400e;">Price</th>
                                <th style="padding: 8px 12px; text-align: right; font-size: 11px; text-transform: uppercase; color: #92400e;">Signal%</th>
                                <th style="padding: 8px 12px; text-align: right; font-size: 11px; text-transform: uppercase; color: #92400e;">Distance</th>
                            </tr>
                            {watchlist_rows}
                        </table>
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
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <!-- Header -->
        <tr>
            <td style="background: linear-gradient(135deg, #059669 0%, #10b981 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                    New Breakout Signal{'s' if len(new_signals) > 1 else ''}!
                </h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    {len(new_signals)} momentum stock{'s' if len(new_signals) > 1 else ''} just hit the signal trigger
                </p>
            </td>
        </tr>

        <!-- Regime Context -->
        {f'''<tr>
            <td style="padding: 24px 24px 0;">
                <div style="text-align: center; font-size: 13px; color: #6b7280;">
                    Market: <strong>{market_regime.get("regime", "").replace("_", " ").title()}</strong>
                    &nbsp;•&nbsp; S&amp;P 500 ${market_regime.get("spy_price", "N/A")}
                </div>
            </td>
        </tr>''' if market_regime else ''}

        <!-- Explanation -->
        <tr>
            <td style="padding: 24px;">
                <div style="background-color: #ecfdf5; border-radius: 12px; padding: 16px; border-left: 4px solid #059669;">
                    <p style="margin: 0; font-size: 14px; color: #065f46;">
                        <strong>Breakout Signals</strong> are stocks that pass ALL three Ensemble filters:
                        top momentum ranking, price breakout confirmation, and favorable risk profile.
                        These high-conviction signals have shown <strong>2.5x higher returns</strong> than single-factor signals.
                        View the signal in your dashboard — toggle Advanced mode for full technical details.
                    </p>
                </div>
            </td>
        </tr>

        <!-- New Signals Table -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827; border-left: 4px solid #172554; padding-left: 12px;">
                    New Breakout Signals
                </h2>
                <table cellpadding="0" cellspacing="0" style="width: 100%; border: 1px solid #d1fae5; border-radius: 8px; overflow: hidden;">
                    <tr style="background-color: #ecfdf5;">
                        <th style="padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #065f46;">Symbol</th>
                        <th style="padding: 12px; text-align: right; font-size: 12px; text-transform: uppercase; color: #065f46;">Price</th>
                        <th style="padding: 12px; text-align: center; font-size: 12px; text-transform: uppercase; color: #065f46;">Mom#</th>
                        <th style="padding: 12px; text-align: right; font-size: 12px; text-transform: uppercase; color: #065f46;">10d</th>
                    </tr>
                    {signal_rows}
                </table>
            </td>
        </tr>

        <!-- Approaching Watchlist -->
        {watchlist_html}

        <!-- CTA -->
        <tr>
            <td style="padding: 0 24px 24px; text-align: center;">
                <a href="https://rigacap.com/app"
                   style="display: inline-block; background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                    View Full Dashboard →
                </a>
            </td>
        </tr>

        <!-- Disclaimer -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <p style="margin: 0; font-size: 12px; color: #6b7280; text-align: center;">
                    This is not financial advice. Always do your own research before trading.
                    <br>Past performance does not guarantee future results.
                </p>
            </td>
        </tr>

        <!-- Footer -->
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>
"""

        # Plain text version
        text_lines = [
            "NEW BREAKOUT SIGNAL ALERT",
            "=" * 40,
            f"{len(new_signals)} momentum stock(s) just hit the signal trigger",
        ]
        if market_regime:
            text_lines.append(f"Market: {market_regime.get('regime', '').replace('_', ' ').title()} | S&P 500 ${market_regime.get('spy_price', 'N/A')}")
        text_lines.extend(["", "NEW SIGNALS:"])
        for s in new_signals[:10]:
            fresh_tag = " [NEW TODAY]" if s.get('days_since_crossover') == 0 else ""
            text_lines.append(
                f"  • {s.get('symbol')}: ${s.get('price', 0):.2f} (Breakout +{s.get('pct_above_dwap', 0):.1f}%) - Mom #{s.get('momentum_rank', 0)}{fresh_tag}"
            )

        if approaching:
            text_lines.extend(["", "APPROACHING TRIGGER:"])
            for a in approaching[:5]:
                text_lines.append(
                    f"  • {a.get('symbol')}: ${a.get('price', 0):.2f} (Breakout +{a.get('pct_above_dwap', 0):.1f}%) - {a.get('distance_to_trigger', 0):.1f}% to go"
                )

        text_lines.extend([
            "",
            "View full dashboard: https://rigacap.com/app",
            "",
            "---",
            "This is not financial advice. Always do your own research before trading.",
            "Past performance does not guarantee future results.",
        ])

        return await self.send_email(
            to_email=to_email,
            subject=f"⚡ {len(new_signals)} New Breakout Signal{'s' if len(new_signals) > 1 else ''} - Momentum + Breakout Signal",
            html_content=html,
            text_content="\n".join(text_lines),
            user_id=user_id
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
        mom_html = f"""
                <tr>
                    <td style="padding: 8px 16px; color: #6b7280; font-size: 14px;">Momentum Rank</td>
                    <td style="padding: 8px 16px; text-align: right; font-weight: 600;">
                        <span style="background-color: #fef3c7; color: #92400e; font-size: 14px; font-weight: 600; padding: 4px 12px; border-radius: 99px; display: inline-block;">
                            #{momentum_rank}
                        </span>
                    </td>
                </tr>""" if momentum_rank else ""

        sector_html = f"""
                <tr>
                    <td style="padding: 8px 16px; color: #6b7280; font-size: 14px;">Sector</td>
                    <td style="padding: 8px 16px; text-align: right; font-weight: 600; color: #374151;">{sector}</td>
                </tr>""" if sector else ""

        greeting = f"Hi {user_name}," if user_name else "Hi,"

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
            <td style="background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%); padding: 32px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="40" height="40" style="display: block; margin: 0 auto 12px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                    LIVE: {symbol} Breakout +{pct_above_dwap:.1f}%
                </h1>
                <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">
                    Intraday breakout detected during market hours
                </p>
            </td>
        </tr>

        <!-- Greeting -->
        <tr>
            <td style="padding: 24px 24px 8px;">
                <p style="margin: 0; font-size: 15px; color: #374151;">{greeting}</p>
                <p style="margin: 8px 0 0 0; font-size: 14px; color: #6b7280;">
                    <strong>{symbol}</strong> just crossed the breakout threshold during market hours.
                    This stock was on your watchlist and has now triggered a buy signal.
                </p>
            </td>
        </tr>

        <!-- Signal Details -->
        <tr>
            <td style="padding: 16px 24px 24px;">
                <table cellpadding="0" cellspacing="0" style="width: 100%; border: 1px solid #fde68a; border-radius: 8px; overflow: hidden;">
                    <tr style="background-color: #fffbeb;">
                        <th colspan="2" style="padding: 12px 16px; text-align: left; font-size: 14px; color: #92400e; font-weight: 600;">
                            {symbol} — Live Signal
                        </th>
                    </tr>
                    <tr>
                        <td style="padding: 8px 16px; color: #6b7280; font-size: 14px;">Live Price</td>
                        <td style="padding: 8px 16px; text-align: right; font-size: 18px; font-weight: 700; color: #059669;">${live_price:.2f}</td>
                    </tr>
                    <tr style="background-color: #fefce8;">
                        <td style="padding: 8px 16px; color: #6b7280; font-size: 14px;">Weighted Avg (200d)</td>
                        <td style="padding: 8px 16px; text-align: right; font-weight: 600; color: #374151;">${dwap:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 16px; color: #6b7280; font-size: 14px;">% Above Trigger</td>
                        <td style="padding: 8px 16px; text-align: right; font-weight: 700; color: #d97706;">+{pct_above_dwap:.1f}%</td>
                    </tr>{mom_html}{sector_html}
                </table>
            </td>
        </tr>

        <!-- Explanation -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <div style="background-color: #fffbeb; border-radius: 12px; padding: 16px; border-left: 4px solid #d97706;">
                    <p style="margin: 0; font-size: 14px; color: #92400e;">
                        <strong>Intraday Signal</strong> — This crossover was detected during market hours,
                        before the end-of-day scan. The signal will be confirmed in tonight's full analysis.
                        Check your dashboard for the latest details.
                    </p>
                </div>
            </td>
        </tr>

        <!-- CTA -->
        <tr>
            <td style="padding: 0 24px 24px; text-align: center;">
                <a href="https://rigacap.com/app"
                   style="display: inline-block; background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%); color: #ffffff; font-size: 16px; font-weight: 600; padding: 16px 40px; border-radius: 12px; text-decoration: none;">
                    View in Dashboard →
                </a>
            </td>
        </tr>

        <!-- Disclaimer -->
        <tr>
            <td style="padding: 0 24px 24px;">
                <p style="margin: 0; font-size: 12px; color: #6b7280; text-align: center;">
                    This is not financial advice. Always do your own research before trading.
                    <br>Past performance does not guarantee future results.
                </p>
            </td>
        </tr>

        <!-- Footer -->
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>
"""

        # Plain text version
        text_lines = [
            f"LIVE SIGNAL: {symbol} breakout +{pct_above_dwap:.1f}%",
            "=" * 40,
            "",
            greeting,
            "",
            f"{symbol} just crossed the breakout trigger during market hours.",
            "",
            f"  Live Price: ${live_price:.2f}",
            f"  Weighted Avg: ${dwap:.2f}",
            f"  % Above Trigger: +{pct_above_dwap:.1f}%",
        ]
        if momentum_rank:
            text_lines.append(f"  Momentum Rank: #{momentum_rank}")
        if sector:
            text_lines.append(f"  Sector: {sector}")
        text_lines.extend([
            "",
            "This signal was detected intraday and will be confirmed in tonight's full scan.",
            "",
            "View dashboard: https://rigacap.com/app",
            "",
            "---",
            "This is not financial advice. Always do your own research before trading.",
            "Past performance does not guarantee future results.",
        ])

        return await self.send_email(
            to_email=to_email,
            subject=f"🔔 LIVE SIGNAL: {symbol} breakout +{pct_above_dwap:.1f}%",
            html_content=html,
            text_content="\n".join(text_lines),
            user_id=user_id
        )

    async def send_referral_reward_email(self, to_email: str, name: str, friend_name: str, user_id: str = None) -> bool:
        """Send a reward notification when a referred friend converts to paid."""
        first_name = name.split()[0] if name else "there"
        friend_first = friend_name.split()[0] if friend_name else "Your friend"

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f3f4f6; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <table cellpadding="0" cellspacing="0" style="width:100%; max-width:600px; margin:0 auto; background-color:#ffffff;">
        <tr>
            <td style="background:linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding:48px 24px; text-align:center;">
                <div style="font-size:48px; margin-bottom:16px;">🎉</div>
                <h1 style="margin:0; color:#c9a84c; font-size:28px; font-weight:700;">
                    You Earned a Free Month!
                </h1>
                <p style="margin:12px 0 0 0; color:rgba(255,255,255,0.9); font-size:16px;">
                    Your referral just paid off
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding:40px 32px;">
                <p style="font-size:18px; color:#374151; margin:0 0 24px 0; line-height:1.6;">
                    Hey {first_name}!
                </p>
                <p style="font-size:16px; color:#374151; margin:0 0 24px 0; line-height:1.6;">
                    Great news — <strong>{friend_first}</strong> just became a paying subscriber,
                    and that means your next invoice is <strong>$0</strong>. One full month of
                    RigaCap signals, on us.
                </p>

                <div style="background:linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%); border-radius:16px; padding:24px; margin:24px 0; text-align:center;">
                    <p style="margin:0 0 8px 0; font-size:14px; color:#059669; font-weight:600;">YOUR REWARD</p>
                    <p style="margin:0; font-size:32px; color:#172554; font-weight:700;">1 Month Free</p>
                    <p style="margin:8px 0 0 0; font-size:14px; color:#6b7280;">Applied to your next invoice automatically</p>
                </div>

                <p style="font-size:16px; color:#374151; margin:24px 0; line-height:1.6;">
                    Keep sharing! Every friend who subscribes earns you another free month.
                </p>

                <div style="text-align:center; margin:32px 0;">
                    <a href="https://rigacap.com/app"
                       style="display:inline-block; background:linear-gradient(135deg, #172554 0%, #1e3a5f 100%); color:#ffffff; font-size:16px; font-weight:600; padding:16px 40px; border-radius:12px; text-decoration:none;">
                        View Dashboard →
                    </a>
                </div>
            </td>
        </tr>
        <tr>
            <td style="background-color:#f9fafb; padding:24px; text-align:center; border-top:1px solid #e5e7eb;">
                <p style="margin:0; font-size:12px; color:#9ca3af;">
                    Trading involves risk. Past performance does not guarantee future results.
                </p>
                <p style="margin:8px 0 0 0; font-size:12px; color:#9ca3af;">
                    &copy; {datetime.now().year} RigaCap, LLC. All rights reserved.
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""

        text = f"""Hey {first_name}!

Great news — {friend_first} just became a paying subscriber, and your next invoice is $0!

YOUR REWARD: 1 Month Free (applied to your next invoice automatically)

Keep sharing! Every friend who subscribes earns you another free month.

View dashboard: https://rigacap.com/app

---
Trading involves risk. Past performance does not guarantee future results.
"""

        return await self.send_email(
            to_email=to_email,
            subject="🎉 You Earned a Free Month! Your Referral Paid Off",
            html_content=html,
            text_content=text,
            user_id=user_id
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
            'strong_bull': ('#10B981', '#d1fae5', 'Strong Bull'),
            'weak_bull': ('#84CC16', '#ecfdf5', 'Weak Bull'),
            'rotating_bull': ('#8B5CF6', '#ede9fe', 'Rotating Bull'),
            'range_bound': ('#F59E0B', '#fef3c7', 'Range-Bound'),
            'weak_bear': ('#F97316', '#fff7ed', 'Weak Bear'),
            'panic_crash': ('#EF4444', '#fee2e2', 'Panic/Crash'),
            'recovery': ('#06B6D4', '#cffafe', 'Recovery'),
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
            spy_delta = f' <span style="color:{"#10B981" if pct >= 0 else "#EF4444"}">{arrow}{abs(pct):.1f}%</span>'
        vix_delta = ""
        if vix_close and prev_vix and prev_vix > 0:
            pct = (vix_close / prev_vix - 1) * 100
            arrow = "↑" if pct >= 0 else "↓"
            vix_delta = f' <span style="color:{"#EF4444" if pct >= 0 else "#10B981"}">{arrow}{abs(pct):.1f}%</span>'

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
              <td style="padding:6px 12px;font-size:14px;color:#374151;width:140px;">{r_name}</td>
              <td style="padding:6px 12px;">
                <div style="background:#f3f4f6;border-radius:4px;overflow:hidden;height:20px;">
                  <div style="background:{r_color};width:{bar_width}%;height:100%;border-radius:4px;"></div>
                </div>
              </td>
              <td style="padding:6px 12px;font-size:14px;color:#374151;text-align:right;width:60px;">{pct}%</td>
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
                <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0 0 8px 0; font-size: 12px; color: #9ca3af;">
                        You're receiving this because you subscribed at rigacap.com.
                    </p>
                    <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                        <a href="{unsub_url}" style="color: #6b7280; text-decoration: none;">Unsubscribe</a>
                    </p>
                    <p style="margin: 8px 0 0 0; font-size: 12px; color: #9ca3af;">
                        Trading involves risk. Past performance does not guarantee future results.
                    </p>
                </td>
            </tr>'''
        elif user_id:
            footer = self._email_footer_html(user_id)
        else:
            footer = '''<tr>
                <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                        Trading involves risk. Past performance does not guarantee future results.
                    </p>
                </td>
            </tr>'''

        html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;">
  <!-- Header -->
  <tr>
    <td style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); padding: 32px 24px; text-align: center;">
      <h1 style="margin:0;color:white;font-size:20px;font-weight:700;">RigaCap Weekly Market Intelligence</h1>
      <p style="margin:8px 0 0 0;color:#94a3b8;font-size:14px;">{date_str}</p>
    </td>
  </tr>

  <!-- Regime Badge -->
  <tr>
    <td style="background:white;padding:24px;text-align:center;">
      <div style="display:inline-block;background:{bg_color};border:2px solid {color};border-radius:12px;padding:12px 24px;">
        <span style="font-size:24px;font-weight:700;color:{color};">{regime_name}</span>
      </div>
      <p style="margin:12px 0 0 0;font-size:14px;color:#6b7280;">{wow_text}</p>
    </td>
  </tr>

  <!-- SPY & VIX -->
  <tr>
    <td style="background:white;padding:0 24px 24px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td width="50%" style="text-align:center;padding:12px;background:#f9fafb;border-radius:8px 0 0 8px;">
            <p style="margin:0;font-size:12px;color:#6b7280;text-transform:uppercase;">S&amp;P 500</p>
            <p style="margin:4px 0 0 0;font-size:20px;font-weight:700;color:#172554;">{spy_display}{spy_delta}</p>
          </td>
          <td width="50%" style="text-align:center;padding:12px;background:#f9fafb;border-radius:0 8px 8px 0;">
            <p style="margin:0;font-size:12px;color:#6b7280;text-transform:uppercase;">Market Fear</p>
            <p style="margin:4px 0 0 0;font-size:20px;font-weight:700;color:#172554;">{_vix_label(vix_close)}{vix_delta}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Outlook & Action -->
  <tr>
    <td style="background:white;padding:0 24px 24px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f9ff;border-radius:8px;border-left:4px solid #172554;">
        <tr>
          <td style="padding:16px;">
            <p style="margin:0 0 8px 0;font-size:13px;color:#6b7280;text-transform:uppercase;">Outlook</p>
            <p style="margin:0 0 12px 0;font-size:16px;font-weight:600;color:#172554;">{outlook.replace('_', ' ').title()}</p>
            <p style="margin:0 0 8px 0;font-size:13px;color:#6b7280;text-transform:uppercase;">Recommended Action</p>
            <p style="margin:0;font-size:16px;font-weight:600;color:#172554;">{action_display}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Transition Probabilities -->
  <tr>
    <td style="background:white;padding:0 24px 24px 24px;">
      <p style="margin:0 0 12px 0;font-size:14px;font-weight:600;color:#172554;">What's Next? Transition Probabilities</p>
      <table width="100%" cellpadding="0" cellspacing="0">
        {trans_rows}
      </table>
    </td>
  </tr>

  <!-- 30-Day Timeline -->
  <tr>
    <td style="background:white;padding:0 24px 24px 24px;">
      <p style="margin:0 0 12px 0;font-size:14px;font-weight:600;color:#172554;">30-Day Regime Timeline</p>
      <table cellpadding="1" cellspacing="1" style="width:100%;">
        <tr>{timeline_blocks}</tr>
      </table>
    </td>
  </tr>

  <!-- CTA -->
  <tr>
    <td style="background:white;padding:0 24px 32px 24px;text-align:center;">
      <p style="margin:0 0 16px 0;font-size:14px;color:#6b7280;">
        RigaCap members get daily buy/sell signals powered by this intelligence.
      </p>
      <a href="https://rigacap.com?utm_source=regime_report&utm_medium=email&utm_campaign=weekly"
         style="display:inline-block;padding:12px 32px;background:#172554;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
        See Our Full Signals →
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
        subject = f"📊 Weekly Market Regime Report — {_now_et().strftime('%B %d, %Y')}"
        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            user_id=user_id,  # For List-Unsubscribe header (paid users only)
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

        subject = "We're sorry to see you go — here's 20% off if you change your mind"

        content = f"""
                <p style="font-size: 18px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    Hey {first_name},
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    We noticed your RigaCap subscription was cancelled. We're sorry to see you go.
                </p>
                <p style="font-size: 16px; color: #374151; margin: 0 0 24px 0; line-height: 1.6;">
                    If something wasn't working for you, we'd genuinely love to hear about it —
                    just reply to this email. We're a small team and we read every response.
                </p>

                <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; padding: 24px; margin: 24px 0;">
                    <h2 style="margin: 0 0 16px 0; font-size: 18px; color: #92400e; border-left: 4px solid #172554; padding-left: 12px;">
                        What You'll Be Missing
                    </h2>
                    <ul style="margin: 0; padding: 0 0 0 20px; color: #374151; line-height: 2;">
                        <li><strong>3-4 high-conviction signals</strong> per month (not 15 low-quality picks)</li>
                        <li><strong>+6% in 2022</strong> while the S&amp;P fell 20% — our system knows when to sit out</li>
                        <li><strong>7-regime market intelligence</strong> — know when conditions favor trading vs cash</li>
                        <li>Trailing stops, breakout filters, and ensemble scoring — <strong>all automated</strong></li>
                    </ul>
                </div>

                <div style="background: linear-gradient(135deg, #172554 0%, #1e3a5f 100%); border-radius: 16px; padding: 24px; margin: 24px 0; text-align: center;">
                    <p style="margin: 0 0 8px 0; font-size: 14px; color: rgba(255,255,255,0.9); text-transform: uppercase; font-weight: 600;">
                        Come Back Offer
                    </p>
                    <p style="margin: 0 0 16px 0; font-size: 24px; font-weight: 700; color: #ffffff;">
                        Get 20% Off Your Next Month
                    </p>
                    <a href="https://rigacap.com/app?promo=COMEBACK20"
                       style="display: inline-block; background-color: #ffffff; color: #172554; font-size: 16px; font-weight: 600; padding: 14px 32px; border-radius: 10px; text-decoration: none;">
                        Reactivate Now &rarr;
                    </a>
                </div>

                <div style="background-color: #eff6ff; border-radius: 12px; padding: 20px; margin: 24px 0; border-left: 4px solid #172554;">
                    <p style="margin: 0; font-size: 14px; color: #1e3a5f;">
                        <strong>See what you'd be getting:</strong>
                        Our full walk-forward track record — 5 years, zero losing years, no hindsight bias.
                        <a href="https://rigacap.com/track-record" style="color: #1e40af; text-decoration: underline;">View Track Record &rarr;</a>
                    </p>
                </div>

                <p style="font-size: 14px; color: #6b7280; margin: 24px 0 0 0;">
                    This offer is valid for 30 days. No pressure — but we'd love to have you back.
                </p>
        """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table cellpadding="0" cellspacing="0" style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
        <tr>
            <td style="background: linear-gradient(135deg, #1f2937 0%, #374151 100%); padding: 48px 24px; text-align: center;">
                <img src="https://rigacap.com/email-logo-v2.png" alt="RigaCap" width="48" height="48" style="display: block; margin: 0 auto 16px auto;" />
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                    We'll Miss You
                </h1>
            </td>
        </tr>
        <tr>
            <td style="padding: 40px 32px;">
                {content}
                <p style="font-size: 16px; color: #374151; margin: 24px 0 0 0; line-height: 1.6;">
                    Happy trading, wherever it takes you.<br>
                    <strong>The RigaCap Team</strong>
                </p>
            </td>
        </tr>
        {self._email_footer_html(user_id)}
    </table>
</body>
</html>"""

        return await self.send_email(to_email, subject, html, user_id=user_id)


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
