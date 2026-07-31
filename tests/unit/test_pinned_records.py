"""Unit tests for the pinned-records collection and compare logic."""

from __future__ import annotations

from sqlit.domains.results.pins import MISSING, PinCollection, PinnedRecord, compare_fields


def _record(table: str = "users", connection: str = "local", **fields) -> PinnedRecord:
    return PinnedRecord(connection=connection, table=table, fields=tuple(fields.items()))


class TestPinCollection:
    def test_toggle_pins_and_unpins(self):
        pins = PinCollection()
        record = _record(id=1)
        assert pins.toggle(record) is True
        assert len(pins) == 1
        assert pins.toggle(record) is False
        assert len(pins) == 0

    def test_identical_rows_deduplicate(self):
        pins = PinCollection()
        pins.toggle(_record(id=1))
        pins.toggle(_record(id=2))
        pins.toggle(_record(id=1))  # unpins the first
        assert [dict(r.fields)["id"] for r in pins.records] == [2]

    def test_preserves_pin_order(self):
        pins = PinCollection()
        pins.toggle(_record(id=2))
        pins.toggle(_record(id=1))
        assert [dict(r.fields)["id"] for r in pins.records] == [2, 1]

    def test_remove_at(self):
        pins = PinCollection()
        pins.toggle(_record(id=1))
        pins.toggle(_record(id=2))
        pins.remove_at(0)
        assert [dict(r.fields)["id"] for r in pins.records] == [2]
        pins.remove_at(5)  # out of range is a no-op
        assert len(pins) == 1

    def test_clear(self):
        pins = PinCollection()
        pins.toggle(_record(id=1))
        pins.clear()
        assert len(pins) == 0

    def test_single_table_detection(self):
        pins = PinCollection()
        pins.toggle(_record(table="users", id=1))
        pins.toggle(_record(table="users", id=2))
        assert pins.is_single_table() is True
        pins.toggle(_record(table="orders", id=3))
        assert pins.is_single_table() is False

    def test_same_table_different_connection_is_not_single(self):
        pins = PinCollection()
        pins.toggle(_record(connection="local", id=1))
        pins.toggle(_record(connection="staging", id=1))
        assert pins.is_single_table() is False


class TestCompareFields:
    def test_flags_differing_values(self):
        rows = compare_fields([_record(id=1, status="active"), _record(id=2, status="active")])
        assert rows == [
            ("id", [1, 2], True),
            ("status", ["active", "active"], False),
        ]

    def test_null_vs_value_differs(self):
        rows = compare_fields([_record(email=None), _record(email="x@y.z")])
        assert rows[0][2] is True

    def test_null_vs_null_is_identical(self):
        rows = compare_fields([_record(email=None), _record(email=None)])
        assert rows[0][2] is False

    def test_missing_field_differs_and_uses_sentinel(self):
        rows = compare_fields([_record(id=1, extra="x"), _record(id=1)])
        extra = next(row for row in rows if row[0] == "extra")
        assert extra[1] == ["x", MISSING]
        assert extra[2] is True

    def test_field_order_follows_first_record_then_extras(self):
        rows = compare_fields([_record(a=1, b=2), _record(b=2, c=3, a=1)])
        assert [name for name, _v, _d in rows] == ["a", "b", "c"]
