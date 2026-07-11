"""Read the tables a SQL statement touches by parsing the SQL text."""

from __future__ import annotations

import functools
import re

import sqlglot
from sqlglot import expressions as exp
from sqlglot.errors import SqlglotError

# Decreasing amount of work - only these statements read tables,
# transaction control, PRAGMA and DDL are ignored before we bother parsing.
_DATA_QUERY = re.compile(
    r"\s*(?:WITH|SELECT|INSERT|UPDATE|DELETE|REPLACE|MERGE)\b", re.IGNORECASE
)

# Django backend vendor -> sqlglot dialect; unmapped vendors parse dialect-free.
_DIALECT_BY_VENDOR = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "mysql": "mysql",
    "oracle": "oracle",
}


def looks_like_data_query(sql: str) -> bool:
    """Whether the statement is one that can read tables (worth parsing)."""
    return _DATA_QUERY.match(sql) is not None


def _blank_placeholders(sql: str) -> str:
    """Replace ``%s`` / ``%(name)s`` placeholders with a literal so the SQL parses,
    leaving any placeholder-looking text inside quoted strings untouched.
    """
    placeholder = re.compile(r"""('(?:[^']|'')*')|("(?:[^"]|"")*")|(%\(\w+\)s|%s)""")

    return placeholder.sub(
        lambda match: "NULL" if match.group(3) else match.group(0), sql
    )


@functools.lru_cache(maxsize=4096)
def extract_table_names(sql: str, vendor: str) -> frozenset[str] | None:
    """Names of the tables the statement reads, or None if it could not be parsed."""
    dialect = _DIALECT_BY_VENDOR.get(vendor)
    blanked_sql = _blank_placeholders(sql)
    try:
        tree = sqlglot.parse_one(blanked_sql, dialect=dialect)
    except (SqlglotError, RecursionError):
        return None
    if tree is None:
        return frozenset()
    # common table expression - can be named as an existed table, but it is not a table
    # e.g. `report` in ` WITH report AS (SELECT id FROM orders WHERE created > '2026-01-01')
    cte_names = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    tables = {table.name for table in tree.find_all(exp.Table)}
    return frozenset(tables - cte_names)
