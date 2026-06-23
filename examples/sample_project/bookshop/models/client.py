"""The `client` aggregate root."""

from django.db import models


class Client(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
