"""Bookshop service functions — the code under test.

Some of functions below cross the boundary between aggregates,
described in boundaries.toml, so the tests must catch it.
"""

from bookshop.models import Purchase, PurchaseLine


# No crossings: Purchase and PurchaseLine are in the same aggregate.
def make_purchase(client, reference, lines):
    purchase = Purchase.objects.create(client=client, reference=reference)
    for book, quantity in lines:
        PurchaseLine.objects.create(
            purchase=purchase, book=book, quantity=quantity
        )
    return purchase


# No crossings: Purchase and PurchaseLine are in the same aggregate.
def get_lines_in_purchase(reference):
    """Lines of a purchase — joins PurchaseLine -> Purchase (same aggregate)."""
    return list(PurchaseLine.objects.filter(purchase__reference=reference))


# Crosses the boundary: Purchase -> Client
def get_purchases_by_client_name(name):
    """Purchases for a client name — joins purchase -> client (crosses!)."""
    return list(Purchase.objects.filter(client__name=name))


# Crosses the boundary: PurchaseLine -> Book
def get_purchase_lines_for_book_title(title):
    """Lines for a book title — joins purchase -> book (crosses!)."""
    return list(PurchaseLine.objects.filter(book__title=title))
