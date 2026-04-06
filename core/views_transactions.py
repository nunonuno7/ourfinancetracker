"""Transaction list v2 views and helpers.

This module keeps the transactions v2 table endpoints together so
``core.views`` can focus on the remaining areas of the application.
"""

import hashlib
import json
import logging
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import (
    Case,
    CharField,
    Count,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.http import http_date, parse_http_date_safe
from django.utils.timezone import now

from .models import Account, Category, Tag, Transaction
from .utils.date_helpers import parse_safe_date, period_key

logger = logging.getLogger(__name__)

TRANSACTION_TYPE_LABELS = {
    Transaction.Type.INCOME: "Income",
    Transaction.Type.EXPENSE: "Expense",
    Transaction.Type.INVESTMENT: "Investment",
    Transaction.Type.TRANSFER: "Transfer",
    Transaction.Type.ADJUSTMENT: "Adjustment",
}
TRANSACTION_TYPE_LABEL_TO_CODE = {
    label.lower(): code for code, label in TRANSACTION_TYPE_LABELS.items()
}


def get_transaction_list_default_date_range(
    today_value: date | None = None,
) -> tuple[date, date]:
    """Return the shared default date range for the transactions list."""
    today_value = today_value or date.today()
    # Keep the initial view focused on recent history without aging a hard-coded year.
    return date(today_value.year - 2, 1, 1), today_value


def _parse_period_param(period_value: str | None) -> tuple[int, int] | None:
    """Parse a ``YYYY-MM`` string into ``(year, month)``."""
    if not period_value or not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period_value):
        return None

    year, month = period_value.split("-", 1)
    return int(year), int(month)


def _parse_transaction_request_data(request):
    """Return request data for transaction endpoints from GET or JSON POST."""
    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}
    return request.GET


def _request_value(data, *keys):
    """Return the last non-blank request value for any key."""
    for key in keys:
        if hasattr(data, "getlist"):
            values = [value for value in data.getlist(key) if value not in (None, "")]
            if values:
                return values[-1]
            continue

        if key not in data:
            continue

        raw_value = data.get(key)
        if isinstance(raw_value, list):
            values = [value for value in raw_value if value not in (None, "")]
            if values:
                return values[-1]
            continue

        if raw_value not in (None, ""):
            return raw_value

    return None


def _request_list(data, *keys) -> list:
    """Return a normalized list of repeated or array-based request values."""
    values: list = []

    for key in keys:
        if hasattr(data, "getlist"):
            values.extend(data.getlist(key))
            continue

        if key not in data:
            continue

        raw_value = data.get(key)
        if isinstance(raw_value, list):
            values.extend(raw_value)
        else:
            values.append(raw_value)

    normalized: list = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue

        parts = value if isinstance(value, list) else str(value).split(",")
        for part in parts:
            normalized_value = str(part).strip()
            if not normalized_value or normalized_value in seen:
                continue
            seen.add(normalized_value)
            normalized.append(normalized_value)

    return normalized


def _request_bool(value, default: bool = False) -> bool:
    """Parse common truthy/falsey request values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _request_int(
    value, default: int, *, minimum: int = 1, maximum: int | None = None
) -> int:
    """Parse an integer request parameter with bounds and sensible defaults."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if parsed < minimum:
        parsed = minimum
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _parse_decimal_filter(value, label: str) -> Decimal | None:
    """Parse an optional decimal filter and log invalid input once."""
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (ArithmeticError, TypeError, ValueError):
        logger.warning("Invalid %s value '%s'", label, value)
        return None


def _parse_positive_int_filter(value, label: str) -> int | None:
    """Parse an optional positive integer filter and log invalid input once."""
    if value in (None, ""):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s value '%s'", label, value)
        return None

    if parsed <= 0:
        logger.warning("Invalid %s value '%s'", label, value)
        return None
    return parsed


