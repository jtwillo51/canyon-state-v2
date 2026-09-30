from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute


def contains(column: InstrumentedAttribute[str], text: str) -> ColumnElement[bool]:
    """Case-insensitive "contains", with LIKE wildcards escaped: a search for "50%" means those
    three characters, not "starts with 50"."""
    term = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{term}%", escape="\\")
