"""Stand-alone Django bootstrap and shared fixtures for the bookshop example."""

import os
import sys

import django
import pytest
from django.conf import settings
from django.db import connection

# Make the `bookshop` package importable as a top-level app.
sys.path.insert(0, os.path.dirname(__file__))


def pytest_configure(config):
    if settings.configured:
        return

    settings.configure(
        INSTALLED_APPS=["bookshop"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create the tables once, straight from the models (no migrations)."""
    from bookshop.models import Book, Client, Purchase, PurchaseLine

    with connection.schema_editor() as schema_editor:
        for model in (Client, Book, Purchase, PurchaseLine):
            schema_editor.create_model(model)
    yield
