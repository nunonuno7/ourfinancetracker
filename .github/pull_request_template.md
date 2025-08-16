# PR Checklist — OurFinanceTracker

**Before opening the PR, tick all:**

## Preflight
- [ ] Lint & format pass: `ruff check .`, `black --check .`, `isort --check-only .`
- [ ] Django checks: `python manage.py check` and `check --deploy`
- [ ] No pending migrations: `makemigrations --check --dry-run`
- [ ] Static ok: `collectstatic --noinput`
- [ ] No secrets added (run `gitleaks detect --redact`)

## Tests (attach summary)
- [ ] `pytest -q --cov=core --cov=ourfinancetracker` passes
- [ ] Coverage **≥ 90%** overall

## Must-have tests exist & pass
- [ ] Models & signals
- [ ] TransactionForm (amounts, period, tags, IN/OUT rules)
- [ ] Import/Export (.xlsx, chunks, template row)
- [ ] JSON endpoints contract (filters, actions HTML)
- [ ] Auth & CSRF (anon redirects, login flow)
- [ ] CSP headers on key pages (no invalid directives/inline)
- [ ] Cache helper (no KeyError)
- [ ] Smoke GETs for main routes

## Deploy notes
- [ ] Migrations/env vars listed
- [ ] Rollback plan

## UI changes (if any)
- [ ] Screenshots or short clip

