"""
conftest.py for finance infrastructure (integration) tests.

These tests require the MySQL database to be available.
Run them with:
    pytest apps/finance/tests/infrastructure/ --reuse-db

The --reuse-db flag tells pytest-django to skip DROP/CREATE and reuse the
existing 'gs_erp' database (configured via TEST.NAME in settings/test.py).
Each test is wrapped in a transaction that rolls back, so no data persists.
"""
