"""Bookshop service functions -- the code under test.

Some functions below cross the boundary between aggregates (declared in
boundaries.toml). This module is in the [ignore] list, so its crossings are
suppressed while it waits to be cleaned up -- its tests still pass.
"""

from sqlalchemy import select

from bookshop.models import Book, Client, Purchase, PurchaseLine


# No violations: Purchase and PurchaseLine are in the same aggregate.
def make_purchase(session, client, reference, lines):
    """Create a purchase and its lines -- writes stay inside the purchase aggregate."""
    purchase = Purchase(client_id=client.id, reference=reference)
    session.add(purchase)
    session.flush()
    for book, quantity in lines:
        line = PurchaseLine(purchase_id=purchase.id, book_id=book.id, quantity=quantity)
        session.add(line)
    session.flush()
    return purchase


# No violations: PurchaseLine and Purchase are in the same aggregate.
def get_lines_in_purchase(session, reference):
    """Lines of a purchase -- joins purchase_lines -> purchases (same aggregate)."""
    statement = (
        select(PurchaseLine)
        .join(PurchaseLine.purchase)
        .where(Purchase.reference == reference)
    )
    return session.scalars(statement).all()


# Crosses the boundary: Purchase -> Client
def get_purchases_by_client_name(session, name):
    """Purchases for a client name -- joins purchases -> clients (crosses!)."""
    statement = select(Purchase).join(Purchase.client).where(Client.name == name)
    return session.scalars(statement).all()


# Crosses the boundary: PurchaseLine -> Book
def get_purchase_lines_for_book_title(session, title):
    """Lines for a book title -- joins purchase_lines -> books (crosses!)."""
    statement = select(PurchaseLine).join(PurchaseLine.book).where(Book.title == title)
    return session.scalars(statement).all()
