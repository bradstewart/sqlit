"""Unit tests for the whole-row record view."""

from __future__ import annotations

from sqlit.domains.results.ui.mixins.results import build_record_fields
from sqlit.domains.results.ui.screens.record_view import _MAX_LINE_LENGTH, RecordViewScreen


class TestBuildRecordFields:
    def test_pairs_columns_with_values(self):
        fields = build_record_fields(["id", "name"], [1, "Jane"])
        assert fields == [("id", 1), ("name", "Jane")]

    def test_missing_column_names_fall_back_to_positional(self):
        fields = build_record_fields(["id"], [1, "Jane", None])
        assert fields == [("id", 1), ("col 2", "Jane"), ("col 3", None)]

    def test_surplus_column_names_are_dropped(self):
        fields = build_record_fields(["id", "name", "email"], [1])
        assert fields == [("id", 1)]

    def test_empty_row(self):
        assert build_record_fields(["id"], []) == []


class TestRecordViewRendering:
    def _render(self, fields):
        return RecordViewScreen(fields)._render_options()

    def test_one_option_per_field(self):
        options = self._render([("id", 1), ("name", "Jane")])
        assert len(options) == 2

    def test_names_padded_to_common_width(self):
        options = self._render([("id", 1), ("longer_name", "x")])
        assert options[0].prompt.plain.startswith("id".ljust(len("longer_name")))

    def test_null_rendered_distinctly(self):
        options = self._render([("email", None)])
        prompt = options[0].prompt
        assert "NULL" in prompt.plain
        null_span = next(span for span in prompt.spans if "dim" in str(span.style))
        assert prompt.plain[null_span.start : null_span.end] == "NULL"

    def test_long_values_truncated_to_line_width(self):
        options = self._render([("body", "x" * (_MAX_LINE_LENGTH * 2))])
        plain = options[0].prompt.plain
        assert plain.endswith("…")
        assert len(plain) <= _MAX_LINE_LENGTH

    def test_newlines_collapsed_to_single_line(self):
        options = self._render([("body", "line one\nline two")])
        assert "\n" not in options[0].prompt.plain
        assert "line one line two" in options[0].prompt.plain

    def test_non_string_values_stringified(self):
        options = self._render([("id", 42)])
        assert "42" in options[0].prompt.plain
