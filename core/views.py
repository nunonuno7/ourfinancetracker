"""
Django *views* for **ourfinancetracker** – versão limpa.

• Imports organizados e sem duplicações
• Cache segura (isolada por utilizador + intervalo) via Django cache backend
• Helpers extra em `core.utils`
• @csrf_exempt removido de endpoints não‑públicos
"""

from __future__ import annotations

# ─────────────────────────────── Imports ────────────────────────────────
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, Iterable
from urllib.parse import urlencode

import pandas as pd
from psycopg2.extras import execute_values
from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection, transaction as db_transaction
from django.db.models import QuerySet
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
    View,
)

from core.forms import (
    AccountBalanceFormSet,
    AccountForm,
    CategoryForm,
    CustomUserCreationForm,
    TransactionForm,
    TransactionImportForm,
)
from core.mixins import UserInFormKwargsMixin
from core.models import (
    Account,
    AccountBalance,
    Category,
    DatePeriod,
    Tag,
    Transaction,
)
from core.utils.cache_helpers import clear_tx_cache
from core.utils.supabase_rpc import call_rpc
import logging
logging.getLogger("django.server").setLevel(logging.WARNING)  # ou logging.ERROR

################################################################################
#                               Menu config API                                #
################################################################################


@login_required
@require_GET
def account_balances_pivot_json(request):
    """Retorna saldos agregados por tipo/moeda num pivot ready‑to‑chart."""
    user_id = request.user.id
    with connection.cursor() as cursor:
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
        return JsonResponse({"columns": [], "rows": []})

    df = pd.DataFrame(
        rows, columns=["type", "currency", "year", "month", "balance"]
    )
    df["period"] = pd.to_datetime(
        dict(year=df.year, month=df.month, day=1)
    ).dt.strftime("%b/%y")

    pivot = (
        df.pivot_table(
            index=["type", "currency"],
            columns="period",
            values="balance",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index(axis=1)
        .reset_index()
    )

    return JsonResponse({"columns": list(pivot.columns), "rows": pivot.to_dict("records")})




class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        ctx["periods"] = DatePeriod.objects.order_by("-year", "-month")
        start_period = self.request.GET.get("start-period")
        end_period = self.request.GET.get("end-period")

        txs = Transaction.objects.filter(user=user).select_related("period", "account")
        bal = AccountBalance.objects.filter(account__user=user).select_related("period", "account__account_type")

        df_tx = pd.DataFrame.from_records(
            txs.values("date", "type", "amount", "period__year", "period__month")
        )
        df_bal = pd.DataFrame.from_records(
            bal.values("period__year", "period__month", "reported_balance", "account__account_type__name")
        )

        df_tx["period"] = (
            df_tx["period__year"].astype(str)
            + "-"
            + df_tx["period__month"].astype(str).str.zfill(2)
        )
        df_bal["period"] = (
            df_bal["period__year"].astype(str)
            + "-"
            + df_bal["period__month"].astype(str).str.zfill(2)
        )

        if start_period and end_period:
            df_tx = df_tx[(df_tx["period"] >= start_period) & (df_tx["period"] <= end_period)]
            df_bal = df_bal[(df_bal["period"] >= start_period) & (df_bal["period"] <= end_period)]

        df_invest = df_bal[df_bal["account__account_type__name"].str.lower() == "investment"]
        patrimonio_mes = df_invest.groupby("period")["reported_balance"].sum()

        patrimonio_final = float(patrimonio_mes.iloc[-1]) if not patrimonio_mes.empty else 0
        patrimonio_inicial = float(patrimonio_mes.iloc[0]) if not patrimonio_mes.empty else 0
        aumento_patrimonio = patrimonio_final - patrimonio_inicial
        aumento_medio = patrimonio_mes.diff().dropna().mean() if len(patrimonio_mes) > 1 else 0

        df_income = df_tx[df_tx["type"] == "IN"]
        receita_mes = df_income.groupby("period")["amount"].sum().astype(float)
        receita_media = receita_mes.mean() if not receita_mes.empty else 0

        df_saving = df_bal[df_bal["account__account_type__name"].str.lower() == "savings"]
        saving_mes = df_saving.groupby("period")["reported_balance"].sum().astype(float)
        periods = sorted(set(receita_mes.index) & set(saving_mes.index))
        despesas_estimadas: list[float] = []
        for i in range(len(periods) - 1):
            p, p1 = periods[i], periods[i + 1]
            despesas_estimadas.append(saving_mes[p] - saving_mes[p1] + receita_mes.get(p, 0))
        despesa_media = pd.Series(despesas_estimadas).mean() if despesas_estimadas else 0

        total_investido = float(df_tx[df_tx["type"] == "IV"]["amount"].sum())
        n_meses = max(len(receita_mes), 1)
        poupanca_media = receita_media - despesa_media - total_investido / n_meses

        ctx["kpis"] = {
            "patrimonio": f"{patrimonio_final:,.0f} €",
            "aumento": f"{aumento_patrimonio:,.0f} €",
            "capital": f"{total_investido:,.0f} €",
            "despesa_media": f"{despesa_media:,.0f} €",
            "receita_media": f"{receita_media:,.0f} €",
            "aumento_riqueza": f"{aumento_medio:,.0f} €",
            "poupanca_media": f"{poupanca_media:,.0f} €",
        }
        return ctx



@login_required
def menu_config(request):
    return JsonResponse(
        {
            "username": request.user.username,
            "links": [
                {"name": "Dashboard", "url": reverse("transaction_list")},
                {"name": "New Transaction", "url": reverse("transaction_create")},
                {"name": "Categories", "url": reverse("category_list")},
                {"name": "Account Balances", "url": reverse("account_balance")},
            ],
        }
    )


################################################################################
#                               Shared mix‑ins                                 #
################################################################################


class OwnerQuerysetMixin(LoginRequiredMixin):
    """Limits queryset to objects owned by the current user."""

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        qs: QuerySet = super().get_queryset()  # type: ignore[misc]
        return qs.filter(user=self.request.user)



################################################################################
#                             Transaction views                                #
################################################################################

class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "core/transaction_list.html"
    context_object_name = "transactions"

    def get_queryset(self):  # type: ignore[override]
        return Transaction.objects.filter(user=self.request.user).order_by("-date")



class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):
        self.object = form.save()

        # 🔁 Limpa cache ao criar nova transação
        from core.utils.cache_helpers import clear_tx_cache
        clear_tx_cache(self.request.user.id)

        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):  # opcional, mas ajuda no debug com HTMX
        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        context["accounts"] = Account.objects.filter(user=user).order_by("name")

        # ⚠️ Importante: adicionar a lista de categorias para o Tom Select
        context["category_list"] = list(
            Category.objects.filter(user=user).values_list("name", flat=True)
        )

        return context



