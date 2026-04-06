"""Transaction estimation views."""

import json
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, connection
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from .models import DatePeriod, Transaction
from .utils.cache_helpers import clear_tx_cache

logger = logging.getLogger(__name__)


# TRANSACTION ESTIMATION FUNCTIONS
# ==============================================================================


@login_required
def estimate_transaction_page(request):
    """Transaction estimation management view."""
    # Get available periods with account balances, excluding the most recent period
    # because we need the next period's data to estimate transactions
    all_periods_with_balances = (
        DatePeriod.objects.filter(account_balances__account__user=request.user)
        .distinct()
        .select_related()
        .order_by("-year", "-month")
    )

    # Exclude the most recent period (first in the ordered list)
    periods_with_balances = all_periods_with_balances[
        1:13
    ]  # Skip first, get next 12 months

    logger.debug(
        f"Found {periods_with_balances.count()} periods with balances for user {request.user.id} (excluding latest period)"
    )

    context = {
        "periods": periods_with_balances,
        "user_id": request.user.id,  # Add for frontend caching
    }

    return render(request, "core/estimate_transactions.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def transaction_estimate(request):
    """Preview or create estimated transaction for a scope."""

    from .services.transaction_estimate import EstimationService, MissingAmountService

    data = request.GET if request.method == "GET" else json.loads(request.body or "{}")
    period_id = data.get("period_id")
    tx_type = data.get("type")
    category_id = data.get("category_id")
    account_id = data.get("account_id")

    if not period_id or not tx_type:
        return JsonResponse({"error": "period_id and type are required"}, status=400)

    filter_kwargs = {
        "user": request.user,
        "period_id": period_id,
        "type": tx_type,
    }
    if category_id:
        filter_kwargs["category_id"] = category_id
    if account_id:
        filter_kwargs["account_id"] = account_id

    base_qs = Transaction.objects.filter(**filter_kwargs).exclude(is_estimated=True)
    actual_total = base_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    existing_estimate = Transaction.objects.filter(
        **filter_kwargs, is_estimated=True
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    estimation_service = EstimationService()
    missing_service = MissingAmountService()

    scope = {
        "period_id": period_id,
        "type": tx_type,
        "category_id": category_id,
        "account_id": account_id,
    }

    preview_estimate = estimation_service.compute(scope, base_amount=actual_total)
    missing_before = missing_service.compute(scope, ignore_estimates=True)
    delta = preview_estimate - existing_estimate
    missing_after = missing_before - delta
    if missing_after < 0:
        missing_after = Decimal("0")

    will_replace = existing_estimate != 0

    if request.method == "GET":
        response = {
            "currently_estimating": float(preview_estimate),
            "current_estimate": float(existing_estimate) if will_replace else None,
            "delta": float(delta),
            "missing": float(missing_after),
            "will_replace": will_replace,
        }
        if will_replace:
            response["message"] = "An existing estimate will be replaced."
        return JsonResponse(response)

    # POST - create new estimated transaction
    period = DatePeriod.objects.get(id=period_id)
    try:
        with db_transaction.atomic():
            existing = Transaction.objects.select_for_update().filter(
                **filter_kwargs, is_estimated=True
            )
            if existing.exists():
                existing.delete()
            tx = Transaction.objects.create(
                user=request.user,
                type=tx_type,
                amount=preview_estimate,
                period=period,
                date=period.get_last_day(),
                category_id=category_id,
                account_id=account_id,
                is_estimated=True,
            )
    except IntegrityError:
        tx = Transaction.objects.filter(**filter_kwargs, is_estimated=True).first()

    clear_tx_cache(request.user.id, force=True)
    return JsonResponse(
        {
            "currently_estimating": float(preview_estimate),
            "transaction_id": tx.id,
            "current_estimate": float(preview_estimate),
            "delta": 0.0,
            "missing": float(missing_after),
            "will_replace": False,
        },
        status=201,
    )


@require_POST
@login_required
def estimate_transaction_for_period(request):
    """Estimate transaction for a specific period."""
    from .services.finance_estimation import FinanceEstimationService

    try:
        data = json.loads(request.body)
        period_id = data.get("period_id")

        if not period_id:
            return JsonResponse({"success": False, "error": "Period ID required"})

        # Get the period
        try:
            period = DatePeriod.objects.get(id=period_id)
        except DatePeriod.DoesNotExist:
            return JsonResponse({"success": False, "error": "Period not found"})

        logger.info(
            f"Estimating transaction for period {period.label} (user {request.user.id})"
        )

        # Run estimation
        estimation_service = FinanceEstimationService(request.user)
        estimated_tx = estimation_service.estimate_transaction_for_period(period)

        # Get updated summary data
        summary = estimation_service.get_estimation_summary(period)

        # Clear transaction cache
        clear_tx_cache(request.user.id, force=True)

        message = f"Estimation completed for {period.label}"
        if estimated_tx:
            message += f" - Created transaction ID {estimated_tx.id}"
        else:
            message += " - No estimation needed (period appears balanced)"

        return JsonResponse(
            {
                "success": True,
                "transaction_id": estimated_tx.id if estimated_tx else None,
                "summary": summary,
                "message": message,
            }
        )

    except Exception as e:
        logger.error(f"Error estimating transaction for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def get_estimation_summaries(request):
    """Get estimation summaries for multiple periods."""
    from .services.finance_estimation import FinanceEstimationService

    try:
        # Get year filter from request
        year_filter = request.GET.get("year")

        # Get periods with account balances, properly ordered
        periods_qs = (
            DatePeriod.objects.filter(account_balances__account__user=request.user)
            .distinct()
            .order_by("-year", "-month")
        )

        # Apply year filter if provided
        if year_filter:
            try:
                year = int(year_filter)
                periods_qs = periods_qs.filter(year=year)
                logger.debug(f"Applied year filter: {year}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid year filter: {year_filter}")

        # For explicit year filters, return the full year (up to 12 months).
        # Without filters, keep historical behavior of skipping the most recent
        # period because the default estimation flow relies on forward balances.
        if year_filter:
            periods = periods_qs[:12]
        else:
            periods = periods_qs[1:13]  # Skip first, get next 12 months

        logger.debug(f"Found {periods.count()} periods for user {request.user.id}")

        estimation_service = FinanceEstimationService(request.user)
        summaries = []

        # Use select_related for better performance
        periods_with_data = periods.select_related().prefetch_related(
            "account_balances__account"
        )

        for period in periods_with_data:
            try:
                summary = estimation_service.get_estimation_summary(period)
                summaries.append(summary)
                logger.debug(
                    f"Generated summary for period {period.label}: {summary['status']}"
                )
            except Exception as period_error:
                logger.error(f"Error processing period {period.id}: {period_error}")
                # Add error summary for this period
                summaries.append(
                    {
                        "period_id": period.id,
                        "period": period.label,
                        "status": "error",
                        "status_message": f"Error: {str(period_error)}",
                        "estimated_type": None,
                        "estimated_amount": 0,
                        "has_estimated_transaction": False,
                        "estimated_transaction_id": None,
                        "details": {},
                    }
                )

        # Ensure summaries are properly ordered by period (most recent first)
        summaries.sort(
            key=lambda x: (
                (
                    int(x["period"].split(" ")[1])
                    if len(x["period"].split(" ")) > 1
                    else 0
                ),  # Year
                (
                    [
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ].index(x["period"].split(" ")[0])
                    + 1
                    if len(x["period"].split(" ")) > 1
                    else 0
                ),  # Month
            ),
            reverse=True,
        )

        logger.info(
            f"Returning {len(summaries)} estimation summaries for user {request.user.id}"
        )

        return JsonResponse({"success": True, "summaries": summaries})

    except Exception as e:
        logger.error(
            f"Error getting estimation summaries for user {request.user.id}: {e}"
        )
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
@login_required
def delete_estimated_transaction(request, transaction_id):
    """Delete an estimated transaction."""
    try:
        # Get the transaction and verify it belongs to user and is estimated
        try:
            tx = Transaction.objects.get(
                id=transaction_id, user=request.user, is_estimated=True
            )
        except Transaction.DoesNotExist:
            logger.warning(
                f"Estimated transaction {transaction_id} not found for user {request.user.id}"
            )
            return JsonResponse(
                {"success": True, "message": "No estimated transaction found to delete"}
            )

        period_label = tx.period.label if tx.period else "Unknown"
        tx.delete()

        # Clear cache
        clear_tx_cache(request.user.id, force=True)

        return JsonResponse(
            {
                "success": True,
                "message": f"Estimated transaction for {period_label} deleted successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error deleting estimated transaction {transaction_id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
@login_required
def delete_estimated_transaction_by_period(request, period_id):
    """Delete estimated transaction for a specific period."""
    try:
        # Get the period
        try:
            period = DatePeriod.objects.get(id=period_id)
        except DatePeriod.DoesNotExist:
            return JsonResponse({"success": False, "error": "Period not found"})

        # Find and delete estimated transactions for this period anduser
        estimated_transactions = Transaction.objects.filter(
            user=request.user, period=period, is_estimated=True
        )

        deleted_count = estimated_transactions.count()
        estimated_transactions.delete()

        logger.info(
            f"Deleted {deleted_count} estimated transaction(s) for period {period.label}"
        )

        # Clear cache
        clear_tx_cache(request.user.id, force=True)

        return JsonResponse(
            {
                "success": True,
                "message": f"Deleted {deleted_count} estimated transaction(s) for {period.label}",
            }
        )

    except Exception as e:
        logger.error(
            f"Error deleting estimated transactions for period {period_id}: {e}"
        )
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def get_available_years(request):
    """Get years that have periods with account balances."""
    try:
        # Get distinct years from periods that have account balances for this user
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT dp.year
                FROM core_dateperiod dp
                INNER JOIN core_accountbalance ab ON ab.period_id = dp.id
                INNER JOIN core_account a ON ab.account_id = a.id
                WHERE a.user_id = %s
                ORDER BY dp.year DESC
            """,
                [request.user.id],
            )

            years = [row[0] for row in cursor.fetchall()]

        logger.debug(
            f"Found {len(years)} years with balance periods for user {request.user.id}: {years}"
        )

        return JsonResponse({"success": True, "years": years})

    except Exception as e:
        logger.error(f"Error getting available years for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


__all__ = [
    "estimate_transaction_page",
    "transaction_estimate",
    "estimate_transaction_for_period",
    "get_estimation_summaries",
    "delete_estimated_transaction",
    "delete_estimated_transaction_by_period",
    "get_available_years",
]
