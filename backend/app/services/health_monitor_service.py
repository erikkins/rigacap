"""
Pipeline Health Monitor Service

Lightweight daily health check across 5 categories:
- Data freshness (pickle, dashboard, CSVs)
- Worker performance (memory, duration, errors)
- Database health (RDS CPU, storage, connections)
- Signal quality (ensemble signals, positions)
- Infrastructure (CloudWatch alarms, log errors)

Runs WITHOUT loading the pickle — uses only S3 HEAD, CloudWatch metrics, and DB counts.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Optional

import boto3
import pytz

logger = logging.getLogger(__name__)

_ET = pytz.timezone("US/Eastern")

S3_BUCKET = os.environ.get("PRICE_DATA_BUCKET", "rigacap-prod-price-data-149218244179")
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "rigacap-prod-worker")
API_FUNCTION_NAME = os.environ.get("API_FUNCTION_NAME", "rigacap-prod-api")
WORKER_MEMORY_MB = 3008
WORKER_TIMEOUT_S = 900

# US market holidays 2026 (NYSE closed)
# Update annually or pull from a holiday calendar
US_MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


class HealthStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class HealthCheck:
    category: str
    name: str
    status: HealthStatus
    value: str
    threshold: str
    message: str
    resolution: str = ""


@dataclass
class HealthReport:
    timestamp: datetime
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def overall_status(self) -> HealthStatus:
        if any(c.status == HealthStatus.RED for c in self.checks):
            return HealthStatus.RED
        if any(c.status == HealthStatus.YELLOW for c in self.checks):
            return HealthStatus.YELLOW
        return HealthStatus.GREEN

    @property
    def green_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.GREEN)

    @property
    def yellow_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.YELLOW)

    @property
    def red_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.RED)

    @property
    def yellow_names(self) -> list[str]:
        return [c.name for c in self.checks if c.status == HealthStatus.YELLOW]

    @property
    def red_names(self) -> list[str]:
        return [c.name for c in self.checks if c.status == HealthStatus.RED]


def _is_market_day(d: date) -> bool:
    """Check if date is a US market trading day (not weekend or holiday)."""
    if d.weekday() >= 5:
        return False
    if d in US_MARKET_HOLIDAYS_2026:
        return False
    return True


def _last_market_day(d: date) -> date:
    """Find the most recent market day on or before d."""
    while not _is_market_day(d):
        d -= timedelta(days=1)
    return d


def _hours_since(dt: datetime) -> float:
    """Hours since a UTC datetime."""
    now = datetime.utcnow()
    return (now - dt).total_seconds() / 3600


class HealthMonitorService:
    def __init__(self):
        self._s3 = None
        self._cw = None
        self._cw_logs = None

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name="us-east-1")
        return self._s3

    @property
    def cw(self):
        if self._cw is None:
            self._cw = boto3.client("cloudwatch", region_name="us-east-1")
        return self._cw

    @property
    def cw_logs(self):
        if self._cw_logs is None:
            self._cw_logs = boto3.client("logs", region_name="us-east-1")
        return self._cw_logs

    async def run_all_checks(self) -> HealthReport:
        """Run all health checks and return a report."""
        report = HealthReport(timestamp=datetime.now(_ET).replace(tzinfo=None))

        check_methods = [
            self._check_pickle_size,
            self._check_pickle_freshness,
            self._check_dashboard_freshness,
            self._check_spy_csv_freshness,
            self._check_worker_memory,
            self._check_worker_duration,
            self._check_worker_errors,
            self._check_rds_cpu,
            self._check_rds_storage,
            self._check_ensemble_signals,
            self._check_open_positions,
            self._check_dashboard_parseable,
            self._check_cloudwatch_alarms,
            self._check_worker_log_errors,
            self._check_daily_snapshot,
            self._check_data_source_health,
            self._check_last_data_fetch,
        ]

        for method in check_methods:
            try:
                check = await method()
                report.checks.append(check)
            except Exception as e:
                logger.error(f"Health check {method.__name__} failed: {e}")
                report.checks.append(HealthCheck(
                    category="Error",
                    name=method.__name__.replace("_check_", "").replace("_", " ").title(),
                    status=HealthStatus.RED,
                    value="ERROR",
                    threshold="N/A",
                    message=f"Check itself failed: {str(e)[:100]}",
                    resolution="Check CloudWatch logs for health monitor errors",
                ))

        return report

    # ──────────────────────────────────────────────────────────────
    # Data Freshness Checks
    # ──────────────────────────────────────────────────────────────

    def _freshness_thresholds(self) -> tuple[float, float, float, float]:
        """Return (weekday_yellow, weekday_red, weekend_yellow, weekend_red) hours."""
        # Called per-check with specific thresholds
        raise NotImplementedError

    def _s3_last_modified(self, key: str) -> Optional[datetime]:
        """Get LastModified (UTC) for an S3 object. Returns None if not found."""
        try:
            resp = self.s3.head_object(Bucket=S3_BUCKET, Key=key)
            return resp["LastModified"].replace(tzinfo=None)
        except Exception:
            return None

    def _freshness_status(
        self, hours: float, weekday_yellow: float, weekday_red: float,
        weekend_yellow: float, weekend_red: float
    ) -> HealthStatus:
        """Determine status based on hours since update and day-of-week aware thresholds.

        Uses relaxed (weekend) thresholds when no scan is expected to have run
        since the data was last refreshed — weekends, holidays, and the period
        before today's scan completes (e.g. Monday 7:30 AM, data from Friday).
        """
        now_et = datetime.now(_ET)
        today = now_et.date()

        # Has today's scan already run? Scan is at 4:30 PM ET, allow until 5 PM.
        todays_scan_done = _is_market_day(today) and now_et.hour >= 17

        if todays_scan_done:
            # Today is a market day and scan should be done — expect fresh data
            yellow, red = weekday_yellow, weekday_red
        elif _is_market_day(today) and now_et.hour < 17:
            # Today is a market day but scan hasn't run yet.
            # Check if there's a weekend/holiday gap since last market day.
            prev_mkt = _last_market_day(today - timedelta(days=1))
            gap_days = (today - prev_mkt).days
            if gap_days >= 2:
                # Weekend/holiday gap (e.g. Monday morning) — relax thresholds
                yellow, red = weekend_yellow, weekend_red
            else:
                # Normal weekday morning (Tue-Fri) — yesterday's scan should exist
                yellow, red = weekday_yellow, weekday_red
        else:
            # Weekend or holiday — no scan expected
            yellow, red = weekend_yellow, weekend_red

        if hours >= red:
            return HealthStatus.RED
        if hours >= yellow:
            return HealthStatus.YELLOW
        return HealthStatus.GREEN

    async def _check_pickle_size(self) -> HealthCheck:
        """Check pickle size on S3 (HEAD request only)."""
        try:
            resp = self.s3.head_object(Bucket=S3_BUCKET, Key="prices/all_data.pkl.gz")
            size_mb = resp["ContentLength"] / (1024 * 1024)
        except Exception as e:
            return HealthCheck(
                category="Data Freshness", name="Pickle Size",
                status=HealthStatus.RED, value="MISSING",
                threshold="<700 MB", message=f"Could not read pickle: {e}",
                resolution="Check S3 bucket permissions and pickle rebuild job",
            )

        if size_mb > 820:
            status = HealthStatus.RED
        elif size_mb > 700:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.GREEN

        return HealthCheck(
            category="Data Freshness", name="Pickle Size",
            status=status, value=f"{size_mb:.0f} MB",
            threshold="<700 MB yellow, <820 MB red",
            message=f"Pickle is {size_mb:.0f} MB (ephemeral /tmp = 1024 MB)",
            resolution="Increase ephemeral storage in Terraform (max 10 GB)" if status != HealthStatus.GREEN else "",
        )

    async def _check_pickle_freshness(self) -> HealthCheck:
        """Check when pickle was last updated."""
        last_mod = self._s3_last_modified("prices/all_data.pkl.gz")
        if last_mod is None:
            return HealthCheck(
                category="Data Freshness", name="Pickle Freshness",
                status=HealthStatus.RED, value="MISSING",
                threshold="<20h weekday", message="Pickle not found on S3",
                resolution="Run pickle rebuild manually via Lambda invoke",
            )

        hours = _hours_since(last_mod)
        status = self._freshness_status(hours, 20, 28, 68, 92)
        return HealthCheck(
            category="Data Freshness", name="Pickle Freshness",
            status=status, value=f"{hours:.1f}h ago",
            threshold="<20h weekday / <68h weekend",
            message=f"Last updated: {last_mod.strftime('%Y-%m-%d %H:%M')} UTC",
            resolution="Check daily_scan CloudWatch logs, may need manual invoke" if status != HealthStatus.GREEN else "",
        )

    async def _check_dashboard_freshness(self) -> HealthCheck:
        """Check when dashboard.json was last updated."""
        last_mod = self._s3_last_modified("signals/dashboard.json")
        if last_mod is None:
            return HealthCheck(
                category="Data Freshness", name="Dashboard Freshness",
                status=HealthStatus.RED, value="MISSING",
                threshold="<18h weekday", message="dashboard.json not found on S3",
                resolution="Run export_dashboard_cache manually",
            )

        hours = _hours_since(last_mod)
        status = self._freshness_status(hours, 18, 26, 68, 92)
        return HealthCheck(
            category="Data Freshness", name="Dashboard Freshness",
            status=status, value=f"{hours:.1f}h ago",
            threshold="<18h weekday / <68h weekend",
            message=f"Last updated: {last_mod.strftime('%Y-%m-%d %H:%M')} UTC",
            resolution="Run export_dashboard_cache manually" if status != HealthStatus.GREEN else "",
        )

    async def _check_spy_csv_freshness(self) -> HealthCheck:
        """Check SPY CSV as a sentinel for per-symbol CSV freshness."""
        last_mod = self._s3_last_modified("prices/SPY.csv")
        if last_mod is None:
            return HealthCheck(
                category="Data Freshness", name="SPY CSV Freshness",
                status=HealthStatus.RED, value="MISSING",
                threshold="<20h weekday", message="SPY.csv not found on S3",
                resolution="Check csv_export_from_scan logs",
            )

        hours = _hours_since(last_mod)
        status = self._freshness_status(hours, 20, 28, 68, 92)
        return HealthCheck(
            category="Data Freshness", name="SPY CSV Freshness",
            status=status, value=f"{hours:.1f}h ago",
            threshold="<20h weekday / <68h weekend",
            message=f"Last updated: {last_mod.strftime('%Y-%m-%d %H:%M')} UTC",
            resolution="Check csv_export_from_scan logs" if status != HealthStatus.GREEN else "",
        )

    async def _check_daily_snapshot(self) -> HealthCheck:
        """Check yesterday's (most recent past) market day snapshot exists."""
        today_et = datetime.now(_ET).date()
        target = _last_market_day(today_et - timedelta(days=1))
        key = f"snapshots/{target.isoformat()}/dashboard.json"
        last_mod = self._s3_last_modified(key)

        if last_mod is None:
            return HealthCheck(
                category="Data Freshness", name="Daily Snapshot",
                status=HealthStatus.YELLOW, value="MISSING",
                threshold=f"Exists for {target}",
                message=f"Snapshot for {target} not found at {key}",
                resolution="Run export_dashboard_cache with include_snapshot",
            )

        return HealthCheck(
            category="Data Freshness", name="Daily Snapshot",
            status=HealthStatus.GREEN, value=f"{target}",
            threshold=f"Exists for {target}",
            message=f"Snapshot present, updated {last_mod.strftime('%Y-%m-%d %H:%M')} UTC",
        )

    # ──────────────────────────────────────────────────────────────
    # Worker Performance Checks
    # ──────────────────────────────────────────────────────────────

    def _get_cw_metric(
        self, namespace: str, metric_name: str, dimensions: list[dict],
        stat: str, period_hours: int = 24
    ) -> Optional[float]:
        """Get a single CloudWatch metric value over the last N hours."""
        now = datetime.utcnow()
        try:
            resp = self.cw.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=now - timedelta(hours=period_hours),
                EndTime=now,
                Period=period_hours * 3600,
                Statistics=[stat],
            )
            points = resp.get("Datapoints", [])
            if not points:
                return None
            return points[0].get(stat)
        except Exception as e:
            logger.warning(f"CloudWatch metric {metric_name} query failed: {e}")
            return None

    async def _check_worker_memory(self) -> HealthCheck:
        """Check Worker Lambda max memory usage (CloudWatch)."""
        # Lambda reports memory as "Max Memory Used (MB)" via CloudWatch Insights,
        # but the standard metric is not available. Use Duration as a proxy check
        # and rely on the log-based check for OOM detection.
        # Actually, Lambda does NOT emit MaxMemoryUsed as a CW metric.
        # We'll use the custom log-based approach instead.
        # For now, check if any recent invocations were reported via logs.
        try:
            log_group = f"/aws/lambda/{WORKER_FUNCTION_NAME}"
            now_ms = int(datetime.utcnow().timestamp() * 1000)
            start_ms = now_ms - (24 * 3600 * 1000)

            resp = self.cw_logs.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=now_ms,
                filterPattern="Max Memory Used",
                limit=10,
            )

            max_memory = 0
            for event in resp.get("events", []):
                msg = event.get("message", "")
                # REPORT lines: "Max Memory Used: 2456 MB"
                if "Max Memory Used:" in msg:
                    try:
                        part = msg.split("Max Memory Used:")[1].split("MB")[0].strip()
                        mem = int(part)
                        max_memory = max(max_memory, mem)
                    except (ValueError, IndexError):
                        pass

            if max_memory == 0:
                return HealthCheck(
                    category="Worker Performance", name="Worker Memory",
                    status=HealthStatus.GREEN, value="No data",
                    threshold=f"<{int(WORKER_MEMORY_MB * 0.8)} MB (80%)",
                    message="No Worker invocations in last 24h (or no REPORT lines)",
                )

            pct = (max_memory / WORKER_MEMORY_MB) * 100
            if pct > 90:
                status = HealthStatus.RED
            elif pct > 80:
                status = HealthStatus.YELLOW
            else:
                status = HealthStatus.GREEN

            return HealthCheck(
                category="Worker Performance", name="Worker Memory",
                status=status, value=f"{max_memory} MB ({pct:.0f}%)",
                threshold=f"<{int(WORKER_MEMORY_MB * 0.8)} MB (80%)",
                message=f"Peak memory in last 24h: {max_memory}/{WORKER_MEMORY_MB} MB",
                resolution="Increase Worker memory or optimize pickle loading" if status != HealthStatus.GREEN else "",
            )

        except Exception as e:
            logger.warning(f"Worker memory check failed: {e}")
            return HealthCheck(
                category="Worker Performance", name="Worker Memory",
                status=HealthStatus.GREEN, value="N/A",
                threshold=f"<{int(WORKER_MEMORY_MB * 0.8)} MB",
                message=f"Could not query logs: {str(e)[:80]}",
            )

    async def _check_worker_duration(self) -> HealthCheck:
        """Check Worker Lambda max duration (CloudWatch)."""
        val = self._get_cw_metric(
            "AWS/Lambda", "Duration",
            [{"Name": "FunctionName", "Value": WORKER_FUNCTION_NAME}],
            "Maximum", period_hours=24,
        )

        if val is None:
            return HealthCheck(
                category="Worker Performance", name="Worker Duration",
                status=HealthStatus.GREEN, value="No data",
                threshold="<600s yellow, <810s red",
                message="No Worker invocations in last 24h",
            )

        seconds = val / 1000  # CloudWatch reports ms
        if seconds > 810:
            status = HealthStatus.RED
        elif seconds > 600:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.GREEN

        return HealthCheck(
            category="Worker Performance", name="Worker Duration",
            status=status, value=f"{seconds:.0f}s",
            threshold=f"<600s yellow, <810s red (timeout={WORKER_TIMEOUT_S}s)",
            message=f"Max execution time in last 24h: {seconds:.0f}s",
            resolution="Check incremental fetch time, may need to split job" if status != HealthStatus.GREEN else "",
        )

    async def _check_worker_errors(self) -> HealthCheck:
        """Check Worker Lambda error count (CloudWatch, 24h)."""
        val = self._get_cw_metric(
            "AWS/Lambda", "Errors",
            [{"Name": "FunctionName", "Value": WORKER_FUNCTION_NAME}],
            "Sum", period_hours=24,
        )

        errors = int(val) if val else 0
        if errors > 3:
            status = HealthStatus.RED
        elif errors > 0:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.GREEN

        return HealthCheck(
            category="Worker Performance", name="Worker Errors",
            status=status, value=f"{errors}",
            threshold=">0 yellow, >3 red",
            message=f"{errors} error(s) in last 24h",
            resolution="Check Worker CloudWatch logs for errors/timeouts" if status != HealthStatus.GREEN else "",
        )

    # ──────────────────────────────────────────────────────────────
    # Database Health Checks
    # ──────────────────────────────────────────────────────────────

    async def _check_rds_cpu(self) -> HealthCheck:
        """Check RDS CPU utilization (CloudWatch)."""
        # Find the DB instance identifier from environment
        db_id = os.environ.get("RDS_INSTANCE_ID", "rigacap-prod-db-v2")

        val = self._get_cw_metric(
            "AWS/RDS", "CPUUtilization",
            [{"Name": "DBInstanceIdentifier", "Value": db_id}],
            "Average", period_hours=1,
        )

        if val is None:
            return HealthCheck(
                category="Database", name="RDS CPU",
                status=HealthStatus.GREEN, value="No data",
                threshold="<70% yellow, <85% red",
                message="Could not retrieve RDS CPU metrics",
            )

        if val > 85:
            status = HealthStatus.RED
        elif val > 70:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.GREEN

        return HealthCheck(
            category="Database", name="RDS CPU",
            status=status, value=f"{val:.1f}%",
            threshold="<70% yellow, <85% red",
            message=f"Average CPU in last hour: {val:.1f}%",
            resolution="Investigate slow queries or increase instance size" if status != HealthStatus.GREEN else "",
        )

    async def _check_rds_storage(self) -> HealthCheck:
        """Check RDS free storage space (CloudWatch)."""
        db_id = os.environ.get("RDS_INSTANCE_ID", "rigacap-prod-db-v2")

        val = self._get_cw_metric(
            "AWS/RDS", "FreeStorageSpace",
            [{"Name": "DBInstanceIdentifier", "Value": db_id}],
            "Average", period_hours=1,
        )

        if val is None:
            return HealthCheck(
                category="Database", name="RDS Storage",
                status=HealthStatus.GREEN, value="No data",
                threshold=">5 GB yellow, >3 GB red",
                message="Could not retrieve RDS storage metrics",
            )

        gb = val / (1024 ** 3)
        if gb < 3:
            status = HealthStatus.RED
        elif gb < 5:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.GREEN

        return HealthCheck(
            category="Database", name="RDS Storage",
            status=status, value=f"{gb:.1f} GB free",
            threshold=">5 GB yellow, >3 GB red",
            message=f"Free storage: {gb:.1f} GB",
            resolution="Run VACUUM, archive old data, or increase storage" if status != HealthStatus.GREEN else "",
        )

    # ──────────────────────────────────────────────────────────────
    # Signal Quality Checks
    # ──────────────────────────────────────────────────────────────

    async def _check_ensemble_signals(self) -> HealthCheck:
        """Check if ensemble signals were generated for the last completed scan day.

        The health report runs at 7:30 AM ET — before the 4 PM scan.
        So we check yesterday's (previous market day's) signals, not today's.
        """
        from app.core.database import async_session, EnsembleSignal
        from sqlalchemy import select, func

        today_et = datetime.now(_ET).date()
        target = _last_market_day(today_et - timedelta(days=1))

        try:
            async with async_session() as db:
                result = await db.execute(
                    select(func.count()).where(EnsembleSignal.signal_date == target)
                )
                count = result.scalar() or 0
        except Exception as e:
            return HealthCheck(
                category="Signals", name="Ensemble Signals",
                status=HealthStatus.YELLOW, value="DB ERROR",
                threshold=f">0 signals for {target}",
                message=f"Could not query DB: {str(e)[:80]}",
                resolution="Check database connectivity",
            )

        # 0 signals on a market day is yellow (could be legitimate in bear market)
        if count == 0 and _is_market_day(target):
            status = HealthStatus.YELLOW
            msg = f"No signals for {target} — may be normal in bear regime"
            res = "Check daily_scan. May be normal in bear market."
        else:
            status = HealthStatus.GREEN
            msg = f"{count} signal(s) for {target}"
            res = ""

        return HealthCheck(
            category="Signals", name="Ensemble Signals",
            status=status, value=str(count),
            threshold=f">0 signals for {target}",
            message=msg, resolution=res,
        )

    async def _check_open_positions(self) -> HealthCheck:
        """Check open position count in the live model portfolio (Ensemble caps at 6)."""
        from app.core.database import async_session, ModelPosition
        from sqlalchemy import select, func

        try:
            async with async_session() as db:
                result = await db.execute(
                    select(func.count()).where(
                        ModelPosition.status == "open",
                        ModelPosition.portfolio_type == "live",
                    )
                )
                count = result.scalar() or 0
        except Exception as e:
            return HealthCheck(
                category="Signals", name="Open Positions",
                status=HealthStatus.YELLOW, value="DB ERROR",
                threshold="<=6",
                message=f"Could not query DB: {str(e)[:80]}",
                resolution="Check database connectivity",
            )

        if count > 6:
            status = HealthStatus.YELLOW
            msg = f"{count} open positions (Ensemble cap = 6)"
            res = "Check position entry logic. Ensemble caps at 6."
        else:
            status = HealthStatus.GREEN
            msg = f"{count} open live position(s)"
            res = ""

        return HealthCheck(
            category="Signals", name="Open Positions (Live)",
            status=status, value=str(count),
            threshold="<=6",
            message=msg, resolution=res,
        )

    # ──────────────────────────────────────────────────────────────
    # Infrastructure Checks
    # ──────────────────────────────────────────────────────────────

    async def _check_dashboard_parseable(self) -> HealthCheck:
        """Fetch dashboard.json from S3 and verify it parses as valid JSON."""
        import json

        try:
            resp = self.s3.get_object(Bucket=S3_BUCKET, Key="signals/dashboard.json")
            body = resp["Body"].read()
            data = json.loads(body)

            # Basic structure validation
            if not isinstance(data, dict):
                return HealthCheck(
                    category="Infrastructure", name="Dashboard Parseable",
                    status=HealthStatus.RED, value="Invalid",
                    threshold="Valid JSON object",
                    message="dashboard.json is not a JSON object",
                    resolution="Re-export via export_dashboard_cache",
                )

            size_kb = len(body) / 1024
            return HealthCheck(
                category="Infrastructure", name="Dashboard Parseable",
                status=HealthStatus.GREEN, value=f"{size_kb:.0f} KB",
                threshold="Valid JSON object",
                message=f"Dashboard JSON valid ({size_kb:.0f} KB, {len(data)} top-level keys)",
            )
        except json.JSONDecodeError as e:
            return HealthCheck(
                category="Infrastructure", name="Dashboard Parseable",
                status=HealthStatus.RED, value="Parse Error",
                threshold="Valid JSON object",
                message=f"JSON parse error: {str(e)[:80]}",
                resolution="Re-export via export_dashboard_cache",
            )
        except Exception as e:
            return HealthCheck(
                category="Infrastructure", name="Dashboard Parseable",
                status=HealthStatus.RED, value="ERROR",
                threshold="Valid JSON object",
                message=f"Could not fetch dashboard.json: {str(e)[:80]}",
                resolution="Check S3 bucket access and dashboard export job",
            )

    async def _check_cloudwatch_alarms(self) -> HealthCheck:
        """Check if any CloudWatch alarms are in ALARM state."""
        try:
            resp = self.cw.describe_alarms(StateValue="ALARM", MaxRecords=10)
            alarms = resp.get("MetricAlarms", [])

            if alarms:
                names = [a["AlarmName"] for a in alarms]
                return HealthCheck(
                    category="Infrastructure", name="CloudWatch Alarms",
                    status=HealthStatus.RED,
                    value=f"{len(alarms)} in ALARM",
                    threshold="0 alarms",
                    message=f"Active alarms: {', '.join(names[:5])}",
                    resolution="Check CloudWatch console for alarm details",
                )

            return HealthCheck(
                category="Infrastructure", name="CloudWatch Alarms",
                status=HealthStatus.GREEN, value="0 in ALARM",
                threshold="0 alarms",
                message="All CloudWatch alarms OK",
            )
        except Exception as e:
            return HealthCheck(
                category="Infrastructure", name="CloudWatch Alarms",
                status=HealthStatus.YELLOW, value="ERROR",
                threshold="0 alarms",
                message=f"Could not query alarms: {str(e)[:80]}",
            )

    async def _check_worker_log_errors(self) -> HealthCheck:
        """Check Worker logs for critical errors (OOM, timeout) in last 24h."""
        try:
            log_group = f"/aws/lambda/{WORKER_FUNCTION_NAME}"
            now_ms = int(datetime.utcnow().timestamp() * 1000)
            start_ms = now_ms - (24 * 3600 * 1000)

            # Check for MemoryError / OOM
            oom_resp = self.cw_logs.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=now_ms,
                filterPattern='"MemoryError" OR "Cannot allocate memory" OR "Runtime exited with error"',
                limit=5,
            )
            oom_count = len(oom_resp.get("events", []))

            # Check for timeouts
            timeout_resp = self.cw_logs.filter_log_events(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=now_ms,
                filterPattern='"Task timed out"',
                limit=5,
            )
            timeout_count = len(timeout_resp.get("events", []))

            issues = []
            if oom_count > 0:
                issues.append(f"{oom_count} OOM/crash")
            if timeout_count > 0:
                issues.append(f"{timeout_count} timeout")

            if oom_count > 0:
                status = HealthStatus.RED
                resolution = "Worker is running out of memory — increase memory_size or optimize"
            elif timeout_count > 0:
                status = HealthStatus.YELLOW
                resolution = "Worker is timing out — check job duration or split into smaller jobs"
            else:
                status = HealthStatus.GREEN
                resolution = ""

            return HealthCheck(
                category="Infrastructure", name="Worker Log Errors",
                status=status,
                value=", ".join(issues) if issues else "Clean",
                threshold="0 OOM, 0 timeouts",
                message=f"Last 24h: {oom_count} OOM, {timeout_count} timeouts",
                resolution=resolution,
            )
        except Exception as e:
            return HealthCheck(
                category="Infrastructure", name="Worker Log Errors",
                status=HealthStatus.GREEN, value="N/A",
                threshold="0 OOM, 0 timeouts",
                message=f"Could not query logs: {str(e)[:80]}",
            )


    async def _check_data_source_health(self) -> HealthCheck:
        """Check health of market data sources (Alpaca + yfinance)."""
        try:
            from app.services.market_data_provider import market_data_provider

            health = market_data_provider.get_health_summary()
            alpaca = health.get("alpaca", {})
            yfinance = health.get("yfinance", {})

            alpaca_status = alpaca.get("status", "green")
            yfinance_status = yfinance.get("status", "green")
            alpaca_fails = alpaca.get("consecutive_failures", 0)
            yfinance_fails = yfinance.get("consecutive_failures", 0)

            if alpaca_status == "red" and yfinance_status == "red":
                status = HealthStatus.RED
                msg = f"Both sources failing (Alpaca: {alpaca_fails} failures, yfinance: {yfinance_fails} failures)"
                resolution = "Check Alpaca API status and yfinance availability"
            elif alpaca_status == "red" or yfinance_status == "red":
                status = HealthStatus.YELLOW
                failed_src = "Alpaca" if alpaca_status == "red" else "yfinance"
                msg = f"{failed_src} down, using fallback"
                resolution = f"Check {failed_src} API status"
            elif alpaca_fails > 0 or yfinance_fails > 0:
                status = HealthStatus.YELLOW
                msg = f"Alpaca: {alpaca_fails} fails, yfinance: {yfinance_fails} fails"
                resolution = "Monitor — may recover automatically"
            else:
                status = HealthStatus.GREEN
                msg = "Both data sources healthy"
                resolution = ""

            last_source = market_data_provider.last_bars_source or "none"
            return HealthCheck(
                category="Data Sources",
                name="Market Data Sources",
                status=status,
                value=f"Primary: {last_source}",
                threshold="Both sources responding",
                message=msg,
                resolution=resolution,
            )
        except Exception as e:
            return HealthCheck(
                category="Data Sources",
                name="Market Data Sources",
                status=HealthStatus.GREEN,
                value="N/A",
                threshold="Both sources responding",
                message=f"Could not check: {str(e)[:80]}",
            )


    async def _check_last_data_fetch(self) -> HealthCheck:
        """Check the last daily scan data fetch: source, timing, fallback status."""
        import json

        try:
            resp = self.s3.get_object(Bucket=S3_BUCKET, Key="signals/last_fetch_meta.json")
            meta = json.loads(resp["Body"].read().decode("utf-8"))
        except Exception as e:
            err_str = str(e)
            if "NoSuchKey" in err_str or "does not exist" in err_str:
                return HealthCheck(
                    category="Data Freshness", name="Last Data Fetch",
                    status=HealthStatus.YELLOW, value="No data",
                    threshold="Fetch metadata exists",
                    message="No fetch metadata found — daily scan may not have run yet",
                    resolution="Run daily_scan on Worker Lambda",
                )
            return HealthCheck(
                category="Data Freshness", name="Last Data Fetch",
                status=HealthStatus.YELLOW, value="ERROR",
                threshold="Fetch metadata exists",
                message=f"Could not read fetch metadata: {err_str[:80]}",
                resolution="Check S3 bucket access",
            )

        source = meta.get("data_source", "unknown")
        fetch_date = meta.get("fetch_date", "unknown")
        duration = meta.get("fetch_duration_seconds", "?")
        used_fallback = meta.get("used_fallback", False)
        settlement = meta.get("settlement_check", {})
        settled = settlement.get("settled", False)
        settle_attempts = settlement.get("attempts", 0)
        fetch_start = meta.get("fetch_start_utc", "?")
        fetch_end = meta.get("fetch_end_utc", "?")
        symbols_updated = meta.get("symbols_updated", 0)
        symbols_failed = meta.get("symbols_failed", 0)

        # Check freshness — metadata should be from the last market day
        last_mod = self._s3_last_modified("signals/last_fetch_meta.json")
        hours_ago = _hours_since(last_mod) if last_mod else 999

        # Determine status
        if used_fallback and symbols_failed > 50:
            status = HealthStatus.RED
            resolution = "Primary source failed with high error count — check Alpaca/yfinance health"
        elif used_fallback:
            status = HealthStatus.YELLOW
            resolution = f"Fell back from primary — check if Alpaca bars are settling in time"
        elif self._freshness_status(hours_ago, 20, 28, 68, 92) == HealthStatus.RED:
            status = HealthStatus.RED
            resolution = "Fetch metadata is stale — daily scan may not be running"
        else:
            status = HealthStatus.GREEN
            resolution = ""

        # Build display value: "Alpaca | 4:22-4:25 PM ET | 182s"
        # Extract just times from the full datetime strings
        start_time = fetch_start.split(" ")[-1] if " " in fetch_start else fetch_start
        end_time = fetch_end.split(" ")[-1] if " " in fetch_end else fetch_end
        value = f"{source} | {start_time}–{end_time} UTC | {duration}s"
        if used_fallback:
            value += " (fallback)"

        settle_msg = ""
        if settled == "skipped":
            settle_msg = "settlement skipped (forced source)"
        elif settled:
            settle_msg = f"settled on attempt {settle_attempts}"
        else:
            settle_msg = f"NOT settled after {settle_attempts} attempts"

        message = (
            f"{fetch_date}: {symbols_updated} symbols updated, "
            f"{symbols_failed} failed, {settle_msg}"
        )

        return HealthCheck(
            category="Data Freshness", name="Last Data Fetch",
            status=status, value=value,
            threshold="Primary source, no fallback",
            message=message,
            resolution=resolution,
        )


health_monitor_service = HealthMonitorService()
