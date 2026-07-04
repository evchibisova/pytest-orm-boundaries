"""Test examples: call the service functions and watch the plugin react."""

from bookshop import catalog, purchases
from bookshop.models import Book, Client


def test_make_purchase():
    client = Client.objects.create(name="John Smith", email="john.smith@example.com")
    book = Book.objects.create(title="Once in a Fairytale", isbn="9780262011532", price=42)
    purchase = purchases.make_purchase(client, "P-1", [(book, 2)])

    # Reading the lines back joins only within the `purchase` aggregate: allowed.
    assert len(purchases.get_lines_in_purchase(purchase.reference)) == 1


def test_get_purchases_by_client_name():
    # Crosses boundary: purchase -> client.
    purchases.get_purchases_by_client_name("John Smith")


def test_get_purchase_lines_for_book_title():
    # Crosses boundary: purchase -> book.
    purchases.get_purchase_lines_for_book_title("Once in a Fairytale")


def test_count_purchases():
    # Clean: stays inside the `purchase` aggregate.
    # Test is needed for "stale import" demonstration
    catalog.count_purchases()
