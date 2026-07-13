"""A CQRS-style read model - deliberately spans every aggregate.

Read models answer cross-aggregate questions (dashboards, flat reports), so they
join across boundaries on purpose.
"""

from bookshop.models import PurchaseLine


def build_sales_report():
    """Flat sales rows joining client and book onto each purchase line."""
    return list(
        PurchaseLine.objects.values(
            "purchase__reference",
            "purchase__client__name",
            "book__title",
            "quantity",
        )
    )
