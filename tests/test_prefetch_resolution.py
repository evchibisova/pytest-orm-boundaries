"""Unit tests for resolving a prefetch lookup into the model pairs it walks."""

import pytest

pytest.importorskip("django")

from django.db import models  # noqa: E402
from django.db.models import Prefetch  # noqa: E402

from pytest_orm_boundaries.prefetch_resolution import (  # noqa: E402
    resolve_prefetch_step_models,
)


class Author(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "contenttypes"


class Book(models.Model):
    title = models.CharField(max_length=100)
    author = models.ForeignKey(Author, related_name="books", on_delete=models.CASCADE)

    class Meta:
        app_label = "contenttypes"


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)  # no related_name

    class Meta:
        app_label = "contenttypes"


class Tag(models.Model):
    books = models.ManyToManyField(Book, related_name="tags")

    class Meta:
        app_label = "contenttypes"


def test_forward_fk_resolves_one_step():
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Book, lookups=("author",)
    )
    assert step_model_pairs == [("contenttypes.Book", "contenttypes.Author")]


def test_reverse_fk_with_related_name_resolves():
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Author, lookups=("books",)
    )
    assert step_model_pairs == [("contenttypes.Author", "contenttypes.Book")]


def test_reverse_fk_default_accessor_resolves():
    # Review.book has no related_name; the reverse side is ``review_set``, a
    # name get_field doesn't know -- it must be matched by accessor.
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Book, lookups=("review_set",)
    )
    assert step_model_pairs == [("contenttypes.Book", "contenttypes.Review")]


def test_many_to_many_resolves_both_directions():
    forward = resolve_prefetch_step_models(source_model=Tag, lookups=("books",))
    reverse = resolve_prefetch_step_models(source_model=Book, lookups=("tags",))
    assert forward == [("contenttypes.Tag", "contenttypes.Book")]
    assert reverse == [("contenttypes.Book", "contenttypes.Tag")]


def test_nested_lookup_yields_a_pair_per_step():
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Author, lookups=("books__tags",)
    )
    assert step_model_pairs == [
        ("contenttypes.Author", "contenttypes.Book"),
        ("contenttypes.Book", "contenttypes.Tag"),
    ]


def test_non_relation_step_ends_the_walk():
    # ``title`` is a plain field: nothing to traverse.
    assert resolve_prefetch_step_models(source_model=Book, lookups=("title",)) == []


def test_unknown_step_is_ignored():
    assert resolve_prefetch_step_models(source_model=Book, lookups=("nope",)) == []


def test_prefetch_object_is_resolved_like_its_path():
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Book, lookups=(Prefetch("author"),)
    )
    assert step_model_pairs == [("contenttypes.Book", "contenttypes.Author")]


def test_multiple_lookups_each_resolve():
    step_model_pairs = resolve_prefetch_step_models(
        source_model=Book, lookups=("author", "tags")
    )
    assert step_model_pairs == [
        ("contenttypes.Book", "contenttypes.Author"),
        ("contenttypes.Book", "contenttypes.Tag"),
    ]
