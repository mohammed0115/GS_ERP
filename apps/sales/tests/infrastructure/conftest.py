"""
conftest.py for sales infrastructure (integration) tests.

Run with:
    pytest apps/sales/tests/infrastructure/ --reuse-db

Each test is wrapped in a transaction that rolls back, so no data persists.
"""
