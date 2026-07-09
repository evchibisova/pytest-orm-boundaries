"""All bookshop models, re-exported so Django sees them under `bookshop`.

The DDD aggregates (client / book / purchase) are declared in boundaries.toml,
not here: aggregate boundaries are a domain concept, independent of how the
models are laid out in code.
"""

from bookshop.models.book import Book
from bookshop.models.client import Client
from bookshop.models.purchase import Purchase, PurchaseLine

__all__ = ["Book", "Client", "Purchase", "PurchaseLine"]
