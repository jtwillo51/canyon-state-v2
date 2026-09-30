"""Multi-column sorting for list endpoints: `?sort=-close_rate&sort=-referrals` sorts by close rate, then
by referrals. A leading "-" means descending; empty values sort last either way."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement

MAX_SORT_COLUMNS = 3


def check_sort(keys: Sequence[str]) -> list[str]:
    """For a Pydantic validator: at most 3 columns, each used once."""
    columns = [k.removeprefix("-") for k in keys]
    if len(keys) > MAX_SORT_COLUMNS:
        raise ValueError(f"Sort by at most {MAX_SORT_COLUMNS} columns.")
    if len(set(columns)) != len(columns):
        raise ValueError("Sort by each column only once.")
    return list(keys)


def order_by(keys: Sequence[str], columns: dict[str, ColumnElement[Any]]) -> list[ColumnElement[Any]]:
    """ORDER BY clauses for the requested sort keys, in order."""
    clauses = []
    for key in keys:
        column = columns[key.removeprefix("-")]
        clauses.append((column.desc() if key.startswith("-") else column.asc()).nulls_last())
    return clauses
