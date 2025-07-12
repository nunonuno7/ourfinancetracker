
from datetime import datetime
from dateutil.relativedelta import relativedelta

def period_str(dt):
    """Convert datetime to period string YYYY-MM"""
    return dt.strftime("%Y-%m")

def add_one_month(period: str):
    """Add one month to period string"""
    dt = datetime.strptime(period, "%Y-%m")
    return (dt + relativedelta(months=1)).strftime("%Y-%m")
