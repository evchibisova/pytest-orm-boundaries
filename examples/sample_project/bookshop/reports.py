"""Read-side helpers that eager-load related rows with select_related.

Unlike purchases.py, this module is *not* in boundaries.toml's [ignore] list,
so the crossing below shows up in the plugin's end-of-run report.
"""

from bookshop.models import Purchase, PurchaseLine


# Crosses the boundary: select_related joins in Client alongside Purchase.
def list_purchases_with_client():
    """Purchases with the client preloaded — select_related crosses purchase -> client."""
    return list(Purchase.objects.select_related("client"))


# Clean: select_related stays inside the `purchase` aggregate.
def list_lines_with_purchase():
    """Lines with the purchase preloaded — select_related stays within the purchase aggregate."""
    return list(PurchaseLine.objects.select_related("purchase"))


# Clean: filtering on the foreign-key id reads Purchase's own client_id column,
# so the Client table is never joined — pointing at another aggregate by id is fine.
def count_purchases_for_client(client_id):
    """Purchases for a client id — filters the FK column, no join, no crossing."""
    return Purchase.objects.filter(client_id=client_id).count()
