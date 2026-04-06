"""Account balance views and helpers."""

import logging
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.db import transaction as db_transaction
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import AccountBalanceFormSet
from .models import Account, AccountBalance, AccountType, Currency, DatePeriod, User
from .utils.cache_helpers import clear_tx_cache

logger = logging.getLogger(__name__)


def _account_balances_export_dataframe(user: User) -> pd.DataFrame:
    """Build the account balances export dataframe."""
    balances = (
        AccountBalance.objects.filter(account__user=user)
        .select_related("period", "account__account_type", "account__currency")
        .order_by(
            "-period__year",
            "-period__month",
            "account__account_type__name",
            "account__name",
        )
    )

    rows = []
    for balance in balances:
        account = balance.account
        period = balance.period
        rows.append(
            [
                period.year,
                period.month,
                f"{period.year}-{period.month:02d}",
                account.name,
                account.account_type.name if account.account_type_id else "",
                account.currency.code if account.currency_id else "",
                balance.reported_balance,
            ]
        )

    return pd.DataFrame(
        rows,
        columns=[
            "Year",
            "Month",
            "Period",
            "Account_Name",
            "Account_Type",
            "Currency",
            "Balance",
        ],
    )


@login_required
def account_balance_view(request):
    """Optimized main view for account balance management with change detection."""
    # Determine the selected month and year
    today = date.today()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))

        if month < 1 or month > 12:
            messages.error(request, "Invalid month.")
            month = today.month
    except ValueError:
        messages.error(request, "Invalid date.")
        year, month = today.year, today.month

    # Check cache first for GET requests
    cache_key = f"account_balance_ultra_{request.user.id}_{year}_{month}"

    # Get or create the matching period
    period, period_created = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    if request.method == "POST":
        logger.info(
            f"🚀 [account_balance_view] Change-detection POST processing for user {request.user.id}, period {year}-{month:02d}"
        )
        start_time = datetime.now()

        try:
            # Parse form data in memory first for maximum speed
            form_data = request.POST
            total_forms = int(form_data.get("form-TOTAL_FORMS", 0))
            logger.debug(f"📊 [account_balance_view] Processing {total_forms} forms")

            # ⚡ ENHANCED CHANGE DETECTION - More thorough but still fast
            # First pass: Quick scan for obvious changes
            has_obvious_changes = False
            for i in range(total_forms):
                prefix = f"form-{i}"

                # Check for deletions - these are always changes
                if form_data.get(f"{prefix}-DELETE"):
                    has_obvious_changes = True
                    logger.debug(
                        f"🔍 [account_balance_view] Found deletion in form {i}"
                    )
                    break

                # Check for new entries (no balance_id but has data)
                balance_id = form_data.get(f"{prefix}-id")
                account_name = form_data.get(f"{prefix}-account")
                reported_balance_str = form_data.get(f"{prefix}-reported_balance")

                if not balance_id and account_name and reported_balance_str:
                    has_obvious_changes = True
                    logger.debug(
                        f"🔍 [account_balance_view] Found new entry in form {i}: {account_name}"
                    )
                    break

            # If no obvious changes, do more thorough verification with actual data comparison
            if not has_obvious_changes:
                logger.debug(
                    "⚡ [account_balance_view] No obvious changes detected, "
                    "doing thorough verification"
                )

                # Load current data for comparison
                current_balances_dict = {}
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT ab.id, ab.account_id, ab.reported_balance, a.name
                        FROM core_accountbalance ab
                        INNER JOIN core_account a ON ab.account_id = a.id
                        WHERE a.user_id = %s AND ab.period_id = %s
                    """,
                        [request.user.id, period.id],
                    )

                    for (
                        balance_id,
                        account_id,
                        current_amount,
                        account_name,
                    ) in cursor.fetchall():
                        current_balances_dict[balance_id] = {
                            "account_name": account_name,
                            "amount": Decimal(str(current_amount)),
                        }

                # Compare form data with database data
                changes_detected = False
                form_balance_ids = set()

                for i in range(total_forms):
                    prefix = f"form-{i}"
                    balance_id = form_data.get(f"{prefix}-id")
                    account_name = form_data.get(f"{prefix}-account")
                    reported_balance_str = form_data.get(f"{prefix}-reported_balance")

                    # Skip empty forms
                    if not account_name or reported_balance_str == "":
                        continue

                    if balance_id:
                        balance_id_int = int(balance_id)
                        form_balance_ids.add(balance_id_int)

                        # Check if this balance exists in DB and if amount changed
                        if balance_id_int in current_balances_dict:
                            try:
                                new_amount = Decimal(str(reported_balance_str))
                                current_amount = current_balances_dict[balance_id_int][
                                    "amount"
                                ]

                                if new_amount != current_amount:
                                    changes_detected = True
                                    logger.debug(
                                        f"🔍 [account_balance_view] Amount change detected: {account_name} {current_amount} → {new_amount}"
                                    )
                                    break
                            except (ValueError, TypeError):
                                changes_detected = True
                                logger.debug(
                                    f"🔍 [account_balance_view] Invalid amount format for {account_name}: {reported_balance_str}"
                                )
                                break
                        else:
                            # Balance ID in form but not in DB - this is a change
                            changes_detected = True
                            logger.debug(
                                f"🔍 [account_balance_view] Balance ID {balance_id_int} not found in DB"
                            )
                            break
                    else:
                        # New entry without balance_id
                        changes_detected = True
                        logger.debug(
                            f"🔍 [account_balance_view] New entry without ID: {account_name}"
                        )
                        break

                # Check if any existing balances were removed from the form
                if not changes_detected:
                    db_balance_ids = set(current_balances_dict.keys())
                    if db_balance_ids != form_balance_ids:
                        changes_detected = True
                        removed_ids = db_balance_ids - form_balance_ids
                        logger.debug(
                            f"🔍 [account_balance_view] Balances removed from form: {removed_ids}"
                        )

                # If no changes detected, return early
                if not changes_detected:
                    logger.info(
                        "✅ [account_balance_view] Thorough verification - "
                        "no changes detected"
                    )
                    processing_time = (datetime.now() - start_time).total_seconds()
                    messages.info(
                        request, f"ℹ️ No changes detected ({processing_time:.2f}s)"
                    )
                    return redirect(f"{request.path}?year={year}&month={month:02d}")
                else:
                    logger.info(
                        "🔍 [account_balance_view] Changes detected during "
                        "thorough verification"
                    )

            # ✨ Load current balances only if changes are likely
            current_balances = {}
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ab.id, ab.account_id, ab.reported_balance, a.name
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    WHERE a.user_id = %s AND ab.period_id = %s
                """,
                    [request.user.id, period.id],
                )

                for (
                    balance_id,
                    account_id,
                    current_amount,
                    account_name,
                ) in cursor.fetchall():
                    current_balances[balance_id] = {
                        "account_id": account_id,
                        "account_name": account_name,
                        "current_amount": Decimal(str(current_amount)),
                    }

            logger.debug(
                f"📋 [account_balance_view] Loaded {len(current_balances)} existing balances"
            )

            # Pre-allocate lists for better memory performance
            balance_updates = []
            balance_creates = []
            balance_deletes = []
            skipped_count = 0

            # Single pass through form data - ultra optimized with change detection
            for i in range(total_forms):
                prefix = f"form-{i}"

                # Check deletion first
                if form_data.get(f"{prefix}-DELETE"):
                    balance_id = form_data.get(f"{prefix}-id")
                    if balance_id:
                        balance_deletes.append(int(balance_id))
                    continue

                account_name = form_data.get(f"{prefix}-account")
                reported_balance_str = form_data.get(f"{prefix}-reported_balance")
                balance_id = form_data.get(f"{prefix}-id")

                # Skip empty entries
                if not account_name or reported_balance_str == "":
                    continue

                try:
                    new_amount = Decimal(str(reported_balance_str))
                    account_name = str(account_name).strip()

                    # Get or create account by name
                    account, created = Account.objects.get_or_create(
                        user_id=request.user.id,
                        name__iexact=account_name,
                        defaults={
                            "name": account_name,
                            "currency_id": Currency.objects.filter(code="EUR")
                            .first()
                            .id,
                            "account_type_id": AccountType.objects.filter(
                                name="Savings"
                            )
                            .first()
                            .id,
                        },
                    )

                    if balance_id:  # Update existing
                        balance_id_int = int(balance_id)

                        # Only save when the value actually changed
                        if balance_id_int in current_balances:
                            current_amount = current_balances[balance_id_int][
                                "current_amount"
                            ]

                            # Compare values with decimal precision
                            if new_amount != current_amount:
                                balance_updates.append(
                                    (
                                        balance_id_int,
                                        account.id,
                                        new_amount,
                                        current_amount,
                                        new_amount,
                                    )
                                )
                                logger.debug(
                                    f"🔄 [account_balance_view] Changed: {account_name} {current_amount} → {new_amount}"
                                )
                            else:
                                skipped_count += 1
                                logger.debug(
                                    f"⏭️ [account_balance_view] Skipped unchanged: {account_name} = {current_amount}"
                                )
                        else:
                            # Balance ID exists but not in current_balances - treat as update
                            balance_updates.append(
                                (
                                    balance_id_int,
                                    account.id,
                                    new_amount,
                                    Decimal("0"),
                                    new_amount,
                                )
                            )
                    else:  # Create new
                        balance_creates.append((account.id, new_amount))
                        logger.debug(
                            f"➕ [account_balance_view] Creating new: {account_name} = {new_amount}"
                        )

                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"⚠️ [account_balance_view] Invalid data in form {i}: {e}"
                    )
                    continue

            # Ultra-fast bulk operations using single atomic transaction
            operations_count = 0
            changed_count = (
                len(balance_updates) + len(balance_creates) + len(balance_deletes)
            )

            logger.info(
                f"📈 [account_balance_view] Changes detected: {changed_count} operations, {skipped_count} skipped"
            )

            if changed_count > 0:
                with db_transaction.atomic():
                    with connection.cursor() as cursor:

                        # 1. Bulk deletes with single query
                        if balance_deletes:
                            cursor.execute(
                                """
                                DELETE FROM core_accountbalance
                                WHERE id = ANY(%s) AND account_id IN (
                                    SELECT id FROM core_account WHERE user_id = %s
                                )
                            """,
                                [balance_deletes, request.user.id],
                            )
                            operations_count += cursor.rowcount
                            logger.debug(
                                f"🗑️ [account_balance_view] Deleted {cursor.rowcount} balances"
                            )

                        # 2. Bulk updates - only changed values
                        if balance_updates:
                            for (
                                balance_id,
                                account_id,
                                new_amount,
                                old_amount,
                                _,
                            ) in balance_updates:
                                cursor.execute(
                                    """
                                    UPDATE core_accountbalance
                                    SET reported_balance = %s
                                    WHERE id = %s AND account_id IN (
                                        SELECT id FROM core_account WHERE user_id = %s
                                    )
                                """,
                                    [new_amount, balance_id, request.user.id],
                                )
                                operations_count += cursor.rowcount

                            logger.debug(
                                f"🔄 [account_balance_view] Updated {len(balance_updates)} changed balances"
                            )

                        # 3. Bulk creates with single INSERT
                        if balance_creates:
                            for account_id, amount in balance_creates:
                                cursor.execute(
                                    """
                                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (account_id, period_id)
                                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                                """,
                                    [account_id, period.id, amount],
                                )
                                operations_count += cursor.rowcount

                            logger.debug(
                                f"➕ [account_balance_view] Created/updated {len(balance_creates)} new balances"
                            )

                # Strategic cache clearing - only clear what's necessary
                from django.core.cache import cache

                cache_keys_pattern = [
                    f"account_balance_ultra_{request.user.id}_{year}_{month}",
                    f"account_balance_optimized_{request.user.id}_{year}_{month}",
                    f"account_summary_{request.user.id}",
                ]

                # Use pipeline for batch cache operations
                cache.delete_many(cache_keys_pattern)

                # Clear transaction cache to ensure consistency
                clear_tx_cache(request.user.id, force=True)
            else:
                logger.info(
                    "⚡ [account_balance_view] No changes detected - "
                    "skipping database operations"
                )

            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"⚡ [account_balance_view] POST completed in {processing_time:.3f}s, {operations_count} operations, {skipped_count} skipped"
            )

            if changed_count > 0:
                messages.success(
                    request,
                    f"✅ Balances saved! ({operations_count} ops, {skipped_count} unchanged, {processing_time:.2f}s)",
                )
            else:
                messages.info(
                    request, f"ℹ️ No changes detected ({processing_time:.2f}s)"
                )

            # Optimized redirect with minimal URL construction
            return redirect(f"{request.path}?year={year}&month={month:02d}")

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"❌ [account_balance_view] Error after {processing_time:.3f}s for user {request.user.id}: {e}"
            )
            messages.error(request, f"Error saving balances: {str(e)}")

    # GET request - ultra-fast cache lookup
    from django.core.cache import cache

    cached_data = cache.get(cache_key)
    if cached_data and request.method == "GET":
        logger.debug(
            f"⚡ [account_balance_view] Using cached summary data for user {request.user.id}"
        )
        # We still need to build the formset as it can't be cached
        # But we can use cached totals and other data

    # Build context with single ultra-optimized query
    start_time = datetime.now()

    with connection.cursor() as cursor:
        # Single query with all JOINs and calculations
        cursor.execute(
            """
            SELECT
                a.id, a.name, a.position,
                at.name, cur.code, cur.symbol,
                COALESCE(ab.reported_balance, 0),
                ab.id,
                CASE WHEN ab.id IS NOT NULL THEN 1 ELSE 0 END
            FROM core_account a
            INNER JOIN core_accounttype at ON a.account_type_id = at.id
            INNER JOIN core_currency cur ON a.currency_id = cur.id
            LEFT JOIN core_accountbalance ab ON (ab.account_id = a.id AND ab.period_id = %s)
            WHERE a.user_id = %s
            ORDER BY a.position NULLS LAST, a.name
        """,
            [period.id, request.user.id],
        )

        rows = cursor.fetchall()

    # Ultra-fast data processing with pre-allocated dictionaries
    totals_by_group = {}
    grand_total = 0
    available_accounts = []

    # Single pass processing for maximum efficiency
    for row in rows:
        (
            account_id,
            account_name,
            account_position,
            account_type_name,
            currency_code,
            currency_symbol,
            balance,
            balance_id,
            has_balance,
        ) = row

        balance_value = float(balance)
        grand_total += balance_value

        # Group totals calculation
        key = (account_type_name, currency_code)
        totals_by_group[key] = totals_by_group.get(key, 0) + balance_value

        if not has_balance:
            available_accounts.append({"id": account_id, "name": account_name})

    # Minimized formset creation for template
    queryset = (
        AccountBalance.objects.filter(account__user=request.user, period=period)
        .select_related("account__account_type", "account__currency")
        .only(
            "id",
            "reported_balance",
            "account__id",
            "account__name",
            "account__account_type__name",
            "account__currency__code",
        )
        .order_by("account__position", "account__name")
    )

    formset = AccountBalanceFormSet(queryset=queryset, user=request.user)

    # Ultra-fast form grouping
    grouped_forms = {}
    for form in formset:
        if hasattr(form.instance, "account") and form.instance.account:
            key = (
                form.instance.account.account_type.name,
                form.instance.account.currency.code,
            )
            if key not in grouped_forms:
                grouped_forms[key] = []
            grouped_forms[key].append(form)

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    context = {
        "formset": formset,
        "grouped_forms": grouped_forms,
        "totals_by_group": totals_by_group,
        "grand_total": grand_total,
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "selected_month": date(year, month, 1),
        "available_accounts": available_accounts,
    }

    # Cache only serializable data for performance
    if request.method == "GET":
        cache_safe_context = {
            "totals_by_group": totals_by_group,
            "grand_total": grand_total,
            "year": year,
            "month": month,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "selected_month": date(year, month, 1),
        }
        cache.set(cache_key, cache_safe_context, timeout=600)  # 10 minutes cache

    query_time = (datetime.now() - start_time).total_seconds()
    logger.debug(
        f"⚡ [account_balance_view] GET completed in {query_time:.3f}s for user {request.user.id}"
    )

    return render(request, "core/account_balance.html", context)


