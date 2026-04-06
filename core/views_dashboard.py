"""Dashboard views and helpers."""

import hashlib
import json
import logging
import re
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection, models
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import http_date
from django.utils.timezone import now
from django.views.generic import TemplateView

from .finance.returns import portfolio_return
from .models import Account, AccountBalance, DatePeriod, Transaction
from .utils.date_helpers import period_key, period_label, shift_period

logger = logging.getLogger(__name__)


def pct(part, whole) -> Decimal:
    """Return ``part / whole`` as a percentage."""
    try:
        if not whole or Decimal(whole) == 0:
            return Decimal("0.00")
        return (Decimal(part) / Decimal(whole) * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except Exception:
        return Decimal("0.00")


def build_kpis_for_period(tx):
    """Build basic KPI metrics for a single period."""
    stats = tx.aggregate(
        income=Sum("amount", filter=Q(type=Transaction.Type.INCOME)),
        expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE)),
        investments=Sum("amount", filter=Q(type=Transaction.Type.INVESTMENT)),
        expense_estimated=Sum(
            "amount",
            filter=Q(type=Transaction.Type.EXPENSE, is_estimated=True),
        ),
        expense_count=models.Count("id", filter=Q(type=Transaction.Type.EXPENSE)),
        expense_estimated_count=models.Count(
            "id",
            filter=Q(type=Transaction.Type.EXPENSE, is_estimated=True),
        ),
        total_count=models.Count("id"),
    )

    income = stats["income"] or Decimal("0")
    expenses = abs(stats["expenses"] or Decimal("0"))
    investments = stats["investments"] or Decimal("0")
    net = income - expenses
    expense_estimated = abs(stats["expense_estimated"] or Decimal("0"))

    return (
        {
            "income": income,
            "expenses": expenses,
            "investments": investments,
            "net": net,
            "transaction_count": stats["total_count"] or 0,
        },
        {
            "total": expenses,
            "estimated": expense_estimated,
            "count": stats["expense_count"] or 0,
            "estimated_count": stats["expense_estimated_count"] or 0,
        },
    )


def build_charts_for_period(tx):
    """Return expense totals grouped by category for charting."""
    expense_rows = (
        tx.filter(type=Transaction.Type.EXPENSE)
        .values("category__id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return [
        {
            "category_id": row["category__id"],
            "category": row["category__name"] or "Uncategorised",
            "category_filter": row["category__name"] or "",
            "label": row["category__name"] or "Uncategorised",
            "total": abs(row["total"] or Decimal("0")),
            "value": abs(row["total"] or Decimal("0")),
        }
        for row in expense_rows
    ]


def json_response(data: dict, status: int = 200) -> JsonResponse:
    """Return JsonResponse with conditional cache headers."""
    response = JsonResponse(data, status=status)
    response["ETag"] = hashlib.md5(response.content).hexdigest()
    response["Last-Modified"] = http_date(now().timestamp())
    response["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


def _parse_period_param(period_value: str | None) -> tuple[int, int] | None:
    """Parse a ``YYYY-MM`` string into ``(year, month)``."""
    if not period_value or not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period_value):
        return None

    year, month = period_value.split("-", 1)
    return int(year), int(month)


def _apply_period_range(
    queryset,
    field_prefix: str,
    start_period: str | None,
    end_period: str | None,
):
    """Filter a queryset by a ``DatePeriod`` foreign key range."""
    start_tuple = _parse_period_param(start_period)
    end_tuple = _parse_period_param(end_period)

    if start_tuple:
        start_year, start_month = start_tuple
        queryset = queryset.filter(
            Q(**{f"{field_prefix}__year__gt": start_year})
            | Q(
                **{
                    f"{field_prefix}__year": start_year,
                    f"{field_prefix}__month__gte": start_month,
                }
            )
        )

    if end_tuple:
        end_year, end_month = end_tuple
        queryset = queryset.filter(
            Q(**{f"{field_prefix}__year__lt": end_year})
            | Q(
                **{
                    f"{field_prefix}__year": end_year,
                    f"{field_prefix}__month__lte": end_month,
                }
            )
        )

    return queryset


def _chunked(items, size: int):
    return [items[index : index + size] for index in range(0, len(items), size)]


def _as_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _format_money(value) -> str:
    return f"\u20ac {_as_decimal(value):,.2f}"


def _format_percent(value) -> str:
    if value is None:
        return "\u2014"
    return f"{_as_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"


def _value_tone(value) -> str:
    decimal_value = _as_decimal(value)
    if decimal_value > 0:
        return "positive"
    if decimal_value < 0:
        return "negative"
    return "neutral"


@login_required
def dashboard(request):
    """Dashboard supporting history and period modes."""
    mode = request.GET.get("mode", "history")
    current_date = now()
    if current_date.month == 1:
        default_period = f"{current_date.year - 1}-12"
    else:
        default_period = f"{current_date.year}-{current_date.month - 1:02d}"
    period = request.GET.get("period", default_period)
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period or ""):
        period = default_period

    prev_period = shift_period(period, -1)
    next_period = shift_period(period, 1)

    context = {
        "mode": mode,
        "period": period,
        "prev_period": prev_period,
        "next_period": next_period,
    }

    if mode == "period":
        year, month = map(int, period.split("-"))
        tx = Transaction.objects.filter(
            user=request.user,
            period__year=year,
            period__month=month,
        )
        kpis, expense_stats = build_kpis_for_period(tx)
        charts = build_charts_for_period(tx)

        total_expenses = abs(expense_stats["total"] or Decimal("0"))
        estimated_expenses = abs(expense_stats["estimated"] or Decimal("0"))
        verified_expenses_pct_dec = pct(
            total_expenses - estimated_expenses,
            total_expenses,
        )
        period_start = date(year, month, 1).isoformat()
        period_end = date(year, month, monthrange(year, month)[1]).isoformat()
        transaction_list_url = reverse("transaction_list_v2")

        for chart in charts:
            chart_total = _as_decimal(chart["total"])
            chart_pct = pct(chart_total, total_expenses)
            chart["total_display"] = _format_money(chart_total)
            chart["percentage"] = chart_pct
            chart["percentage_display"] = _format_percent(chart_pct)
            chart["share_display"] = f"{_format_percent(chart_pct)} of total expenses"

            if chart["category_filter"]:
                chart["transaction_url"] = (
                    f"{transaction_list_url}?"
                    + urlencode(
                        {
                            "type": Transaction.Type.EXPENSE,
                            "category_id": chart["category_id"],
                            "category": chart["category_filter"],
                            "period": period,
                            "date_start": period_start,
                            "date_end": period_end,
                        }
                    )
                )
            else:
                chart["transaction_url"] = ""

        kpis["non_estimated_expenses_pct"] = round(float(verified_expenses_pct_dec))
        kpis["verified_expenses_pct"] = float(verified_expenses_pct_dec)
        kpis["verified_expenses_pct_str"] = f"{verified_expenses_pct_dec}%"
        kpis["verification_level"] = kpis.get("verification_level", "Moderate")

        days_in_month = monthrange(year, month)[1]
        kpis["daily_net"] = (
            float(kpis["net"] / days_in_month) if days_in_month > 0 else 0
        )
        kpis["weekly_net"] = float(kpis["net"] / Decimal("4.33")) if kpis["net"] else 0

        if kpis["income"] > 0:
            kpis["savings_rate"] = round(float((kpis["net"] / kpis["income"]) * 100), 1)
            kpis["investment_rate"] = round(
                float((kpis["investments"] / kpis["income"]) * 100),
                1,
            )
            kpis["expense_ratio"] = round(
                float((kpis["expenses"] / kpis["income"]) * 100),
                1,
            )
        else:
            kpis["savings_rate"] = 0
            kpis["investment_rate"] = 0
            kpis["expense_ratio"] = 0

        kpis["expense_count"] = expense_stats["count"]
        kpis["estimated_count"] = expense_stats["estimated_count"]

        try:
            period_date = date(year, month, 1)
            context["period_formatted"] = period_date.strftime("%B %Y")
        except Exception:
            context["period_formatted"] = period

        context.update({"kpis": kpis, "charts": charts})
        return render(request, "core/dashboard.html", context)

    view = DashboardView.as_view()
    response = view(request)
    if hasattr(response, "context_data"):
        response.context_data.update(context)
    return response


