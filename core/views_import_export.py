"""Import and export views for transactions and combined data."""

import logging
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from celery.exceptions import OperationalError
from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from .models import Transaction, User
from .utils.date_helpers import parse_optional_safe_date, parse_safe_date
from .views_account_balance import _account_balances_export_dataframe

logger = logging.getLogger(__name__)


def _get_import_transactions_task():
    """
    Resolve the import task via ``core.views`` so existing test patches on
    ``core.views.import_transactions_task`` keep working after modularization.
    """
    from . import views as core_views

    return core_views.import_transactions_task


@login_required
def import_transactions_xlsx(request):
    """Import transactions from Excel file asynchronously."""
    if request.method == "POST":
        try:
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                messages.error(request, "No file uploaded.")
                return render(request, "core/import_form.html")

            logger.info(
                f"[import_transactions_xlsx] Starting import for user {request.user.id}, file: {uploaded_file.name}"
            )

            if not uploaded_file.name.lower().endswith(".xlsx"):
                messages.error(
                    request, "Invalid file extension. Please upload an .xlsx file."
                )
                return render(request, "core/import_form.html")

            allowed_mime = {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            }
            if uploaded_file.content_type not in allowed_mime:
                messages.error(
                    request, "Invalid file type. Please upload a valid Excel file."
                )
                return render(request, "core/import_form.html")

            max_upload_size = 5 * 1024 * 1024
            if uploaded_file.size > max_upload_size:
                messages.error(request, "File too large. Maximum size is 5MB.")
                return render(request, "core/import_form.html")

            tmp_dir = Path(settings.MEDIA_ROOT) / "imports"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / f"{uuid.uuid4()}.xlsx"
            with tmp_path.open("wb+") as dest:
                for chunk in uploaded_file.chunks():
                    dest.write(chunk)

            result = None
            import_task = _get_import_transactions_task()
            use_async = (
                not settings.DEBUG
                and not settings.CELERY_BROKER_URL.startswith("memory")
            )

            if use_async:
                try:
                    import_task.delay(request.user.id, str(tmp_path))
                    messages.info(
                        request,
                        "Import started in background. You will be notified when it completes.",
                    )
                    return redirect("transaction_list")
                except (OperationalError, ConnectionError) as exc:
                    logger.exception(
                        "Celery unavailable, running import synchronously",
                        exc_info=exc,
                    )
                    result = import_task(request.user.id, str(tmp_path))
            else:
                result = import_task(request.user.id, str(tmp_path))

            imported = result.get("imported", 0) if isinstance(result, dict) else 0
            messages.success(request, f"Import completed: {imported} transactions.")
            return redirect("transaction_list")

        except Exception as exc:
            logger.error(f"Import error for user {request.user.id}: {exc}")
            messages.error(request, f"Import failed: {str(exc)}")

    return render(request, "core/import_form.html")


def import_transactions_template(request):
    """Download Excel template for transaction import."""
    data = {
        "Date": ["2025-01-01", "2025-01-02", "2025-01-03"],
        "Type": ["Income", "Expense", "Investment"],
        "Amount": [1000.00, -50.00, -200.00],
        "Category": ["Salary", "Food", "Stocks"],
        "Account": ["Savings", "Savings", "Investments"],
        "Tags": ["monthly", "daily", "monthly"],
        "Notes": ["Monthly salary", "Lunch", "ETF purchase"],
    }

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Transactions", index=False)

    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        'attachment; filename="transaction_import_template.xlsx"'
    )
    return response


@login_required
def task_status(request, task_id):
    """Return status for a Celery task."""
    result = AsyncResult(task_id)
    data = {"task_id": task_id, "status": result.status}
    if result.status == "SUCCESS":
        data["result"] = result.result
    return JsonResponse(data)


def _transactions_export_dataframe(
    user: User, start_date: date | None = None, end_date: date | None = None
) -> pd.DataFrame:
    """Build the transactions export dataframe with optional date filters."""
    queryset = (
        Transaction.objects.filter(user=user)
        .select_related("category", "account")
        .prefetch_related("tags")
        .order_by("-date", "-id")
    )

    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    rows = []
    for tx in queryset:
        rows.append(
            [
                tx.date,
                tx.type,
                tx.amount,
                tx.category.name if tx.category_id else "",
                tx.account.name if tx.account_id else "",
                ", ".join(sorted(tag.name for tag in tx.tags.all())),
                tx.notes or "",
            ]
        )

    return pd.DataFrame(
        rows,
        columns=["Date", "Type", "Amount", "Category", "Account", "Tags", "Notes"],
    )


def _export_filename(
    prefix: str, start_date: date | None = None, end_date: date | None = None
) -> str:
    """Return a filename that reflects whether the export is filtered."""
    if start_date and end_date:
        return f"{prefix}_{start_date}_{end_date}.xlsx"
    if start_date:
        return f"{prefix}_{start_date}_onwards.xlsx"
    if end_date:
        return f"{prefix}_until_{end_date}.xlsx"
    return f"{prefix}_all.xlsx"


@login_required
def export_transactions_xlsx(request):
    """Export transactions to Excel."""
    start_date = parse_safe_date(
        request.GET.get("date_start"), date(date.today().year, 1, 1)
    )
    end_date = parse_safe_date(request.GET.get("date_end"), date.today())

    df = _transactions_export_dataframe(
        request.user, start_date=start_date, end_date=end_date
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Transactions", index=False)

    output.seek(0)

    filename = f"transactions_{start_date}_{end_date}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_data_xlsx(request):
    """Export both transactions and account balances to a single Excel file."""
    start_date = parse_optional_safe_date(request.GET.get("date_start"))
    end_date = parse_optional_safe_date(request.GET.get("date_end"))

    tx_df = _transactions_export_dataframe(
        request.user, start_date=start_date, end_date=end_date
    )
    bal_df = _account_balances_export_dataframe(request.user)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tx_df.to_excel(writer, sheet_name="Transactions", index=False)
        bal_df.to_excel(writer, sheet_name="Account_Balances", index=False)

    output.seek(0)

    filename = _export_filename("data_export", start_date, end_date)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


__all__ = [
    "import_transactions_xlsx",
    "import_transactions_template",
    "task_status",
    "export_transactions_xlsx",
    "export_data_xlsx",
]
