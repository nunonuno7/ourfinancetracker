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
| Backend       | Django 5.2.1 · Python 3.12                |
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
# edit values as needed

# Create the database and apply migrations
python manage.py migrate

# Start the local server
python manage.py runserver
```

## 🌐 Additional domains

To authorise new domains in `ALLOWED_HOSTS` or the list of CSRF trusted origins, set additional environment variables:

```bash
EXTRA_ALLOWED_HOSTS=example.com,sub.domain.com
EXTRA_CSRF_TRUSTED_ORIGINS=https://example.com,https://sub.domain.com
```

Use comma-separated values. For `EXTRA_CSRF_TRUSTED_ORIGINS`, each origin must include the scheme (`http://` or `https://`).

## 📄 Licence

Distributed under the MIT licence. See the `LICENSE` file for more details.