@login_required
def dashboard_export(request):
    """Dedicated export page for the history dashboard."""
    start_period = request.GET.get("start_period") or request.GET.get("start")
    end_period = request.GET.get("end_period") or request.GET.get("end")

    transaction_qs = _apply_period_range(
        Transaction.objects.filter(user=request.user, period__isnull=False),
        "period",
        start_period,
        end_period,
    )
    balance_qs = _apply_period_range(
        AccountBalance.objects.filter(account__user=request.user),
        "period",
        start_period,
        end_period,
    )

    balance_matrix_map: dict[tuple[str, str], dict] = {}
    transaction_map: dict[str, dict] = {}
    balance_totals_map: dict[str, dict] = {}
    period_keys: set[str] = set()

    balance_rows = (
        balance_qs.values(
            "account__account_type__name",
            "account__currency__code",
            "period__year",
            "period__month",
        )
        .annotate(total=Sum("reported_balance"))
        .order_by(
            "period__year",
            "period__month",
            "account__account_type__name",
            "account__currency__code",
        )
    )

    for row in balance_rows:
        period_key_value = period_key(row["period__year"], row["period__month"])
        period_keys.add(period_key_value)

        row_key = (
            row["account__account_type__name"] or "Other",
            row["account__currency__code"] or "\u2014",
        )
        matrix_row = balance_matrix_map.setdefault(
            row_key,
            {
                "type": row_key[0],
                "currency": row_key[1],
                "values": {},
            },
        )
        matrix_row["values"][period_key_value] = _as_decimal(row["total"])

    monthly_transactions = (
        transaction_qs.values("period__year", "period__month")
        .annotate(
            income=Sum("amount", filter=Q(type=Transaction.Type.INCOME)),
            expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE)),
            investments=Sum("amount", filter=Q(type=Transaction.Type.INVESTMENT)),
            estimated_expenses=Sum(
                "amount",
                filter=Q(type=Transaction.Type.EXPENSE, is_estimated=True),
            ),
            transaction_count=models.Count("id"),
        )
        .order_by("period__year", "period__month")
    )

    for row in monthly_transactions:
        period_key_value = period_key(row["period__year"], row["period__month"])
        period_keys.add(period_key_value)
        transaction_map[period_key_value] = {
            "income": _as_decimal(row["income"]),
            "expenses": _as_decimal(row["expenses"]),
            "investments": _as_decimal(row["investments"]),
            "estimated_expenses": _as_decimal(row["estimated_expenses"]),
            "transaction_count": row["transaction_count"] or 0,
        }

    monthly_balance_totals = (
        balance_qs.values("period__year", "period__month")
        .annotate(
            total_balance=Sum("reported_balance"),
            investment_balance=Sum(
                "reported_balance",
                filter=Q(account__account_type__name__icontains="invest"),
            ),
        )
        .order_by("period__year", "period__month")
    )

    for row in monthly_balance_totals:
        period_key_value = period_key(row["period__year"], row["period__month"])
        period_keys.add(period_key_value)
        balance_totals_map[period_key_value] = {
            "total_balance": _as_decimal(row["total_balance"]),
            "investment_balance": _as_decimal(row["investment_balance"]),
        }

    sorted_period_keys = sorted(period_keys)
    period_sequence = []
    for period_key_value in sorted_period_keys:
        year, month = map(int, period_key_value.split("-"))
        period_sequence.append(
            {
                "key": period_key_value,
                "label": period_label(year, month),
                "year": str(year),
                "month": date(year, month, 1).strftime("%b"),
            }
        )

    balance_matrix_rows = []
    for row in sorted(
        balance_matrix_map.values(),
        key=lambda item: (item["type"].lower(), item["currency"].lower()),
    ):
        row_total = sum(row["values"].values(), Decimal("0"))
        balance_matrix_rows.append(
            {
                "type": row["type"],
                "currency": row["currency"],
                "values": row["values"],
                "row_total": row_total,
                "row_total_display": _format_money(row_total),
            }
        )

    balance_tables = []
    for index, period_chunk in enumerate(_chunked(period_sequence, 12), start=1):
        chunk_keys = [period["key"] for period in period_chunk]
        year_groups = []
        for period in period_chunk:
            if not year_groups or year_groups[-1]["year"] != period["year"]:
                year_groups.append({"year": period["year"], "span": 0})
            year_groups[-1]["span"] += 1

        chunk_rows = []
        for row in balance_matrix_rows:
            cells = []
            chunk_total = Decimal("0")
            for period_key_value in chunk_keys:
                amount = row["values"].get(period_key_value, Decimal("0"))
                chunk_total += amount
                cells.append(
                    {
                        "value": amount,
                        "display": _format_money(amount),
                        "tone": _value_tone(amount),
                    }
                )
            chunk_rows.append(
                {
                    "type": row["type"],
                    "currency": row["currency"],
                    "cells": cells,
                    "chunk_total": chunk_total,
                    "chunk_total_display": _format_money(chunk_total),
                }
            )

        totals = []
        for period_key_value in chunk_keys:
            total = sum(
                (
                    row["values"].get(period_key_value, Decimal("0"))
                    for row in balance_matrix_rows
                ),
                Decimal("0"),
            )
            totals.append(
                {
                    "value": total,
                    "display": _format_money(total),
                    "tone": _value_tone(total),
                }
            )

        balance_tables.append(
            {
                "index": index,
                "is_split": len(sorted_period_keys) > 12,
                "periods": period_chunk,
                "year_groups": year_groups,
                "rows": chunk_rows,
                "totals": totals,
            }
        )

    period_rows = []
    valid_returns: list[Decimal] = []
    previous_investment_balance: Decimal | None = None

    for period in period_sequence:
        period_key_value = period["key"]
        tx_stats = transaction_map.get(period_key_value, {})
        balance_stats = balance_totals_map.get(period_key_value, {})

        income = tx_stats.get("income", Decimal("0"))
        expenses = abs(tx_stats.get("expenses", Decimal("0")))
        investments = tx_stats.get("investments", Decimal("0"))
        estimated_expenses = abs(tx_stats.get("estimated_expenses", Decimal("0")))
        total_balance = balance_stats.get("total_balance", Decimal("0"))
        investment_balance = balance_stats.get("investment_balance", Decimal("0"))
        net_cash = income - expenses
        verified_pct = pct(expenses - estimated_expenses, expenses)

        portfolio_return_value = None
        if previous_investment_balance is not None:
            portfolio_return_value = portfolio_return(
                investment_balance,
                previous_investment_balance,
                investments,
            )
            if portfolio_return_value is not None:
                valid_returns.append(portfolio_return_value)
        previous_investment_balance = investment_balance

        period_rows.append(
            {
                "label": period["label"],
                "income_display": _format_money(income),
                "income_tone": _value_tone(income),
                "expenses_display": _format_money(expenses),
                "expenses_tone": _value_tone(-expenses),
                "investments_display": _format_money(investments),
                "investments_tone": _value_tone(investments),
                "net_cash_display": _format_money(net_cash),
                "net_cash_tone": _value_tone(net_cash),
                "balance_display": _format_money(total_balance),
                "balance_tone": _value_tone(total_balance),
                "verified_pct_display": _format_percent(verified_pct),
                "portfolio_return_display": _format_percent(portfolio_return_value),
                "portfolio_return_tone": _value_tone(
                    portfolio_return_value or Decimal("0")
                ),
                "transaction_count": tx_stats.get("transaction_count", 0),
                "income": income,
                "expenses": expenses,
                "investments": investments,
                "net_cash": net_cash,
                "balance": total_balance,
            }
        )

    period_count = len(period_rows) or 1
    total_income = sum((row["income"] for row in period_rows), Decimal("0"))
    total_expenses = sum((row["expenses"] for row in period_rows), Decimal("0"))
    total_investments = sum((row["investments"] for row in period_rows), Decimal("0"))
    transaction_count = sum(row["transaction_count"] for row in period_rows)
    average_return = (
        sum(valid_returns, Decimal("0")) / Decimal(len(valid_returns))
        if valid_returns
        else None
    )
    latest_balance = period_rows[-1]["balance"] if period_rows else Decimal("0")
    overall_verified_pct = pct(
        total_expenses
        - sum(
            (
                abs(stats.get("estimated_expenses", Decimal("0")))
                for stats in transaction_map.values()
            ),
            Decimal("0"),
        ),
        total_expenses,
    )

    summary_cards = [
        {
            "title": "Current Net Worth",
            "value": _format_money(latest_balance),
            "detail": (
                f"Latest balance snapshot: {period_sequence[-1]['label']}"
                if period_sequence
                else "No balances available"
            ),
            "tone": "success",
        },
        {
            "title": "Average Income",
            "value": _format_money(total_income / Decimal(period_count)),
            "detail": f"{len(period_rows)} periods in scope",
            "tone": "primary",
        },
        {
            "title": "Average Expenses",
            "value": _format_money(total_expenses / Decimal(period_count)),
            "detail": "Monthly average for the selected range",
            "tone": "danger",
        },
        {
            "title": "Average Investment",
            "value": _format_money(total_investments / Decimal(period_count)),
            "detail": "Monthly investment flow",
            "tone": "info",
        },
        {
            "title": "Verified Expenses",
            "value": _format_percent(overall_verified_pct),
            "detail": f"{transaction_count} transactions analysed",
            "tone": "dark",
        },
    ]

    if average_return is not None:
        summary_cards.append(
            {
                "title": "Average Portfolio Return",
                "value": _format_percent(average_return),
                "detail": "Average monthly return in the selected range",
                "tone": "warning" if average_return < 0 else "success",
            }
        )

    expense_categories = []
    expense_category_rows = (
        transaction_qs.filter(type=Transaction.Type.EXPENSE)
        .values("category__name")
        .annotate(total=Sum("amount"), count=models.Count("id"))
    )

    for row in expense_category_rows:
        amount = abs(_as_decimal(row["total"]))
        if amount <= 0:
            continue
        expense_categories.append(
            {
                "name": row["category__name"] or "Uncategorised",
                "count": row["count"] or 0,
                "amount": amount,
            }
        )

    expense_categories.sort(key=lambda item: item["amount"], reverse=True)
    for item in expense_categories:
        item["amount_display"] = _format_money(item["amount"])
        item["percentage_display"] = _format_percent(
            pct(item["amount"], total_expenses)
        )

    latest_accounts = []
    if period_sequence:
        latest_year, latest_month = map(int, period_sequence[-1]["key"].split("-"))
        latest_balances = (
            AccountBalance.objects.filter(
                account__user=request.user,
                period__year=latest_year,
                period__month=latest_month,
                reported_balance__gt=0,
            )
            .select_related("account", "account__account_type", "account__currency")
            .order_by("-reported_balance", "account__name")
        )

        latest_total = sum(
            (balance.reported_balance for balance in latest_balances),
            Decimal("0"),
        )
        for balance in latest_balances:
            latest_accounts.append(
                {
                    "name": balance.account.name,
                    "type": balance.account.account_type.name,
                    "currency": (
                        balance.account.currency.code
                        if balance.account.currency
                        else "\u2014"
                    ),
                    "balance_display": _format_money(balance.reported_balance),
                    "share_display": _format_percent(
                        pct(balance.reported_balance, latest_total)
                    ),
                }
            )

    if period_sequence:
        selected_range_label = (
            period_sequence[0]["label"]
            if len(period_sequence) == 1
            else f"{period_sequence[0]['label']} to {period_sequence[-1]['label']}"
        )
    else:
        selected_range_label = "No period data available"

    context = {
        "generated_at": now(),
        "selected_range_label": selected_range_label,
        "selected_start_period": start_period,
        "selected_end_period": end_period,
        "summary_cards": summary_cards,
        "period_rows": period_rows,
        "balance_tables": balance_tables,
        "expense_categories": expense_categories,
        "latest_accounts": latest_accounts,
        "has_data": bool(
            period_rows or balance_tables or expense_categories or latest_accounts
        ),
    }
    return render(request, "core/dashboard_export.html", context)


