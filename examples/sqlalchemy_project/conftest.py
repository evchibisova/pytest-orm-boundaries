"""Engine, schema, and session fixtures for the SQLAlchemy bookshop example."""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Make the `bookshop` package importable as a top-level package.
sys.path.insert(0, os.path.dirname(__file__))

from bookshop.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """One in-memory engine for the whole run.

    StaticPool keeps a single underlying connection, so the schema created here
    is visible to every session the tests open.
    """
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """A session per test, rolled back at teardown so tests stay isolated."""
    with Session(engine) as session:
        yield session
        session.rollback()
