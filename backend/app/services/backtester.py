"""
Backtester Service - Simulate trading over historical data

Runs the DWAP strategy over historical data to generate:
- Simulated open positions (what we would currently hold)
- Trade history (closed trades)
- Performance metrics

Supports multiple exit strategies:
- trailing_stop: Sell when price drops X% from high water mark
- fixed_target: Sell when price reaches X% profit
- hybrid: After reaching initial target, switch to trailing stop
- time_based: Sell after max holding period
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from app.core.config import settings
from app.services.scanner import scanner_service


class ExitStrategyType(str, Enum):
    """Types of exit strategies"""
    TRAILING_STOP = "trailing_stop"       # Current momentum strategy
    FIXED_TARGET = "fixed_target"         # Sell at X% profit
    HYBRID = "hybrid"                     # Target + trailing after
    TIME_BASED = "time_based"             # Max hold period
    STOP_LOSS_TARGET = "stop_loss_target" # Legacy DWAP: stop loss + profit target


@dataclass
class ExitStrategyConfig:
    """Configuration for exit strategy"""
    strategy_type: ExitStrategyType = ExitStrategyType.TRAILING_STOP

    # Trailing stop parameters
    trailing_stop_pct: float = 12.0  # % drop from high to trigger exit

    # Fixed target parameters
    profit_target_pct: float = 20.0  # % gain to trigger exit

    # Hybrid parameters (target first, then trail)
    hybrid_initial_target_pct: float = 15.0  # First target to hit
    hybrid_trailing_pct: float = 8.0  # Trailing % after hitting target

    # Time-based parameters
    max_hold_days: int = 60  # Max days to hold

    # Stop loss (can be combined with any strategy)
    stop_loss_pct: float = 0.0  # 0 = no stop loss, >0 = fixed stop loss

    def to_dict(self):
        return {
            "strategy_type": self.strategy_type.value,
            "trailing_stop_pct": self.trailing_stop_pct,
            "profit_target_pct": self.profit_target_pct,
            "hybrid_initial_target_pct": self.hybrid_initial_target_pct,
            "hybrid_trailing_pct": self.hybrid_trailing_pct,
            "max_hold_days": self.max_hold_days,
            "stop_loss_pct": self.stop_loss_pct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExitStrategyConfig":
        """Create from dictionary"""
        strategy_type = data.get("strategy_type", "trailing_stop")
        if isinstance(strategy_type, str):
            strategy_type = ExitStrategyType(strategy_type)
        return cls(
            strategy_type=strategy_type,
            trailing_stop_pct=data.get("trailing_stop_pct", 12.0),
            profit_target_pct=data.get("profit_target_pct", 20.0),
            hybrid_initial_target_pct=data.get("hybrid_initial_target_pct", 15.0),
            hybrid_trailing_pct=data.get("hybrid_trailing_pct", 8.0),
            max_hold_days=data.get("max_hold_days", 60),
            stop_loss_pct=data.get("stop_loss_pct", 0.0),
        )


@dataclass
class SimulatedPosition:
    """A position from backtesting"""
    id: int
    symbol: str
    shares: float
    entry_price: float
    entry_date: str
    current_price: float
    stop_loss: float
    profit_target: float
    pnl_pct: float
    pnl_dollars: float
    days_held: int
    dwap_at_entry: float
    pct_above_dwap_at_entry: float

    def to_dict(self):
        return asdict(self)


@dataclass
class SimulatedTrade:
    """A completed trade from backtesting"""
    id: int
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    days_held: int
    dwap_at_entry: float
    momentum_score: float = 0
    momentum_rank: int = 0
    pct_above_dwap_at_entry: float = 0
    num_candidates: int = 0
    # Signal strength metadata fields
    dwap_age: int = 0              # Days since DWAP cross
    short_mom: float = 0           # 10-day momentum %
    long_mom: float = 0            # 60-day momentum %
    volatility: float = 0          # 20-day annualized vol %
    dist_from_high: float = 0      # % from 50-day high
    vol_ratio: float = 0           # Volume / 200-day avg
    spy_trend: float = 0           # SPY % above 200MA

    def to_dict(self):
        return asdict(self)


@dataclass
class BacktestResult:
    """Complete backtest results"""
    positions: List[SimulatedPosition]
    trades: List[SimulatedTrade]
    total_return_pct: float
    win_rate: float
    total_trades: int
    open_positions: int
    total_pnl: float
    max_drawdown_pct: float
    sharpe_ratio: float
    start_date: str
    end_date: str

    # Enhanced metrics
    calmar_ratio: float = 0.0           # Return / Max Drawdown
    sortino_ratio: float = 0.0          # Return / Downside Deviation
    profit_factor: float = 0.0          # Gross Wins / Gross Losses
    avg_win_pct: float = 0.0            # Average winning trade %
    avg_loss_pct: float = 0.0           # Average losing trade %
    win_loss_ratio: float = 0.0         # avg_win / avg_loss
    recovery_factor: float = 0.0        # Net Profit / Max Drawdown
    max_consecutive_losses: int = 0
    ulcer_index: float = 0.0            # Measures depth/duration of drawdowns

    # Debug info
    debug_info: str = ""                # Diagnostic information for troubleshooting

    # Raw position state for walk-forward carry-over (not serialized to API)
    raw_positions: Dict = field(default_factory=dict)

    def to_dict(self):
        result = {**asdict(self)}
        result.pop('raw_positions', None)  # Don't expose internal state
        result['positions'] = [p.to_dict() for p in self.positions]
        result['trades'] = [t.to_dict() for t in self.trades]
        return result


class BacktesterService:
    """
    Simulates the momentum trading strategy over historical data

    Strategy v2 features:
    - Momentum-based ranking (10/60 day)
    - Trailing stops (15%)
    - Weekly rebalancing (Fridays)
    - Market regime filter (SPY > 200MA)
    """

    def __init__(self):
        self.initial_capital = 100000
        self.position_size_pct = settings.POSITION_SIZE_PCT / 100  # 18%
        self.max_positions = settings.MAX_POSITIONS  # 5
        self.trailing_stop_pct = settings.TRAILING_STOP_PCT / 100  # 12%
        self.short_mom_days = settings.SHORT_MOMENTUM_DAYS  # 10
        self.long_mom_days = settings.LONG_MOMENTUM_DAYS  # 60
        self.min_volume = settings.MIN_VOLUME
        self.min_price = settings.MIN_PRICE
        # Legacy DWAP settings for backward compatibility
        self.stop_loss_pct = settings.STOP_LOSS_PCT / 100  # 8%
        self.profit_target_pct = settings.PROFIT_TARGET_PCT / 100  # 20%
        self.dwap_threshold_pct = settings.DWAP_THRESHOLD_PCT / 100  # 5%
        self.volume_spike_mult = settings.VOLUME_SPIKE_MULT
        # Momentum scoring weights (tunable via AI optimization)
        self.short_mom_weight = settings.SHORT_MOM_WEIGHT
        self.long_mom_weight = settings.LONG_MOM_WEIGHT
        self.volatility_penalty = settings.VOLATILITY_PENALTY
        self.near_50d_high_pct = settings.NEAR_50D_HIGH_PCT
        # V2 params (defaults = disabled/no-op for backward compatibility)
        self.rsi_oversold_filter = 100   # 100 = disabled
        self.volume_ratio_min = 0.0      # 0 = disabled
        self.exit_type = "trailing_stop"
        self.hybrid_initial_target_pct = 15.0
        self.hybrid_trailing_pct = 8.0
        self.max_hold_days = 60
        self.sector_cap = 0              # 0 = disabled
        self.regime_reentry_mode = False  # False = classic (SPY>MA200 only), True = smart re-entry
        self.bear_keep_pct = 0.0         # 0.0 = close all on regime exit, 0.5 = keep top 50% of positions
        self.graduated_reentry = False   # Graduated re-entry: deploy partial capital on recovery signals
        # Liquidity tier bonus (injected by walk-forward service per period)
        self.tier1_set: set = set()
        self.tier1_bonus: float = 0.0

    def _calculate_enhanced_metrics(
        self,
        trades: List[SimulatedTrade],
        equity_curve: List[Dict],
        returns: List[float],
        total_return_pct: float,
        max_dd: float
    ) -> Dict:
        """
        Calculate enhanced performance metrics.

        Returns dict with:
        - calmar_ratio: Return / Max Drawdown
        - sortino_ratio: Return / Downside Deviation
        - profit_factor: Gross Wins / Gross Losses
        - avg_win_pct, avg_loss_pct, win_loss_ratio
        - recovery_factor: Net Profit / Max Drawdown
        - max_consecutive_losses
        - ulcer_index
        """
        # Sortino Ratio
        sortino_ratio = 0.0
        if returns:
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = np.std(negative_returns) * np.sqrt(252)
                annualized_return = np.mean(returns) * 252
                sortino_ratio = annualized_return / downside_std if downside_std > 0 else 0

        # Calmar Ratio
        calmar_ratio = 0.0
        if max_dd > 0:
            # Annualize return based on period length
            num_days = len(equity_curve)
            years = num_days / 252 if num_days > 0 else 1
            annualized_return = (total_return_pct / years) if years > 0 else total_return_pct
            calmar_ratio = annualized_return / max_dd if max_dd > 0 else 0

        # Profit Factor
        profit_factor = 0.0
        gross_wins = sum(t.pnl for t in trades if t.pnl > 0)
        gross_losses = abs(sum(t.pnl for t in trades if t.pnl < 0))
        if gross_losses > 0:
            profit_factor = gross_wins / gross_losses
        elif gross_wins > 0:
            profit_factor = 10.0  # Cap at 10 if no losses

        # Win/Loss metrics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]

        avg_win_pct = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
        avg_loss_pct = abs(np.mean([t.pnl_pct for t in losing_trades])) if losing_trades else 0
        win_loss_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else (avg_win_pct if avg_win_pct > 0 else 0)

        # Recovery Factor
        recovery_factor = 0.0
        total_pnl = sum(t.pnl for t in trades)
        if max_dd > 0 and total_pnl > 0:
            # Normalize by initial capital
            recovery_factor = (total_pnl / self.initial_capital * 100) / max_dd

        # Max Consecutive Losses
        max_consecutive_losses = 0
        current_streak = 0
        for t in sorted(trades, key=lambda x: x.exit_date):
            if t.pnl < 0:
                current_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_streak)
            else:
                current_streak = 0

        # Ulcer Index (measures depth and duration of drawdowns)
        ulcer_index = 0.0
        if equity_curve:
            peak = equity_curve[0]['equity']
            squared_drawdowns = []
            for point in equity_curve:
                equity = point['equity']
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100
                squared_drawdowns.append(dd ** 2)
            ulcer_index = np.sqrt(np.mean(squared_drawdowns))

        return {
            'calmar_ratio': round(calmar_ratio, 2),
            'sortino_ratio': round(sortino_ratio, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_win_pct': round(avg_win_pct, 2),
            'avg_loss_pct': round(avg_loss_pct, 2),
            'win_loss_ratio': round(win_loss_ratio, 2),
            'recovery_factor': round(recovery_factor, 2),
            'max_consecutive_losses': max_consecutive_losses,
            'ulcer_index': round(ulcer_index, 2)
        }

    def _get_row_for_date(self, df: pd.DataFrame, date: pd.Timestamp) -> Optional[pd.Series]:
        """
        Get the row for a given date, handling timezone mismatches.
        Returns None if date not found.
        """
        try:
            if date in df.index:
                return df.loc[date]
            # Fallback: match by date string
            date_str = date.strftime('%Y-%m-%d')
            matches = df.index[df.index.strftime('%Y-%m-%d') == date_str]
            if len(matches) > 0:
                return df.loc[matches[0]]
        except (KeyError, IndexError):
            pass
        return None

    def _days_between(self, date1: pd.Timestamp, date2) -> int:
        """
        Calculate days between two dates, handling timezone mismatches.
        Converts both to timezone-naive for comparison.
        """
        # Convert date1 to naive if it has timezone
        if hasattr(date1, 'tz') and date1.tz is not None:
            d1 = date1.tz_localize(None)
        else:
            d1 = date1

        # Convert date2 to Timestamp if it's a string
        if isinstance(date2, str):
            d2 = pd.Timestamp(date2)
        else:
            d2 = date2

        # Convert d2 to naive if it has timezone
        if hasattr(d2, 'tz') and d2.tz is not None:
            d2 = d2.tz_localize(None)

        return (d1 - d2).days

    def _should_rebalance(self, date: pd.Timestamp, last_rebalance: Optional[pd.Timestamp]) -> bool:
        """
        Check if we should rebalance on this date (weekly on Fridays)

        Args:
            date: Current date
            last_rebalance: Date of last rebalance

        Returns:
            True if we should rebalance
        """
        is_friday = date.weekday() == 4
        if last_rebalance is None:
            return True
        days_since = self._days_between(date, last_rebalance)
        return is_friday and days_since >= 5

    def _compute_dwap_age(self, symbol: str, date: pd.Timestamp) -> int:
        """
        Compute days since the most recent DWAP crossover (price crossing above DWAP × 1.05).
        Scans backward up to 252 trading days. Returns calendar days since cross, capped at 252.
        Returns 0 if no crossover found.
        """
        df = scanner_service.data_cache.get(symbol)
        if df is None or len(df) < 200:
            return 0

        # Find the location of the current date
        row = self._get_row_for_date(df, date)
        if row is None:
            return 0

        loc = df.index.get_loc(row.name)
        if isinstance(loc, slice):
            loc = loc.start

        # Scan backward up to 252 days to find last day price was BELOW DWAP × 1.05
        lookback = min(252, loc)
        for i in range(1, lookback + 1):
            idx = loc - i
            if idx < 0:
                break
            prev_row = df.iloc[idx]
            prev_dwap = prev_row.get('dwap', np.nan)
            if pd.isna(prev_dwap) or prev_dwap <= 0:
                continue
            prev_pct = (prev_row['close'] / prev_dwap - 1)
            if prev_pct < self.dwap_threshold_pct:
                # Found the last day below threshold — cross happened on next day
                cross_date = df.index[idx + 1]
                days_since = self._days_between(date, cross_date)
                return min(days_since, 252)

        # Was above threshold for entire lookback
        return 252

    def _compute_spy_trend(self, date: pd.Timestamp) -> float:
        """
        Return SPY's % above its 200-day MA at the given date.
        Positive = bullish, negative = bearish.
        """
        if 'SPY' not in scanner_service.data_cache:
            return 0.0

        spy_df = scanner_service.data_cache['SPY']
        row = self._get_row_for_date(spy_df, date)
        if row is None:
            return 0.0

        spy_price = row['close']
        spy_ma200 = row.get('ma_200', np.nan)
        if pd.isna(spy_ma200) or spy_ma200 <= 0:
            return 0.0

        return round((spy_price / spy_ma200 - 1) * 100, 2)

    def _check_market_regime(self, date: pd.Timestamp) -> bool:
        """
        Check if SPY is above 200-day MA (favorable market)

        Returns:
            True if market is favorable (SPY > 200MA)
        """
        if 'SPY' not in scanner_service.data_cache:
            return True  # Default to favorable if no SPY data

        spy_df = scanner_service.data_cache['SPY']
        row = self._get_row_for_date(spy_df, date)
        if row is None:
            return True
        spy_price = row['close']
        spy_ma200 = row.get('ma_200', np.nan)

        if pd.isna(spy_ma200):
            return True

        return spy_price > spy_ma200

    def _check_regime_reentry(self, date: pd.Timestamp, cash_mode_days: int) -> bool:
        """
        Smarter regime re-entry check. Used when regime_reentry_mode is enabled.
        Returns True if conditions suggest it's safe to re-enter the market,
        even if SPY is still below MA200.

        Two fast re-entry paths:
        1. Trend recovery: SPY > MA50 (shorter-term uptrend restored)
        2. V-recovery: SPY dropped >8% recently but is bouncing (above 10-day SMA)

        Anti-churn: Must be in cash at least 5 days before allowing re-entry.
        """
        # Anti-churn cooldown
        if cash_mode_days < 5:
            return False

        if 'SPY' not in scanner_service.data_cache:
            return False

        spy_df = scanner_service.data_cache['SPY']
        row = self._get_row_for_date(spy_df, date)
        if row is None:
            return False

        spy_price = row['close']
        spy_ma50 = row.get('ma_50', np.nan)
        spy_ma200 = row.get('ma_200', np.nan)

        # Path A: If SPY already above MA200, standard re-entry (always allowed)
        if not pd.isna(spy_ma200) and spy_price > spy_ma200:
            return True

        # Path B: Trend recovery — SPY above MA50 (faster signal than MA200)
        if not pd.isna(spy_ma50) and spy_price > spy_ma50:
            return True

        # Path C: V-recovery detection — sharp drop + bounce
        # Check if SPY dropped >8% from its 30-day high but is now recovering
        try:
            loc = spy_df.index.get_indexer([date], method='ffill')[0]
            if loc < 0:
                loc = None
        except Exception:
            loc = None
        if loc is not None and loc >= 30:
            recent_high = spy_df['close'].iloc[loc-30:loc].max()
            drawdown_pct = (spy_price - recent_high) / recent_high
            # SPY dropped >8% from recent high
            if drawdown_pct < -0.08:
                # Check if bouncing: price > 10-day SMA
                sma_10 = spy_df['close'].iloc[loc-9:loc+1].mean()
                if spy_price > sma_10:
                    return True

        return False

    def _compute_breadth(self, date: pd.Timestamp, symbols: List[str], ma_period: int = 50) -> float:
        """Compute market breadth: % of symbols trading above their N-day MA."""
        above = 0
        total = 0
        for sym in symbols:
            if sym in ('SPY', '^VIX') or sym not in scanner_service.data_cache:
                continue
            df = scanner_service.data_cache[sym]
            row = self._get_row_for_date(df, date)
            if row is None:
                continue
            ma_key = f'ma_{ma_period}'
            ma_val = row.get(ma_key, np.nan)
            if pd.isna(ma_val):
                continue
            total += 1
            if row['close'] > ma_val:
                above += 1
        return (above / total * 100) if total > 0 else 50.0

    def _check_graduated_reentry(self, date: pd.Timestamp, symbols: List[str],
                                  cash_mode_days: int, prev_breadth: float) -> tuple:
        """
        Graduated re-entry: returns (deploy_pct, reason) based on recovery signals.

        Instead of binary cash/invested, detects early recovery signals and
        deploys capital gradually:
          - 0.0  = stay in full cash (no recovery signals)
          - 0.30 = breadth thrust detected (cautious deployment)
          - 0.50 = SPY > MA50 + VIX falling (moderate deployment)
          - 1.0  = SPY > MA200 (full re-entry, same as classic)

        Returns (deploy_pct, reason_string).
        """
        if cash_mode_days < 5:
            return 0.0, "cooldown"

        if 'SPY' not in scanner_service.data_cache:
            return 0.0, "no_spy"

        spy_df = scanner_service.data_cache['SPY']
        row = self._get_row_for_date(spy_df, date)
        if row is None:
            return 0.0, "no_data"

        spy_price = row['close']
        spy_ma50 = row.get('ma_50', np.nan)
        spy_ma200 = row.get('ma_200', np.nan)

        # Full re-entry: SPY > MA200
        if not pd.isna(spy_ma200) and spy_price > spy_ma200:
            return 1.0, "spy_above_ma200"

        # Compute current breadth
        breadth = self._compute_breadth(date, symbols, ma_period=50)

        # Breadth thrust: rapid improvement from oversold (prev < 30% → current > 55%)
        breadth_thrust = prev_breadth < 30 and breadth > 55

        # VIX check: is VIX falling?
        vix_falling = False
        vix_df = scanner_service.data_cache.get('^VIX')
        if vix_df is not None:
            try:
                loc = vix_df.index.get_indexer([date], method='ffill')[0]
                if loc >= 20:
                    vix_now = vix_df['close'].iloc[loc]
                    vix_ma20 = vix_df['close'].iloc[loc-19:loc+1].mean()
                    vix_falling = vix_now < vix_ma20
            except Exception:
                pass

        # Moderate deployment: SPY > MA50 + VIX falling
        if not pd.isna(spy_ma50) and spy_price > spy_ma50 and vix_falling:
            return 0.50, "spy_above_ma50_vix_falling"

        # Cautious deployment: breadth thrust detected
        if breadth_thrust:
            return 0.30, "breadth_thrust"

        # SPY > MA50 alone (without VIX confirmation) — lighter deployment
        if not pd.isna(spy_ma50) and spy_price > spy_ma50:
            return 0.30, "spy_above_ma50"

        # VIX falling alone — very cautious
        if vix_falling and breadth > 40:
            return 0.20, "vix_falling_breadth_improving"

        return 0.0, "no_signal"

    def _check_exit_condition(
        self,
        pos: dict,
        current_price: float,
        current_date: pd.Timestamp,
        exit_strategy: ExitStrategyConfig
    ) -> Optional[str]:
        """
        Check if position should be exited based on exit strategy.

        Args:
            pos: Position dictionary with entry info
            current_price: Current price
            current_date: Current date
            exit_strategy: Exit strategy configuration

        Returns:
            Exit reason string if should exit, None otherwise
        """
        entry_price = pos['entry_price']
        pnl_pct = (current_price - entry_price) / entry_price * 100
        days_held = self._days_between(current_date, pos['entry_date'])

        # Check stop loss first (applies to all strategies)
        if exit_strategy.stop_loss_pct > 0:
            if pnl_pct <= -exit_strategy.stop_loss_pct:
                return 'stop_loss'

        strategy_type = exit_strategy.strategy_type

        if strategy_type == ExitStrategyType.TRAILING_STOP:
            # Update high water mark
            high_water = pos.get('high_water_mark', entry_price)
            if current_price > high_water:
                pos['high_water_mark'] = current_price
                high_water = current_price
            # Check trailing stop from high
            drop_from_high = (high_water - current_price) / high_water * 100
            if drop_from_high >= exit_strategy.trailing_stop_pct:
                return 'trailing_stop'

        elif strategy_type == ExitStrategyType.FIXED_TARGET:
            # Exit when profit target is reached
            if pnl_pct >= exit_strategy.profit_target_pct:
                return 'profit_target'

        elif strategy_type == ExitStrategyType.HYBRID:
            # After hitting initial target, switch to trailing stop
            if pos.get('hybrid_target_hit'):
                # Already hit target, use trailing stop
                high_water = pos.get('high_water_mark', entry_price)
                if current_price > high_water:
                    pos['high_water_mark'] = current_price
                    high_water = current_price
                drop_from_high = (high_water - current_price) / high_water * 100
                if drop_from_high >= exit_strategy.hybrid_trailing_pct:
                    return 'hybrid_trailing'
            else:
                # Check if we hit initial target
                if pnl_pct >= exit_strategy.hybrid_initial_target_pct:
                    pos['hybrid_target_hit'] = True
                    pos['high_water_mark'] = current_price

        elif strategy_type == ExitStrategyType.TIME_BASED:
            # Exit after max hold days
            if days_held >= exit_strategy.max_hold_days:
                return 'time_exit'

        elif strategy_type == ExitStrategyType.STOP_LOSS_TARGET:
            # Legacy: fixed stop loss and profit target
            stop_loss = pos.get('stop_loss', entry_price * (1 - self.stop_loss_pct))
            profit_target = pos.get('profit_target', entry_price * (1 + self.profit_target_pct))
            if current_price <= stop_loss:
                return 'stop_loss'
            if current_price >= profit_target:
                return 'profit_target'

        return None

    def _calculate_momentum_score(self, symbol: str, date: pd.Timestamp) -> Optional[dict]:
        """
        Calculate momentum score for a symbol on a given date

        Returns:
            Dict with score info or None if invalid
        """
        if symbol not in scanner_service.data_cache:
            return None

        df = scanner_service.data_cache[symbol]

        # Handle timezone-aware date matching
        try:
            if date in df.index:
                loc = df.index.get_loc(date)
            else:
                # Try to find nearest date (handles timezone mismatches)
                date_only = date.strftime('%Y-%m-%d')
                matches = df.index[df.index.strftime('%Y-%m-%d') == date_only]
                if len(matches) == 0:
                    return None
                loc = df.index.get_loc(matches[0])
        except (KeyError, IndexError):
            return None
        if loc < max(self.short_mom_days, self.long_mom_days, 50):
            return None

        row = df.iloc[loc]  # Use iloc since we already have the integer location
        price = row['close']
        volume = row['volume']

        # Basic filters
        if price < self.min_price or volume < self.min_volume:
            return None

        # V2: Volume ratio filter (reject if today's volume / 20d avg < threshold)
        if self.volume_ratio_min > 0:
            vol_20d_avg = df['volume'].iloc[max(0, loc-19):loc+1].mean()
            if vol_20d_avg > 0 and (volume / vol_20d_avg) < self.volume_ratio_min:
                return None

        # V2: RSI filter (reject if RSI > threshold, i.e. overextended)
        if self.rsi_oversold_filter < 100:
            closes_for_rsi = df['close'].iloc[max(0, loc-14):loc+1]
            if len(closes_for_rsi) >= 15:
                from app.services.strategy_params_v2 import compute_rsi
                rsi_series = compute_rsi(closes_for_rsi, period=14)
                current_rsi = rsi_series.iloc[-1]
                if not pd.isna(current_rsi) and current_rsi > self.rsi_oversold_filter:
                    return None

        # Calculate momentum
        short_mom_price = df.iloc[loc - self.short_mom_days]['close']
        long_mom_price = df.iloc[loc - self.long_mom_days]['close']

        short_mom = (price / short_mom_price - 1) * 100
        long_mom = (price / long_mom_price - 1) * 100

        # Calculate volatility (20-day)
        returns = df['close'].iloc[loc-19:loc+1].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 0 else 30

        # MA filters
        ma_20 = df['close'].iloc[loc-19:loc+1].mean()
        ma_50 = df['close'].iloc[loc-49:loc+1].mean() if loc >= 49 else price

        # Distance from 50-day high
        high_50d = df['close'].iloc[max(0, loc-49):loc+1].max()
        dist_from_high = (price / high_50d - 1) * 100

        # Quality filter
        passes_trend = price > ma_20 and price > ma_50
        passes_breakout = dist_from_high >= -self.near_50d_high_pct
        passes_quality = passes_trend and passes_breakout

        # Composite score
        composite_score = (
            short_mom * self.short_mom_weight +
            long_mom * self.long_mom_weight -
            volatility * self.volatility_penalty
        )

        # Liquidity tier bonus
        if self.tier1_bonus > 0 and symbol in self.tier1_set:
            composite_score += self.tier1_bonus

        return {
            'symbol': symbol,
            'price': price,
            'short_mom': short_mom,
            'long_mom': long_mom,
            'volatility': volatility,
            'composite_score': composite_score,
            'passes_quality': passes_quality,
            'dist_from_high': dist_from_high
        }

    def run_backtest(
        self,
        lookback_days: int = 252,  # 1 year default
        end_date: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        use_momentum_strategy: bool = True,  # Deprecated, use strategy_type
        ticker_list: Optional[List[str]] = None,
        exit_strategy: Optional[ExitStrategyConfig] = None,
        strategy_type: Optional[str] = None,  # "momentum", "dwap", "dwap_hybrid"
        force_close_at_end: bool = False,  # Close all positions at simulation end
        initial_positions: Optional[Dict[str, dict]] = None  # Carry-over positions from previous period
    ) -> BacktestResult:
        """
        Run backtest over historical data

        Args:
            lookback_days: Number of trading days to simulate (ignored if start_date provided)
            end_date: End date for backtest (default: today)
            start_date: Start date for backtest (overrides lookback_days if provided)
            use_momentum_strategy: DEPRECATED - use strategy_type instead
            ticker_list: Optional list of tickers to limit backtest to
            exit_strategy: Optional exit strategy configuration
            strategy_type: Strategy to use - "momentum", "dwap", or "dwap_hybrid"
                          If None, falls back to use_momentum_strategy for compatibility
            force_close_at_end: If True, close all open positions at period end
                               and record as trades with exit_reason="rebalance_exit"
            initial_positions: Carry-over positions from a previous period (walk-forward).
                              Dict mapping symbol -> position dict with entry_price, shares, etc.

        Returns:
            BacktestResult with positions, trades, and metrics
        """
        if not scanner_service.data_cache:
            raise RuntimeError("No data loaded. Run a scan first.")

        end_date = end_date or datetime.now()

        # Resolve strategy_type from parameters
        if strategy_type is None:
            # Backward compatibility: use use_momentum_strategy flag
            strategy_type = "momentum" if use_momentum_strategy else "dwap"

        # Set up exit strategy based on strategy type
        if exit_strategy is None:
            if strategy_type == "momentum":
                exit_strategy = ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TRAILING_STOP,
                    trailing_stop_pct=self.trailing_stop_pct * 100
                )
            elif strategy_type == "dwap_hybrid":
                # DWAP entry + trailing stop exit (the rocket catcher)
                exit_strategy = ExitStrategyConfig(
                    strategy_type=ExitStrategyType.TRAILING_STOP,
                    trailing_stop_pct=self.trailing_stop_pct * 100,
                    stop_loss_pct=self.stop_loss_pct * 100 if self.stop_loss_pct > 0 else 0
                )
            elif strategy_type == "ensemble":
                # ENSEMBLE: DWAP entry timing + momentum quality filter + configurable exit
                if self.exit_type == "hybrid":
                    exit_strategy = ExitStrategyConfig(
                        strategy_type=ExitStrategyType.HYBRID,
                        hybrid_initial_target_pct=self.hybrid_initial_target_pct,
                        hybrid_trailing_pct=self.hybrid_trailing_pct,
                        trailing_stop_pct=self.trailing_stop_pct * 100,
                    )
                elif self.exit_type == "time_capped":
                    exit_strategy = ExitStrategyConfig(
                        strategy_type=ExitStrategyType.TIME_BASED,
                        max_hold_days=self.max_hold_days,
                        trailing_stop_pct=self.trailing_stop_pct * 100,
                    )
                else:
                    exit_strategy = ExitStrategyConfig(
                        strategy_type=ExitStrategyType.TRAILING_STOP,
                        trailing_stop_pct=self.trailing_stop_pct * 100,
                    )
            else:  # "dwap" - legacy
                exit_strategy = ExitStrategyConfig(
                    strategy_type=ExitStrategyType.STOP_LOSS_TARGET,
                    stop_loss_pct=self.stop_loss_pct * 100,
                    profit_target_pct=self.profit_target_pct * 100
                )

        # Get symbols to use
        from app.services.scanner import _EXCLUDED_SET
        if ticker_list:
            # Trust the caller's filtered list (WF uses its own exclusion set)
            available_symbols = [s for s in ticker_list if s in scanner_service.data_cache]
        else:
            # No ticker_list: apply full exclusion (standalone backtests)
            available_symbols = [s for s in scanner_service.data_cache.keys() if s not in _EXCLUDED_SET]

        # Get all symbols with enough data
        symbols = []
        # When start_date is given (WF periods), only need 200 for indicator calculation (MA200)
        # When using lookback_days, need lookback + 200 for full range
        min_data_points = 200 if start_date else lookback_days + 200
        for symbol in available_symbols:
            df = scanner_service.data_cache[symbol]
            if len(df) >= min_data_points:
                # Ensure DWAP/MA indicators are computed (required for ensemble/dwap_hybrid)
                if 'dwap' not in df.columns:
                    df = scanner_service._ensure_indicators(df)
                    scanner_service.data_cache[symbol] = df
                symbols.append(symbol)

        if not symbols:
            raise RuntimeError("Not enough historical data for backtest")

        # Ensure SPY indicators are computed for market regime check
        # (SPY may be excluded from trading but is needed for the regime filter)
        if 'SPY' in scanner_service.data_cache:
            spy_df = scanner_service.data_cache['SPY']
            if 'ma_200' not in spy_df.columns or spy_df['ma_200'].isna().all():
                spy_df = scanner_service._ensure_indicators(spy_df)
                scanner_service.data_cache['SPY'] = spy_df

        # Initialize tracking
        capital = self.initial_capital
        positions: Dict[str, dict] = {}  # symbol -> position info
        trades: List[SimulatedTrade] = []
        equity_curve = []
        position_id = 0
        trade_id = 0
        last_rebalance: Optional[pd.Timestamp] = None
        in_cash_mode = False  # True when market is unfavorable
        cash_mode_day_count = 0  # Days spent in cash mode (for anti-churn cooldown)
        graduated_deploy_pct = 0.0  # Current graduated deployment level (0-1)
        prev_breadth = 50.0  # Previous day's breadth for thrust detection

        # Seed carried positions from previous walk-forward period
        if initial_positions:
            positions = {k: dict(v) for k, v in initial_positions.items()}
            position_id = max((p.get('id', 0) for p in positions.values()), default=0)
            # Capital adjustment happens below after we determine the date range,
            # so we can use period-start market prices.
            print(f"[BACKTEST] Seeded {len(positions)} carried positions, "
                  f"position_id starts at {position_id}")

        # Debug tracking
        debug_rebalance_days = 0
        debug_cash_mode_days = 0
        debug_first_rebalance_info = ""

        # Get common date range
        sample_df = scanner_service.data_cache[symbols[0]]

        # Determine date range
        if start_date:
            # Use explicit start/end dates
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            # Handle timezone-aware index
            if sample_df.index.tz is not None:
                start_ts = start_ts.tz_localize(sample_df.index.tz) if start_ts.tz is None else start_ts.tz_convert(sample_df.index.tz)
                end_ts = end_ts.tz_localize(sample_df.index.tz) if end_ts.tz is None else end_ts.tz_convert(sample_df.index.tz)
            dates = sample_df.index[(sample_df.index >= start_ts) & (sample_df.index <= end_ts)]
            print(f"[BACKTEST] Date range: {start_ts} to {end_ts}, found {len(dates)} trading days, {len(symbols)} symbols")
        else:
            # Use lookback_days from end
            dates = sample_df.index[-lookback_days:]
            print(f"[BACKTEST] Using last {lookback_days} days, {len(symbols)} symbols")

        if len(dates) == 0:
            print(f"[BACKTEST] WARNING: No trading days found!")
            print(f"[BACKTEST] Sample index range: {sample_df.index[0]} to {sample_df.index[-1]}")
            print(f"[BACKTEST] Sample index tz: {sample_df.index.tz}")
            print(f"[BACKTEST] Requested: start_ts={start_ts} (tz={start_ts.tz}), end_ts={end_ts} (tz={end_ts.tz})")
            raise RuntimeError("No trading days in date range")

        # Adjust capital for carried positions using period-start prices
        if initial_positions and positions:
            first_date = dates[0]
            carried_value = 0.0
            dropped = []
            for sym, pos in positions.items():
                if sym not in scanner_service.data_cache:
                    dropped.append(sym)
                    continue
                row = self._get_row_for_date(scanner_service.data_cache[sym], first_date)
                if row is None:
                    dropped.append(sym)
                    continue
                carried_value += pos['shares'] * row['close']
            # Remove symbols we can't price
            for sym in dropped:
                print(f"[BACKTEST] Dropping carried position {sym}: no data at period start")
                del positions[sym]
            # Cash = total equity - carried position value
            capital = self.initial_capital - carried_value
            if capital < 0:
                # Shouldn't happen, but guard against it
                print(f"[BACKTEST] WARNING: negative cash after carry-over ({capital:.2f}), clamping to 0")
                capital = 0.0
            print(f"[BACKTEST] Carried position value: ${carried_value:,.2f}, "
                  f"cash: ${capital:,.2f}, total: ${self.initial_capital:,.2f}")

        # Simulate each trading day
        for i, date in enumerate(dates):
            date_str = date.strftime('%Y-%m-%d')

            # Check market regime (momentum, hybrid, and ensemble strategies respect market filter)
            if strategy_type in ("momentum", "dwap_hybrid", "ensemble") and settings.MARKET_FILTER_ENABLED:
                market_favorable = self._check_market_regime(date)

                # If market turns unfavorable, close positions (all or partial)
                if not market_favorable and not in_cash_mode:
                    in_cash_mode = True
                    cash_mode_day_count = 0

                    # Determine which positions to close
                    symbols_to_close = list(positions.keys())
                    if self.bear_keep_pct > 0 and len(positions) > 1:
                        # Rank positions by current PnL%, keep the top performers
                        pos_pnl = []
                        for sym in positions:
                            pos = positions[sym]
                            df = scanner_service.data_cache.get(sym)
                            if df is None:
                                pos_pnl.append((sym, -999))
                                continue
                            row = self._get_row_for_date(df, date)
                            if row is None:
                                pos_pnl.append((sym, -999))
                                continue
                            pnl = (row['close'] - pos['entry_price']) / pos['entry_price']
                            pos_pnl.append((sym, pnl))
                        pos_pnl.sort(key=lambda x: x[1], reverse=True)
                        n_keep = max(1, int(len(pos_pnl) * self.bear_keep_pct))
                        symbols_to_close = [sym for sym, _ in pos_pnl[n_keep:]]

                    for symbol in symbols_to_close:
                        pos = positions[symbol]
                        df = scanner_service.data_cache[symbol]
                        row = self._get_row_for_date(df, date)
                        if row is None:
                            continue
                        current_price = row['close']
                        pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']

                        trade_id += 1
                        trades.append(SimulatedTrade(
                            id=trade_id,
                            symbol=symbol,
                            entry_date=pos['entry_date'],
                            exit_date=date_str,
                            entry_price=pos['entry_price'],
                            exit_price=current_price,
                            shares=pos['shares'],
                            pnl=round((current_price - pos['entry_price']) * pos['shares'], 2),
                            pnl_pct=round(pnl_pct * 100, 2),
                            exit_reason='market_regime',
                            days_held=self._days_between(date, pos['entry_date']),
                            dwap_at_entry=pos.get('dwap_at_entry', 0),
                            momentum_score=pos.get('momentum_score', 0),
                            momentum_rank=pos.get('momentum_rank', 0),
                            pct_above_dwap_at_entry=pos.get('pct_above_dwap_at_entry', 0),
                            num_candidates=pos.get('num_candidates', 0),
                            dwap_age=pos.get('dwap_age', 0),
                            short_mom=pos.get('short_mom', 0),
                            long_mom=pos.get('long_mom', 0),
                            volatility=pos.get('volatility', 0),
                            dist_from_high=pos.get('dist_from_high', 0),
                            vol_ratio=pos.get('vol_ratio', 0),
                            spy_trend=pos.get('spy_trend', 0),
                        ))
                        capital += pos['shares'] * current_price
                        del positions[symbol]

                    # Safety: clear any orphan positions that couldn't be priced
                    if self.bear_keep_pct <= 0 and positions:
                        for sym in list(positions.keys()):
                            print(f"[BACKTEST] WARNING: orphan position {sym} cleared on regime exit (no price data)")
                            del positions[sym]

                elif in_cash_mode:
                    cash_mode_day_count += 1
                    if self.graduated_reentry:
                        # Graduated re-entry: check recovery signals for partial deployment
                        deploy_pct, deploy_reason = self._check_graduated_reentry(
                            date, symbols, cash_mode_day_count, prev_breadth
                        )
                        # Update breadth for next day's thrust detection
                        prev_breadth = self._compute_breadth(date, symbols, ma_period=50)
                        graduated_deploy_pct = deploy_pct
                        if deploy_pct >= 1.0:
                            in_cash_mode = False
                            graduated_deploy_pct = 0.0
                    elif self.regime_reentry_mode:
                        # Smart re-entry: use enhanced logic if enabled, else classic SPY>MA200
                        if self._check_regime_reentry(date, cash_mode_day_count):
                            in_cash_mode = False
                    elif market_favorable:
                        in_cash_mode = False

            # Check existing positions for exits
            symbols_to_close = []
            for symbol, pos in positions.items():
                if symbol not in scanner_service.data_cache:
                    continue

                df = scanner_service.data_cache[symbol]
                row = self._get_row_for_date(df, date)
                if row is None:
                    continue

                current_price = row['close']
                pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']

                # Check exit condition using configured strategy
                exit_reason = self._check_exit_condition(pos, current_price, date, exit_strategy)

                if exit_reason:
                    trade_id += 1
                    trades.append(SimulatedTrade(
                        id=trade_id,
                        symbol=symbol,
                        entry_date=pos['entry_date'],
                        exit_date=date_str,
                        entry_price=pos['entry_price'],
                        exit_price=current_price,
                        shares=pos['shares'],
                        pnl=round((current_price - pos['entry_price']) * pos['shares'], 2),
                        pnl_pct=round(pnl_pct * 100, 2),
                        exit_reason=exit_reason,
                        days_held=self._days_between(date, pos['entry_date']),
                        dwap_at_entry=pos.get('dwap_at_entry', 0),
                        momentum_score=pos.get('momentum_score', 0),
                        momentum_rank=pos.get('momentum_rank', 0),
                        pct_above_dwap_at_entry=pos.get('pct_above_dwap_at_entry', 0),
                        num_candidates=pos.get('num_candidates', 0),
                        dwap_age=pos.get('dwap_age', 0),
                        short_mom=pos.get('short_mom', 0),
                        long_mom=pos.get('long_mom', 0),
                        volatility=pos.get('volatility', 0),
                        dist_from_high=pos.get('dist_from_high', 0),
                        vol_ratio=pos.get('vol_ratio', 0),
                        spy_trend=pos.get('spy_trend', 0),
                    ))
                    capital += pos['shares'] * current_price
                    symbols_to_close.append(symbol)

            # Remove closed positions
            for symbol in symbols_to_close:
                del positions[symbol]

            # Skip new entries if in cash mode (unfavorable market)
            # Exception: graduated re-entry allows partial deployment
            if in_cash_mode and graduated_deploy_pct <= 0:
                debug_cash_mode_days += 1
                position_value = 0.0
                for sym, pos in positions.items():
                    if sym in scanner_service.data_cache:
                        sym_row = self._get_row_for_date(scanner_service.data_cache[sym], date)
                        if sym_row is not None:
                            position_value += pos['shares'] * sym_row['close']
                equity_curve.append({'date': date_str, 'equity': capital + position_value})
                continue

            # Rebalancing logic: momentum=weekly on Fridays, dwap/dwap_hybrid=daily
            should_rebalance = (
                self._should_rebalance(date, last_rebalance)
                if strategy_type == "momentum"
                else True  # DWAP and hybrid check signals daily
            )

            # Graduated re-entry: limit positions and sizing based on deployment level
            effective_max_positions = self.max_positions
            effective_position_size_pct = self.position_size_pct
            if in_cash_mode and graduated_deploy_pct > 0:
                # Scale down: 30% deploy → max 2 positions at reduced size
                effective_max_positions = max(1, int(self.max_positions * graduated_deploy_pct))
                effective_position_size_pct = self.position_size_pct * graduated_deploy_pct

            # Look for new entries if we have room and it's rebalance time
            if len(positions) < effective_max_positions and should_rebalance:
                candidates = []

                if strategy_type == "momentum":
                    # Momentum-based ranking
                    skipped_in_pos = 0
                    skipped_no_score = 0
                    skipped_quality = 0
                    for symbol in symbols:
                        if symbol in positions:
                            skipped_in_pos += 1
                            continue
                        score_data = self._calculate_momentum_score(symbol, date)
                        if not score_data:
                            skipped_no_score += 1
                            continue
                        if not score_data['passes_quality']:
                            skipped_quality += 1
                            continue
                        candidates.append(score_data)

                    # Log on first rebalance day
                    if last_rebalance is None:
                        debug_first_rebalance_info = (f"First rebalance {date_str}: {len(symbols)} sym, "
                              f"{skipped_no_score} no_score, {skipped_quality} failed_quality, {len(candidates)} candidates")
                        print(f"[BACKTEST] {debug_first_rebalance_info}")
                    debug_rebalance_days += 1

                    # Sort by composite score (highest first)
                    candidates.sort(key=lambda x: -x['composite_score'])
                    num_cands = len(candidates)
                    for rank_idx, cand in enumerate(candidates, 1):
                        cand['momentum_rank'] = rank_idx
                        cand['num_candidates'] = num_cands

                    # Enter positions up to max
                    for cand in candidates:
                        if len(positions) >= effective_max_positions:
                            break

                        position_value = self.initial_capital * effective_position_size_pct
                        if position_value > capital:
                            continue

                        shares = position_value / cand['price']
                        capital -= shares * cand['price']

                        position_id += 1
                        entry_price = cand['price']
                        positions[cand['symbol']] = {
                            'id': position_id,
                            'entry_price': entry_price,
                            'entry_date': date_str,
                            'shares': round(shares, 2),
                            'high_water_mark': entry_price,
                            'trailing_stop': round(entry_price * (1 - self.trailing_stop_pct), 2),
                            'dwap_at_entry': 0,  # Not used in momentum strategy
                            'pct_above_dwap_at_entry': 0,
                            'composite_score': cand['composite_score'],
                            'momentum_score': cand.get('composite_score', 0),
                            'momentum_rank': cand.get('momentum_rank', 0),
                            'num_candidates': cand.get('num_candidates', 0)
                        }

                    if candidates:
                        last_rebalance = date

                elif strategy_type == "dwap_hybrid":
                    # DWAP Hybrid: DWAP entry + trailing stop exit (the "rocket catcher")
                    # Scans daily for DWAP crosses, but uses trailing stops to let winners run
                    skipped_no_dwap = 0
                    skipped_filters = 0
                    for symbol in symbols:
                        if symbol in positions:
                            continue

                        df = scanner_service.data_cache[symbol]
                        row = self._get_row_for_date(df, date)
                        if row is None:
                            continue

                        price = row['close']
                        volume = row['volume']
                        dwap = row.get('dwap', np.nan)
                        vol_avg = row.get('vol_avg', np.nan)
                        ma_50 = row.get('ma_50', np.nan)
                        ma_200 = row.get('ma_200', np.nan)

                        if pd.isna(dwap) or dwap <= 0:
                            skipped_no_dwap += 1
                            continue

                        pct_above_dwap = (price / dwap - 1)

                        if (pct_above_dwap >= self.dwap_threshold_pct and
                            volume >= self.min_volume and
                            price >= self.min_price):

                            vol_ratio = volume / vol_avg if vol_avg > 0 else 0
                            is_strong = (
                                vol_ratio >= self.volume_spike_mult and
                                not pd.isna(ma_50) and not pd.isna(ma_200) and
                                price > ma_50 > ma_200
                            )

                            candidates.append({
                                'symbol': symbol,
                                'price': price,
                                'dwap': dwap,
                                'pct_above_dwap': pct_above_dwap,
                                'is_strong': is_strong,
                                'vol_ratio': vol_ratio
                            })
                        else:
                            skipped_filters += 1

                    # Log first entry day for debugging
                    if last_rebalance is None and (candidates or skipped_filters > 0):
                        debug_first_rebalance_info = (f"First scan {date_str}: {len(symbols)} sym, "
                              f"{skipped_no_dwap} no_dwap, {skipped_filters} failed_filters, {len(candidates)} candidates")
                        print(f"[BACKTEST] {debug_first_rebalance_info}")
                    if candidates:
                        debug_rebalance_days += 1

                    # Sort: strong signals first, then by % above DWAP
                    candidates.sort(key=lambda x: (not x['is_strong'], -x['pct_above_dwap']))
                    num_cands = len(candidates)
                    for rank_idx, cand in enumerate(candidates, 1):
                        cand['momentum_rank'] = rank_idx
                        cand['num_candidates'] = num_cands

                    for cand in candidates:
                        if len(positions) >= effective_max_positions:
                            break

                        position_value = self.initial_capital * effective_position_size_pct
                        if position_value > capital:
                            continue

                        shares = position_value / cand['price']
                        capital -= shares * cand['price']

                        position_id += 1
                        entry_price = cand['price']
                        # Hybrid uses trailing stop fields (like momentum) but tracks DWAP entry
                        positions[cand['symbol']] = {
                            'id': position_id,
                            'entry_price': entry_price,
                            'entry_date': date_str,
                            'shares': round(shares, 2),
                            'high_water_mark': entry_price,  # For trailing stop
                            'trailing_stop': round(entry_price * (1 - self.trailing_stop_pct), 2),
                            'dwap_at_entry': round(cand['dwap'], 2),
                            'pct_above_dwap_at_entry': round(cand['pct_above_dwap'] * 100, 1),
                            'momentum_rank': cand.get('momentum_rank', 0),
                            'num_candidates': cand.get('num_candidates', 0)
                        }

                    if candidates:
                        last_rebalance = date

                elif strategy_type == "ensemble":
                    # ENSEMBLE: DWAP entry timing + Momentum quality filter + Trailing stop exit
                    # Scans daily for DWAP signals but only accepts stocks passing momentum quality filter
                    skipped_no_dwap = 0
                    skipped_filters = 0
                    skipped_quality = 0
                    for symbol in symbols:
                        if symbol in positions:
                            continue

                        df = scanner_service.data_cache[symbol]
                        row = self._get_row_for_date(df, date)
                        if row is None:
                            continue

                        price = row['close']
                        volume = row['volume']
                        dwap = row.get('dwap', np.nan)
                        vol_avg = row.get('vol_avg', np.nan)

                        # DWAP entry check (same as dwap_hybrid)
                        if pd.isna(dwap) or dwap <= 0:
                            skipped_no_dwap += 1
                            continue

                        pct_above_dwap = (price / dwap - 1)

                        if not (pct_above_dwap >= self.dwap_threshold_pct and
                                volume >= self.min_volume and
                                price >= self.min_price):
                            skipped_filters += 1
                            continue

                        # Momentum quality filter - calculate score and check quality
                        score_data = self._calculate_momentum_score(symbol, date)
                        if not score_data or not score_data['passes_quality']:
                            skipped_quality += 1
                            continue

                        vol_ratio = volume / vol_avg if vol_avg > 0 else 0

                        candidates.append({
                            'symbol': symbol,
                            'price': price,
                            'dwap': dwap,
                            'pct_above_dwap': pct_above_dwap,
                            'momentum_score': score_data['composite_score'],
                            'vol_ratio': vol_ratio,
                            'short_mom': score_data['short_mom'],
                            'long_mom': score_data['long_mom'],
                            'volatility': score_data['volatility'],
                            'dist_from_high': score_data['dist_from_high'],
                            'dwap_age': self._compute_dwap_age(symbol, date),
                            'spy_trend': self._compute_spy_trend(date),
                        })

                    # Log first entry day for debugging
                    if last_rebalance is None and (candidates or skipped_filters > 0):
                        debug_first_rebalance_info = (f"First scan {date_str}: {len(symbols)} sym, "
                              f"{skipped_no_dwap} no_dwap, {skipped_filters} failed_filters, "
                              f"{skipped_quality} failed_momentum_quality, {len(candidates)} candidates")
                        print(f"[BACKTEST] {debug_first_rebalance_info}")
                    if candidates:
                        debug_rebalance_days += 1

                    # Sort by momentum score (best first), then DWAP strength
                    candidates.sort(key=lambda x: (-x['momentum_score'], -x['pct_above_dwap']))
                    num_cands = len(candidates)
                    for rank_idx, cand in enumerate(candidates, 1):
                        cand['momentum_rank'] = rank_idx
                        cand['num_candidates'] = num_cands

                    for cand in candidates:
                        if len(positions) >= effective_max_positions:
                            break

                        position_value = self.initial_capital * effective_position_size_pct
                        if position_value > capital:
                            continue

                        shares = position_value / cand['price']
                        capital -= shares * cand['price']

                        position_id += 1
                        entry_price = cand['price']
                        # Ensemble uses trailing stop fields (like momentum)
                        positions[cand['symbol']] = {
                            'id': position_id,
                            'entry_price': entry_price,
                            'entry_date': date_str,
                            'shares': round(shares, 2),
                            'high_water_mark': entry_price,  # For trailing stop
                            'trailing_stop': round(entry_price * (1 - self.trailing_stop_pct), 2),
                            'dwap_at_entry': round(cand['dwap'], 2),
                            'pct_above_dwap_at_entry': round(cand['pct_above_dwap'] * 100, 1),
                            'momentum_score': cand['momentum_score'],
                            'momentum_rank': cand.get('momentum_rank', 0),
                            'num_candidates': cand.get('num_candidates', 0),
                            'dwap_age': cand.get('dwap_age', 0),
                            'short_mom': round(cand.get('short_mom', 0), 2),
                            'long_mom': round(cand.get('long_mom', 0), 2),
                            'volatility': round(cand.get('volatility', 0), 2),
                            'dist_from_high': round(cand.get('dist_from_high', 0), 2),
                            'vol_ratio': round(cand.get('vol_ratio', 0), 2),
                            'spy_trend': round(cand.get('spy_trend', 0), 2),
                        }

                    if candidates:
                        last_rebalance = date

                else:
                    # Legacy DWAP strategy (fixed stop loss + profit target)
                    for symbol in symbols:
                        if symbol in positions:
                            continue

                        df = scanner_service.data_cache[symbol]
                        row = self._get_row_for_date(df, date)
                        if row is None:
                            continue

                        price = row['close']
                        volume = row['volume']
                        dwap = row.get('dwap', np.nan)
                        vol_avg = row.get('vol_avg', np.nan)
                        ma_50 = row.get('ma_50', np.nan)
                        ma_200 = row.get('ma_200', np.nan)

                        if pd.isna(dwap) or dwap <= 0:
                            continue

                        pct_above_dwap = (price / dwap - 1)

                        if (pct_above_dwap >= self.dwap_threshold_pct and
                            volume >= self.min_volume and
                            price >= self.min_price):

                            vol_ratio = volume / vol_avg if vol_avg > 0 else 0
                            is_strong = (
                                vol_ratio >= self.volume_spike_mult and
                                not pd.isna(ma_50) and not pd.isna(ma_200) and
                                price > ma_50 > ma_200
                            )

                            candidates.append({
                                'symbol': symbol,
                                'price': price,
                                'dwap': dwap,
                                'pct_above_dwap': pct_above_dwap,
                                'is_strong': is_strong,
                                'vol_ratio': vol_ratio
                            })

                    candidates.sort(key=lambda x: (not x['is_strong'], -x['pct_above_dwap']))
                    num_cands = len(candidates)
                    for rank_idx, cand in enumerate(candidates, 1):
                        cand['momentum_rank'] = rank_idx
                        cand['num_candidates'] = num_cands

                    for cand in candidates:
                        if len(positions) >= effective_max_positions:
                            break

                        position_value = self.initial_capital * effective_position_size_pct
                        if position_value > capital:
                            continue

                        shares = position_value / cand['price']
                        capital -= shares * cand['price']

                        position_id += 1
                        positions[cand['symbol']] = {
                            'id': position_id,
                            'entry_price': cand['price'],
                            'entry_date': date_str,
                            'shares': round(shares, 2),
                            'stop_loss': round(cand['price'] * (1 - self.stop_loss_pct), 2),
                            'profit_target': round(cand['price'] * (1 + self.profit_target_pct), 2),
                            'dwap_at_entry': round(cand['dwap'], 2),
                            'pct_above_dwap_at_entry': round(cand['pct_above_dwap'] * 100, 1),
                            'momentum_rank': cand.get('momentum_rank', 0),
                            'num_candidates': cand.get('num_candidates', 0)
                        }

            # Calculate daily equity
            position_value = 0.0
            for sym, pos in positions.items():
                if sym in scanner_service.data_cache:
                    sym_row = self._get_row_for_date(scanner_service.data_cache[sym], date)
                    if sym_row is not None:
                        position_value += pos['shares'] * sym_row['close']
            equity_curve.append({
                'date': date_str,
                'equity': capital + position_value
            })

        # Snapshot raw positions BEFORE force close for walk-forward carry-over
        raw_positions_snapshot = {k: dict(v) for k, v in positions.items()}

        # Force close remaining positions at period/simulation end if requested
        if force_close_at_end and positions:
            last_date = dates[-1]
            last_date_str = last_date.strftime('%Y-%m-%d')
            print(f"[BACKTEST] Force closing {len(positions)} positions at period end ({last_date_str})")

            for symbol, pos in positions.items():
                df = scanner_service.data_cache.get(symbol)
                if df is None:
                    continue

                # Get price on the last day of simulation
                row = self._get_row_for_date(df, last_date)
                if row is None:
                    # Fall back to latest price
                    current_price = df.iloc[-1]['close']
                else:
                    current_price = row['close']

                pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']

                trade_id += 1
                trades.append(SimulatedTrade(
                    id=trade_id,
                    symbol=symbol,
                    entry_date=pos['entry_date'],
                    exit_date=last_date_str,
                    entry_price=pos['entry_price'],
                    exit_price=current_price,
                    shares=pos['shares'],
                    pnl=round((current_price - pos['entry_price']) * pos['shares'], 2),
                    pnl_pct=round(pnl_pct * 100, 2),
                    exit_reason='rebalance_exit',
                    days_held=self._days_between(last_date, pos['entry_date']),
                    dwap_at_entry=pos.get('dwap_at_entry', 0),
                    momentum_score=pos.get('momentum_score', 0),
                    momentum_rank=pos.get('momentum_rank', 0),
                    pct_above_dwap_at_entry=pos.get('pct_above_dwap_at_entry', 0),
                    num_candidates=pos.get('num_candidates', 0),
                    dwap_age=pos.get('dwap_age', 0),
                    short_mom=pos.get('short_mom', 0),
                    long_mom=pos.get('long_mom', 0),
                    volatility=pos.get('volatility', 0),
                    dist_from_high=pos.get('dist_from_high', 0),
                    vol_ratio=pos.get('vol_ratio', 0),
                    spy_trend=pos.get('spy_trend', 0),
                ))
                capital += pos['shares'] * current_price

            positions.clear()

        # Convert remaining positions to SimulatedPosition objects
        final_positions = []
        today = datetime.now()

        for symbol, pos in positions.items():
            df = scanner_service.data_cache[symbol]
            current_price = df.iloc[-1]['close']
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']

            # Handle both momentum (trailing_stop) and legacy (stop_loss/profit_target) positions
            stop_loss = pos.get('stop_loss') or pos.get('trailing_stop', 0)
            profit_target = pos.get('profit_target', 0)

            final_positions.append(SimulatedPosition(
                id=pos['id'],
                symbol=symbol,
                shares=pos['shares'],
                entry_price=round(pos['entry_price'], 2),
                entry_date=pos['entry_date'],
                current_price=round(current_price, 2),
                stop_loss=stop_loss,
                profit_target=profit_target,
                pnl_pct=round(pnl_pct * 100, 2),
                pnl_dollars=round((current_price - pos['entry_price']) * pos['shares'], 2),
                days_held=self._days_between(pd.Timestamp(today), pos['entry_date']),
                dwap_at_entry=pos.get('dwap_at_entry', 0),
                pct_above_dwap_at_entry=pos.get('pct_above_dwap_at_entry', 0)
            ))

        # Calculate metrics
        total_pnl = sum(t.pnl for t in trades)
        wins = [t for t in trades if t.pnl > 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        # Calculate max drawdown
        peak = equity_curve[0]['equity'] if equity_curve else self.initial_capital
        max_dd = 0
        for point in equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            dd = (peak - point['equity']) / peak
            if dd > max_dd:
                max_dd = dd

        # Final equity
        final_equity = equity_curve[-1]['equity'] if equity_curve else self.initial_capital
        total_return_pct = (final_equity - self.initial_capital) / self.initial_capital * 100

        # Sharpe ratio (simplified - daily returns)
        returns = []
        if len(equity_curve) > 1:
            for i in range(1, len(equity_curve)):
                daily_ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
                returns.append(daily_ret)
            if returns:
                avg_ret = np.mean(returns) * 252  # Annualized
                std_ret = np.std(returns) * np.sqrt(252)
                sharpe = avg_ret / std_ret if std_ret > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        # Calculate enhanced metrics
        enhanced_metrics = self._calculate_enhanced_metrics(
            trades=trades,
            equity_curve=equity_curve,
            returns=returns,
            total_return_pct=total_return_pct,
            max_dd=max_dd * 100
        )

        # Build debug info string
        debug_info = (f"{len(trades)} trades, {len(dates)} days, {debug_rebalance_days} rebal_days, "
                      f"{debug_cash_mode_days} cash_days, {total_return_pct:.2f}% return. "
                      f"{debug_first_rebalance_info or 'No rebalance'}")
        print(f"[BACKTEST] Summary: {debug_info}")
        print(f"[BACKTEST] Date range: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")
        if len(trades) == 0:
            print(f"[BACKTEST] WARNING: No trades executed! Check: market filter, rebalancing, signal generation")

        return BacktestResult(
            positions=final_positions,
            trades=sorted(trades, key=lambda t: t.exit_date, reverse=True),
            raw_positions=raw_positions_snapshot,
            total_return_pct=round(total_return_pct, 2),
            win_rate=round(win_rate, 1),
            total_trades=len(trades),
            open_positions=len(final_positions),
            total_pnl=round(total_pnl, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            sharpe_ratio=round(sharpe, 2),
            start_date=dates[0].strftime('%Y-%m-%d'),
            end_date=dates[-1].strftime('%Y-%m-%d'),
            debug_info=debug_info,
            **enhanced_metrics
        )


# Singleton instance
backtester_service = BacktesterService()
