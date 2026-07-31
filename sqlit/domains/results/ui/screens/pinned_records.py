"""Multi-record inspector for pinned rows."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, OptionList
from textual.widgets.option_list import Option

from sqlit.domains.results.pins import MISSING, PinCollection, compare_fields
from sqlit.domains.results.ui.screens.record_view import FIELD_NAME_STYLE, NULL_VALUE_STYLE, render_field_line
from sqlit.shared.ui.widgets import Dialog

# Cell width cap for the side-by-side compare table; full values are always
# available by expanding the cell into the value view modal.
_MAX_COMPARE_VALUE_LENGTH = 36

# Marker appended to field names whose values differ across pinned records —
# same quiet-chrome language as the FK header markers.
DIFF_MARKER = " ≠"


def _clip(value: Any, limit: int = _MAX_COMPARE_VALUE_LENGTH) -> str:
    text = " ".join(str(value).splitlines())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


class PinnedRecordsScreen(ModalScreen):
    """Modal inspector over the session's pinned records.

    Same-table pins render side by side (one column per record, field names
    as rows) with identical values dimmed and differing field names marked,
    so divergence between records is visible at a glance. Mixed-table pins
    stack per record in the single-record view's dense field-list style.
    """

    BINDINGS = [
        Binding("escape,q", "cancel", "Close", show=False),
        Binding("enter,v", "expand_value", "Expand", show=False),
        Binding("y", "copy_value", "Copy", show=False),
        Binding("x", "remove_record", "Unpin", show=False),
        Binding("X", "clear_records", "Clear", show=False),
        Binding("down,j", "cursor_down", "Next", show=False),
        Binding("up,k", "cursor_up", "Previous", show=False),
        Binding("left,h", "cursor_left", "Left", show=False),
        Binding("right,l", "cursor_right", "Right", show=False),
    ]

    CSS = """
    PinnedRecordsScreen {
        align: center middle;
        background: transparent;
    }

    #pinned-records-dialog {
        width: 120;
        max-width: 95%;
        height: auto;
        max-height: 85%;
    }

    #pinned-records-table {
        height: auto;
        max-height: 100%;
        border: none;
        background: $surface;
    }

    #pinned-records-list {
        height: auto;
        max-height: 100%;
        border: none;
        background: $surface;
    }
    """

    def __init__(self, pins: PinCollection) -> None:
        super().__init__()
        self._pins = pins
        # Stacked mode: option index -> (record index, field index | None).
        self._option_entries: list[tuple[int, int | None]] = []

    @property
    def _compare_mode(self) -> bool:
        return len(self._pins) > 1 and self._pins.is_single_table()

    def compose(self) -> ComposeResult:
        records = self._pins.records
        if self._compare_mode:
            title = f"Pinned: {records[0].label} ({len(records)} records)"
        else:
            title = f"Pinned records ({len(records)})"
        shortcuts = [("Expand", "<enter>"), ("Copy", "y"), ("Unpin", "x"), ("Clear", "X"), ("Close", "<esc>")]
        with Dialog(id="pinned-records-dialog", title=title, shortcuts=shortcuts):
            if self._compare_mode:
                yield self._build_compare_table()
            else:
                yield OptionList(*self._build_stacked_options(), id="pinned-records-list")

    def on_mount(self) -> None:
        self._focus_content()

    def _focus_content(self) -> None:
        try:
            if self._compare_mode:
                self.query_one("#pinned-records-table", DataTable).focus()
            else:
                option_list = self.query_one("#pinned-records-list", OptionList)
                if option_list.option_count:
                    option_list.highlighted = next(
                        (i for i, (_r, field) in enumerate(self._option_entries) if field is not None), 0
                    )
                option_list.focus()
        except Exception:
            pass

    # -- compare mode (same table) -------------------------------------

    def _build_compare_table(self) -> DataTable:
        table: DataTable = DataTable(id="pinned-records-table", cursor_type="cell", zebra_stripes=False)
        records = self._pins.records
        table.add_column(Text("field", style=FIELD_NAME_STYLE), key="field")
        for idx in range(len(records)):
            table.add_column(f"#{idx + 1}", key=str(idx))
        for name, values, differs in compare_fields(records):
            label = Text(name, style=FIELD_NAME_STYLE)
            if differs:
                label.append(DIFF_MARKER, style="dim")
            cells: list[Any] = [label]
            for value in values:
                if value is MISSING:
                    cells.append(Text("—", style="dim"))
                elif value is None:
                    cells.append(Text("NULL", style=NULL_VALUE_STYLE))
                else:
                    cells.append(Text(_clip(value), style="" if differs else "dim"))
            table.add_row(*cells)
        return table

    def _compare_cursor_value(self) -> Any:
        """Raw value under the compare-table cursor, or MISSING when n/a."""
        try:
            table = self.query_one("#pinned-records-table", DataTable)
            row, col = table.cursor_coordinate
        except Exception:
            return MISSING
        if col == 0:
            return MISSING
        rows = compare_fields(self._pins.records)
        if not (0 <= row < len(rows)) or not (1 <= col <= len(self._pins)):
            return MISSING
        return rows[row][1][col - 1]

    # -- stacked mode (mixed tables) -----------------------------------

    def _build_stacked_options(self) -> list[Option]:
        options: list[Option] = []
        self._option_entries = []
        records = self._pins.records
        for record_idx, record in enumerate(records):
            heading = Text(f"{record.label}", style="bold")
            heading.append(f"  ({record.connection})", style="dim")
            options.append(Option(heading, disabled=True))
            self._option_entries.append((record_idx, None))
            name_width = max((len(name) for name, _v in record.fields), default=0)
            for field_idx, (name, value) in enumerate(record.fields):
                options.append(Option(render_field_line(name, value, name_width)))
                self._option_entries.append((record_idx, field_idx))
            if record_idx < len(records) - 1:
                options.append(Option(Text(""), disabled=True))
                self._option_entries.append((record_idx, None))
        return options

    def _stacked_highlighted(self) -> tuple[int, int | None] | None:
        try:
            option_list = self.query_one("#pinned-records-list", OptionList)
        except Exception:
            return None
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self._option_entries)):
            return None
        return self._option_entries[index]

    def _stacked_field(self) -> tuple[str, Any] | None:
        entry = self._stacked_highlighted()
        if entry is None or entry[1] is None:
            return None
        record_idx, field_idx = entry
        fields = self._pins.records[record_idx].fields
        return fields[field_idx] if 0 <= field_idx < len(fields) else None

    # -- shared actions --------------------------------------------------

    def _rebuild(self) -> None:
        if not len(self._pins):
            self.dismiss(None)
            return
        self.refresh(recompose=True)
        self.call_after_refresh(self._focus_content)

    def action_expand_value(self) -> None:
        from sqlit.domains.results.ui.screens.value_view import ValueViewScreen

        if self._compare_mode:
            value = self._compare_cursor_value()
            if value is MISSING:
                return
            try:
                table = self.query_one("#pinned-records-table", DataTable)
                row = table.cursor_coordinate.row
                name = compare_fields(self._pins.records)[row][0]
            except Exception:
                name = "Value"
        else:
            field = self._stacked_field()
            if field is None:
                return
            name, value = field
        self.app.push_screen(ValueViewScreen(str(value) if value is not None else "NULL", title=name))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.action_expand_value()

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        self.action_expand_value()

    def action_copy_value(self) -> None:
        if self._compare_mode:
            value = self._compare_cursor_value()
            if value is MISSING:
                return
        else:
            field = self._stacked_field()
            if field is None:
                return
            _name, value = field
        copy_text = getattr(self.app, "_copy_text", None)
        if callable(copy_text):
            copy_text(str(value) if value is not None else "NULL")
            self.notify("Copied", timeout=1)
        else:
            self.notify("Copy unavailable", timeout=2)

    def _record_index_under_cursor(self) -> int | None:
        if self._compare_mode:
            try:
                table = self.query_one("#pinned-records-table", DataTable)
                col = table.cursor_coordinate.column
            except Exception:
                return None
            return col - 1 if col >= 1 else None
        entry = self._stacked_highlighted()
        return entry[0] if entry else None

    def action_remove_record(self) -> None:
        index = self._record_index_under_cursor()
        if index is None:
            return
        self._pins.remove_at(index)
        self._rebuild()

    def action_clear_records(self) -> None:
        self._pins.clear()
        self.dismiss(None)

    def action_cursor_down(self) -> None:
        self._move_cursor("down")

    def action_cursor_up(self) -> None:
        self._move_cursor("up")

    def action_cursor_left(self) -> None:
        self._move_cursor("left")

    def action_cursor_right(self) -> None:
        self._move_cursor("right")

    def _move_cursor(self, direction: str) -> None:
        try:
            if self._compare_mode:
                table = self.query_one("#pinned-records-table", DataTable)
                getattr(table, f"action_cursor_{direction}")()
            elif direction in ("down", "up"):
                option_list = self.query_one("#pinned-records-list", OptionList)
                getattr(option_list, f"action_cursor_{direction}")()
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def check_action(self, action: str, parameters: Any) -> bool | None:
        if self.app.screen is not self:
            return False
        return super().check_action(action, parameters)
