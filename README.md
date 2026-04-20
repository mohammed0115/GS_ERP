# N-ERP

Django-based ERP platform rebuilt from the legacy Laravel `n.erp` system.

This is a **modular monolith** with clean-architecture boundaries enforced per app. Domain logic lives in `domain/` and `application/`. Django ORM and external gateways are quarantined inside `infrastructure/`. HTTP, admin, and CLI live in `interfaces/`.

---

## Status

| Sprint | Scope | State |
|---|---|---|
| 1.1 | Project skeleton, `common/`, `apps/core` (Money/Quantity/Currency), tests | ✅ Complete |
| 1.2 | `apps/tenancy` — `TenantContext`, middleware, `TenantOwnedModel` | ✅ Complete |
| 1.3 | `apps/users` — custom User, DRF auth, permissions | ✅ Complete |
| 1.4 | `apps/billing` — Subscription / Plan / expiry middleware | ✅ Complete |
| 2.1 | `apps/finance` — double-entry ledger + payments/expenses/transfers | ✅ Complete |
| 2.2 | `apps/catalog` — product + normalized combo recipes | ✅ Complete |
| 2.3 | `apps/inventory` — event-sourced stock movements + projection | ✅ Complete |
| 3.1 | `apps/crm` — customer / supplier / biller / ledger-backed wallet | ✅ Complete |
| 3.2 | `apps/sales` — sale state machine + PostSale | ✅ Complete |
| 3.3 | `apps/purchases` — PostPurchase (symmetric to sales) | ✅ Complete |
| 3.4 | `apps/pos` — cash register sessions | ✅ Complete |
| 4.1 | `apps/hr` — employee / attendance / payroll | ✅ Complete |
| 4.2 | `apps/reports` — read-only selectors for the 22 legacy reports | ✅ Complete |
| 4.3 | `apps/audit` + `apps/notifications` | ✅ Complete |
| 5   | ETL — 10 `import_legacy_*` management commands | ✅ Complete |
| 6   | Reconciliation — `reconcile_migration` automated cut-over validator | ✅ Complete |

See `docs/architecture/` for ADRs and `docs/migration/playbook.md` for cut-over procedure.

---

## Layout

```
nerp/
├── config/                 # Django settings, URL root, Celery, WSGI/ASGI
│   └── settings/           # base.py + development.py + production.py + test.py
├── common/                 # Cross-cutting: exceptions, permissions, pagination, OpenAPI helpers
├── apps/
│   ├── core/               # Money, Quantity, Currency, TimestampedModel, AuditMetaMixin
│   ├── tenancy/            # (sprint 1.2)
│   ├── users/              # (sprint 1.3)
│   └── billing/            # (sprint 1.4)
├── tests/                  # Integration + e2e (unit tests live next to their code)
├── requirements/           # base / development / test / production
├── docker/                 # Dockerfile, docker-compose.yml, entrypoint.sh
├── docs/                   # architecture + migration + api docs
├── pyproject.toml          # pytest, ruff, mypy, coverage config
└── manage.py
```

Per-app internal structure is strict:

```
apps/<context>/
├── domain/           # Pure: entities, value objects, domain services. No Django.
├── application/      # Use cases, commands, queries, selectors, ports (Protocols).
├── infrastructure/   # ORM models, repositories, mappers, external gateways.
├── interfaces/       # HTTP views, serializers, URLs, admin, CLI commands.
└── tests/
```

### Dependency rules (enforced by code review)

- `domain/` imports **nothing** from Django, DRF, or any `infrastructure/`.
- `application/` imports `domain/` and `application/ports.py` only — never `infrastructure/`.
- `interfaces/` calls `application/` use cases and selectors — it is a thin adapter.
- `infrastructure/` implements `application/ports.py` and may import `domain/`.
- Cross-app calls go through use cases or published domain events, never by reaching into another app's `infrastructure/models.py`.

---

## Quickstart

Prerequisites: Docker + Docker Compose.

```bash
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY at minimum.

cd docker
docker compose up --build
```

The API will be at `http://localhost:8000`, OpenAPI docs at `http://localhost:8000/api/docs/`, and the raw schema at `http://localhost:8000/api/schema/`.

---

## Running tests

Tests assume a live Postgres (we do not swap to SQLite — too much depends on Postgres-specific features).

```bash
# With Docker services running:
docker compose exec api pytest

# Or locally against a local Postgres:
pip install -r requirements/test.txt
pytest
```

Coverage report: `pytest --cov --cov-report=term-missing`.

Markers:

- `pytest -m unit` — pure, no DB.
- `pytest -m integration` — DB-backed.
- `pytest -m e2e` — HTTP round-trips.

---

## Conventions

### Money and quantity

Never use `float` for money or stock. Always use `apps.core.domain.value_objects.Money` and `Quantity`. They reject floats at construction time.

```python
from decimal import Decimal
from apps.core.domain import Money, Quantity, Currency

usd = Currency("USD")
price = Money("10.50", usd)
total = price + Money(Decimal("2.99"), usd)    # OK
total = price + Money("5", Currency("EUR"))     # raises CurrencyMismatchError

qty = Quantity("5.25", "kg")
remaining = qty - Quantity("3", "kg")           # OK
over = Quantity("3", "kg") - Quantity("5", "kg")  # raises InvalidQuantityError
```

### Errors

Raise `common.exceptions.domain.DomainError` subclasses from domain and application layers. The DRF handler in `common.exceptions.handlers` turns them into a stable envelope:

```json
{"error": {"code": "validation_error", "message": "...", "details": {...}}}
```

Never raise `django.core.exceptions.*` or `rest_framework.exceptions.*` from domain code.

### Permissions

Declare required permissions explicitly in each view:

```python
from common.permissions import HasPerm

class SaleListView(generics.ListAPIView):
    permission_classes = [HasPerm.for_codenames("sales.view")]
```

Permission codenames follow `<resource>.<action>` (e.g. `sales.view`, `sales.create`, `sales.refund`).

### Use cases

Business logic lives in use-case classes inside `application/use_cases/`. One class per use case. Name them as imperative verbs:

```python
class CreateSale:
    def __init__(self, sales_repo: SaleRepository, inventory: InventoryService): ...
    def execute(self, command: CreateSaleCommand) -> SaleDTO: ...
```

Views call `execute()`; they do not know about ORM objects.

---

## Architectural decisions

See `docs/architecture/adr/` (added per sprint). Key decisions already locked:

- **ADR-001** Modular monolith, not microservices.
- **ADR-003** Tenant context via `contextvars`, not session.
- **ADR-005** Money as `Decimal(18,4)` + `Money` VO.
- **ADR-006** Quantity as `Decimal(18,4)` + `Quantity` VO.
- **ADR-007** Event-sourced stock (`StockMovement` append-only, `StockOnHand` projection).
- **ADR-008** Double-entry ledger in `finance`; no denormalized balances.
- **ADR-011** One permission model (Django groups); `users.role_id` duplicate is dropped.
- **ADR-017** Postgres only.

---

## License

Internal project.