@require_GET
@login_required
def period_autocomplete(request):
    q = request.GET.get("q", "")
    periods = DatePeriod.objects.order_by("-year", "-month")
    if q:
        try:
            y, m = map(int, q.split("-"))
            periods = periods.filter(year=y, month=m)
        except Exception:
            periods = periods.none()
    return JsonResponse(
        [{"value": f"{p.year}-{p.month:02}", "display": p.label} for p in periods], safe=False
    )

@login_required
def transaction_clear_cache(request):
    clear_tx_cache(request.user.id)

    # Se for pedido AJAX, devolve JSON simples (útil para fetch/htmx)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True})

    # Caso contrário, redireciona normalmente com mensagem
    messages.success(request, "✅ Cache limpa.")
    return redirect("transaction_list")


# Cache key helper
def _cache_key(user_id: int, start: date, end: date) -> str:
    return f"tx_cache_user_{user_id}_{start}_{end}"



def parse_safe_date(value: str | None, fallback: date) -> date:
    """Tenta converter *value* para `date` em formatos comuns."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value or "", fmt).date()
        except (ValueError, TypeError):
            continue
    return fallback


@login_required
@require_GET
def transactions_json(request):
    import logging
    import pandas as pd

    logging.getLogger("django.server").setLevel(logging.WARNING)
    user_id = request.user.id

    # 🗓️ Datas de início e fim
    raw_start = request.GET.get("date_start")
    raw_end = request.GET.get("date_end")
    start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
    end_date = parse_safe_date(raw_end, date.today())

    if not start_date or not end_date:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    print(f"📅 Intervalo: {start_date} → {end_date}")

    # ✅ Cache segura por utilizador + intervalo
    raw_key = f"tx_cache_user_{user_id}_{start_date}_{end_date}"
    cache_key = cache.make_key(raw_key)
    print(f"🔑 A aceder ao cache_key: {cache_key}")

    cached_df = cache.get(cache_key)

    if cached_df is not None:
        print("✅ Cache segura usada via Django")
        df = cached_df.copy()
    else:
        print("📅 Query SQL nova (cache ausente ou expirada)")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                       COALESCE(cat.name, '') AS category,
                       COALESCE(acc.name, '') AS account,
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
            """, [user_id, start_date, end_date])
            rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            "id", "date", "year", "month", "type", "amount",
            "category", "account", "currency", "tags"
        ])
        cache.set(raw_key, df.copy(), timeout=300)

    # 🧠 Preparar colunas
    df["date"] = df["date"].astype(str)
    df["period"] = df["year"].astype(str) + "-" + df["month"].astype(int).astype(str).str.zfill(2)
    df["type"] = df["type"].map(dict(Transaction.Type.choices)).fillna(df["type"])
    df["amount_float"] = df["amount"].astype(float)

    # 📊 Cópias para cada filtro (excluindo ele próprio)
    df_for_type = df.copy()
    df_for_category = df.copy()
    df_for_account = df.copy()
    df_for_period = df.copy()

    # 🪟 Filtros recebidos
    tx_type = request.GET.get("type", "").strip()
    category = request.GET.get("category", "").strip()
    account = request.GET.get("account", "").strip()
    period = request.GET.get("period", "").strip()
    search = request.GET.get("search[value]", "").strip()

    if tx_type:
        df = df[df["type"] == tx_type]
        df_for_category = df_for_category[df_for_category["type"] == tx_type]
        df_for_account = df_for_account[df_for_account["type"] == tx_type]
        df_for_period = df_for_period[df_for_period["type"] == tx_type]

    if category:
        df = df[df["category"].str.contains(category, case=False, na=False)]
        df_for_type = df_for_type[df_for_type["category"].str.contains(category, case=False, na=False)]
        df_for_account = df_for_account[df_for_account["category"].str.contains(category, case=False, na=False)]
        df_for_period = df_for_period[df_for_period["category"].str.contains(category, case=False, na=False)]

    if account:
        df = df[df["account"].str.contains(account, case=False, na=False)]
        df_for_type = df_for_type[df_for_type["account"].str.contains(account, case=False, na=False)]
        df_for_category = df_for_category[df_for_category["account"].str.contains(account, case=False, na=False)]
        df_for_period = df_for_period[df_for_period["account"].str.contains(account, case=False, na=False)]

    if period:
        try:
            y, m = map(int, period.split("-"))
            df = df[(df["year"] == y) & (df["month"] == m)]
            df_for_type = df_for_type[(df_for_type["year"] == y) & (df_for_type["month"] == m)]
            df_for_category = df_for_category[(df_for_category["year"] == y) & (df_for_category["month"] == m)]
            df_for_account = df_for_account[(df_for_account["year"] == y) & (df_for_account["month"] == m)]
        except Exception as e:
            print(f"❌ Erro no filtro por período: {e}")

    if search:
        df = df[
            df["category"].str.contains(search, case=False, na=False) |
            df["account"].str.contains(search, case=False, na=False) |
            df["type"].str.contains(search, case=False, na=False) |
            df["tags"].str.contains(search, case=False, na=False)]

    # 🔢 Categorias e períodos com base nos dados visíveis (sem filtro próprio)
    unique_types = sorted(df_for_type["type"].dropna().unique())
    unique_categories = sorted(df_for_category["category"].dropna().unique())
    unique_accounts = sorted(df_for_account["account"].dropna().unique())
    available_periods = sorted(df_for_period["period"].dropna().unique(), reverse=True)

    # 🔄 Ordenação
    order_col = request.GET.get("order[0][column]", "1")
    order_dir = request.GET.get("order[0][dir]", "desc")
    ascending = order_dir != "desc"
    column_map = {
        "0": "period", "1": "date", "2": "type",
        "3": "amount_float", "4": "category", "5": "tags", "6": "account"
    }
    sort_col = column_map.get(order_col, "date")
    if sort_col in df.columns:
        try:
            df.sort_values(by=sort_col, ascending=ascending, inplace=True)
        except Exception as e:
            print(f"⚠️ Erro ao ordenar por {sort_col}: {e}")

    # 💶 Formatar montante
    df["amount"] = df.apply(lambda r: f"€ {r['amount_float']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {r['currency']}", axis=1)

    # 🏷️ Formatar tags HTML
    def format_tags(raw):
        if not raw or not isinstance(raw, str): return "–"
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        return " ".join(f"<span class='badge bg-secondary'>{t}</span>" for t in tags) if tags else "–"
    df["tags"] = df["tags"].astype(str).apply(format_tags)

    # 🔗 Ações HTML
    csrf = request.COOKIES.get("csrftoken", "")
    df["actions"] = df.apply(lambda r: f"""
        <div class='d-flex gap-2 justify-content-center'>
            <a href='/transactions/{r["id"]}/edit/' class='btn btn-sm btn-outline-primary btn-icon-fixed' title='Edit'>
            <span>✏️</span>
            </a>
            <form method='post' action='/transactions/{r["id"]}/delete/' class='delete-form d-inline' data-name='transaction on {r["date"]}'>
            <input type='hidden' name='csrfmiddlewaretoken' value='{csrf}'>
            <button type='submit' class='btn btn-sm btn-outline-danger btn-icon-fixed' title='Delete'>
                <span>🗑</span>
            </button>
            </form>
        </div>
    """, axis=1)

    # 📄 Paginação
    draw = int(request.GET.get("draw", "1"))
    start = int(request.GET.get("start", "0"))
    length = int(request.GET.get("length", "10"))
    total = len(df)
    df_page = df.iloc[start:start + length]

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": df_page[["period", "date", "type", "amount", "category", "tags", "account", "actions"]].to_dict(orient="records"),
        "unique_types": unique_types,
        "unique_categories": unique_categories,
        "unique_accounts": unique_accounts,
        "available_periods": available_periods,
    })



