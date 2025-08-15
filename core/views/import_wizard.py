from __future__ import annotations

import pandas as pd
from io import BytesIO
from typing import List, Dict, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from ..utils.cache_helpers import clear_tx_cache
from ..utils.import_helpers import BulkTransactionImporter

REQUIRED_COLUMNS = ["Date", "Type", "Amount", "Category", "Account"]
VALID_TYPES = {"IN", "EX", "IV", "TR", "AJ"}


def _parse_file(uploaded_file) -> Optional[pd.DataFrame]:
    """Return a DataFrame for the uploaded Excel file or ``None`` if invalid."""
    try:
        data = uploaded_file.read()
        return pd.read_excel(BytesIO(data))
    except Exception:  # broad catch to surface feedback to the user
        return None


def _validate_rows(df: pd.DataFrame) -> Dict[str, List]:
    errors = []
    valid_rows = []
    for idx, row in df.iterrows():
        row_errors = []
        for col in REQUIRED_COLUMNS:
            if pd.isna(row.get(col)) or str(row.get(col)).strip() == "":
                row_errors.append(f"Missing {col}")
        try:
            pd.to_datetime(row.get("Date")).date()
        except Exception:
            row_errors.append("Invalid Date")
        t = str(row.get("Type")).strip().upper()
        if t not in VALID_TYPES:
            row_errors.append("Invalid Type")
        try:
            float(row.get("Amount"))
        except Exception:
            row_errors.append("Invalid Amount")
        if row_errors:
            errors.append({"index": idx + 2, "errors": "; ".join(row_errors)})
        else:
            valid_rows.append({
                "Date": pd.to_datetime(row.get("Date")).date().isoformat(),
                "Type": t,
                "Amount": float(row.get("Amount")),
                "Category": str(row.get("Category")).strip(),
                "Account": str(row.get("Account")).strip(),
                "Notes": row.get("Notes", ""),
                "Tags": row.get("Tags", ""),
            })
    return {"valid": valid_rows, "errors": errors}


@login_required
def upload(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.FILES.get("file"):
        df = _parse_file(request.FILES["file"])
        if df is None:
            messages.error(request, "Could not read Excel file")
            return redirect("transaction_import_wizard")
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            messages.error(request, f"Missing columns: {', '.join(missing)}")
            return redirect("transaction_import_wizard")
        result = _validate_rows(df)
        request.session["import_wizard_data"] = result["valid"]
        context = {
            "valid_count": len(result["valid"]),
            "error_rows": result["errors"],
            "total": len(df),
        }
        return render(request, "core/import_wizard_preview.html", context)
    return render(request, "core/import_wizard_upload.html")


@login_required
def commit(request: HttpRequest) -> HttpResponse:
    rows = request.session.get("import_wizard_data")
    if request.method != "POST" or rows is None:
        return redirect("transaction_import_wizard")
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    importer = BulkTransactionImporter(request.user, batch_size=100)
    result = importer.import_dataframe(df)
    clear_tx_cache(request.user.id, force=True)
    messages.success(request, f"Imported {result['imported']} transactions")
    del request.session["import_wizard_data"]
    return redirect(reverse("transaction_list"))
