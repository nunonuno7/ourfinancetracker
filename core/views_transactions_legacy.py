"""Legacy transaction CRUD, JSON and bulk-operation views."""

import hashlib
import json
import logging
import re
from calendar import monthrange
from datetime import date

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db import transaction as db_transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import http_date, parse_http_date_safe
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from .forms import TransactionForm, UserInFormKwargsMixin
from .mixins import OwnerQuerysetMixin, SimpleDeleteFlowMixin
from .models import Account, Category, DatePeriod, Tag, Transaction
from .utils.cache_helpers import clear_tx_cache, get_cache_key_for_transactions
from .utils.date_helpers import parse_safe_date

logger = logging.getLogger("core.views")

# ==============================================================================
# TRANSACTION VIEWS
# ==============================================================================


class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Create a new transaction with security validation."""

    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def form_valid(self, form):
        """Process a valid form submission and clear cache."""
        self.object = form.save()
        logger.debug(f"📝 Created: {self.object}")  # Debug in terminal

        # Clear cache immediately
        clear_tx_cache(self.request.user.id, force=True)

        # Add a flag so JavaScript knows it should reload
        self.request.session["transaction_changed"] = True

        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": True, "reload_needed": True})

        messages.success(self.request, "Transaction created successfully!")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        """Process an invalid form submission."""
        logger.debug(f"Invalid form: {form.errors}")  # DEBUG
        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Add safe context data."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["accounts"] = Account.objects.filter(user=user).order_by("name")
        context["category_list"] = list(
            Category.objects.filter(user=user, blocked=False).values_list(
                "name", flat=True
            )
        )
        context["tag_list"] = list(
            Tag.objects.filter(user=user).values_list("name", flat=True)
        )
        return context


class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Update an existing transaction with owner validation."""

    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def get_queryset(self):
        return super().get_queryset().prefetch_related("tags")

    def _build_unavailable_transaction_log_context(self, request, pk):
        current_user_tx = (
            Transaction.objects.filter(pk=pk, user=request.user)
            .values("id", "editable", "is_estimated", "is_system", "updated_at")
            .first()
        )
        any_user_tx = Transaction.objects.filter(pk=pk).values("user_id").first()

        return {
            "transaction_pk": pk,
            "request_user_id": request.user.id,
            "exists_for_current_user": current_user_tx is not None,
            "exists_for_other_user": bool(
                any_user_tx and any_user_tx["user_id"] != request.user.id
            ),
            "editable_for_current_user": (
                current_user_tx["editable"] if current_user_tx else None
            ),
            "estimated_for_current_user": (
                current_user_tx["is_estimated"] if current_user_tx else None
            ),
            "system_for_current_user": (
                current_user_tx["is_system"] if current_user_tx else None
            ),
            "updated_at_for_current_user": (
                current_user_tx["updated_at"].isoformat()
                if current_user_tx and current_user_tx["updated_at"]
                else None
            ),
            "method": request.method,
            "path": request.path,
            "referrer": request.META.get("HTTP_REFERER", ""),
            "is_htmx": request.headers.get("HX-Request") == "true",
            "is_ajax": request.headers.get("X-Requested-With") == "XMLHttpRequest",
            "had_transaction_changed_flag": bool(
                request.session.get("transaction_changed")
            ),
        }

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            message = "The transaction no longer exists or is no longer available."
            log_context = self._build_unavailable_transaction_log_context(
                request, kwargs.get("pk")
            )
            logger.warning(
                "Unavailable transaction edit access: %s",
                log_context,
            )
            request.session["transaction_changed"] = True

            if (
                request.headers.get("HX-Request") == "true"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            ):
                return JsonResponse(
                    {
                        "success": False,
                        "error": message,
                        "redirect_url": reverse("transaction_list_v2"),
                    },
                    status=404,
                )

            messages.error(request, message)
            return redirect("transaction_list_v2")

    def get_object(self, queryset=None):
        """Override to provide better error handling and prevent editing estimated transactions."""
        obj = super().get_object(queryset)

        # Prevent editing estimated transactions
        if obj.is_estimated:
            messages.error(
                self.request,
                "Estimated transactions cannot be edited directly. Use the estimation tool at /transactions/estimate/ instead.",
            )
            logger.warning(
                f"User {self.request.user.id} tried to edit estimated transaction {obj.id}"
            )
            raise PermissionDenied("Cannot edit estimated transaction")

        return obj

    def form_valid(self, form):
        # Clear cache immediately
        clear_tx_cache(self.request.user.id, force=True)

        # Add a flag so JavaScript knows it should reload
        self.request.session["transaction_changed"] = True

        messages.success(self.request, "Transaction updated successfully!")

        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_list"] = list(
            Category.objects.filter(user=self.request.user, blocked=False).values_list(
                "name", flat=True
            )
        )
        context["tag_list"] = list(
            Tag.objects.filter(user=self.request.user).values_list("name", flat=True)
        )
        return context


