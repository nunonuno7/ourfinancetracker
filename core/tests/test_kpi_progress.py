import pytest
from core.utils.kpi_progress import kpi_progress_percent

@pytest.mark.parametrize("actual,goal,mode,expected", [
    (2000, 2500, "closest", 80),
    (2000, 2500, "higher", 80),
    (2000, 1500, "closest", 67),
    (2000, 1500, "lower", 67),
])
def test_progress(actual, goal, mode, expected):
    pct = kpi_progress_percent(actual, goal, mode)
    assert abs(pct - expected) <= 1