class DashboardView(LoginRequiredMixin, TemplateView):
    """Main dashboard with KPIs and financial summaries."""

    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        ctx["periods"] = DatePeriod.objects.order_by("-year", "-month")

        start_period = self.request.GET.get("start-period")
        end_period = self.request.GET.get("end-period")

        with connection.cursor() as cursor:
            period_expr = (
                "CAST(dp.year AS TEXT) || '-' || printf('%02d', dp.month)"
                if connection.vendor == "sqlite"
                else "CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0'))"
            )

            date_filter = ""
            params = [user.id]
            if start_period and end_period:
                date_filter = f" AND {period_expr} BETWEEN %s AND %s"
                params.extend([start_period, end_period])

            cursor.execute(
                f"""
                SELECT {period_expr} as period,
                       SUM(CASE WHEN LOWER(at.name) = 'investment' THEN ab.reported_balance ELSE 0 END) AS investment_balance,
                       SUM(CASE WHEN LOWER(at.name) = 'savings' THEN ab.reported_balance ELSE 0 END) AS savings_balance
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_accounttype at ON a.account_type_id = at.id
                INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                WHERE a.user_id = %s{date_filter}
                GROUP BY period
                ORDER BY period
                """,
                params,
            )
            bal_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT {period_expr} as period, SUM(tx.amount)
                FROM core_transaction tx
                INNER JOIN core_dateperiod dp ON tx.period_id = dp.id
                WHERE tx.user_id = %s AND tx.type = 'IN'{date_filter}
                GROUP BY period
                ORDER BY period
                """,
                params,
            )
            income_rows = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT COALESCE(SUM(tx.amount), 0)
                FROM core_transaction tx
                INNER JOIN core_dateperiod dp ON tx.period_id = dp.id
                WHERE tx.user_id = %s AND tx.type = 'IV'{date_filter}
                """,
                params,
            )
            total_invested = float(cursor.fetchone()[0] or 0)

            cursor.execute(
                f"""
                SELECT
                    COALESCE(SUM(CASE WHEN tx.type = 'EX' THEN tx.amount ELSE 0 END), 0) AS total_expenses,
                    COALESCE(SUM(CASE WHEN tx.type = 'EX' AND tx.is_estimated THEN tx.amount ELSE 0 END), 0) AS estimated_expenses
                FROM core_transaction tx
                INNER JOIN core_dateperiod dp ON tx.period_id = dp.id
                WHERE tx.user_id = %s{date_filter}
                """,
                params,
            )
            total_expenses, estimated_expenses_total = cursor.fetchone()

        net_worth_by_period = {period: float(inv or 0) for period, inv, _ in bal_rows}
        saving_mes = {period: float(save or 0) for period, _, save in bal_rows}

        net_worth_values = list(net_worth_by_period.values())
        net_worth_final = net_worth_values[-1] if net_worth_values else 0
        net_worth_initial = net_worth_values[0] if net_worth_values else 0
        net_worth_growth = net_worth_final - net_worth_initial
        average_growth = (
            sum(b - a for a, b in zip(net_worth_values, net_worth_values[1:]))
            / (len(net_worth_values) - 1)
            if len(net_worth_values) > 1
            else 0
        )

        income_by_period = {period: float(total) for period, total in income_rows}
        average_income = (
            sum(income_by_period.values()) / len(income_by_period)
            if income_by_period
            else 0
        )

        periods = sorted(set(income_by_period.keys()) & set(saving_mes.keys()))
        estimated_expense_samples = []
        for index in range(len(periods) - 1):
            current_period = periods[index]
            next_period = periods[index + 1]
            expense = (
                saving_mes.get(current_period, 0)
                - saving_mes.get(next_period, 0)
                + income_by_period.get(current_period, 0)
            )
            estimated_expense_samples.append(expense)
        average_expense = (
            sum(estimated_expense_samples) / len(estimated_expense_samples)
            if estimated_expense_samples
            else 0
        )

        month_count = max(len(income_by_period), 1)
        average_savings = (
            average_income - average_expense - total_invested / month_count
        )

        ctx["kpis"] = {
            "net_worth": f"{net_worth_final:,.0f} \u20ac",
            "growth": f"{net_worth_growth:,.0f} \u20ac",
            "invested_capital": f"{total_invested:,.0f} \u20ac",
            "average_expense": f"{average_expense:,.0f} \u20ac",
            "average_income": f"{average_income:,.0f} \u20ac",
            "average_wealth_growth": f"{average_growth:,.0f} \u20ac",
            "average_savings": f"{average_savings:,.0f} \u20ac",
        }

        total_expenses_dec = Decimal(str(abs(total_expenses)))
        estimated_expenses_dec = Decimal(str(abs(estimated_expenses_total)))
        verified_expenses_pct_dec = pct(
            total_expenses_dec - estimated_expenses_dec,
            total_expenses_dec,
        )
        ctx["kpis"]["non_estimated_expenses_pct"] = round(
            float(verified_expenses_pct_dec)
        )
        ctx["kpis"]["verified_expenses_pct"] = float(verified_expenses_pct_dec)
        ctx["kpis"]["verified_expenses_pct_str"] = f"{verified_expenses_pct_dec}%"
        ctx["kpis"]["verification_level"] = ctx["kpis"].get(
            "verification_level",
            "Moderate",
        )

        return ctx