class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def get_queryset(self):
        # Garante prefetch das tags para performance
        return super().get_queryset().prefetch_related("tags")

    def form_valid(self, form):
        messages.success(self.request, "Transação atualizada com sucesso!")
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            # Renderiza o formulário atualizado (com mensagens)
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return response

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_list"] = list(
            Category.objects.filter(user=self.request.user).values_list("name", flat=True)
        )
        return context




class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_id = self.object.user_id
        response = super().delete(request, *args, **kwargs)
        print(f"🧹 Eliminação via view — limpando cache para user_id={user_id}")
        clear_tx_cache(user_id)
        return response


################################################################################
#                               Category views                                 #
################################################################################


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(user=self.request.user)  # type: ignore[misc]


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):
        merged = hasattr(form, "_merged_category")
        form.save()  # ⚠️ Pode devolver outra instância, mas ignoramos isso

        if merged:
            messages.success(self.request, "✅ The categories were merged successfully.")
        else:
            messages.success(self.request, "✅ Category updated successfully.")

        return redirect(self.get_success_url())
    
    
class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        option = request.POST.get("option")

        if option == "delete_all":
            # Apaga todas as transações associadas
            Transaction.objects.filter(category=self.object).delete()
            self.object.delete()
            messages.success(request, f"✅ Category and all its transactions were deleted.")
        elif option == "move_to_other":
            # Obter ou criar categoria 'Other'
            fallback = Category.get_fallback(request.user)

            # Fundir se já existir
            if fallback != self.object:
                Transaction.objects.filter(category=self.object).update(category=fallback)
                self.object.delete()
                messages.success(request, f"🔁 Transactions moved to 'Other'. Category deleted.")
            else:
                messages.warning(request, f"⚠️ Cannot delete 'Other' category.")
        else:
            messages.error(request, "❌ No valid option selected.")

        return redirect(self.success_url)


