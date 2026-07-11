"""Read-side reports -- each function crosses (or stays inside) a boundary a
different way. Unlike purchases.py this module is *not* in boundaries.toml's
[ignore] list, so the crossings below show up in the plugin's end-of-run report.
"""

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from bookshop.models import Book, Client, Purchase, PurchaseLine


# Crosses purchase <-> client: an explicit ORM join pulls in both tables.
def list_purchases_with_client(session):
    """Purchases joined to their client -- crosses purchase -> client."""
    statement = select(Purchase, Client).join(Purchase.client)
    return session.execute(statement).all()


# Crosses purchase <-> book: a join through purchase_lines into books.
def list_purchase_lines_with_book(session):
    """Purchase lines joined to their book -- crosses purchase -> book."""
    statement = select(PurchaseLine, Book).join(PurchaseLine.book)
    return session.execute(statement).all()


# Crosses purchase <-> client: joinedload emits a JOIN (SQLAlchemy's select_related).
def list_purchases_eager_client(session):
    """Purchases with the client eager-loaded -- joinedload crosses purchase -> client."""
    eager_client = joinedload(Purchase.client)
    statement = select(Purchase).options(eager_client)
    return session.scalars(statement).unique().all()


# Crosses purchase <-> client: the client table is reached only through a subquery.
def find_purchases_from_clients_in_city(session, city):
    """Purchases whose client is in a city -- subquery still crosses purchase -> client."""
    clients_in_city = select(Client.id).where(Client.city == city)
    from_those_clients = Purchase.client_id.in_(clients_in_city)
    statement = select(Purchase).where(from_those_clients)
    return session.scalars(statement).all()


# Crosses purchase <-> client: the same join, hand-written as raw SQL.
def list_purchases_with_client_via_raw_sql(session):
    """The join written by hand -- text() crosses purchase -> client too."""
    statement = text("SELECT p.id FROM purchases p JOIN clients c ON p.client_id = c.id")
    return session.execute(statement).all()


# Clean: the join stays inside the `purchase` aggregate.
def list_lines_with_purchase(session):
    """Lines joined to their purchase -- stays within the purchase aggregate."""
    statement = select(PurchaseLine, Purchase).join(PurchaseLine.purchase)
    return session.execute(statement).all()


# Clean: filtering on the foreign-key id reads Purchase's own client_id column,
# so the clients table is never joined -- pointing at another aggregate by id is fine.
def count_purchases_for_client(session, client_id):
    """Purchases for a client id -- filters the FK column, no join, no crossing."""
    statement = select(Purchase).where(Purchase.client_id == client_id)
    return session.scalars(statement).all()
