def kpi_progress_percent(actual: float, goal: float, mode: str = "closest") -> int:
    try:
        a = float(actual)
        g = float(goal)
        if g <= 0:
            return 0
    except Exception:
        return 0

    def clamp(x):
        return max(0, min(100, int(round(x))))

    if mode == "higher":
        return clamp((a / g) * 100)
    if mode == "lower":
        over = max(0.0, (a - g) / g) * 100.0
        return clamp(100.0 - over)

    diff_ratio = abs(a - g) / g
    return clamp((1.0 - diff_ratio) * 100.0)
