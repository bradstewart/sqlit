"""Table widgets for sqlit."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from rich.align import Align
from rich.errors import MarkupError
from rich.markup import escape
from rich.protocol import is_renderable
from rich.text import Text
from textual.coordinate import Coordinate

from textual.containers import Container
from textual.events import Key
from textual.strip import Strip
from textual_fastdatatable import DataTable as FastDataTable


# Header markers for relationship columns: an outgoing FK column links away
# to another table (→), a column referenced by other tables' FKs links back
# (←). Kept deliberately quiet — dim marker, italic values — so relationships
# read at a glance without adding visual noise.
FK_HEADER_MARKER = " →"
FK_TARGET_HEADER_MARKER = " ←"
_FK_MARKER_STYLE = "dim"
_FK_VALUE_STYLE = "italic"


class SqlitDataTable(FastDataTable):
    """FastDataTable with correct header behavior when show_header is False.

    Disables hover tooltips - use 'v' to view cell values.
    """

    # Track if a manual tooltip is being shown (via 'v' key)
    _manual_tooltip_active: bool = False

    # Column indices whose values render with the FK tint; populated by
    # set_foreign_key_columns once FK metadata is known.
    _fk_value_column_indices: frozenset[int] = frozenset()

    def set_foreign_key_columns(self, fk_columns: set[str], fk_target_columns: set[str]) -> None:
        """Mark relationship columns: append header markers and tint FK values.

        Args:
            fk_columns: normalized (lowercase) names of outgoing FK columns.
            fk_target_columns: normalized names of columns referenced by
                other tables' foreign keys.

        Idempotent — FK metadata arrives asynchronously and may be applied
        more than once to the same table.
        """
        fk_indices: set[int] = set()
        for idx, column in enumerate(self.ordered_columns):
            plain = column.label.plain
            base = plain.removesuffix(FK_HEADER_MARKER).removesuffix(FK_TARGET_HEADER_MARKER)
            key = base.strip().lower()
            if key in fk_columns:
                marker = FK_HEADER_MARKER
                fk_indices.add(idx)
            elif key in fk_target_columns:
                marker = FK_TARGET_HEADER_MARKER
            else:
                continue
            if plain == base:
                column.label = Text.assemble(base, (marker, _FK_MARKER_STYLE))
        self._fk_value_column_indices = frozenset(fk_indices)
        try:
            # Rendered lines are cached; invalidate so the new header
            # markers and value tint actually repaint.
            self._clear_caches()
            self.refresh()
        except Exception:
            pass

    def _apply_fk_value_style(self, renderable: Any) -> Any:
        """Give an FK cell's rendered value the (subtle) link tint."""
        if isinstance(renderable, str):
            return Text(renderable, style=_FK_VALUE_STYLE)
        if isinstance(renderable, Text):
            styled = renderable.copy()
            styled.stylize(_FK_VALUE_STYLE)
            return styled
        if isinstance(renderable, Align) and isinstance(renderable.renderable, str):
            return Align(Text(renderable.renderable, style=_FK_VALUE_STYLE), align="right")
        return renderable

    def _set_tooltip_from_cell_at(self, coordinate: Any) -> None:
        """Override to disable hover tooltips entirely."""
        # Don't set tooltip on hover - we handle this manually via 'v' key
        pass

    def action_copy_selection(self) -> None:
        """Copy selection to clipboard, guarding against empty tables."""
        # Guard against empty table - the library doesn't check this.
        # A schema-only backend (columns but no rows) still has backend != None.
        if self.backend is None or self.backend.row_count == 0:
            return
        # Call parent implementation
        super().action_copy_selection()

    def render_line(self, y: int) -> Strip:
        width, _ = self.size
        scroll_x, scroll_y = self.scroll_offset

        fixed_rows_height = self.fixed_rows
        if self.show_header:
            fixed_rows_height += self.header_height

        if y >= fixed_rows_height:
            y += scroll_y

        if not self.show_header:
            # FastDataTable still renders the header row at y=0; offset by 1 when hidden.
            y += 1

        return self._render_line(y, scroll_x, scroll_x + width, self.rich_style)

    def _get_cell_renderable(self, row_index: int, column_index: int) -> Any:
        """Format cells with plain text for NULL/bool/date values."""
        if row_index == -1:
            return self.ordered_columns[column_index].label

        datum = self.get_cell_at(Coordinate(row=row_index, column=column_index))
        column = self.ordered_columns[column_index]
        renderable = self._format_cell(datum, column)
        if datum is not None and column_index in self._fk_value_column_indices:
            renderable = self._apply_fk_value_style(renderable)
        return renderable

    def _format_cell(self, obj: object, col: Any | None) -> Any:
        if obj is None:
            return self._format_null()

        if isinstance(obj, str):
            if self.render_markup:
                try:
                    return Text.from_markup(obj)
                except MarkupError:
                    return escape(obj)
            return escape(obj)

        if isinstance(obj, bool):
            return "True" if obj else "False"

        if isinstance(obj, (float, Decimal)):
            return Align(f"{obj:n}", align="right")

        if isinstance(obj, int):
            if col is not None and getattr(col, "is_id", False):
                return Align(str(obj), align="right")
            return Align(f"{obj:n}", align="right")

        if isinstance(obj, (datetime, time)):
            return obj.isoformat(timespec="milliseconds").replace("+00:00", "Z")

        if isinstance(obj, date):
            return obj.isoformat()

        if isinstance(obj, timedelta):
            return str(obj)

        if isinstance(obj, (bytes, bytearray, memoryview)):
            return f"<BLOB {len(bytes(obj))} bytes>"

        if not is_renderable(obj):
            return escape(str(obj))

        return obj

    def _format_null(self) -> Text:
        null_rep = getattr(self, "null_rep", None)
        if isinstance(null_rep, Text):
            return null_rep
        return Text(str(null_rep) if null_rep is not None else "NULL")


class ResultsTableContainer(Container):
    """A focusable container for the results DataTable.

    This container holds focus when its child DataTable is replaced,
    preventing focus from jumping to another widget during table updates.
    Key events are forwarded to the child DataTable.
    """

    can_focus = True

    def on_key(self, event: Key) -> None:
        """Forward key events to the child DataTable."""
        # Find the DataTable child
        try:
            table = self.query_one(SqlitDataTable)
            # Let the table handle navigation keys
            if event.key in ("up", "down", "left", "right", "pageup", "pagedown", "home", "end"):
                # Simulate the key on the table
                table.post_message(event)
                event.stop()
        except Exception:
            pass

    def on_focus(self, event: Any) -> None:
        """When container gets focus, style it as active."""
        self.add_class("container-focused")

    def on_blur(self, event: Any) -> None:
        """When container loses focus, remove active styling."""
        self.remove_class("container-focused")
