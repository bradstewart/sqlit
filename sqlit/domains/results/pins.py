"""Session-scoped pinned records for multi-record inspection.

Pins capture a row's values at pin time (they don't track the live table),
along with the table and connection they came from, so records collected
while chasing foreign keys can be compared side by side afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Placeholder for a field that one record has and another doesn't (only
# possible when pins from different queries over the same table diverge).
MISSING = object()


@dataclass(frozen=True)
class PinnedRecord:
    """One pinned row: identity (connection, table) plus captured fields."""

    connection: str
    table: str
    fields: tuple[tuple[str, Any], ...]

    @property
    def label(self) -> str:
        return self.table or "results"


class PinCollection:
    """An ordered, de-duplicated set of pinned records."""

    def __init__(self) -> None:
        self._records: list[PinnedRecord] = []

    @property
    def records(self) -> list[PinnedRecord]:
        return list(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def toggle(self, record: PinnedRecord) -> bool:
        """Pin the record, or unpin it if an identical pin exists.

        Returns True when the record ends up pinned, False when unpinned.
        """
        if record in self._records:
            self._records.remove(record)
            return False
        self._records.append(record)
        return True

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self._records):
            del self._records[index]

    def clear(self) -> None:
        self._records.clear()

    def is_single_table(self) -> bool:
        """True when every pin comes from the same connection + table."""
        return len({(r.connection, r.table) for r in self._records}) == 1


def compare_fields(records: list[PinnedRecord]) -> list[tuple[str, list[Any], bool]]:
    """Align same-table records field-by-field for the compare view.

    Returns one row per field name — ``(name, values, differs)`` with values
    in record order — preserving the first record's field order and appending
    any names only later records have. ``differs`` is True when the rendered
    values are not all identical (MISSING counts as different from any value).
    """
    order: list[str] = []
    seen: set[str] = set()
    for record in records:
        for name, _value in record.fields:
            if name not in seen:
                seen.add(name)
                order.append(name)

    rows: list[tuple[str, list[Any], bool]] = []
    for name in order:
        values: list[Any] = []
        for record in records:
            mapping = dict(record.fields)
            values.append(mapping.get(name, MISSING))
        rendered = {("\0missing" if v is MISSING else "\0null" if v is None else str(v)) for v in values}
        rows.append((name, values, len(rendered) > 1))
    return rows