################################################################################
#                               Account views                                  #
################################################################################





class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self) -> QuerySet:
        return (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .order_by("position", "name")
        )
# views.py
    def get_context_data(self, **kwargs):
        """
        Adiciona as contas do utilizador e categorias ao contexto.
        """
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("name")
        Category.objects.filter(user=self.request.user).order_by("name").values_list("name", flat=True)


        return context


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        # Verificar se existe conta com o mesmo nome
        existing = form.find_duplicate()

        if existing:
            # Se a fusão ainda não foi confirmada, apenas mostrar erro no formulário
            if not self.request.POST.get("confirm_merge", "").lower() == "true":
                form.add_error(None, "Já existe uma conta com esse nome. Queres fundir os saldos?")
                return self.form_invalid(form)

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        # Verifica se há outra conta com o mesmo nome (ignorando maiúsculas/minúsculas)
        new_name = form.cleaned_data["name"].strip()
        existing = Account.objects.filter(
            user=self.request.user,
            name__iexact=new_name
        ).exclude(pk=self.object.pk).first()

        if existing:
            # Guarda o objeto editado para depois fundir
            form.save(commit=False)  # não guardamos já no DB
            return redirect(
                "account_merge",
                source_pk=self.object.pk,
                target_pk=existing.pk
            )

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")

    def dispatch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.is_default():
            return HttpResponseForbidden("⚠️ The default 'Cash' account cannot be deleted.")
        return super().dispatch(request, *args, **kwargs)


class AccountMergeView(OwnerQuerysetMixin, View):
    template_name = "core/confirms/account_confirm_merge.html"
    success_url = reverse_lazy("account_list")

    def get(self, request, *args, **kwargs):
        self.source = self.get_source_account()
        self.target = self.get_target_account()

        if not self.source or not self.target:
            messages.error(request, "Accounts not found for merging.")
            return redirect("account_list")

        return render(request, self.template_name, {
            "source": self.source,
            "target": self.target,
        })


    def post(self, request, *args, **kwargs):
        target = self.get_target_account()
        source = self.get_source_account()

        if not source or not target or source == target:
            messages.error(request, "Invalid merge.")
            return redirect("account_list")

        # Reconciliar saldos duplicados
        for bal in AccountBalance.objects.filter(account=source):
            existing = AccountBalance.objects.filter(
                account=target, period=bal.period
            ).first()

            if existing:
                # Exemplo: somar os saldos
                existing.reported_balance += bal.reported_balance
                existing.save()
                bal.delete()
            else:
                bal.account = target
                bal.save()

        source.delete()
        messages.success(request, f"Merged account '{source.name}' into '{target.name}'")
        return redirect(self.success_url)


    def get_source_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["source_pk"]).first()

    def get_target_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["target_pk"]).first()

################################################################################
#                           Account balance view                               #
################################################################################

