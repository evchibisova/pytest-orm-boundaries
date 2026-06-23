"""All bookshop models, re-exported so Django sees them under `bookshop`.

The DDD aggregates (client / book / purchase) are declared in boundaries.toml,
not here: aggregate boundaries are a domain concept, independent of how the
models are laid out in code.
"""

from .book import Book
from .client import Client
from .purchase import Purchase, PurchaseLine

__all__ = ["Book", "Client", "Purchase", "PurchaseLine"]