def _parse_positive_int_filters(values: list, label: str) -> list[int]:
    """Parse repeated positive integer filters while preserving request order."""
    parsed_values: list[int] = []
    seen: set[int] = set()
    for value in values:
        parsed = _parse_positive_int_filter(value, label)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        parsed_values.append(parsed)
    return parsed_values


def _normalize_transaction_type_filters(values: list[str]) -> list[str]:
    """Normalize transaction type values from labels/codes to canonical codes."""
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = TRANSACTION_TYPE_LABEL_TO_CODE.get(value.lower(), value)
        if normalized not in TRANSACTION_TYPE_LABELS:
            logger.warning("Invalid type value '%s'", value)
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)
    return normalized_values


def _normalize_transaction_filters(data: dict) -> dict:
    """Normalize request parameters for the transactions v2 endpoints."""
    raw_start = _request_value(data, "date_start", "start_date")
    raw_end = _request_value(data, "date_end", "end_date")
    default_start, default_end = get_transaction_list_default_date_range()

    if not raw_start and not raw_end:
        start_date = default_start
        end_date = default_end
    else:
        start_date = parse_safe_date(raw_start, default_start)
        end_date = parse_safe_date(raw_end, default_end)

    sort_field = str(_request_value(data, "sort_field") or "date").strip().lower()
    if sort_field not in {
        "date",
        "period",
        "type",
        "amount",
        "category",
        "tags",
        "account",
    }:
        sort_field = "date"

    sort_direction = (
        "asc"
        if str(_request_value(data, "sort_direction") or "desc").strip().lower()
        == "asc"
        else "desc"
    )

    type_values = _normalize_transaction_type_filters(_request_list(data, "type"))
    category_ids = _parse_positive_int_filters(
        _request_list(data, "category_id"),
        "category_id",
    )
    account_ids = _parse_positive_int_filters(
        _request_list(data, "account_id"),
        "account_id",
    )

    period_values: list[str] = []
    period_tuples: list[tuple[int, int]] = []
    for period_value in _request_list(data, "period"):
        parsed_period = _parse_period_param(period_value)
        if parsed_period is None:
            logger.warning("Invalid period value '%s'", period_value)
            continue
        period_values.append(period_value)
        period_tuples.append(parsed_period)

    tags_terms = [
        term.strip().lower()
        for term in str(_request_value(data, "tags") or "").split(",")
        if term.strip()
    ]

    return {
        "date_start": start_date,
        "date_end": end_date,
        "page": _request_int(_request_value(data, "page"), 1, minimum=1),
        "page_size": _request_int(
            _request_value(data, "page_size"),
            25,
            minimum=1,
            maximum=1000,
        ),
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "include_system": _request_bool(
            _request_value(data, "include_system"),
            default=False,
        ),
        "type": type_values[0] if len(type_values) == 1 else "",
        "types": type_values,
        "category_id": category_ids[0] if len(category_ids) == 1 else None,
        "category_ids": category_ids,
        "category": str(_request_value(data, "category") or "").strip(),
        "account_id": account_ids[0] if len(account_ids) == 1 else None,
        "account_ids": account_ids,
        "account": str(_request_value(data, "account") or "").strip(),
        "period": period_values[0] if len(period_values) == 1 else "",
        "periods": period_values,
        "period_tuple": period_tuples[0] if len(period_tuples) == 1 else None,
        "period_tuples": period_tuples,
        "search": str(_request_value(data, "search") or "").strip(),
        "amount_min": _parse_decimal_filter(
            _request_value(data, "amount_min"),
            "amount_min",
        ),
        "amount_max": _parse_decimal_filter(
            _request_value(data, "amount_max"),
            "amount_max",
        ),
        "tags_terms": tags_terms,
        "force_refresh": _request_bool(_request_value(data, "force"), default=False),
    }


