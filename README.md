# ourfinancetracker

> **Personal finance management web application**

This repository contains the source code for **ourfinancetracker**, a Django application that allows users to record monthly balances, income, and expenses, giving them a consolidated view of their financial health without relying on external banking APIs.

## ✨ Key features

- Monthly dashboard with income, estimated expenses, and balances
- Unlimited bank and investment accounts
- Customisable categories per user
- Reusable tags to categorise transactions
- Automatic expense estimates based on balance
- Multi-currency with support for different account types
- Reports based on monthly periods
- Responsive interface with dynamic forms

## 🏗️ Tech stack

| Layer         | Technology                                |
| ------------- | ----------------------------------------- |
| Backend       | Django 5.1.11 · Python 3.12               |
| Database      | PostgreSQL (via Supabase)                 |
| Frontend      | Django Templates (initial phase)          |
| Deployment    | Render.com (configured via `render.yaml`) |
| Dev Tools     | pip · pre-commit · GitHub Actions         |

## 📐 Data model

### ER diagram

```mermaid
erDiagram

%% ---------- AUTHENTICATION ----------
auth_user||--o{auth_user_groups: has
auth_user||--o{auth_user_user_permissions: has
auth_group||--o{auth_group_permissions: has
auth_user_groups}o--||auth_group: member_of
auth_user_user_permissions}o--||auth_permission: granted_to
auth_group_permissions}o--||auth_permission: grants
auth_permission}o--||django_content_type: applies_to
django_admin_log}o--||auth_user: action_by
django_admin_log}o--||django_content_type: relates_to

%% ---------- CORE ----------
auth_user||--o{core_account: owns
auth_user||--o{core_transaction: records
auth_user||--o{core_category: defines

core_account}o--||core_accounttype: typed_as
core_account}o--||core_currency: in_currency

core_accountbalance}o--||core_account: for_account
core_accountbalance}o--||date_period: for_period

core_transaction}o--||core_category: categorised_as
core_transaction}o--||date_period: for_period

core_transaction_tags}o--||core_transaction: tags_txn
core_transaction_tags}o--||core_tag: with_tag
```

## 🚀 Getting started

```bash
# Clone the repository
git clone https://github.com/nunonuno7/ourfinancetracker.git
cd ourfinancetracker

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# for local development, keep DEBUG=True
# set SUPABASE_DB_URL only if you want to use Supabase Postgres;
# otherwise the app falls back to a local SQLite database

# Create the database and apply migrations
python manage.py migrate

# Start the local server
python manage.py runserver
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser. Do not use `https://` with Django's built-in development server.

## Database support

- PostgreSQL is the primary runtime target for production and CI parity.
- SQLite is still supported for local development, quick test feedback, and fallback setups where no database URL is configured.
- Some high-traffic views contain PostgreSQL-optimized SQL paths. SQLite should be treated as a convenience environment, not as the source of truth for production behavior.

## 🌐 Additional domains

To authorise new domains in `ALLOWED_HOSTS` or the list of CSRF trusted origins, set additional environment variables:

```bash
EXTRA_ALLOWED_HOSTS=example.com,sub.domain.com
EXTRA_CSRF_TRUSTED_ORIGINS=https://example.com,https://sub.domain.com
```

Use comma-separated values. For `EXTRA_CSRF_TRUSTED_ORIGINS`, each origin must include the scheme (`http://` or `https://`).

## 🍪 Cookie policy and integrations

The application now sets both session and CSRF cookies with `SameSite=Strict` to mitigate cross-site request forgery. This can
affect integrations that rely on cross-site requests or iframes. If an integration requires a more permissive policy, the
behaviour can be overridden via environment variables:

```bash
SESSION_COOKIE_SAMESITE=Lax
CSRF_COOKIE_SAMESITE=Lax
```

Use `None`, `Lax`, or `Strict` as needed.

## 📄 Licence

Distributed under the MIT licence. See the `LICENSE` file for more details.

## 🧪 Running tests

```bash
# Quick local run (SQLite, default in settings_test)
pytest

# PostgreSQL parity run
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/ourfinancetracker_ci pytest
```

`settings_test.py` prefers `TEST_DATABASE_URL` when present and otherwise falls back to SQLite. GitHub Actions runs both variants.

## Compatibility notes

- New transaction list links and integrations should send `account_id` and `category_id`.
- Legacy name-based filters (`account` and `category`) are still accepted temporarily for older deep links and stored session state, but they should be treated as transitional compatibility only.

## Browser smoke tests

Smoke tests use Playwright against Django's static live server and are intentionally isolated from the default `pytest` run.

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
RUN_BROWSER_SMOKE=1 pytest -q core/tests/test_browser_smoke.py
```

For PostgreSQL parity, set `TEST_DATABASE_URL` before the command above. The CI workflow runs these browser smoke tests on Ubuntu with PostgreSQL.

When you run browser smoke tests on local SQLite, only the non-AJAX flows are expected to run reliably. The full browser suite is validated in CI against PostgreSQL.

To ensure the test suite passes before code is pushed, install the
`pre-commit` hook that runs tests on the `pre-push` stage:

```bash
pip install pre-commit
pre-commit install --hook-type pre-push
```

With the hook installed, `pytest` is executed automatically and the push is
blocked if any test fails.
