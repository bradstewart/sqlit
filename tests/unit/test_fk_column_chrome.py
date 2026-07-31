"""Unit tests for the FK relationship markers on result tables."""

from __future__ import annotations

from rich.text import Text

from sqlit.shared.ui.widgets_tables import FK_HEADER_MARKER, FK_TARGET_HEADER_MARKER, SqlitDataTable


def _make_table() -> SqlitDataTable:
    return SqlitDataTable(
        column_labels=["id", "user_id", "note"],
        data=[(1, "u1", "hi")],
        null_rep="NULL",
    )


class TestSetForeignKeyColumns:
    def test_fk_column_header_gets_forward_marker(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, set())
        assert table.ordered_columns[1].label.plain == f"user_id{FK_HEADER_MARKER}"

    def test_referenced_column_header_gets_reverse_marker(self):
        table = _make_table()
        table.set_foreign_key_columns(set(), {"id"})
        assert table.ordered_columns[0].label.plain == f"id{FK_TARGET_HEADER_MARKER}"

    def test_unrelated_columns_untouched(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, {"id"})
        assert table.ordered_columns[2].label.plain == "note"

    def test_idempotent_across_repeated_application(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, {"id"})
        table.set_foreign_key_columns({"user_id"}, {"id"})
        assert table.ordered_columns[1].label.plain == f"user_id{FK_HEADER_MARKER}"
        assert table.ordered_columns[0].label.plain == f"id{FK_TARGET_HEADER_MARKER}"

    def test_matching_is_case_insensitive(self):
        table = SqlitDataTable(column_labels=["User_Id"], data=[("u1",)], null_rep="NULL")
        table.set_foreign_key_columns({"user_id"}, set())
        assert table.ordered_columns[0].label.plain == f"User_Id{FK_HEADER_MARKER}"

    def test_only_forward_fk_values_are_tinted(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, {"id"})
        assert set(table._fk_value_column_indices) == {1}


class TestFkValueTint:
    def test_fk_cell_value_is_styled(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, set())
        renderable = table._get_cell_renderable(0, 1)
        assert isinstance(renderable, Text)
        assert any("italic" in str(span.style) for span in renderable.spans)

    def test_non_fk_cell_value_is_not_styled(self):
        table = _make_table()
        table.set_foreign_key_columns({"user_id"}, set())
        renderable = table._get_cell_renderable(0, 2)
        assert not isinstance(renderable, Text) or not renderable.spans

    def test_null_fk_cell_keeps_null_rendering(self):
        table = SqlitDataTable(column_labels=["user_id"], data=[(None,)], null_rep="NULL")
        table.set_foreign_key_columns({"user_id"}, set())
        renderable = table._get_cell_renderable(0, 0)
        assert renderable.plain == "NULL"
        assert not any("italic" in str(span.style) for span in renderable.spans)