class TransactionDeleteView(SimpleDeleteFlowMixin, OwnerQuerysetMixin, DeleteView):
    """Delete a transaction with owner validation."""

    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list_v2")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_id = self.object.user_id

        # Delete the transaction
        response = super().delete(request, *args, **kwargs)

        # Clear cache after deletion
        clear_tx_cache(user_id, force=True)

        # Handle AJAX requests
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.headers.get("Content-Type") == "application/json"
        ):
            return JsonResponse(
                {"success": True, "message": "Transaction deleted successfully!"}
            )

        request.session["transaction_changed"] = True
        messages.success(request, "Transaction deleted successfully!")
        return response

    def post(self, request, *args, **kwargs):
        """Override post to handle both AJAX and regular form submissions."""
        self.object = self.get_object()

        # For AJAX requests, delete immediately
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return self.delete(request, *args, **kwargs)

        return self.delete(request, *args, **kwargs)


def transactions_json(request):
    """JSON API for DataTables with cache and dynamic filters."""
    user_id = request.user.id

    # Dates
    raw_start = request.GET.get("date_start")
    raw_end = request.GET.get("date_end")
    start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
    end_date = parse_safe_date(raw_end, date.today())

    if not start_date or not end_date:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    cache_key = get_cache_key_for_transactions(user_id, start_date, end_date)
    cached = cache.get(cache_key)

    if cached is not None:
        if isinstance(cached, dict):
            df = cached["df"].copy()
            last_modified = cached.get("last_modified", now())
        else:
            df = cached.copy()
            last_modified = now()
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                       COALESCE(cat.name, '') AS category,
                       COALESCE(acc.name, 'No account') AS account,
                       COALESCE(curr.symbol, '') AS currency,
                       COALESCE(STRING_AGG(tag.name, ', '), '') AS tags
                FROM core_transaction tx
                LEFT JOIN core_category cat ON tx.category_id = cat.id
                LEFT JOIN core_account acc ON tx.account_id = acc.id
                LEFT JOIN core_currency curr ON acc.currency_id = curr.id
                LEFT JOIN core_dateperiod dp ON tx.period_id = dp.id
                LEFT JOIN core_transactiontag tt ON tt.transaction_id = tx.id
                LEFT JOIN core_tag tag ON tt.tag_id = tag.id
                WHERE tx.user_id = %s AND tx.date BETWEEN %s AND %s
                GROUP BY tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                         cat.name, acc.name, curr.symbol
                ORDER BY tx.id
            """,
                [user_id, start_date, end_date],
            )
            rows = cursor.fetchall()

        df = pd.DataFrame(
            rows,
            columns=[
                "id",
                "date",
                "year",
                "month",
                "type",
                "amount",
                "category",
                "account",
                "currency",
                "tags",
            ],
        )
        last_modified = (
            Transaction.objects.filter(
                user_id=user_id, date__range=(start_date, end_date)
            ).aggregate(Max("updated_at"))["updated_at__max"]
            or now()
        )
        cache.set(
            cache_key, {"df": df.copy(), "last_modified": last_modified}, timeout=300
        )

    # Transformations and formatting
    df["date"] = df["date"].astype(str)
    df["period"] = (
        df["year"].astype(str) + "-" + df["month"].astype(int).astype(str).str.zfill(2)
    )
    df["type"] = df["type"].map(dict(Transaction.Type.choices)).fillna(df["type"])
    df["amount_float"] = df["amount"].astype(float)

    # Add investment direction for display with line break
    df["type_display"] = df.apply(
        lambda row: (
            f"Investment<br>({'Withdrawal' if row['amount_float'] < 0 else 'Reinforcement'})"
            if row["type"] == "Investment"
            else row["type"]
        ),
        axis=1,
    )

    # GET filters
    tx_type = request.GET.get("type", "").strip()
    category = request.GET.get("category", "").strip()
    account = request.GET.get("account", "").strip()
    period = request.GET.get("period", "").strip()
    search = request.GET.get("search[value]", "").strip()

    # Advanced filters
    amount_min = request.GET.get("amount_min", "").strip()
    amount_max = request.GET.get("amount_max", "").strip()
    tags_filter = request.GET.get("tags", "").strip()

    df_for_type = df.copy()
    df_for_category = df.copy()
    df_for_account = df.copy()
    df_for_period = df.copy()

    if tx_type:
        df = df[df["type"] == tx_type]
        df_for_category = df_for_category[df_for_category["type"] == tx_type]
        df_for_account = df_for_account[df_for_account["type"] == tx_type]
        df_for_period = df_for_period[df_for_period["type"] == tx_type]

    if category:
        df = df[df["category"].str.contains(category, case=False, na=False)]
        df_for_type = df_for_type[
            df_for_type["category"].str.contains(category, case=False, na=False)
        ]
        df_for_account = df_for_account[
            df_for_account["category"].str.contains(category, case=False, na=False)
        ]
        df_for_period = df_for_period[
            df_for_period["category"].str.contains(category, case=False, na=False)
        ]

    if account:
        df = df[df["account"].str.contains(account, case=False, na=False)]
        df_for_type = df_for_type[
            df_for_type["account"].str.contains(account, case=False, na=False)
        ]
        df_for_category = df_for_category[
            df_for_category["account"].str.contains(account, case=False, na=False)
        ]
        df_for_period = df_for_period[
            df_for_period["account"].str.contains(account, case=False, na=False)
        ]

    if period:
        try:
            y, m = map(int, period.split("-"))
            df = df[(df["year"] == y) & (df["month"] == m)]
            df_for_type = df_for_type[
                (df_for_type["year"] == y) & (df_for_type["month"] == m)
            ]
            df_for_category = df_for_category[
                (df_for_category["year"] == y) & (df_for_category["month"] == m)
            ]
            df_for_account = df_for_account[
                (df_for_account["year"] == y) & (df_for_account["month"] == m)
            ]
        except Exception as e:
            logger.warning(f"Invalid period value '{period}': {e}")

    if search:
        df = df[
            df["category"].str.contains(search, case=False, na=False)
            | df["account"].str.contains(search, case=False, na=False)
            | df["type"].str.contains(search, case=False, na=False)
            | df["tags"].str.contains(search, case=False, na=False)
        ]

    # Advanced filters
    if amount_min:
        try:
            min_val = float(amount_min)
            df = df[df["amount_float"] >= min_val]
            logger.debug(
                f"Applied amount_min filter: {min_val}, remaining rows: {len(df)}"
            )
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_min value: {amount_min}")

    if amount_max:
        try:
            max_val = float(amount_max)
            df = df[df["amount_float"] <= max_val]
            logger.debug(
                f"Applied amount_max filter: {max_val}, remaining rows: {len(df)}"
            )
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_max value: {amount_max}")

    if tags_filter:
        tag_list = [t.strip().lower() for t in tags_filter.split(",") if t.strip()]
        if tag_list:
            # Use regex to match any of the tags
            tag_pattern = "|".join(tag_list)
            df = df[df["tags"].str.contains(tag_pattern, case=False, na=False)]
            logger.debug(f"Applied tags filter: {tag_list}, remaining rows: {len(df)}")

    # Dynamic unique filters - map backend types to display names for frontend
    backend_types = sorted([t for t in df_for_type["type"].dropna().unique() if t])
    available_types = []
    type_mapping = {
        "IN": "Income",
        "EX": "Expense",
        "IV": "Investment",
        "TR": "Transfer",
        "AJ": "Adjustment",
    }
    for backend_type in backend_types:
        display_type = type_mapping.get(backend_type, backend_type)
        available_types.append(display_type)

    available_categories = sorted(
        [c for c in df_for_category["category"].dropna().unique() if c]
    )

    available_accounts = sorted(
        [a for a in df_for_account["account"].dropna().unique() if a]
    )

    available_periods = sorted(
        [p for p in df_for_period["period"].dropna().unique() if p], reverse=True
    )

    # Sorting
    order_col = request.GET.get("order[0][column]", "1")
    order_dir = request.GET.get("order[0][dir]", "desc")
    ascending = order_dir != "desc"
    column_map = {
        "0": "period",
        "1": "date",
        "2": "type",
        "3": "amount_float",
        "4": "category",
        "5": "tags",
        "6": "account",
    }
    sort_col = column_map.get(order_col, "date")
    if sort_col in df.columns:
        try:
            df.sort_values(by=sort_col, ascending=ascending, inplace=True)
        except Exception as e:
            logger.warning(f"Failed to sort by '{sort_col}': {e}")

    # Format amounts
    df["amount"] = df.apply(
        lambda r: f"€ {r['amount_float']:,.2f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
        + f" {r['currency']}",
        axis=1,
    )

    # Create actions as an HTML string
    df["actions"] = df.apply(
        lambda r: f"""
        <div class='btn-group'>
          <a href='/transactions/{r["id"]}/edit/' class='btn btn-sm btn-outline-primary'>✏️</a>
          <a href='/transactions/{r["id"]}/delete/' class='btn btn-sm btn-outline-danger'>🗑️</a>
        </div>
        """,
        axis=1,
    )

    # Pagination (DataTables)
    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    page_df = df.iloc[start : start + length]

    response_data = {
        "draw": draw,
        "recordsTotal": len(df),
        "recordsFiltered": len(df),
        "data": page_df.to_dict(orient="records"),
        "filters": {
            "types": available_types,
            "categories": available_categories,
            "accounts": available_accounts,
            "periods": available_periods,
        },
    }

    response_json = json.dumps(response_data, sort_keys=True, cls=DjangoJSONEncoder)
    etag = hashlib.md5(response_json.encode("utf-8")).hexdigest()

    if request.headers.get("If-None-Match") == etag:
        return HttpResponse(status=304)

    ims = request.headers.get("If-Modified-Since")
    if ims:
        ims_ts = parse_http_date_safe(ims)
        if ims_ts is not None and int(last_modified.timestamp()) <= ims_ts:
            return HttpResponse(status=304)

    response = JsonResponse(response_data)
    response["ETag"] = etag
    response["Last-Modified"] = http_date(last_modified.timestamp())
    response["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


@require_POST
@login_required
def transaction_bulk_update(request):
    """Bulk update transactions (mark as estimated, etc.)."""
    try:
        data = json.loads(request.body)
        action = data.get("action")
        transaction_ids = data.get("transaction_ids", [])

        if not transaction_ids:
            return JsonResponse({"success": False, "error": "No transactions selected"})

        # Validate transactions belong to user
        transactions = Transaction.objects.filter(
            id__in=transaction_ids, user=request.user
        )

        if len(transactions) != len(transaction_ids):
            return JsonResponse(
                {"success": False, "error": "Some transactions not found"}
            )

        updated = 0

        # Use atomic transaction to ensure all updates happen together
        with db_transaction.atomic():
            if action == "mark_estimated":
                updated = transactions.update(is_estimated=True)
            elif action == "mark_unestimated":
                updated = transactions.update(is_estimated=False)
            else:
                return JsonResponse({"success": False, "error": "Invalid action"})

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id, force=True)
        logger.info(
            f"✅ Bulk update completed: {updated} transactions updated, cache cleared for user {request.user.id}"
        )

        return JsonResponse(
            {
                "success": True,
                "updated": updated,
                "message": f"{updated} transactions updated",
            }
        )

    except Exception as e:
        logger.error(f"Bulk update error for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
@login_required
def transaction_bulk_duplicate(request):
    """Bulk duplicate transactions into a selected month."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get("transaction_ids", [])
        target_period_value = str(data.get("target_period") or "").strip()

        if not transaction_ids:
            return JsonResponse({"success": False, "error": "No transactions selected"})

        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", target_period_value):
            return JsonResponse(
                {"success": False, "error": "Target month is required"},
                status=400,
            )

        target_year, target_month = map(int, target_period_value.split("-"))

        # Get original transactions
        transactions = (
            Transaction.objects.filter(id__in=transaction_ids, user=request.user)
            .select_related("category", "account", "period")
            .prefetch_related("tags")
        )

        if len(transactions) != len(transaction_ids):
            return JsonResponse(
                {"success": False, "error": "Some transactions not found"}
            )

        created = 0
        target_period, _ = DatePeriod.objects.get_or_create(
            year=target_year,
            month=target_month,
            defaults={"label": date(target_year, target_month, 1).strftime("%B %Y")},
        )

        # Use atomic transaction for all operations
        with db_transaction.atomic():
            new_transactions = []
            for tx in transactions:
                original_tags = list(tx.tags.all())
                target_day = min(tx.date.day, monthrange(target_year, target_month)[1])
                target_date = date(target_year, target_month, target_day)

                # Create duplicate in the selected month.
                new_tx = Transaction.objects.create(
                    user=tx.user,
                    type=tx.type,
                    amount=tx.amount,
                    date=target_date,
                    notes=f"Duplicate of transaction from {tx.date}",
                    is_estimated=tx.is_estimated,
                    period=target_period,
                    account=tx.account,
                    category=tx.category,
                )
                new_transactions.append((new_tx, original_tags))
                created += 1

            # Copy tags for all new transactions
            for new_tx, original_tags in new_transactions:
                if original_tags:
                    new_tx.tags.add(*original_tags)

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id, force=True)
        logger.info(
            f"✅ Bulk duplicate completed: {created} transactions created in current month, cache cleared for user {request.user.id}"
        )

        return JsonResponse(
            {
                "success": True,
                "created": created,
                "target_period": target_period_value,
                "message": f"{created} transactions duplicated",
            }
        )

    except Exception as e:
        logger.error(f"Bulk duplicate error for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_POST
@login_required
def transaction_bulk_delete(request):
    """Bulk delete transactions with optimized performance."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get("transaction_ids", [])

        if not transaction_ids:
            return JsonResponse({"success": False, "error": "No transactions selected"})

        logger.info(
            f"🗑️ [transaction_bulk_delete] Starting bulk delete of {len(transaction_ids)} transactions for user {request.user.id}"
        )

        # Validate transactions belong to user in a single query
        valid_transactions = Transaction.objects.filter(
            id__in=transaction_ids, user=request.user
        ).values_list("id", flat=True)

        valid_count = len(valid_transactions)
        if valid_count != len(transaction_ids):
            invalid_count = len(transaction_ids) - valid_count
            logger.warning(
                f"⚠️ [transaction_bulk_delete] {invalid_count} transactions not found or don't belong to user"
            )
            return JsonResponse(
                {
                    "success": False,
                    "error": f"{invalid_count} transactions not found or access denied",
                }
            )

        # Use optimized bulk deletion with atomic transaction
        with db_transaction.atomic():
            # First, delete related TransactionTag entries in bulk
            from .models import TransactionTag

            tag_delete_count = TransactionTag.objects.filter(
                transaction_id__in=valid_transactions
            ).delete()[0]

            logger.debug(
                f"🏷️ [transaction_bulk_delete] Deleted {tag_delete_count} transaction tags"
            )

            # Then delete transactions in bulk - much faster than individual deletes
            deleted_info = Transaction.objects.filter(
                id__in=valid_transactions, user=request.user
            ).delete()

            deleted_count = deleted_info[0]  # Total objects deleted
            logger.info(
                f"🗑️ [transaction_bulk_delete] Bulk deleted {deleted_count} objects from database"
            )

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id, force=True)
        logger.info(
            f"✅ Bulk delete completed: {valid_count} transactions deleted, cache cleared for user {request.user.id}"
        )

        return JsonResponse(
            {
                "success": True,
                "deleted": valid_count,
                "message": f"{valid_count} transactions deleted successfully",
            }
        )

    except Exception as e:
        logger.error(f"❌ Bulk delete error for user {request.user.id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
def transaction_clear_cache(request):
    """Clear transaction cache for current user."""
    try:
        clear_tx_cache(request.user.id, force=True)

        # Handle AJAX requests
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.headers.get("Content-Type") == "application/json"
        ):
            return JsonResponse(
                {"success": True, "message": "Data refreshed successfully!"}
            )

        messages.success(request, "Data refreshed successfully!")
        return redirect("transaction_list_v2")

    except Exception as e:
        logger.error(f"Error refreshing data for user {request.user.id}: {e}")

        # Handle AJAX requests
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.headers.get("Content-Type") == "application/json"
        ):
            return JsonResponse({"success": False, "error": str(e)}, status=500)

        messages.error(request, f"Failed to refresh data: {str(e)}")
        return redirect("transaction_list_v2")


@require_http_methods(["POST"])
@login_required
def clear_transaction_cache_view(request):
    """
    View to clear the transaction cache for the current user.
    """
    user_id = request.user.id
    clear_tx_cache(user_id, force=True)
    return JsonResponse(
        {"status": "success", "message": "Transaction cache cleared successfully."}
    )


__all__ = [
    "TransactionCreateView",
    "TransactionUpdateView",
    "TransactionDeleteView",
    "transactions_json",
    "transaction_bulk_update",
    "transaction_bulk_duplicate",
    "transaction_bulk_delete",
    "transaction_clear_cache",
    "clear_transaction_cache_view",
]