def _hydrate_initial_filter_labels(user_id: int, initial_filters: dict) -> dict:
    """Add human-readable labels when only filter IDs were explicitly provided."""
    hydrated = dict(initial_filters)

    category_id = hydrated.get("category_id")
    if category_id and not isinstance(category_id, list) and not hydrated.get("category"):
        category_name = (
            Category.objects.filter(user_id=user_id, pk=category_id)
            .values_list("name", flat=True)
            .first()
        )
        if category_name:
            hydrated["category"] = category_name

    account_id = hydrated.get("account_id")
    if account_id and not isinstance(account_id, list) and not hydrated.get("account"):
        account_name = (
            Account.objects.filter(user_id=user_id, pk=account_id)
            .values_list("name", flat=True)
            .first()
        )
        if account_name:
            hydrated["account"] = account_name

    return hydrated


def _initial_transaction_filters_for_view(request) -> dict:
    """Return only explicitly requested filters for the HTML page bootstrap."""
    if request.method != "GET" or not request.GET:
        return {}

    request_data = _parse_transaction_request_data(request)
    normalized = _normalize_transaction_filters(request_data)
    initial_filters = {}

    def has_request_key(*keys) -> bool:
        return any(key in request_data for key in keys)

    def normalized_filter_value(key: str):
        if key == "type":
            return normalized["types"] if len(normalized["types"]) > 1 else normalized["type"]
        if key == "account_id":
            return (
                normalized["account_ids"]
                if len(normalized["account_ids"]) > 1
                else normalized["account_id"]
            )
        if key == "category_id":
            return (
                normalized["category_ids"]
                if len(normalized["category_ids"]) > 1
                else normalized["category_id"]
            )
        if key == "period":
            return (
                normalized["periods"]
                if len(normalized["periods"]) > 1
                else normalized["period"]
            )
        return normalized.get(key)

    if has_request_key("date_start", "start_date"):
        initial_filters["date_start"] = normalized["date_start"].isoformat()
    if has_request_key("date_end", "end_date"):
        initial_filters["date_end"] = normalized["date_end"].isoformat()

    for key in (
        "type",
        "account_id",
        "account",
        "category_id",
        "category",
        "period",
        "amount_min",
        "amount_max",
        "tags",
        "search",
        "page",
        "page_size",
        "sort_field",
        "sort_direction",
    ):
        value = normalized_filter_value(key)
        if has_request_key(key) and value not in (None, "", []):
            initial_filters[key] = value

    return _hydrate_initial_filter_labels(request.user.id, initial_filters)


def _matching_transaction_type_codes(term: str) -> list[str]:
    """Return type codes whose display labels match a search term."""
    term_lower = term.strip().lower()
    if not term_lower:
        return []
    return [
        code
        for code, label in TRANSACTION_TYPE_LABELS.items()
        if term_lower in label.lower()
    ]