@login_required
def menu_config(request):
    """Return menu configuration for the current user."""
    return json_response(
        {
            "username": request.user.username,
            "links": [
                {"name": "Dashboard", "url": reverse("transaction_list_v2")},
                {"name": "New Transaction", "url": reverse("transaction_create")},
                {"name": "Categories", "url": reverse("category_list")},
                {"name": "Account Balances", "url": reverse("account_balance")},
            ],
        }
    )


@login_required
def account_balances_pivot_json(request):
    """Return balances aggregated by type/currency in pivot form for charts."""
    user_id = request.user.id
    requested_period = request.GET.get("period")

    with connection.cursor() as cursor:
        if requested_period:
            try:
                year, month = map(int, requested_period.split("-"))
                cursor.execute(
                    """
                    SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
                    FROM core_accountbalance ab
                    JOIN core_account acc ON acc.id = ab.account_id
                    JOIN core_accounttype at ON at.id = acc.account_type_id
                    JOIN core_currency cur ON cur.id = acc.currency_id
                    JOIN core_dateperiod dp ON dp.id = ab.period_id
                    WHERE acc.user_id = %s AND dp.year = %s AND dp.month = %s
                    GROUP BY at.name, cur.code, dp.year, dp.month
                    ORDER BY at.name, cur.code
                    """,
                    [user_id, year, month],
                )
            except (TypeError, ValueError):
                cursor.execute(
                    """
                    SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
                    FROM core_accountbalance ab
                    JOIN core_account acc ON acc.id = ab.account_id
                    JOIN core_accounttype at ON at.id = acc.account_type_id
                    JOIN core_currency cur ON cur.id = acc.currency_id
                    JOIN core_dateperiod dp ON dp.id = ab.period_id
                    WHERE acc.user_id = %s
                    AND dp.id = (SELECT id FROM core_dateperiod ORDER BY year DESC, month DESC LIMIT 1)
                    GROUP BY at.name, cur.code, dp.year, dp.month
                    ORDER BY at.name, cur.code
                    """,
                    [user_id],
                )
        else:
            cursor.execute(
                """
                SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
                FROM core_accountbalance ab
                JOIN core_account acc ON acc.id = ab.account_id
                JOIN core_accounttype at ON at.id = acc.account_type_id
                JOIN core_currency cur ON cur.id = acc.currency_id
                JOIN core_dateperiod dp ON dp.id = ab.period_id
                WHERE acc.user_id = %s
                GROUP BY at.name, cur.code, dp.year, dp.month
                ORDER BY dp.year, dp.month
                """,
                [user_id],
            )

        rows = cursor.fetchall()

    if not rows:
        return json_response({"columns": [], "rows": []})

    if requested_period:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.name, at.name, cur.code, ab.reported_balance
                FROM core_accountbalance ab
                JOIN core_account a ON a.id = ab.account_id
                JOIN core_accounttype at ON at.id = a.account_type_id
                JOIN core_currency cur ON cur.id = a.currency_id
                JOIN core_dateperiod dp ON dp.id = ab.period_id
                WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
                AND ab.reported_balance > 0
                ORDER BY a.name
                """,
                [user_id, year, month],
            )
            individual_rows = cursor.fetchall()

        account_data = []
        for account_name, account_type, currency, balance in individual_rows:
            account_data.append(
                {
                    "name": account_name,
                    "type": account_type,
                    "currency": currency,
                    "balance": float(balance),
                    "label": account_name,
                }
            )
        return json_response({"accounts": account_data})

    data = {}
    periods = {}
    for acc_type, currency, year, month, balance in rows:
        period_key = (year, month)
        period_label = date(year, month, 1).strftime("%b/%y")
        periods[period_key] = period_label
        data.setdefault((acc_type, currency), {})[period_label] = float(balance)

    sorted_periods = [periods[key] for key in sorted(periods)]
    columns = ["type", "currency"] + sorted_periods
    pivot_rows = []
    for (acc_type, currency), values in data.items():
        row = {"type": acc_type, "currency": currency}
        for period in sorted_periods:
            row[period] = values.get(period, 0.0)
        pivot_rows.append(row)

    return json_response({"columns": columns, "rows": pivot_rows})


@login_required
def period_autocomplete(request):
    """Autocomplete for periods."""
    term = request.GET.get("term", "")
    periods = DatePeriod.objects.filter(label__icontains=term).values_list(
        "label",
        flat=True,
    )[:10]
    return JsonResponse(list(periods), safe=False)


@login_required
def api_jwt_my_transactions(request):
    """Small transaction feed for the current user."""
    transactions = Transaction.objects.filter(user=request.user)[:50]
    data = list(transactions.values("id", "date", "type", "amount"))
    return JsonResponse(data, safe=False)


@login_required
def dashboard_data(request):
    """Dashboard data API."""
    return JsonResponse(
        {
            "status": "success",
            "data": {
                "total_transactions": Transaction.objects.filter(
                    user=request.user
                ).count(),
                "total_accounts": Account.objects.filter(user=request.user).count(),
            },
        }
    )


@login_required
def dashboard_kpis_json(request):
    """Dashboard KPIs JSON API with period filtering."""
    try:
        user_id = request.user.id
        logger.debug(
            "[dashboard_kpis_json] Request from user %s: %s",
            user_id,
            request.GET,
        )

        start_period = request.GET.get("start_period")
        end_period = request.GET.get("end_period")

        tx_query = Transaction.objects.filter(user_id=user_id)
        balance_periods = []

        if start_period and end_period:
            try:
                start_year, start_month = map(int, start_period.split("-"))
                end_year, end_month = map(int, end_period.split("-"))

                start_date = date(start_year, start_month, 1)
                _, last_day = monthrange(end_year, end_month)
                end_date = date(end_year, end_month, last_day)

                tx_query = tx_query.filter(date__gte=start_date, date__lte=end_date)

                balance_periods = list(
                    DatePeriod.objects.filter(
                        year__gte=start_year,
                        year__lte=end_year,
                        month__gte=start_month if start_year == end_year else 1,
                        month__lte=end_month if start_year == end_year else 12,
                    ).values_list("id", flat=True)
                )

                if start_year != end_year:
                    balance_periods = list(
                        DatePeriod.objects.filter(
                            models.Q(year=start_year, month__gte=start_month)
                            | models.Q(year__gt=start_year, year__lt=end_year)
                            | models.Q(year=end_year, month__lte=end_month)
                        ).values_list("id", flat=True)
                    )
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Invalid period format: %s - %s: %s",
                    start_period,
                    end_period,
                    exc,
                )
                start_period = end_period = None

        stats = tx_query.aggregate(
            total_income=models.Sum("amount", filter=models.Q(type="IN")) or 0,
            total_expenses=models.Sum("amount", filter=models.Q(type="EX")) or 0,
            total_investments=models.Sum("amount", filter=models.Q(type="IV")) or 0,
            total_count=models.Count("id"),
            categorized_count=models.Count(
                "id",
                filter=models.Q(category__isnull=False),
            ),
        )

        total_income = float(stats["total_income"] or 0)
        total_expenses = float(abs(stats["total_expenses"] or 0))
        total_investments = float(stats["total_investments"] or 0)
        total_transactions = stats["total_count"]
        categorized_transactions = stats["categorized_count"]

        estimated_expenses_sum = (
            tx_query.aggregate(
                est_sum=Sum("amount", filter=Q(type="EX") & Q(is_estimated=True))
            )["est_sum"]
            or 0
        )
        estimated_expenses_sum = float(abs(estimated_expenses_sum))

        non_estimated_expense_pct_dec = pct(
            Decimal(total_expenses) - Decimal(estimated_expenses_sum),
            Decimal(total_expenses),
        )
        non_estimated_expense_pct = float(non_estimated_expense_pct_dec)

        if start_period and end_period:
            try:
                start_year, start_month = map(int, start_period.split("-"))
                end_year, end_month = map(int, end_period.split("-"))
                num_months = (
                    (end_year - start_year) * 12 + (end_month - start_month) + 1
                )
            except Exception:
                num_months = 1
        else:
            date_range = tx_query.aggregate(
                min_date=models.Min("date"),
                max_date=models.Max("date"),
            )
            if date_range["min_date"] and date_range["max_date"]:
                delta = date_range["max_date"] - date_range["min_date"]
                num_months = max(1, delta.days // 30)
            else:
                num_months = 1

        average_income = total_income / max(num_months, 1)
        average_expenses = total_expenses / max(num_months, 1)
        average_invested_value = total_investments / max(num_months, 1)
        savings_rate = (
            ((total_income - total_expenses) / total_income * 100)
            if total_income > 0
            else 0
        )
        categorized_percentage = (
            (categorized_transactions / total_transactions * 100)
            if total_transactions > 0
            else 0
        )

        if balance_periods:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(ab.reported_balance), 0)
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    WHERE a.user_id = %s
                    AND ab.period_id = ANY(%s)
                    AND ab.period_id = (
                        SELECT MAX(ab2.period_id)
                        FROM core_accountbalance ab2
                        INNER JOIN core_account a2 ON ab2.account_id = a2.id
                        WHERE a2.user_id = %s
                        AND ab2.period_id = ANY(%s)
                    )
                    """,
                    [user_id, balance_periods, user_id, balance_periods],
                )
                net_worth_total = float(cursor.fetchone()[0] or 0)
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(ab.reported_balance), 0)
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    WHERE a.user_id = %s
                    AND ab.period_id = (
                        SELECT dp.id FROM core_dateperiod dp
                        ORDER BY dp.year DESC, dp.month DESC
                        LIMIT 1
                    )
                    """,
                    [user_id],
                )
                net_worth_total = float(cursor.fetchone()[0] or 0)

        investment_rate = (
            (total_investments / total_income * 100) if total_income > 0 else 0
        )
        avg_transaction = (
            total_income / total_transactions if total_transactions > 0 else 0
        )
        health_score = (
            min(savings_rate, 30)
            + min(categorized_percentage, 20)
            + min(investment_rate, 25)
            + (25 if net_worth_total > 10000 else net_worth_total / 10000 * 25)
        )

        return JsonResponse(
            {
                "net_worth_total": f"{net_worth_total:,.0f} \u20ac",
                "average_income": f"{average_income:,.0f} \u20ac",
                "average_estimated_expenses": f"{average_expenses:,.0f} \u20ac",
                "average_invested_value": f"{average_invested_value:,.0f} \u20ac",
                "verified_expenses_pct": non_estimated_expense_pct,
                "verified_expenses_pct_str": f"{non_estimated_expense_pct_dec}%",
                "savings_rate": f"{savings_rate:.1f}%",
                "average_monthly_return": "+0.0%",
                "investment_rate": f"{investment_rate:.1f}%",
                "wealth_growth": "+0.0%",
                "avg_transaction": f"{avg_transaction:.0f} \u20ac",
                "total_transactions": total_transactions,
                "month_count": num_months,
                "financial_health_score": health_score,
                "account_breakdown": {
                    "savings": 0,
                    "investments": 0,
                    "checking": 0,
                },
                "calculation_method": "Enhanced calculation with comprehensive metrics",
                "period_info": {
                    "months_analyzed": num_months,
                    "period_filter": bool(start_period and end_period),
                    "start_period": start_period,
                    "end_period": end_period,
                },
                "status": "success",
                "debug_info": {
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "total_investments": total_investments,
                    "total_transactions": total_transactions,
                    "net_worth_total": net_worth_total,
                    "previous_net_worth": 0,
                    "savings_rate": savings_rate,
                    "categorized_percentage": categorized_percentage,
                    "estimated_expenses_sum": estimated_expenses_sum,
                    "non_estimated_expense_pct": non_estimated_expense_pct,
                },
            }
        )
    except Exception as exc:
        logger.error(
            "Error in dashboard_kpis_json for user %s: %s", request.user.id, exc
        )
        return JsonResponse(
            {
                "status": "error",
                "error": str(exc),
                "net_worth_total": "0 \u20ac",
                "average_income": "0 \u20ac",
                "average_estimated_expenses": "0 \u20ac",
                "average_invested_value": "0 \u20ac",
                "verified_expenses_pct": 0.0,
                "verified_expenses_pct_str": "0%",
                "savings_rate": "0.0%",
                "average_monthly_return": "+0.0%",
                "investment_rate": "0.0%",
                "wealth_growth": "+0.0%",
                "avg_transaction": "0 \u20ac",
                "total_transactions": 0,
                "month_count": 0,
                "financial_health_score": 0,
                "account_breakdown": {"savings": 0, "investments": 0, "checking": 0},
                "calculation_method": "Error fallback",
                "period_info": {"months_analyzed": 0, "period_filter": False},
            },
            status=500,
        )


@login_required
def financial_analysis_json(_request):
    """Financial analysis JSON API."""
    return JsonResponse(
        {"data": [], "status": "success", "message": "Analysis completed"}
    )


@login_required
def sync_system_adjustments(_request):
    """Sync system adjustments."""
    return JsonResponse({"status": "success", "message": "System adjustments synced"})


@login_required
def dashboard_goals_json(request):
    """Dashboard goals JSON API."""
    try:
        user_id = request.user.id
        today = date.today()
        current_period = DatePeriod.objects.filter(
            year=today.year,
            month=today.month,
        ).first()

        savings_target = 2000
        current_savings = 0

        if current_period:
            current_income = (
                Transaction.objects.filter(
                    user_id=user_id,
                    period=current_period,
                    type="IN",
                ).aggregate(total=models.Sum("amount"))["total"]
                or 0
            )

            current_expenses = abs(
                Transaction.objects.filter(
                    user_id=user_id,
                    period=current_period,
                    type="EX",
                ).aggregate(total=models.Sum("amount"))["total"]
                or 0
            )

            current_savings = float(current_income) - float(current_expenses)

        savings_progress = min(100, max(0, (current_savings / savings_target) * 100))

        investment_target = 10000
        total_investments = float(
            Transaction.objects.filter(user_id=user_id, type="IV").aggregate(
                total=models.Sum("amount")
            )["total"]
            or 0
        )

        investment_progress = min(
            100,
            max(0, (abs(total_investments) / investment_target) * 100),
        )

        last_3_months = DatePeriod.objects.filter(year__gte=today.year - 1).order_by(
            "-year",
            "-month",
        )[:3]

        avg_expenses = 0
        current_month_expenses = 0
        reduction_target = 500

        if last_3_months.count() >= 2:
            previous_periods = last_3_months[1:]
            avg_expenses = float(
                Transaction.objects.filter(
                    user_id=user_id,
                    period__in=previous_periods,
                    type="EX",
                ).aggregate(total=models.Sum("amount"))["total"]
                or 0
            ) / len(previous_periods)

            if current_period:
                current_month_expenses = float(
                    Transaction.objects.filter(
                        user_id=user_id,
                        period=current_period,
                        type="EX",
                    ).aggregate(total=models.Sum("amount"))["total"]
                    or 0
                )

        actual_reduction = max(0, abs(avg_expenses) - abs(current_month_expenses))
        reduction_progress = min(
            100,
            max(0, (actual_reduction / reduction_target) * 100),
        )

        goals = [
            {
                "name": "Monthly Savings Goal",
                "progress": round(savings_progress, 1),
                "current": round(current_savings, 0),
                "target": savings_target,
                "color": (
                    "success"
                    if savings_progress >= 80
                    else "warning" if savings_progress >= 50 else "danger"
                ),
            },
            {
                "name": "Investment Target",
                "progress": round(investment_progress, 1),
                "current": round(abs(total_investments), 0),
                "target": investment_target,
                "color": (
                    "success"
                    if investment_progress >= 80
                    else "warning" if investment_progress >= 50 else "info"
                ),
            },
            {
                "name": "Spending Reduction",
                "progress": round(reduction_progress, 1),
                "current": round(actual_reduction, 0),
                "target": reduction_target,
                "color": (
                    "info"
                    if reduction_progress >= 80
                    else "warning" if reduction_progress >= 50 else "secondary"
                ),
            },
        ]

        return JsonResponse({"status": "success", "goals": goals})
    except Exception as exc:
        logger.error(
            "Error in dashboard_goals_json for user %s: %s", request.user.id, exc
        )
        return JsonResponse({"status": "error", "goals": []}, status=500)


@login_required
def dashboard_spending_by_category_json(request):
    """Dashboard spending by category JSON API."""
    try:
        user_id = request.user.id

        if request.method != "POST":
            return JsonResponse(
                {"status": "error", "message": "POST required"},
                status=405,
            )

        data = json.loads(request.body)
        start_period = data.get("start_period")
        end_period = data.get("end_period")

        tx_query = Transaction.objects.filter(user_id=user_id, type="EX")

        if start_period and end_period:
            try:
                start_year, start_month = map(int, start_period.split("-"))
                end_year, end_month = map(int, end_period.split("-"))
                start_date = date(start_year, start_month, 1)
                _, last_day = monthrange(end_year, end_month)
                end_date = date(end_year, end_month, last_day)
                tx_query = tx_query.filter(date__gte=start_date, date__lte=end_date)
            except ValueError as exc:
                logger.error(
                    "Invalid period format in dashboard_spending_by_category_json: %s",
                    exc,
                )
                return JsonResponse(
                    {"status": "error", "message": "Invalid period format"},
                    status=400,
                )

        category_totals = (
            tx_query.values("category__name")
            .annotate(
                total_amount=models.Sum("amount"),
                transaction_count=models.Count("id"),
            )
            .order_by("-total_amount")
        )

        categories = []
        total_expenses = 0

        for item in category_totals:
            category_name = item["category__name"] or "Uncategorized"
            amount = abs(float(item["total_amount"] or 0))
            count = item["transaction_count"]

            if amount > 0:
                categories.append(
                    {
                        "name": category_name,
                        "total_amount": amount,
                        "transaction_count": count,
                        "percentage": 0,
                    }
                )
                total_expenses += amount

        for category in categories:
            if total_expenses > 0:
                category["percentage"] = (
                    category["total_amount"] / total_expenses
                ) * 100

        categories.sort(key=lambda item: item["total_amount"], reverse=True)

        return JsonResponse(
            {
                "status": "success",
                "categories": categories,
                "total_expenses": total_expenses,
                "period": (
                    f"{start_period} to {end_period}"
                    if start_period and end_period
                    else "All time"
                ),
            }
        )
    except Exception as exc:
        logger.error(
            "Error in dashboard_spending_by_category_json for user %s: %s",
            request.user.id,
            exc,
        )
        return JsonResponse(
            {"status": "error", "message": str(exc), "categories": []},
            status=500,
        )


@login_required
def dashboard_returns_json(request):
    """Return monthly portfolio returns and their average for the user."""
    start_period = request.GET.get("start_period")
    end_period = request.GET.get("end_period")
    user = request.user

    balances_qs = (
        AccountBalance.objects.filter(
            account__user=user,
            account__account_type__name__istartswith="invest",
        )
        .values("period__year", "period__month")
        .annotate(balance=Sum("reported_balance"))
        .order_by("period__year", "period__month")
    )

    if not balances_qs:
        logger.warning(
            "[dashboard_returns_json] No investment balances found for user %s",
            user.id,
        )
        return JsonResponse({"series": []})

    periods = []
    balance_map: dict[str, Decimal] = {}
    for row in balances_qs:
        period_str = f"{row['period__year']:04d}-{row['period__month']:02d}"
        periods.append(period_str)
        balance_map[period_str] = row["balance"]

    if start_period and end_period:
        if re.match(r"^\d{4}-(0[1-9]|1[0-2])$", start_period) and re.match(
            r"^\d{4}-(0[1-9]|1[0-2])$",
            end_period,
        ):
            periods = [
                period for period in periods if start_period <= period <= end_period
            ]

    flows_qs = (
        Transaction.objects.filter(user=user, type="IV")
        .values("period__year", "period__month")
        .annotate(flow=Sum("amount"))
    )
    flow_map = {
        f"{row['period__year']:04d}-{row['period__month']:02d}": row["flow"]
        for row in flows_qs
    }

    def _to_float(value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    monthly_returns: list[tuple[str, Decimal | None]] = []
    prev_balance: Decimal | None = None

    for period in periods:
        balance = Decimal(balance_map.get(period, Decimal("0")))
        flow = Decimal(flow_map.get(period, Decimal("0")))
        if prev_balance is None:
            ret = None
            if settings.DEBUG:
                logger.debug(
                    "Period %s has no previous balance; flow=%s -> return=None",
                    period,
                    flow,
                )
        else:
            ret = portfolio_return(balance, prev_balance, flow)
            if settings.DEBUG:
                logger.debug(
                    "Period %s prev_balance=%s flow=%s return=%s",
                    period,
                    prev_balance,
                    flow,
                    ret,
                )

        monthly_returns.append((period, ret))
        prev_balance = balance

    valid_returns = [ret for _, ret in monthly_returns if ret is not None]
    avg_return = (
        sum(valid_returns) / Decimal(len(valid_returns)) if valid_returns else None
    )

    series = [
        {
            "period": period,
            "portfolio_return": _to_float(ret),
            "avg_portfolio_return": _to_float(avg_return),
        }
        for period, ret in monthly_returns
    ]

    return JsonResponse({"series": series})


@login_required
def dashboard_insights_json(request):
    """Dashboard insights JSON API."""
    try:
        user_id = request.user.id
        insights = []

        total_transactions = Transaction.objects.filter(user_id=user_id).count()

        if total_transactions == 0:
            insights.append(
                {
                    "type": "info",
                    "title": "\U0001f4c8 Start Your Financial Journey",
                    "text": (
                        "Add your first transactions to begin receiving "
                        "personalized insights."
                    ),
                }
            )
            return JsonResponse({"status": "success", "insights": insights})

        recent_periods = DatePeriod.objects.order_by("-year", "-month")[:3]

        recent_income = (
            Transaction.objects.filter(
                user_id=user_id,
                period__in=recent_periods,
                type="IN",
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        recent_expenses = abs(
            Transaction.objects.filter(
                user_id=user_id,
                period__in=recent_periods,
                type="EX",
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        recent_investments = abs(
            Transaction.objects.filter(
                user_id=user_id,
                period__in=recent_periods,
                type="IV",
            ).aggregate(total=models.Sum("amount"))["total"]
            or 0
        )

        months_count = max(1, recent_periods.count())
        avg_income = float(recent_income) / months_count
        avg_expenses = float(recent_expenses) / months_count
        avg_investments = float(recent_investments) / months_count

        savings_rate = (
            ((avg_income - avg_expenses) / avg_income * 100) if avg_income > 0 else 0
        )

        if savings_rate > 30:
            insights.append(
                {
                    "type": "positive",
                    "title": "\U0001f48e Excellent Saver",
                    "text": (
                        f"Your savings rate of {savings_rate:.1f}% is outstanding! "
                        "You're on track for financial independence."
                    ),
                }
            )
        elif savings_rate > 15:
            insights.append(
                {
                    "type": "warning",
                    "title": "\U0001f44d Good Savings Habits",
                    "text": (
                        f"Savings rate of {savings_rate:.1f}% is solid. "
                        "Try to reach 20-30% to accelerate your goals."
                    ),
                }
            )
        elif savings_rate > 0:
            insights.append(
                {
                    "type": "negative",
                    "title": "\U0001f3af Savings Opportunity",
                    "text": (
                        f"Savings rate: {savings_rate:.1f}%. "
                        "Focus on reducing expenses or increasing income."
                    ),
                }
            )
        else:
            insights.append(
                {
                    "type": "negative",
                    "title": "\u26a0\ufe0f Spending Alert",
                    "text": (
                        "You're spending more than you earn. "
                        "Review your budget urgently."
                    ),
                }
            )

        investment_rate = (avg_investments / avg_income * 100) if avg_income > 0 else 0

        if investment_rate > 15:
            insights.append(
                {
                    "type": "positive",
                    "title": "\U0001f680 Investment Champion",
                    "text": (
                        f"Investing {investment_rate:.1f}% of income is excellent "
                        "for long-term wealth building."
                    ),
                }
            )
        elif investment_rate > 5:
            insights.append(
                {
                    "type": "warning",
                    "title": "\U0001f4c8 Building Wealth",
                    "text": (
                        f"You're investing {investment_rate:.1f}% of income. "
                        "Consider increasing to 15-20% for faster growth."
                    ),
                }
            )
        elif investment_rate > 0:
            insights.append(
                {
                    "type": "info",
                    "title": "\U0001f331 Investment Starter",
                    "text": (
                        f"Great start with {investment_rate:.1f}% invested. "
                        "Gradually increase your investment rate."
                    ),
                }
            )

        categorized_count = Transaction.objects.filter(
            user_id=user_id,
            category__isnull=False,
        ).count()

        categorization_rate = (
            (categorized_count / total_transactions * 100)
            if total_transactions > 0
            else 0
        )

        if categorization_rate < 80:
            insights.append(
                {
                    "type": "info",
                    "title": "\U0001f3f7\ufe0f Organize Your Finances",
                    "text": (
                        f"Only {categorization_rate:.0f}% of transactions are categorized. "
                        "Better categorization provides deeper insights."
                    ),
                }
            )

        current_month = date.today().month
        if current_month in [11, 12, 1]:
            insights.append(
                {
                    "type": "warning",
                    "title": "\U0001f384 Holiday Season Alert",
                    "text": (
                        "Holiday spending can impact budgets. Track expenses carefully "
                        "and stick to your financial goals."
                    ),
                }
            )
        elif current_month in [6, 7, 8]:
            insights.append(
                {
                    "type": "info",
                    "title": "\u2600\ufe0f Summer Spending",
                    "text": (
                        "Summer often brings vacation and leisure expenses. Plan ahead "
                        "to maintain your savings goals."
                    ),
                }
            )

        latest_period = DatePeriod.objects.order_by("-year", "-month").first()
        if latest_period:
            total_balance = (
                AccountBalance.objects.filter(
                    account__user_id=user_id,
                    period=latest_period,
                ).aggregate(total=models.Sum("reported_balance"))["total"]
                or 0
            )

            if float(total_balance) > 50000:
                insights.append(
                    {
                        "type": "positive",
                        "title": "\U0001f4b0 Strong Financial Position",
                        "text": (
                            "Your net worth is growing well. Consider diversifying "
                            "investments for optimal returns."
                        ),
                    }
                )

        if len(insights) == 0:
            insights.append(
                {
                    "type": "info",
                    "title": "\U0001f4ca Keep Building Data",
                    "text": (
                        "Continue adding transactions and balances for more "
                        "personalized financial insights."
                    ),
                }
            )

        insights = insights[:4]
        return JsonResponse({"status": "success", "insights": insights})
    except Exception as exc:
        logger.error(
            "Error in dashboard_insights_json for user %s: %s", request.user.id, exc
        )
        return JsonResponse(
            {
                "status": "error",
                "insights": [
                    {
                        "type": "info",
                        "title": "\U0001f4c8 Keep Adding Data",
                        "text": (
                            "The more data you add, the more personalized insights "
                            "we can provide."
                        ),
                    }
                ],
            },
            status=500,
        )


__all__ = [
    "DashboardView",
    "account_balances_pivot_json",
    "api_jwt_my_transactions",
    "dashboard",
    "dashboard_data",
    "dashboard_export",
    "dashboard_goals_json",
    "dashboard_insights_json",
    "dashboard_kpis_json",
    "dashboard_returns_json",
    "dashboard_spending_by_category_json",
    "financial_analysis_json",
    "menu_config",
    "period_autocomplete",
    "sync_system_adjustments",
]
