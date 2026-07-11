"""A clean service -- stays inside the `purchase` aggregate.

Listed in boundaries.toml's [ignore] even though it never crosses, so the plugin
flags that entry as a *stale* ignore at the end of the run.
"""

from sqlalchemy import func, select

from bookshop.models import Purchase


def count_purchases(session):
    """Total number of purchases -- single-table query, no crossing."""
    count = func.count(Purchase.id)
    statement = select(count)
    return session.scalar(statement)