def _apply_transactions_v2_filters(
    queryset, filters: dict, exclude_filters: set[str] | None = None
):
    """Apply transactions v2 filters to a queryset."""
    excluded = exclude_filters or set()
    needs_distinct = False

    if not filters["include_system"] and "include_system" not in excluded:
        queryset = queryset.filter(Q(is_system=False) | Q(is_system__isnull=True))

    if filters["types"] and "type" not in excluded:
        queryset = queryset.filter(type__in=filters["types"])

    if filters["category_ids"] and "category" not in excluded:
        queryset = queryset.filter(category_id__in=filters["category_ids"])
    elif filters["category"] and "category" not in excluded:
        # Temporary compatibility for older deep links/session state.
        # New callers should send category_id instead of partial names.
        queryset = queryset.filter(category__name__icontains=filters["category"])

    if filters["account_ids"] and "account" not in excluded:
        queryset = queryset.filter(account_id__in=filters["account_ids"])
    elif filters["account"] and "account" not in excluded:
        # Temporary compatibility for older deep links/session state.
        # New callers should send account_id instead of partial names.
        queryset = queryset.filter(account__name__icontains=filters["account"])

    if filters["period_tuples"] and "period" not in excluded:
        period_query = Q()
        for year, month in filters["period_tuples"]:
            period_query |= Q(period__year=year, period__month=month)
        queryset = queryset.filter(period_query)

    if filters["amount_min"] is not None and "amount_min" not in excluded:
        queryset = queryset.filter(amount__gte=filters["amount_min"])

    if filters["amount_max"] is not None and "amount_max" not in excluded:
        queryset = queryset.filter(amount__lte=filters["amount_max"])

    if filters["search"] and "search" not in excluded:
        search_term = filters["search"]
        search_query = (
            Q(category__name__icontains=search_term)
            | Q(account__name__icontains=search_term)
            | Q(tags__name__icontains=search_term)
        )
        matching_types = _matching_transaction_type_codes(search_term)
        if matching_types:
            search_query |= Q(type__in=matching_types)
        queryset = queryset.filter(search_query)
        needs_distinct = True

    if filters["tags_terms"] and "tags" not in excluded:
        tags_query = Q()
        for tag_term in filters["tags_terms"]:
            tags_query |= Q(tags__name__icontains=tag_term)
        queryset = queryset.filter(tags_query)
        needs_distinct = True

    if needs_distinct:
        queryset = queryset.distinct()

    return queryset


