"""Unit tests for load_config: aggregate parsing and validation."""

from textwrap import dedent

import pytest

from pytest_orm_boundaries.config import BoundariesConfigError, load_config


def _write(tmp_path, text: str):
    path = tmp_path / "boundaries.toml"
    path.write_text(dedent(text))
    return path


def test_load_aggregates(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates.client]
        models = ["shop.Client"]

        [aggregates.order]
        models = ["shop.Order", "shop.OrderLine"]
        """,
    )
    assert load_config(path=path).aggregates_by_model == {
        "shop.client": "client",
        "shop.order": "order",
        "shop.orderline": "order",
    }


def test_load_inline_table_form(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates]
        fulfillment = { models = ["logistics.Shipment", "logistics.Package"] }
        """,
    )
    assert load_config(path=path).aggregates_by_model == {
        "logistics.shipment": "fulfillment",
        "logistics.package": "fulfillment",
    }


def test_load_empty_config_is_empty_map(tmp_path):
    path = _write(tmp_path, "")
    assert load_config(path=path).aggregates_by_model == {}


def test_labels_are_lowercased(tmp_path):
    path = _write(tmp_path, '[aggregates.client]\nmodels = ["Shop.Client"]\n')
    assert load_config(path=path).aggregates_by_model == {"shop.client": "client"}


def test_same_model_twice_in_one_aggregate_is_allowed(tmp_path):
    path = _write(
        tmp_path,
        '[aggregates.order]\nmodels = ["shop.Order", "shop.Order"]\n',
    )
    assert load_config(path=path).aggregates_by_model == {"shop.order": "order"}


def test_invalid_toml_raises_config_error(tmp_path):
    path = _write(tmp_path, "[aggregates.order]\nmodels = [")
    with pytest.raises(BoundariesConfigError, match="invalid TOML"):
        load_config(path=path)


def test_model_in_two_aggregates_raises(tmp_path):
    path = _write(
        tmp_path,
        """
        [aggregates.order]
        models = ["shop.Order"]

        [aggregates.billing]
        models = ["shop.Order"]
        """,
    )
    with pytest.raises(BoundariesConfigError, match="claimed by two aggregates"):
        load_config(path=path)


def test_aggregate_models_must_be_in_named_section(tmp_path):
    path = _write(tmp_path, '[aggregates]\norder = ["shop.Order"]\n')
    with pytest.raises(
        BoundariesConfigError,
        match=(
            r"aggregate 'order' must define models in its own section: "
            r"\[aggregates\.order\] with models"
        ),
    ):
        load_config(path=path)


def test_models_must_be_a_list(tmp_path):
    path = _write(tmp_path, '[aggregates.order]\nmodels = "shop.Order"\n')
    with pytest.raises(BoundariesConfigError, match="models must be a list"):
        load_config(path=path)


def test_non_string_member_raises(tmp_path):
    path = _write(tmp_path, "[aggregates.order]\nmodels = [123]\n")
    with pytest.raises(BoundariesConfigError, match="non-string entry"):
        load_config(path=path)


def test_models_are_required(tmp_path):
    path = _write(tmp_path, "[aggregates.order]\n")
    with pytest.raises(BoundariesConfigError, match="missing required 'models'"):
        load_config(path=path)


def test_models_must_not_be_empty(tmp_path):
    path = _write(tmp_path, "[aggregates.order]\nmodels = []\n")
    with pytest.raises(BoundariesConfigError, match="models must not be empty"):
        load_config(path=path)


def test_unknown_aggregate_fields_raise(tmp_path):
    path = _write(
        tmp_path,
        '[aggregates.order]\nmodels = ["shop.Order"]\nmodel = "shop.Order"\n',
    )
    with pytest.raises(BoundariesConfigError, match=r"unknown field\(s\): model"):
        load_config(path=path)


def test_aggregates_must_be_named_sections(tmp_path):
    path = _write(tmp_path, "aggregates = []\n")
    with pytest.raises(
        BoundariesConfigError,
        match=r"define aggregates as named sections.*\[aggregates\.order\]",
    ):
        load_config(path=path)
