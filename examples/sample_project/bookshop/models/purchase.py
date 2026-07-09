"""The `purchase` aggregate: Purchase (root) and PurchaseLine (internal member)."""

from django.db import models

from bookshop.models.book import Book
from bookshop.models.client import Client


class Purchase(models.Model):
    client = models.ForeignKey(
        Client, related_name="purchases", on_delete=models.CASCADE
    )
    reference = models.CharField(max_length=50)


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(
        Purchase, related_name="lines", on_delete=models.CASCADE
    )
    book = models.ForeignKey(
        Book, related_name="purchase_lines", on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1)