def _transactions_v2_cache_key(
    user_id: int,
    filters: dict,
    *,
    suffix: str = "list",
    include_view_state: bool = True,
) -> str:
    """Build a short cache key that stays compatible with existing invalidation."""
    cache_payload = {
        "suffix": suffix,
        "date_start": filters["date_start"].isoformat(),
        "date_end": filters["date_end"].isoformat(),
        "include_system": filters["include_system"],
        "types": filters["types"],
        "category_ids": filters["category_ids"],
        "category": filters["category"],
        "account_ids": filters["account_ids"],
        "account": filters["account"],
        "periods": filters["periods"],
        "search": filters["search"],
        "amount_min": (
            str(filters["amount_min"]) if filters["amount_min"] is not None else ""
        ),
        "amount_max": (
            str(filters["amount_max"]) if filters["amount_max"] is not None else ""
        ),
        "tags_terms": filters["tags_terms"],
    }
    if include_view_state:
        cache_payload.update(
            {
                "page": filters["page"],
                "page_size": filters["page_size"],
                "sort_field": filters["sort_field"],
                "sort_direction": filters["sort_direction"],
            }
        )
    digest = hashlib.sha256(
        json.dumps(cache_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"tx_v2_{user_id}_{suffix}_{digest}"


def _build_cached_json_response(
    request,
    cache_entry: dict,
    *,
    force_refresh: bool = False,
) -> HttpResponse | JsonResponse:
    """Serve JSON with conditional ETag/Last-Modified support."""
    last_modified = cache_entry["last_modified"]
    etag = cache_entry["etag"]

    if not force_refresh and request.headers.get("If-None-Match") == etag:
        return HttpResponse(status=304)

    ims = request.headers.get("If-Modified-Since")
    if not force_refresh and ims:
        ims_ts = parse_http_date_safe(ims)
        if ims_ts is not None and int(last_modified.timestamp()) <= ims_ts:
            return HttpResponse(status=304)

    response = JsonResponse(cache_entry["response_data"])
    response["ETag"] = etag
    response["Last-Modified"] = http_date(last_modified.timestamp())
    response["Cache-Control"] = "private, max-age=0, must-revalidate"
    return response


def _make_cached_json_entry(response_data: dict, last_modified) -> dict:
    """Build a cache entry with serialized metadata for conditional requests."""
    response_json = json.dumps(response_data, sort_keys=True, cls=DjangoJSONEncoder)
    return {
        "response_data": response_data,
        "etag": hashlib.md5(response_json.encode("utf-8")).hexdigest(),
        "last_modified": last_modified,
    }


def _annotate_transactions_v2_sort_fields(queryset):
    """Annotate reusable fields for UI sorting without materializing full datasets."""
    first_tag_name = Subquery(
        Tag.objects.filter(transaction_links__transaction=OuterRef("pk"))
        .order_by("name")
        .values("name")[:1]
    )

    return queryset.annotate(
        sort_category=Lower(Coalesce("category__name", Value(""))),
        sort_account=Lower(Coalesce("account__name", Value(""))),
        sort_type=Case(
            *[
                When(type=code, then=Value(label.lower()))
                for code, label in TRANSACTION_TYPE_LABELS.items()
            ],
            default=Lower(Coalesce("type", Value(""))),
            output_field=CharField(),
        ),
        sort_tags=Lower(Coalesce(first_tag_name, Value(""))),
        sort_period_year=Coalesce("period__year", Value(0)),
        sort_period_month=Coalesce("period__month", Value(0)),
    )


def _order_transactions_v2_queryset(queryset, filters: dict):
    """Apply UI sorting to the filtered transactions queryset."""
    queryset = _annotate_transactions_v2_sort_fields(queryset)
    direction = "-" if filters["sort_direction"] == "desc" else ""
    sort_field = filters["sort_field"]

    if sort_field == "amount":
        order_by = [f"{direction}amount", f"{direction}date", f"{direction}id"]
    elif sort_field == "type":
        order_by = [f"{direction}sort_type", f"{direction}date", f"{direction}id"]
    elif sort_field == "category":
        order_by = [
            f"{direction}sort_category",
            f"{direction}date",
            f"{direction}id",
        ]
    elif sort_field == "account":
        order_by = [
            f"{direction}sort_account",
            f"{direction}date",
            f"{direction}id",
        ]
    elif sort_field == "tags":
        order_by = [f"{direction}sort_tags", f"{direction}date", f"{direction}id"]
    elif sort_field == "period":
        order_by = [
            f"{direction}sort_period_year",
            f"{direction}sort_period_month",
            f"{direction}date",
            f"{direction}id",
        ]
    else:
        order_by = [f"{direction}date", f"{direction}id"]

    return queryset.order_by(*order_by)


def _transactions_v2_filter_options(user_id: int, filters: dict) -> dict:
    """Return dropdown options based on the current filter context."""
    cache_key = _transactions_v2_cache_key(
        user_id,
        filters,
        suffix="filters",
        include_view_state=False,
    )

    if not filters["force_refresh"]:
        cached_options = cache.get(cache_key)
        if cached_options is not None:
            logger.debug(
                "[transactions_json_v2] filter options cache hit user=%s",
                user_id,
            )
            return cached_options

    base_qs = Transaction.objects.filter(
        user_id=user_id,
        date__range=(filters["date_start"], filters["date_end"]),
    )

    def filtered_qs(excluded_filter: str):
        return _apply_transactions_v2_filters(base_qs, filters, {excluded_filter})

    type_values = [
        {
            "value": code,
            "label": TRANSACTION_TYPE_LABELS.get(code, code),
        }
        for code in sorted(
            {
                code
                for code in filtered_qs("type").values_list("type", flat=True).distinct()
                if code
            },
            key=lambda code: TRANSACTION_TYPE_LABELS.get(code, code),
        )
    ]

    category_values = [
        {"value": category_id, "label": category_name}
        for category_id, category_name in (
            filtered_qs("category")
            .exclude(category__name__isnull=True)
            .exclude(category__name="")
            .values_list("category__id", "category__name")
            .order_by("category__name")
            .distinct()
        )
    ]

    account_values = [
        {"value": account_id, "label": account_name}
        for account_id, account_name in (
            filtered_qs("account")
            .exclude(account__name__isnull=True)
            .exclude(account__name="")
            .values_list("account__id", "account__name")
            .order_by("account__name")
            .distinct()
        )
    ]

    period_values = [
        {
            "value": period_key(year, month),
            "label": period_key(year, month),
        }
        for year, month in (
            filtered_qs("period")
            .exclude(period__year__isnull=True)
            .values_list("period__year", "period__month")
            .order_by("-period__year", "-period__month")
            .distinct()
        )
    ]

    filter_options = {
        "types": type_values,
        "categories": category_values,
        "accounts": account_values,
        "periods": period_values,
    }
    cache.set(cache_key, filter_options, timeout=300)
    return filter_options


def _format_transaction_amount_v2(amount: Decimal, currency_symbol: str) -> str:
    """Preserve the existing table formatting for transaction amounts."""
    normalized_amount = f"\u20ac {abs(amount):,.2f}".replace(",", "X").replace(".", ",")
    normalized_amount = normalized_amount.replace("X", ".")
    return f"{normalized_amount} {currency_symbol}"


def _serialize_transactions_v2(transactions) -> list[dict]:
    """Serialize paginated transaction objects for the v2 table."""
    serialized = []
    for tx in transactions:
        currency_symbol = "\u20ac"
        if tx.account and tx.account.currency and tx.account.currency.symbol:
            currency_symbol = tx.account.currency.symbol

        period_value = ""
        year = None
        month = None
        if tx.period_id and tx.period:
            year = tx.period.year
            month = tx.period.month
            period_value = period_key(year, month)

        serialized.append(
            {
                "id": tx.id,
                "date": tx.date.isoformat(),
                "year": year,
                "month": month,
                "type": TRANSACTION_TYPE_LABELS.get(tx.type, tx.type),
                "amount": float(tx.amount),
                "amount_formatted": _format_transaction_amount_v2(
                    tx.amount, currency_symbol
                ),
                "category_id": tx.category_id,
                "category": tx.category.name if tx.category else "",
                "account_id": tx.account_id,
                "account": tx.account.name if tx.account else "No account",
                "currency": currency_symbol,
                "tags": ", ".join(sorted(tag.name for tag in tx.tags.all())),
                "is_system": tx.is_system,
                "editable": tx.editable,
                "is_estimated": tx.is_estimated,
                "period": period_value,
            }
        )

    return serialized


@login_required
def clear_session_flag(request):
    """Clear session flags."""
    if "transaction_changed" in request.session:
        del request.session["transaction_changed"]
    return JsonResponse({"success": True})


@login_required
def transaction_list_v2(request):
    """Modern transaction list view."""
    default_start, default_end = get_transaction_list_default_date_range()
    context = {
        "force_refresh_once": request.session.pop("transaction_changed", False),
        "initial_filters": _initial_transaction_filters_for_view(request),
        "filter_defaults": {
            "date_start": default_start.isoformat(),
            "date_end": default_end.isoformat(),
        },
        "default_date_start": default_start.isoformat(),
        "default_date_end": default_end.isoformat(),
    }
    return render(request, "core/transaction_list_v2.html", context)


@login_required
def transactions_json_v2(request):
    """JSON API for the transactions v2 table using database-side filtering."""
    user_id = request.user.id
    filters = _normalize_transaction_filters(_parse_transaction_request_data(request))
    cache_key = _transactions_v2_cache_key(user_id, filters, suffix="list")

    if not filters["force_refresh"]:
        cached_entry = cache.get(cache_key)
        if cached_entry is not None:
            logger.debug(
                "[transactions_json_v2] cache hit user=%s page=%s sort=%s/%s",
                user_id,
                filters["page"],
                filters["sort_field"],
                filters["sort_direction"],
            )
            return _build_cached_json_response(
                request,
                cached_entry,
                force_refresh=False,
            )

    logger.debug(
        "[transactions_json_v2] query user=%s page=%s page_size=%s sort=%s/%s",
        user_id,
        filters["page"],
        filters["page_size"],
        filters["sort_field"],
        filters["sort_direction"],
    )

    base_queryset = Transaction.objects.filter(
        user_id=user_id,
        date__range=(filters["date_start"], filters["date_end"]),
    )
    filtered_queryset = _apply_transactions_v2_filters(base_queryset, filters)
    query_metrics = filtered_queryset.aggregate(
        total_count=Count("pk", distinct=True),
        max_updated=Max("updated_at"),
    )
    total_count = query_metrics["total_count"] or 0
    last_modified = query_metrics["max_updated"] or now()

    start_idx = (filters["page"] - 1) * filters["page_size"]
    end_idx = start_idx + filters["page_size"]
    page_queryset = (
        _order_transactions_v2_queryset(filtered_queryset, filters)
        .select_related("category", "account__currency", "period")
        .prefetch_related("tags")
    )
    page_transactions = list(page_queryset[start_idx:end_idx])

    response_data = {
        "transactions": _serialize_transactions_v2(page_transactions),
        "total_count": total_count,
        "current_page": filters["page"],
        "page_size": filters["page_size"],
        "filters": _transactions_v2_filter_options(user_id, filters),
    }

    if total_count == 0:
        total_tx_count = Transaction.objects.filter(user_id=user_id).count()
        logger.warning(
            "[transactions_json_v2] no transactions for user=%s in range %s..%s (user total=%s)",
            user_id,
            filters["date_start"],
            filters["date_end"],
            total_tx_count,
        )

    cache_entry = _make_cached_json_entry(response_data, last_modified)
    cache.set(cache_key, cache_entry, timeout=300)
    return _build_cached_json_response(
        request,
        cache_entry,
        force_refresh=filters["force_refresh"],
    )


@login_required
def transactions_totals_v2(request):
    """Get transaction totals using the same database-side filters as the table."""
    user_id = request.user.id
    filters = _normalize_transaction_filters(_parse_transaction_request_data(request))
    cache_key = _transactions_v2_cache_key(
        user_id,
        filters,
        suffix="totals",
        include_view_state=False,
    )

    if not filters["force_refresh"]:
        cached_entry = cache.get(cache_key)
        if cached_entry is not None:
            logger.debug("[transactions_totals_v2] cache hit user=%s", user_id)
            return _build_cached_json_response(
                request,
                cached_entry,
                force_refresh=False,
            )

    logger.debug(
        "[transactions_totals_v2] query user=%s range=%s..%s",
        user_id,
        filters["date_start"],
        filters["date_end"],
    )

    queryset = Transaction.objects.filter(
        user_id=user_id,
        date__range=(filters["date_start"], filters["date_end"]),
    )
    filtered_queryset = _apply_transactions_v2_filters(queryset, filters)
    aggregates = filtered_queryset.aggregate(
        income=Sum("amount", filter=Q(type=Transaction.Type.INCOME)),
        expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE)),
        investments=Sum("amount", filter=Q(type=Transaction.Type.INVESTMENT)),
        transfers=Sum("amount", filter=Q(type=Transaction.Type.TRANSFER)),
        last_modified=Max("updated_at"),
    )

    totals = {
        "income": aggregates["income"] or Decimal("0"),
        "expenses": aggregates["expenses"] or Decimal("0"),
        "investments": aggregates["investments"] or Decimal("0"),
        "transfers": aggregates["transfers"] or Decimal("0"),
    }
    totals["balance"] = totals["income"] - totals["expenses"]

    rounded_totals = {
        key: float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        for key, value in totals.items()
    }
    last_modified = aggregates["last_modified"] or now()

    cache_entry = _make_cached_json_entry(rounded_totals, last_modified)
    cache.set(cache_key, cache_entry, timeout=300)
    return _build_cached_json_response(
        request,
        cache_entry,
        force_refresh=filters["force_refresh"],
    )


__all__ = [
    "clear_session_flag",
    "transaction_list_v2",
    "transactions_json_v2",
    "transactions_totals_v2",
]
