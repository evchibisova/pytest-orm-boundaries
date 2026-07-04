"""A clean service — stays inside the `purchase` aggregate.

Used by the example to show a *stale* ignore.
"""

from .models import Purchase


def count_purchases():
    """Total number of purchases — single-aggregate query, no crossing."""
    return Purchase.objects.count()