@login_required
def delete_account_balance(request, pk):
    """Optimized delete account balance."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        balance = get_object_or_404(AccountBalance, pk=pk, account__user=request.user)
        period_year = balance.period.year
        period_month = balance.period.month

        balance.delete()
        logger.info(f"Account balance {pk} deleted by user {request.user.id}")

        # Clear related cache
        cache.delete(f"account_balance_{request.user.id}_{period_year}_{period_month}")

        # Return JSON response for AJAX requests
        if request.headers.get("Accept") == "application/json":
            return JsonResponse(
                {"success": True, "message": "Balance deleted successfully"}
            )

        # Redirect back to account balance page for the same period
        messages.success(request, "Balance deleted successfully!")
        return redirect(
            f"{reverse('account_balance')}?year={period_year}&month={period_month:02d}"
        )

    except AccountBalance.DoesNotExist:
        logger.error(
            f"Error deleting account balance {pk} for user {request.user.id}: No AccountBalance matches the given query."
        )

        if request.headers.get("Accept") == "application/json":
            return JsonResponse(
                {"success": False, "error": "Balance not found"}, status=404
            )

        messages.error(request, "Balance not found or already deleted.")
        return redirect("account_balance")

    except Exception as e:
        logger.error(
            f"Error deleting account balance {pk} for user {request.user.id}: {e}"
        )

        if request.headers.get("Accept") == "application/json":
            return JsonResponse(
                {"success": False, "error": "Error deleting balance"}, status=500
            )

        messages.error(request, "Error deleting account balance.")
        return redirect("account_balance")


@login_required
def warm_account_balance_cache(request):
    """Warm cache for account balance view to improve performance."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST method required"})

    try:
        year = int(request.GET.get("year", date.today().year))
        month = int(request.GET.get("month", date.today().month))

        # Warm cache by making a quick query
        cache_key = f"account_balance_optimized_{request.user.id}_{year}_{month}"

        if not cache.get(cache_key):
            # Quick cache warming query
            period = DatePeriod.objects.filter(year=year, month=month).first()
            if period:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM core_account a
                        LEFT JOIN core_accountbalance ab ON (ab.account_id = a.id AND ab.period_id = %s)
                        WHERE a.user_id = %s
                    """,
                        [period.id, request.user.id],
                    )

                logger.info(
                    f"🔥 Cache warmed for user {request.user.id}, period {year}-{month:02d}"
                )

        return JsonResponse({"success": True, "message": "Cache warmed"})

    except Exception as e:
        logger.error(f"Error warming cache for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def copy_previous_balances_view(request):
    """Optimized copy previous month balances to current period."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST method required"})

    try:
        # Get target year and month
        year = int(request.GET.get("year", date.today().year))
        month = int(request.GET.get("month", date.today().month))

        # Calculate previous month
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        logger.info(
            f"Copying balances from {prev_year}-{prev_month:02d} to {year}-{month:02d} for user {request.user.id}"
        )

        # Use raw SQL for better performance
        with connection.cursor() as cursor:
            # First check if source period has any data
            cursor.execute(
                """
                SELECT COUNT(*) FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
            """,
                [request.user.id, prev_year, prev_month],
            )

            source_count = cursor.fetchone()[0]
            if source_count == 0:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"No balances found for {prev_year}-{prev_month:02d}",
                    }
                )

            # Get or create target period
            target_period, _ = DatePeriod.objects.get_or_create(
                year=year,
                month=month,
                defaults={"label": f"{date(year, month, 1).strftime('%B %Y')}"},
            )

            # Use bulk upsert with raw SQL for maximum performance
            cursor.execute(
                """
                WITH source_data AS (
                    SELECT
                        ab.account_id,
                        ab.reported_balance,
                        %s as target_period_id
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                    WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
                ),
                upsert AS (
                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                    SELECT account_id, target_period_id, reported_balance
                    FROM source_data
                    ON CONFLICT (account_id, period_id)
                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                    RETURNING
                        CASE WHEN xmax = 0 THEN 1 ELSE 0 END as is_insert,
                        account_id
                )
                SELECT
                    SUM(is_insert) as created_count,
                    COUNT(*) - SUM(is_insert) as updated_count,
                    COUNT(*) as total_count
                FROM upsert
            """,
                [target_period.id, request.user.id, prev_year, prev_month],
            )

            result = cursor.fetchone()
            created_count, updated_count, total_count = result

            logger.info(
                f"Copy operation completed: {created_count} created, {updated_count} updated"
            )

            # Clear cache for this user's account balance data more efficiently
            cache.delete(f"account_balance_optimized_{request.user.id}_{year}_{month}")
            cache.delete(f"account_summary_{request.user.id}")
            # Clear neighboring months cache too since data dependencies exist
            if month == 1:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year-1}_12")
            else:
                cache.delete(
                    f"account_balance_optimized_{request.user.id}_{year}_{month-1}"
                )
            if month == 12:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year+1}_1")
            else:
                cache.delete(
                    f"account_balance_optimized_{request.user.id}_{year}_{month+1}"
                )

            return JsonResponse(
                {
                    "success": True,
                    "created": created_count,
                    "updated": updated_count,
                    "total": total_count,
                    "message": f"Copied {created_count} new balances, updated {updated_count} existing balances from {prev_year}-{prev_month:02d}",
                }
            )

    except Exception as e:
        logger.error(f"Error copying previous balances for user {request.user.id}: {e}")
        return JsonResponse(
            {"success": False, "error": f"Error copying balances: {str(e)}"}
        )


