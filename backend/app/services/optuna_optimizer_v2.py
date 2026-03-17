"""
V2 Optuna Multi-Objective Optimizer for Strategy Parameters

Key differences from V1 (optuna_optimizer.py):
- Dual-objective: maximize return, minimize drawdown (Pareto frontier)
- Extended parameter space with 7 alpha levers
- Conditional parameter sampling (exit type → sub-params)
- risk_preference parameter to select point on Pareto frontier
- V1 is preserved as-is for backward compatibility
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.strategy_params_v2 import (
    V2_PARAM_SPACES,
    V2_CONDITIONAL_PARAMS,
    V2_REGIME_CONSTRAINTS,
)


class StrategyOptimizerV2:
    """
    Multi-objective Bayesian optimizer using Optuna TPE.

    Returns Pareto-optimal parameter sets trading off return vs drawdown.
    The risk_preference parameter selects where on the frontier to pick.
    """

    def optimize(
        self,
        strategy_type: str,
        objective_fn: Callable[[Dict[str, Any]], Optional[Tuple[float, float]]],
        regime_risk_level: str = "medium",
        warm_start_params: Optional[Dict[str, Any]] = None,
        n_trials: int = 30,
        seed_date: Optional[datetime] = None,
        risk_preference: float = 0.5,
    ) -> Optional[Dict[str, Any]]:
        """
        Run multi-objective Bayesian optimization.

        Args:
            strategy_type: "ensemble" (only supported type for V2)
            objective_fn: Takes params dict, returns (total_return_pct, max_drawdown_pct)
                         or None if trial failed. Return is maximized, drawdown minimized.
            regime_risk_level: Market regime risk level for constraint narrowing
            warm_start_params: Previous period's best params for warm-starting
            n_trials: Number of optimization trials
            seed_date: Date for deterministic seeding
            risk_preference: 0.0=conservative (lowest DD), 1.0=aggressive (highest return),
                            0.5=balanced (best return/DD ratio)

        Returns:
            Dict with "best_params", "best_return", "best_drawdown", "pareto_size",
            or None if all trials failed.
        """
        import optuna
        from optuna.samplers import TPESampler

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        if seed_date:
            seed = int(seed_date.timestamp()) % (2**31)
        else:
            seed = 42

        space = V2_PARAM_SPACES.get(strategy_type)
        if not space:
            return None

        # Apply regime constraints
        constrained_space = self._apply_regime_constraints(space, regime_risk_level)

        sampler = TPESampler(
            seed=seed,
            n_startup_trials=max(n_trials // 3, 3),
            multivariate=True,
        )

        study = optuna.create_study(
            directions=["maximize", "minimize"],  # maximize return, minimize drawdown
            sampler=sampler,
        )

        # Warm-start: enqueue previous best as first trial
        if warm_start_params:
            enqueue_params = self._build_enqueue_params(warm_start_params, constrained_space)
            if enqueue_params:
                study.enqueue_trial(enqueue_params)

        # Track all completed trials for Pareto selection
        trial_results: List[Dict[str, Any]] = []

        def optuna_objective(trial):
            params = self._suggest_params(trial, constrained_space)

            result = objective_fn(params)
            if result is None:
                raise optuna.TrialPruned()

            total_return_pct, max_drawdown_pct = result

            # Store for later Pareto selection
            trial_results.append({
                "params": params.copy(),
                "return_pct": total_return_pct,
                "drawdown_pct": max_drawdown_pct,
            })

            return total_return_pct, max_drawdown_pct

        study.optimize(optuna_objective, n_trials=n_trials, show_progress_bar=False)

        if not trial_results:
            return None

        # Extract Pareto frontier and select based on risk_preference
        pareto_trials = self._get_pareto_frontier(trial_results)
        selected = self._select_from_frontier(pareto_trials, risk_preference)

        return {
            "best_params": selected["params"],
            "best_return": selected["return_pct"],
            "best_drawdown": selected["drawdown_pct"],
            "pareto_size": len(pareto_trials),
        }

    def _suggest_params(
        self,
        trial,
        constrained_space: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """
        Suggest parameters from Optuna trial, respecting conditional sampling.
        """
        params = {}

        # First pass: sample all non-conditional params
        for param_name, param_def in constrained_space.items():
            if param_name in V2_CONDITIONAL_PARAMS:
                continue  # Handle in second pass

            params[param_name] = self._suggest_single_param(trial, param_name, param_def)

        # Second pass: sample conditional params only when parent condition is met
        for param_name, cond_info in V2_CONDITIONAL_PARAMS.items():
            if param_name not in constrained_space:
                continue

            parent_value = params.get(cond_info["parent"])
            if parent_value == cond_info["condition"]:
                params[param_name] = self._suggest_single_param(
                    trial, param_name, constrained_space[param_name]
                )

        return params

    def _suggest_single_param(self, trial, param_name: str, param_def: Dict) -> Any:
        """Suggest a single parameter value from an Optuna trial."""
        if param_def.get("type") == "categorical":
            return trial.suggest_categorical(param_name, param_def["choices"])
        elif isinstance(param_def.get("step"), int) or (
            isinstance(param_def.get("low"), int)
            and isinstance(param_def.get("high"), int)
        ):
            return trial.suggest_int(
                param_name,
                int(param_def["low"]),
                int(param_def["high"]),
                step=int(param_def.get("step", 1)),
            )
        else:
            return trial.suggest_float(
                param_name,
                param_def["low"],
                param_def["high"],
                step=param_def.get("step"),
            )

    def _build_enqueue_params(
        self,
        warm_params: Dict[str, Any],
        constrained_space: Dict[str, Dict],
    ) -> Dict[str, Any]:
        """Build enqueue-compatible params from warm-start, clamping to bounds."""
        enqueue = {}
        for param_name, param_def in constrained_space.items():
            if param_name not in warm_params:
                continue

            # Skip conditional params whose parent condition isn't met
            if param_name in V2_CONDITIONAL_PARAMS:
                cond = V2_CONDITIONAL_PARAMS[param_name]
                parent_val = warm_params.get(cond["parent"])
                if parent_val != cond["condition"]:
                    continue

            val = warm_params[param_name]
            if param_def.get("type") == "categorical":
                if val in param_def["choices"]:
                    enqueue[param_name] = val
            else:
                low = param_def["low"]
                high = param_def["high"]
                enqueue[param_name] = max(low, min(high, val))

        return enqueue

    def _get_pareto_frontier(
        self, trials: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract Pareto-optimal trials (maximize return, minimize drawdown).

        A trial is Pareto-optimal if no other trial has both higher return
        AND lower drawdown.
        """
        pareto = []
        for candidate in trials:
            is_dominated = False
            for other in trials:
                if other is candidate:
                    continue
                # Other dominates if it has >= return AND <= drawdown (strict in at least one)
                if (other["return_pct"] >= candidate["return_pct"] and
                    other["drawdown_pct"] <= candidate["drawdown_pct"] and
                    (other["return_pct"] > candidate["return_pct"] or
                     other["drawdown_pct"] < candidate["drawdown_pct"])):
                    is_dominated = True
                    break
            if not is_dominated:
                pareto.append(candidate)

        # Sort by return ascending for frontier traversal
        pareto.sort(key=lambda x: x["return_pct"])
        return pareto if pareto else trials[:1]  # Fallback to best single trial

    def _select_from_frontier(
        self,
        pareto: List[Dict[str, Any]],
        risk_preference: float,
    ) -> Dict[str, Any]:
        """
        Select a point on the Pareto frontier based on risk_preference.

        0.0 = lowest drawdown (conservative)
        1.0 = highest return (aggressive)
        0.5 = best return/drawdown ratio (knee point)
        """
        if len(pareto) == 1:
            return pareto[0]

        if risk_preference <= 0.1:
            # Conservative: lowest drawdown
            return min(pareto, key=lambda x: x["drawdown_pct"])

        if risk_preference >= 0.9:
            # Aggressive: highest return
            return max(pareto, key=lambda x: x["return_pct"])

        # Balanced: find knee point (best return/drawdown ratio)
        # Score each point: higher return is good, higher drawdown is bad
        best = None
        best_score = -float("inf")
        for trial in pareto:
            dd = max(trial["drawdown_pct"], 0.1)  # Avoid division by zero
            # Weight return vs drawdown by risk_preference
            score = (
                risk_preference * trial["return_pct"]
                - (1 - risk_preference) * dd
            )
            if score > best_score:
                best_score = score
                best = trial

        return best

    def _apply_regime_constraints(
        self,
        space: Dict[str, Dict],
        risk_level: str,
    ) -> Dict[str, Dict]:
        """
        Narrow parameter bounds based on market regime risk level.
        Extended from V1 for V2's additional params.
        """
        constraints = V2_REGIME_CONSTRAINTS.get(risk_level, {})
        if not constraints:
            return dict(space)

        constrained = {}
        for param_name, param_def in space.items():
            new_def = dict(param_def)
            if param_name in constraints:
                overrides = constraints[param_name]

                # Handle categorical overrides (replace choices entirely)
                if overrides.get("type") == "categorical" and "choices" in overrides:
                    new_def = dict(overrides)
                else:
                    if "low" in overrides and "low" in new_def:
                        new_def["low"] = max(new_def["low"], overrides["low"])
                    if "high" in overrides and "high" in new_def:
                        new_def["high"] = min(new_def["high"], overrides["high"])
                    # Ensure low <= high
                    if "low" in new_def and "high" in new_def:
                        if new_def["low"] > new_def["high"]:
                            new_def["low"] = new_def["high"]

            constrained[param_name] = new_def

        return constrained
