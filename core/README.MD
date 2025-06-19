
# ourfinancetracker

A lightweight, self-hostable personal-finance tracker built with **Django 5.2** and a modern JS front‑end (HTMX + Bootstrap 5 + noUiSlider).  
It supports bank‑statement imports, smart filtering, monthly dashboards and (coming soon) scheduling of recurring transactions & automatic FX conversion.

---

## Table of Contents
1. [Quick start](#quick-start)
2. [Core features](#core-features)
3. [Financial‑metric calculations](#financial-metric-calculations)
4. [Data model & taxonomy](#data-model--taxonomy)
5. [CLI / management commands](#cli--management-commands)
6. [Roadmap](#roadmap)
7. [Contributing](#contributing)
8. [Licence](#licence)

---

## Quick start

```bash
git clone https://github.com/nunonuno7/ourfinancetracker.git
cd ourfinancetracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Browse to `http://127.0.0.1:8000/`, log in and start importing statements (`Transactions → Import Excel`) or monthly balances (`Account Balances → Import Excel`).

---

## Core features

| Area                       | Status | Notes |
| -------------------------- | :----: | ----- |
| Transaction CRUD           | ✅     | Inline form with HTMX; autocomplete for tags & categories |
| Excel import / export      | ✅     | `transactions` and `account_balances` both support `.xlsx` |
| Dashboard (`/dashboard/`)  | ✅     | Auto-selects **last 12 months**, dynamic filters, correct totals |
| Caching                    | ✅     | LocMem + per-user keys; manual “Clear cache” button |
| Recurring transactions     | 🚧     | Model done; scheduling via Celery next |
| Multi-currency + FX        | 🚧     | Currency table ready; rates & conversions in backlog |
| Supabase / Looker reports  | ✅     | JWT + PostgREST proxy ready for embed dashboards |

---

## Financial‑metric calculations

> **Goal:** separate real cash‑flow *expenses* from investment market swings while keeping investment returns measurable.

| Term | Definition |
| ---- | ---------- |
| **Saving opening balance (month n)** | Sum of all **saving**‑type account balances at `00:00` on day 1 of month *n*. |
| **Saving opening balance (month n + 1)** | Same accounts, `00:00` on day 1 of month *n + 1*. |
| **Income (month n)** | Sum of transactions with `type = "income"` during month *n*. |
| **Invested amount (flow)** | Sum of all transactions with `type = "investimento"`. |
| **Portfolio value (stock)** | Closing/monthly balance of **investment**‑type accounts (market value of held assets). |

### 1 – Monthly Expenses  

To ignore unrealised P/L on investments and focus purely on cash outflow:

```
Expenses(n) = Saving_open(n)  –  Saving_open(n+1)  +  Income(n)
```

### 2 – Investments  

```
Invested (flow) = Σ transactions(type = "investimento")
Portfolio value (stock) = balance of investment accounts at month end
```

### 3 – Profitability  

Use **TWR** (time‑weighted return) or **IRR**:

* Cash flows  → Invested amounts  
* Start / end → Portfolio value for each month  

### 4 – Key points  

* Separating **saving** vs **investment** avoids market noise in expense tracking.  
* Only **real flows** (deposits, withdrawals, asset purchases) impact *Expenses* or *Invested amount*.  
* Unrealised gains/losses influence **Profitability**, not **Expenses**.

---

## Data model & taxonomy

* `AccountType` – `"saving"` | `"investment"` | `"credit"` | ...  
* `Transaction` – `type`, `currency`, `amount`, `date`, `tags` (m2m)  
* `AccountBalance` – monthly snapshot linked to `DatePeriod`  
* `DatePeriod` – unique `(year, month)` rows created on demand  

Full schema diagram lives in [`core/mermaidchart.md`](./mermaidchart.md).

---

## CLI / management commands

| Command | Description |
| ------- | ----------- |
| `import_transactions_xlsx <file>` | Import XLSX with Date · Type · Amount · Category · Tags · Account |
| `account_balance_import_xlsx <file>` | Fast chunked import of monthly balances |
| `clear_tx_cache` | Remove cached DataFrames |
| `recalc_dashboard_kpis` (coming) | Pre-compute KPIs overnight |

---

## Roadmap
* Recurring-transaction scheduler  
* Automatic FX conversion  
* Celery + Flower for background jobs  
* Docker compose for production

---

## Contributing

PRs & issues welcome—follow [Conventional Commits](https://www.conventionalcommits.org/) and run:

```bash
pre-commit run --all-files
pytest
```

---

## Licence

MIT © Nuno Veiga, 2025