@login_required
def account_balance_view(request):
    # Limpa mensagens anteriores (ex: "Saldo guardado com sucesso")
    list(get_messages(request))

    # 🗓️ Determinar o mês/ano selecionado
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # 🔁 Obter ou criar o período correspondente
    period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    # 📥 Query base dos saldos do utilizador nesse período
    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        period=period
    ).select_related("account", "account__account_type", "account__currency")

    if request.method == "POST":
        formset = AccountBalanceFormSet(request.POST, queryset=qs_base, user=request.user)

        if formset.is_valid():
            instances = formset.save(commit=False)

            for form in formset:
                if form.cleaned_data.get("DELETE"):
                    continue

                inst = form.save(commit=False)
                inst.period = period  # 🧠 já tínhamos o período acima

                if inst.account.user_id is None:
                    inst.account.user = request.user
                    inst.account.save()

                # Atualiza se já existir saldo para essa conta/período
                existing = AccountBalance.objects.filter(
                    account=inst.account,
                    period=period,
                ).first()

                if existing:
                    existing.reported_balance = inst.reported_balance
                    existing.save()
                else:
                    inst.save()

            # 🔄 Fundir contas duplicadas (por nome)
            _merge_duplicate_accounts(request.user)

            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")

        messages.error(request, "Erro ao guardar os saldos. Verifica os campos.")
    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    # 🧮 Agrupar saldos por tipo/moeda e calcular totais
    grouped_forms = {}
    totals_by_group = {}
    grand_total = 0

    for form in formset:
        account = form.instance.account
        key = (account.account_type.name, account.currency.code)
        grouped_forms.setdefault(key, []).append(form)

    for key, forms in grouped_forms.items():
        subtotal = sum((f.instance.reported_balance or 0) for f in forms)
        totals_by_group[key] = subtotal
        grand_total += subtotal

    # 📦 Enviar dados para o template
    context = {
        "formset": formset,
        "grouped_forms": grouped_forms,
        "totals_by_group": totals_by_group,
        "grand_total": grand_total,
        "year": year,
        "month": month,
        "selected_month": date(year, month, 1),
    }

    return render(request, "core/account_balance.html", context)

def _merge_duplicate_accounts(user):
    seen: dict[str, Account] = {}
    for acc in Account.objects.filter(user=user).order_by("name"):
        key = acc.name.strip().lower()
        if key in seen:
            primary = seen[key]
            AccountBalance.objects.filter(account=acc).update(account=primary)
            acc.delete()
        else:
            seen[key] = acc

################################################################################
#                               Misc views                                     #
################################################################################

def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("transaction_list")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


class LogoutView(RedirectView):
    pattern_name = "login"

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super().get(request, *args, **kwargs)


class HomeView(TemplateView):
    template_name = "core/home.html"


@require_POST
@login_required
def delete_account_balance(request, pk):
    try:
        obj = AccountBalance.objects.get(pk=pk, account__user=request.user)
        obj.delete()
        return JsonResponse({"success": True})
    except AccountBalance.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)



@require_GET
@login_required
def copy_previous_balances_view(request):
    """Copies balances from the previous month if they do not already exist."""
    year = int(request.GET.get("year"))
    month = int(request.GET.get("month"))

    # Calcula mês anterior
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    user = request.user
    created_count = 0

    previous_period = DatePeriod.objects.filter(year=prev_year, month=prev_month).first()
    if not previous_period:
        return JsonResponse({"success": False, "error": "Previous period not found"}, status=404)

    target_period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    previous_balances = AccountBalance.objects.filter(
        account__user=user,
        period=previous_period
    ).select_related("account")

    for bal in previous_balances:
        exists = AccountBalance.objects.filter(
            account=bal.account,
            period=target_period
        ).exists()

        if not exists:
            AccountBalance.objects.create(
                account=bal.account,
                period=target_period,
                reported_balance=bal.reported_balance
            )
            created_count += 1

    return JsonResponse({"success": True, "created": created_count})



@login_required
def move_account_up(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    above = Account.objects.filter(user=request.user, position__lt=account.position).order_by("-position").first()
    if above:
        account.position, above.position = above.position, account.position
        account.save()
        above.save()
    return redirect("account_list")

@login_required
def move_account_down(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    below = Account.objects.filter(user=request.user, position__gt=account.position).order_by("position").first()
    if below:
        account.position, below.position = below.position, account.position
        account.save()
        below.save()
    return redirect("account_list")

@login_required
def account_reorder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order = data.get("order", [])
            for item in order:
                Account.objects.filter(pk=item["id"], user=request.user).update(position=item["position"])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "invalid method"}, status=405)



@login_required
def category_autocomplete(request):
    """Autocomplete de categorias filtradas por utilizador."""
    q = request.GET.get("q", "").strip()
    results = Category.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name")

    data = [{"name": c.name} for c in results]
    return JsonResponse(data, safe=False)

@login_required
def tag_autocomplete(request):
    """Autocomplete de tags globais do utilizador."""
    q = request.GET.get("q", "").strip()
    results = Tag.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name").values("name").distinct()

    return JsonResponse(list(results), safe=False)


