"""
plot_scaling.py
================

Utility helpers for aligning training-time and deployment-time metrics on a
common y-axis.  Values are min-max scaled into [0,1] using consistent ranges so
that trends remain comparable even if absolute values differ between the
simulator and the testbed.
"""

from __future__ import annotations

from typing import Dict, Tuple


# Default plot ranges for frequently used metrics.  Ratios already bounded in
# [0,1] keep that range; rewards and costs use conservative bounds so they stay
# within the same axis as defence ratios when plotted together.
PLOT_METRIC_RANGES: Dict[str, Tuple[float, float]] = {
    # Training metrics
    "Defense/R_succ": (0.0, 1.0),
    "Defense/S_MTD_overall": (0.0, 1.0),
    "Defense/MTD_Rate": (0.0, 1.0),
    "Episode/Reward_Total": (-150.0, 150.0),
    "Episode/avg_cost": (0.0, 5.0),
    "Episode/avg_raw_reward": (-5.0, 5.0),
    # Deployment/runtime metrics
    "cti_alert_rate": (0.0, 1.0),
    "blacklist_size_ratio": (0.0, 1.0),
    "uptime_ratio": (0.0, 1.0),
    "breach_success_rate": (0.0, 1.0),
    "decoy_lure_rate": (0.0, 1.0),
}


def scale_metric_for_plot(key: str, value: float) -> float:
    """Scale a metric value to [0,1] using the configured bounds."""
    low, high = PLOT_METRIC_RANGES.get(key, (0.0, 1.0))
    if high == low:
        return 0.0
    scaled = (value - low) / (high - low)
    return max(0.0, min(1.0, scaled))


def scale_metrics_for_plot(metrics: Dict[str, float]) -> Dict[str, float]:
    """Return a Plot/ prefixed dict with metrics scaled into [0,1]."""
    scaled = {}
    for k, v in metrics.items():
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        scaled[f"Plot/{k}"] = scale_metric_for_plot(k, val)
    return scaled