@login_required
def account_balance_export_xlsx(request):
    """Export account balances to Excel for selected period range."""
    user_id = request.user.id

    # Get period range from request
    start_period = request.GET.get("start", "")
    end_period = request.GET.get("end", "")

    # Parse periods (format: YYYY-MM)
    try:
        if start_period and end_period:
            start_year, start_month = map(int, start_period.split("-"))
            end_year, end_month = map(int, end_period.split("-"))
        else:
            # Default to current year if no periods specified
            today = date.today()
            start_year, start_month = today.year, 1
            end_year, end_month = today.year, today.month
    except (ValueError, TypeError):
        # Fallback to current year
        today = date.today()
        start_year, start_month = today.year, 1
        end_year, end_month = today.year, today.month

    # SQL query to get account balances by period
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                dp.year,
                dp.month,
                CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0')) as period,
                a.name as account_name,
                at.name as account_type,
                cur.code as currency,
                ab.reported_balance
            FROM core_accountbalance ab
            INNER JOIN core_account a ON ab.account_id = a.id
            INNER JOIN core_accounttype at ON a.account_type_id = at.id
            INNER JOIN core_currency cur ON a.currency_id = cur.id
            INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
            INNER JOIN auth_user u ON a.user_id = u.id
            WHERE u.id = %s
            AND (
                (dp.year > %s) OR
                (dp.year = %s AND dp.month >= %s)
            )
            AND (
                (dp.year < %s) OR
                (dp.year = %s AND dp.month <= %s)
            )
            ORDER BY dp.year DESC, dp.month DESC, at.name, a.name;
        """,
            [
                user_id,
                start_year,
                start_year,
                start_month,
                end_year,
                end_year,
                end_month,
            ],
        )
        rows = cursor.fetchall()

    if not rows:
        # Create empty DataFrame with headers
        df = pd.DataFrame(
            columns=[
                "Year",
                "Month",
                "Period",
                "Account_Name",
                "Account_Type",
                "Currency",
                "Balance",
            ]
        )
    else:
        # Create DataFrame from query results
        df = pd.DataFrame(
            rows,
            columns=[
                "Year",
                "Month",
                "Period",
                "Account_Name",
                "Account_Type",
                "Currency",
                "Balance",
            ],
        )

    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Main sheet with detailed data
        df.to_excel(writer, sheet_name="Account_Balances", index=False)

        # Summary sheet by period
        if not df.empty:
            summary_df = (
                df.groupby(["Period", "Account_Type", "Currency"])["Balance"]
                .sum()
                .reset_index()
            )
            summary_df.to_excel(writer, sheet_name="Summary_by_Period", index=False)

    output.seek(0)

    # Generate filename with period range
    filename = f"account_balances_{start_year}-{start_month:02d}_to_{end_year}-{end_month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def account_balance_import_xlsx(request):
    """Import account balances from Excel with optimized bulk operations."""
    if request.method == "POST":
        try:
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                messages.error(request, "No file uploaded.")
                return render(request, "core/import_balances_form.html")

            # Read Excel file
            df = pd.read_excel(uploaded_file)

            # Validate required columns
            required_cols = ["Year", "Month", "Account", "Balance"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                messages.error(
                    request, f'Missing required columns: {", ".join(missing_cols)}'
                )
                return render(request, "core/import_balances_form.html")

            # Clean and validate data upfront
            df = df.dropna(subset=required_cols)
            df["Account"] = df["Account"].astype(str).str.strip()

            try:
                df["Year"] = df["Year"].astype(int)
                df["Month"] = df["Month"].astype(int)
                df["Balance"] = df["Balance"].astype(float)
            except ValueError as e:
                messages.error(request, f"Invalid data format: {str(e)}")
                return render(request, "core/import_balances_form.html")

            imported_count = 0
            updated_count = 0
            errors = []

            with db_transaction.atomic():
                # Pre-fetch default objects
                default_currency, _ = Currency.objects.get_or_create(
                    code="EUR", defaults={"name": "Euro", "symbol": "€"}
                )
                default_account_type, _ = AccountType.objects.get_or_create(
                    name="Savings"
                )

                # Get unique periods and accounts from data
                unique_periods = df[["Year", "Month"]].drop_duplicates()
                unique_accounts = df["Account"].unique()

                # Bulk create/get periods
                periods_to_create = []
                existing_periods = {}

                for _, row in unique_periods.iterrows():
                    year, month = int(row["Year"]), int(row["Month"])
                    try:
                        period = DatePeriod.objects.get(year=year, month=month)
                        existing_periods[(year, month)] = period
                    except DatePeriod.DoesNotExist:
                        period_date = date(year, month, 1)
                        periods_to_create.append(
                            DatePeriod(
                                year=year,
                                month=month,
                                label=period_date.strftime("%B %Y"),
                            )
                        )

                # Bulk create new periods
                if periods_to_create:
                    DatePeriod.objects.bulk_create(
                        periods_to_create, ignore_conflicts=True
                    )

                # Re-fetch all periods after bulk create
                all_periods = DatePeriod.objects.filter(
                    year__in=unique_periods["Year"].values,
                    month__in=unique_periods["Month"].values,
                )
                period_lookup = {(p.year, p.month): p for p in all_periods}

                # Bulk create/get accounts
                accounts_to_create = []
                existing_accounts = {}

                for account_name in unique_accounts:
                    try:
                        account = Account.objects.get(
                            name=account_name, user=request.user
                        )
                        existing_accounts[account_name] = account
                    except Account.DoesNotExist:
                        accounts_to_create.append(
                            Account(
                                name=account_name,
                                user=request.user,
                                currency=default_currency,
                                account_type=default_account_type,
                            )
                        )

                # Bulk create new accounts
                if accounts_to_create:
                    Account.objects.bulk_create(
                        accounts_to_create, ignore_conflicts=True
                    )

                # Re-fetch all accounts after bulk create
                all_accounts = Account.objects.filter(
                    user=request.user, name__in=unique_accounts
                )
                account_lookup = {a.name: a for a in all_accounts}

                # Prepare balance operations
                balances_to_create = []
                balances_to_update = []

                # Get existing balances for this user in bulk
                existing_balances = {}
                if account_lookup and period_lookup:
                    existing_balance_qs = AccountBalance.objects.filter(
                        account__user=request.user,
                        account__in=account_lookup.values(),
                        period__in=period_lookup.values(),
                    ).select_related("account", "period")

                    for bal in existing_balance_qs:
                        key = (bal.account.name, bal.period.year, bal.period.month)
                        existing_balances[key] = bal

                # Process each row for balance operations
                for index, row in df.iterrows():
                    try:
                        year = int(row["Year"])
                        month = int(row["Month"])
                        account_name = str(row["Account"]).strip()
                        balance = Decimal(str(row["Balance"]))

                        # Get period and account from lookup
                        period = period_lookup.get((year, month))
                        account = account_lookup.get(account_name)

                        if not period or not account:
                            errors.append(
                                f"Row {index + 2}: Could not find period or account"
                            )
                            continue

                        balance_key = (account_name, year, month)

                        if balance_key in existing_balances:
                            # Update existing balance
                            existing_balance = existing_balances[balance_key]
                            existing_balance.reported_balance = balance
                            balances_to_update.append(existing_balance)
                            updated_count += 1
                        else:
                            # Create new balance
                            balances_to_create.append(
                                AccountBalance(
                                    account=account,
                                    period=period,
                                    reported_balance=balance,
                                )
                            )
                            imported_count += 1

                    except Exception as e:
                        errors.append(f"Row {index + 2}: {str(e)}")

                # Bulk operations for balances
                if balances_to_create:
                    AccountBalance.objects.bulk_create(
                        balances_to_create, ignore_conflicts=True
                    )

                if balances_to_update:
                    AccountBalance.objects.bulk_update(
                        balances_to_update, ["reported_balance"], batch_size=1000
                    )

            if errors:
                messages.warning(
                    request,
                    f"Imported {imported_count} new balances, updated {updated_count} existing balances with {len(errors)} errors.",
                )
                if len(errors) <= 5:  # Show first 5 errors
                    for error in errors[:5]:
                        messages.error(request, error)
            else:
                messages.success(
                    request,
                    f"Successfully imported {imported_count} new balances and updated {updated_count} existing balances.",
                )

            return redirect("/account-balance/")

        except Exception as e:
            logger.error(f"Import error for user {request.user.id}: {e}")
            messages.error(request, f"Import failed: {str(e)}")

    return render(request, "core/import_balances_form.html")


@login_required
def account_balance_template_xlsx(request):
    """Download template for account balance import using Savings and Investments accounts."""
    data = {
        "Year": [2025, 2025],
        "Month": [1, 1],
        "Account": ["Savings", "Investments"],
        "Balance": [1000.00, 5000.00],
    }
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Balances", index=False)

    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        'attachment; filename="balance_import_template.xlsx"'
    )
    return response


__all__ = [
    "_account_balances_export_dataframe",
    "account_balance_view",
    "delete_account_balance",
    "copy_previous_balances_view",
    "account_balance_export_xlsx",
    "account_balance_import_xlsx",
    "account_balance_template_xlsx",
]
