"""The `book` aggregate root."""

from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
