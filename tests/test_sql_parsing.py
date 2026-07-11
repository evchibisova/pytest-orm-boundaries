"""Unit tests for sql_parsing: table extraction, placeholder blanking, filtering."""

from pytest_orm_boundaries.sql_parsing import (
    _blank_placeholders,
    extract_table_names,
    looks_like_data_query,
)


def test_extracts_tables_from_join():
    tables = extract_table_names("SELECT * FROM a JOIN b ON a.id = b.a_id", "sqlite")
    assert tables == frozenset({"a", "b"})


def test_extracts_tables_from_subquery():
    sql = "SELECT id FROM a WHERE x IN (SELECT id FROM b WHERE name = %s)"
    assert extract_table_names(sql, "sqlite") == frozenset({"a", "b"})


def test_blanks_percent_s_placeholder():
    # A bare %s would be read as modulo and fail to parse.
    assert extract_table_names("SELECT id FROM a WHERE name = %s", "sqlite") == (
        frozenset({"a"})
    )


def test_leaves_placeholder_inside_string_literal():
    assert _blank_placeholders("SELECT '100%s off'") == "SELECT '100%s off'"


def test_excludes_cte_names():
    sql = "WITH c AS (SELECT id FROM b) SELECT * FROM a JOIN c ON a.id = c.id"
    assert extract_table_names(sql, "sqlite") == frozenset({"a", "b"})


def test_unparseable_sql_returns_none():
    assert extract_table_names("SELECT * FROM", "sqlite") is None


def test_looks_like_data_query_accepts_table_based_queries():
    assert looks_like_data_query("  SELECT 1")
    assert looks_like_data_query("INSERT INTO a VALUES (1)")
    assert looks_like_data_query("WITH c AS (SELECT 1) SELECT * FROM c")


def test_looks_like_data_query_rejects_noise():
    assert not looks_like_data_query('SAVEPOINT "s1"')
    assert not looks_like_data_query('RELEASE SAVEPOINT "s1"')
    assert not looks_like_data_query("PRAGMA foreign_keys = ON")


def test_unknown_vendor_parses_without_dialect():
    tables = extract_table_names("SELECT id FROM a", "some-third-party-backend")
    assert tables == frozenset({"a"})
