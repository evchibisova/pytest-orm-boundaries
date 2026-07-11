"""Test examples: call the service functions and watch the plugin react."""

import pytest

from bookshop import catalog, purchases, reports
from bookshop.models import Book, Client


@pytest.fixture
def john(session):
    client = Client(name="John Smith", email="john.smith@example.com", city="Berlin")
    session.add(client)
    session.flush()
    return client


@pytest.fixture
def fairytale(session):
    book = Book(title="Once in a Fairytale", isbn="9780262011532")
    session.add(book)
    session.flush()
    return book


def test_make_purchase(session, john, fairytale):
    purchase = purchases.make_purchase(session, john, "P-1", [(fairytale, 2)])

    # Reading the lines back joins only within the `purchase` aggregate: allowed.
    lines = purchases.get_lines_in_purchase(session, purchase.reference)
    assert len(lines) == 1


def test_get_purchases_by_client_name(session):
    # Crosses purchase -> client, but purchases.py is in [ignore] -> suppressed.
    purchases.get_purchases_by_client_name(session, "John Smith")


def test_get_purchase_lines_for_book_title(session):
    # Crosses purchase -> book, but purchases.py is in [ignore] -> suppressed.
    purchases.get_purchase_lines_for_book_title(session, "Once in a Fairytale")


def test_count_purchases(session):
    # Clean, yet catalog.py is in [ignore] -> demonstrates a stale ignore.
    catalog.count_purchases(session)


def test_list_purchases_with_client(session):
    # Explicit ORM join crosses purchase <-> client (reported).
    reports.list_purchases_with_client(session)


def test_list_purchase_lines_with_book(session):
    # Join through purchase_lines crosses purchase <-> book (reported).
    reports.list_purchase_lines_with_book(session)


def test_list_purchases_eager_client(session):
    # joinedload crosses purchase <-> client (reported).
    reports.list_purchases_eager_client(session)


def test_find_purchases_from_clients_in_city(session):
    # Subquery crosses purchase <-> client (reported).
    reports.find_purchases_from_clients_in_city(session, "Berlin")


def test_list_purchases_with_client_via_raw_sql(session):
    # Raw text() SQL crosses purchase <-> client (reported).
    reports.list_purchases_with_client_via_raw_sql(session)


def test_list_lines_with_purchase(session):
    # select stays inside the purchase aggregate -> clean.
    reports.list_lines_with_purchase(session)


def test_count_purchases_for_client(session):
    # Filter by FK id -> reads one table, no join -> clean.
    reports.count_purchases_for_client(session, 1)