@login_required
def export_transactions_xlsx(request):

    user_id = request.user.id

    # 🧠 Query SQL otimizada com tags agregadas
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
            t.date AS Date,
            t.type AS Type,
            t.amount AS Amount,
            COALESCE(c.name, '') AS Category,
            (
                SELECT STRING_AGG(tg.name, ', ')
                FROM core_transaction_tags tt
                JOIN core_tag tg ON tg.id = tt.tag_id
                WHERE tt.transaction_id = t.id
            ) AS Tags,
            COALESCE(a.name, '') AS Account,
            CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS Period
            FROM core_transaction t
            LEFT JOIN core_category c ON t.category_id = c.id
            LEFT JOIN core_account a ON t.account_id = a.id
            LEFT JOIN core_dateperiod p ON t.period_id = p.id
            WHERE t.user_id = %s
            GROUP BY t.id, t.date, t.type, t.amount, c.name, a.name, p.year, p.month
            ORDER BY t.date DESC
        """, [user_id])
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]



    # ⚙️ Criar DataFrame e exportar para Excel
    df = pd.DataFrame(rows, columns=columns)
    #print("📄 DataFrame criado com sucesso", flush=True)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Transações")
    buffer.seek(0)


    # 📤 Enviar ficheiro para download
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=transactions.xlsx'
    return response


@login_required
def import_transactions_xlsx(request):
    if request.method == "GET":
        print("🧾 [GET] A mostrar formulário de importação")
        return render(request, "core/import_form.html")

    print("🚀 [POST] Início da importação de transações via Excel")

    try:
        file = request.FILES["file"]
        df = pd.read_excel(file)
        print(f"📄 Ficheiro recebido com {len(df)} linhas")

        required = {"Date", "Type", "Amount", "Category", "Tags", "Account"}
        if not required.issubset(df.columns):
            missing = required - set(df.columns)
            print(f"❌ Faltam colunas: {missing}")
            messages.error(request, f"Missing columns: {', '.join(missing)}")
            return redirect("transaction_import_xlsx")

        user_id = request.user.id
        transactions = []
        tag_links = []
        periods_cache = {}
        category_cache = {}
        account_cache = {}
        tag_cache = {}

        timestamp = now()
        print(f"📌 Timestamp para created_at/updated_at: {timestamp}")

        with connection.cursor() as cursor, db_transaction.atomic():
            cursor.execute("SELECT id FROM core_accounttype WHERE name ILIKE 'Savings' LIMIT 1")
            row = cursor.fetchone()
            if not row:
                raise Exception("Tipo de conta 'Savings' não existe.")
            default_account_type_id = row[0]

            for idx, row in df.iterrows():
                print(f"🔎 Linha {idx + 1}")
                raw_date = row["Date"]
                if pd.isna(raw_date):
                    print(f"⚠️ Linha {idx + 1} ignorada: data em branco")
                    continue

                try:
                    date_val = pd.to_datetime(raw_date).date()
                except Exception as e:
                    print(f"⚠️ Linha {idx + 1} ignorada: data inválida → {raw_date} ({e})")
                    continue
                if not date_val:
                    print(f"⚠️ Linha {idx + 1} ignorada: data inválida")
                    continue

                # Período
                key_period = (date_val.year, date_val.month)
                if key_period not in periods_cache:
                    cursor.execute("""
                        INSERT INTO core_dateperiod (year, month, label)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (year, month) DO NOTHING
                        RETURNING id
                    """, [date_val.year, date_val.month, date_val.strftime("%B %Y")])
                    row_period = cursor.fetchone()
                    if not row_period:
                        cursor.execute("SELECT id FROM core_dateperiod WHERE year = %s AND month = %s", key_period)
                        row_period = cursor.fetchone()
                    periods_cache[key_period] = row_period[0]

                period_id = periods_cache[key_period]

                # Categoria
                cat_name = str(row["Category"]).strip()
                if cat_name not in category_cache:
                    cursor.execute("""
                        INSERT INTO core_category (user_id, name, position, created_at, updated_at)
                        VALUES (%s, %s, 0, %s, %s)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, cat_name, timestamp, timestamp])
                    row_cat = cursor.fetchone()
                    if not row_cat:
                        cursor.execute("SELECT id FROM core_category WHERE user_id = %s AND name = %s", [user_id, cat_name])
                        row_cat = cursor.fetchone()
                    category_cache[cat_name] = row_cat[0]

                category_id = category_cache[cat_name]

                # Conta
                acc_name = str(row["Account"]).strip()
                if acc_name not in account_cache:
                    cursor.execute("""
                        INSERT INTO core_account (user_id, name, account_type_id, currency_id, created_at, position)
                        VALUES (%s, %s, %s, NULL, %s, 0)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, acc_name, default_account_type_id, timestamp])
                    row_acc = cursor.fetchone()
                    if not row_acc:
                        cursor.execute("SELECT id FROM core_account WHERE user_id = %s AND name = %s", [user_id, acc_name])
                        row_acc = cursor.fetchone()
                    account_cache[acc_name] = row_acc[0]

                account_id = account_cache[acc_name]

                # Transação
                transactions.append((
                    user_id, date_val, row["Amount"], row["Type"], period_id,
                    category_id, account_id, "", False, True,
                    timestamp, timestamp
                ))

                # Tags
                raw_tags = str(row.get("Tags", "")).split(",")
                tags_cleaned = [t.strip() for t in raw_tags if t.strip()]
                for tag in tags_cleaned:
                    tag_links.append((len(transactions) - 1, tag))

            print(f"📝 Transações preparadas: {len(transactions)}")

            # Inserir transações
            def chunked(iterable, size=100):
                for i in range(0, len(iterable), size):
                    yield iterable[i:i + size]

            transaction_ids = []
            for chunk in chunked(transactions, 100):
                execute_values(cursor, """
                    INSERT INTO core_transaction
                    (user_id, date, amount, type, period_id, category_id, account_id,
                     notes, is_estimated, is_cleared, created_at, updated_at)
                    VALUES %s
                    RETURNING id
                """, chunk)
                transaction_ids.extend([row[0] for row in cursor.fetchall()])

            # Tags
            all_tag_names = sorted(set(tag for _, tag in tag_links))
            if all_tag_names:
                cursor.execute(
                    "SELECT id, name FROM core_tag WHERE name = ANY(%s) AND user_id = %s",
                    [all_tag_names, user_id]
                )
                for tag_id, tag_name in cursor.fetchall():
                    tag_cache[tag_name] = tag_id

                missing = [name for name in all_tag_names if name not in tag_cache]
                if missing:
                    execute_values(cursor, """
                        INSERT INTO core_tag (user_id, name, position)
                        VALUES %s
                        RETURNING id, name
                    """, [(user_id, name, 0) for name in missing])
                    for tag_id, tag_name in cursor.fetchall():
                        tag_cache[tag_name] = tag_id

            # Ligações tag-transação
            links = []
            for i, tx_id in enumerate(transaction_ids):
                for idx, tag_name in tag_links:
                    if idx == i:
                        tag_id = tag_cache.get(tag_name)
                        if tag_id:
                            links.append((tx_id, tag_id))

            if links:
                execute_values(cursor, """
                    INSERT INTO core_transactiontag (transaction_id, tag_id)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """, links)

        # 🧹 Limpar cache de transações do utilizador
        from core.utils.cache_helpers import clear_tx_cache
        clear_tx_cache(request.user.id)

        # ✅ Mensagem de sucesso
        messages.success(request, f"✔ {len(transaction_ids)} transactions imported successfully!")

    except Exception as e:
        print("❌ Erro:", str(e))
        messages.error(request, f"❌ Import failed: {str(e)}")

    return redirect("transaction_list")




@login_required
def import_transactions_template(request):
    # Dados de exemplo
    example_data = [{
        "Date": "2025-06-10",
        "Type": "Expense",
        "Amount": 45.67,
        "Category": "Groceries",
        "Tags": "food,supermarket",
        "Account": "Conta Principal"
    }]

    df = pd.DataFrame(example_data)

    # Criar ficheiro Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")

    output.seek(0)

    # Responder com download
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="transactions_template.xlsx"'
    return response



from openpyxl import Workbook, load_workbook

# core/views.py

@login_required
def account_balance_export_xlsx(request):
    user_id = request.user.id

    # 🧠 Query SQL otimizada
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.year AS Year,
                p.month AS Month,
                a.name AS Account,
                at.name AS Type,
                COALESCE(curr.code, 'EUR') AS Currency,
                ab.reported_balance AS Balance
            FROM core_accountbalance ab
            INNER JOIN core_account a ON ab.account_id = a.id
            LEFT JOIN core_accounttype at ON a.account_type_id = at.id
            LEFT JOIN core_currency curr ON a.currency_id = curr.id
            INNER JOIN core_dateperiod p ON ab.period_id = p.id
            WHERE a.user_id = %s
            ORDER BY p.year, p.month, a.name
        """, [user_id])
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

    # ⚙️ Criar DataFrame e exportar para Excel
    df = pd.DataFrame(rows, columns=columns)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Balances")
    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="account_balances.xlsx"'
    return response






