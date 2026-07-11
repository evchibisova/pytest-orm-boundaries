"""SQLAlchemy models for the bookshop example.

The DDD aggregates (client / book / purchase) are declared in boundaries.toml,
not here: aggregate boundaries are a domain concept, independent of how the
tables are mapped. Aggregates are declared by table name, so each model sets an
explicit ``__tablename__`` the config can refer to.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    """The `client` aggregate root."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    city: Mapped[str] = mapped_column(default="")


class Book(Base):
    """The `book` aggregate root."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    isbn: Mapped[str]


class Purchase(Base):
    """The `purchase` aggregate root."""

    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    reference: Mapped[str]

    client: Mapped[Client] = relationship()
    lines: Mapped[list[PurchaseLine]] = relationship(back_populates="purchase")


class PurchaseLine(Base):
    """An internal member of the `purchase` aggregate."""

    __tablename__ = "purchase_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    quantity: Mapped[int] = mapped_column(default=1)

    purchase: Mapped[Purchase] = relationship(back_populates="lines")
    book: Mapped[Book] = relationship()
