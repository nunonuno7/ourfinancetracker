from __future__ import annotations

"""Helpers for computing KPI progress percentages."""


def kpi_progress_percent(actual: float, goal: float, mode: str = "closest") -> int:
    """Return progress percentage between 0 and 100.

    Parameters
    ----------
    actual: float
        The current value of the KPI.
    goal: float
        The target value for the KPI. If ``goal`` is ``<= 0`` the function
        returns ``0``.
    mode: str
        ``"closest"`` (default) considers distance from the goal symmetrically
        above/below it. ``"higher"`` treats higher values as better, while
        ``"lower"`` treats lower values as better.
    """
    try:
        a = float(actual)
        g = float(goal)
        if g <= 0:
            return 0
    except Exception:
        return 0

    def clamp(x: float) -> int:
        return max(0, min(100, int(round(x))))

    if mode == "higher":
        return clamp((a / g) * 100.0)
    if mode == "lower":
        over = max(0.0, (a - g) / g) * 100.0
        return clamp(100.0 - over)

    # default: closest
    diff_ratio = abs(a - g) / g
    return clamp((1.0 - diff_ratio) * 100.0)
