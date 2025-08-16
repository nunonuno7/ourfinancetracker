from __future__ import annotations

def kpi_progress_percent(actual: float, goal: float, mode: str = "closest") -> int:
    try:
        a = float(actual)
        g = float(goal)
        if g <= 0:
            return 0
    except Exception:
        return 0

    clamp = lambda x: max(0, min(100, int(round(x))))
    if mode == "higher":
        return clamp((a / g) * 100)
    if mode == "lower":
        return clamp(100 - max(0, ((a - g) / g) * 100))
    return clamp((1 - abs(a - g) / g) * 100)