@login_required
def account_balance_import_xlsx(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file or not file.name.endswith(".xlsx"):
            messages.error(request, "Please upload a valid .xlsx Excel file.")
            return redirect("account_balance_import_xlsx")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f"Error reading Excel file: {e}")
            return redirect("account_balance_import_xlsx")

        required_cols = {"Year", "Month", "Account", "Balance"}
        if not required_cols.issubset(df.columns):
            messages.error(request, f"Missing required columns: {', '.join(required_cols)}")
            return redirect("account_balance_import_xlsx")

        user_id = request.user.id
        created = 0
        timestamp = now()

        with connection.cursor() as cursor, db_transaction.atomic():
            # Caches
            periods_cache = {}
            accounts_cache = {}

            # ID's fixos
            cursor.execute("SELECT id FROM core_accounttype WHERE name ILIKE 'Savings' LIMIT 1")
            default_type_id = cursor.fetchone()[0]

            cursor.execute("SELECT id FROM core_currency WHERE code = 'EUR'")
            default_currency_id = cursor.fetchone()[0]

            for idx, row in df.iterrows():
                try:
                    year = int(row["Year"])
                    month = int(row["Month"])
                    account_name = str(row["Account"]).strip()
                    balance = float(row["Balance"])
                except Exception as e:
                    messages.warning(request, f"❌ Skipped row {idx + 1}: {e}")
                    continue

                key_period = (year, month)
                if key_period not in periods_cache:
                    cursor.execute("""
                        INSERT INTO core_dateperiod (year, month, label)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (year, month) DO NOTHING
                        RETURNING id
                    """, [year, month, date(year, month, 1).strftime("%B %Y")])
                    row_period = cursor.fetchone()
                    if not row_period:
                        cursor.execute("SELECT id FROM core_dateperiod WHERE year = %s AND month = %s", key_period)
                        row_period = cursor.fetchone()
                    periods_cache[key_period] = row_period[0]

                period_id = periods_cache[key_period]

                if account_name not in accounts_cache:
                    cursor.execute("""
                        INSERT INTO core_account (user_id, name, account_type_id, currency_id, created_at, position)
                        VALUES (%s, %s, %s, %s, %s, 0)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, account_name, default_type_id, default_currency_id, timestamp])
                    row_acc = cursor.fetchone()
                    if not row_acc:
                        cursor.execute("SELECT id FROM core_account WHERE user_id = %s AND name = %s", [user_id, account_name])
                        row_acc = cursor.fetchone()
                    accounts_cache[account_name] = row_acc[0]

                account_id = accounts_cache[account_name]

                cursor.execute("""
                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (account_id, period_id)
                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                """, [account_id, period_id, balance])
                created += 1

        messages.success(request, f"✅ {created} balances imported successfully.")
        return redirect("account_balance")

    return render(request, "core/import_balances_form.html")



@login_required
def account_balance_template_xlsx(request):
    from io import BytesIO
    from django.http import HttpResponse
    import pandas as pd

    # Cabeçalho + linha de exemplo
    df = pd.DataFrame([{
        "Year": 2025,
        "Month": 6,
        "Account": "Bpi",
        "Balance": 1234.56
    }])

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=account_balances_template.xlsx"
    return response


 
# ─── API para Looker -----------------------------------------------------------
from core.utils.supabase_rpc import call_rpc          # utilitário já criado antes


import jwt
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from core.utils.supabase_rpc import call_rpc

@require_GET
def api_jwt_my_transactions(request):
    """
    Endpoint seguro via JWT: devolve as transações do utilizador autenticado via token JWT.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return HttpResponseForbidden("Falta o header Authorization com token JWT.")

    token = auth_header.replace("Bearer ", "").strip()
    try:
        payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["user_id"])
    except Exception as e:
        return HttpResponseForbidden(f"Token inválido: {str(e)}")

    rows = call_rpc(user_id, "get_my_transactions")
    return JsonResponse(rows, safe=False)




