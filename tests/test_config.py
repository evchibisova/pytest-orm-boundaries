"""Unit tests for load_aggregates_from_config: parsing and validation."""

from textwrap import dedent

import pytest

from pytest_orm_boundaries.config import (
    BoundariesConfigError,
    load_aggregates_from_config,
)


def _write(tmp_path, text: str):
    path = tmp_path / "boundaries.toml"
    path.write_text(dedent(text))
    return path


def test_load_simple_aggregates(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates]
        client = ["shop.Client"]
        order = ["shop.Order", "shop.OrderLine"]
        """,
    )
    assert load_aggregates_from_config(path=path) == {
        "shop.client": "client",
        "shop.order": "order",
        "shop.orderline": "order",
    }


def test_load_table_section_form(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates.fulfillment]
        models = ["logistics.Shipment", "logistics.Package"]
        """,
    )
    assert load_aggregates_from_config(path=path) == {
        "logistics.shipment": "fulfillment",
        "logistics.package": "fulfillment",
    }


def test_load_empty_config_is_empty_map(tmp_path):
    assert load_aggregates_from_config(path=_write(tmp_path, "")) == {}


def test_labels_are_lowercased(tmp_path):
    path = _write(tmp_path, '[aggregates]\nclient = ["Shop.Client"]\n')
    assert load_aggregates_from_config(path=path) == {"shop.client": "client"}


def test_same_model_twice_in_one_aggregate_is_allowed(tmp_path):
    path = _write(tmp_path, '[aggregates]\norder = ["shop.Order", "shop.Order"]\n')
    assert load_aggregates_from_config(path=path) == {"shop.order": "order"}


def test_invalid_toml_raises_config_error(tmp_path):
    path = _write(tmp_path, "[aggregates]\norder = [")
    with pytest.raises(BoundariesConfigError, match="invalid TOML"):
        load_aggregates_from_config(path=path)


def test_model_in_two_aggregates_raises(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates]
        order = ["shop.Order"]
        billing = ["shop.Order"]
        """,
    )
    with pytest.raises(BoundariesConfigError, match="claimed by two aggregates"):
        load_aggregates_from_config(path=path)


def test_non_list_members_raise(tmp_path):
    # A bare string instead of a list is a common mistake.
    path = _write(tmp_path, '[aggregates]\norder = "shop.Order"\n')
    with pytest.raises(BoundariesConfigError, match="must be a list"):
        load_aggregates_from_config(path=path)


def test_non_string_member_raises(tmp_path):
    path = _write(tmp_path, "[aggregates]\norder = [123]\n")
    with pytest.raises(BoundariesConfigError, match="non-string member"):
        load_aggregates_from_config(path=path)