@login_required
def dashboard_data(request):
    user_id = request.user.id

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH base AS (
              SELECT p.year, p.month,
                     SUM(CASE WHEN t.type = 'IN' THEN t.amount ELSE 0 END) AS income
              FROM core_transaction t
              JOIN core_dateperiod p ON t.period_id = p.id
              WHERE t.user_id = %s
              GROUP BY p.year, p.month
            ),
            saldos AS (
              SELECT p.year, p.month, SUM(ab.reported_balance) AS saldo
              FROM core_accountbalance ab
              JOIN core_dateperiod p ON ab.period_id = p.id
              JOIN core_account a ON ab.account_id = a.id
              WHERE a.user_id = %s
              GROUP BY p.year, p.month
            )
            SELECT b.year, b.month, b.income,
                   s1.saldo AS saldo_n,
                   s2.saldo AS saldo_nplus1,
                   COALESCE(s1.saldo - s2.saldo + b.income, 0) AS expense_est
            FROM base b
            LEFT JOIN saldos s1 ON s1.year = b.year AND s1.month = b.month
            LEFT JOIN saldos s2 ON (
              (s2.year = b.year AND s2.month = b.month + 1) OR
              (s2.year = b.year + 1 AND b.month = 12 AND s2.month = 1)
            )
            ORDER BY b.year, b.month;
        """, [user_id, user_id])

        rows = cursor.fetchall()

    labels = [f"{y}-{m:02d}" for y, m, *_ in rows]
    income = [float(inc or 0) for _, _, inc, *_ in rows]
    expense = [float(e or 0) for *_, e in rows]

    return JsonResponse({
        "labels": labels,
        "income": income,
        "expense": expense
    })



