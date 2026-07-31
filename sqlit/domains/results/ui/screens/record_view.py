"""Record view screen for inspecting a whole result row vertically."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from sqlit.shared.ui.widgets import Dialog

# Values longer than this are truncated in the list; the full value is
# always available by expanding the field into the value view modal.
_MAX_VALUE_DISPLAY_LENGTH = 500


class RecordViewScreen(ModalScreen):
    """Modal dialog showing one row as a dense vertical `column: value` list.

    Wide rows are easier to read top-to-bottom than by scrolling the results
    table horizontally. Each field is one line; long values are truncated and
    can be expanded into the existing value view modal, which also provides
    JSON tree browsing and copy.
    """

    BINDINGS = [
        Binding("escape,q", "cancel", "Close", show=False),
        Binding("enter,v", "expand_field", "Expand", show=False),
        Binding("y", "copy_field", "Copy", show=False),
        Binding("down,j", "cursor_down", "Next", show=False),
        Binding("up,k", "cursor_up", "Previous", show=False),
        Binding("g", "cursor_first", "First", show=False),
        Binding("G", "cursor_last", "Last", show=False),
    ]

    CSS = """
    RecordViewScreen {
        align: center middle;
        background: transparent;
    }

    #record-view-dialog {
        width: 90;
        max-width: 90%;
        height: auto;
        max-height: 80%;
    }

    #record-view-list {
        height: auto;
        max-height: 100%;
        border: none;
        background: $surface;
    }
    """

    def __init__(self, fields: list[tuple[str, Any]], title: str = "Record") -> None:
        """Initialize the record view.

        Args:
            fields: (column name, value) pairs in result-column order.
                    Values are raw cell values; None renders as NULL.
            title: Dialog title (e.g. "Row 3 of 42").
        """
        super().__init__()
        self._fields = fields
        self._title = title

    @property
    def fields(self) -> list[tuple[str, Any]]:
        return self._fields

    def compose(self) -> ComposeResult:
        shortcuts = [("Expand", "<enter>"), ("Copy", "y"), ("Close", "<esc>")]
        with Dialog(id="record-view-dialog", title=self._title, shortcuts=shortcuts):
            yield OptionList(*self._render_options(), id="record-view-list")

    def on_mount(self) -> None:
        option_list = self.query_one("#record-view-list", OptionList)
        if option_list.option_count:
            option_list.highlighted = 0
        option_list.focus()

    def _render_options(self) -> list[Option]:
        name_width = max((len(name) for name, _value in self._fields), default=0)
        options: list[Option] = []
        for name, value in self._fields:
            line = Text()
            line.append(name.ljust(name_width), style="bold cyan")
            line.append("  ")
            if value is None:
                line.append("NULL", style="dim italic")
            else:
                # One line per field: collapse newlines and truncate long values.
                text = " ".join(str(value).splitlines())
                if len(text) > _MAX_VALUE_DISPLAY_LENGTH:
                    text = text[:_MAX_VALUE_DISPLAY_LENGTH] + "…"
                line.append(text)
            line.no_wrap = True
            line.overflow = "ellipsis"
            options.append(Option(line))
        return options

    def _highlighted_field(self) -> tuple[str, Any] | None:
        option_list = self.query_one("#record-view-list", OptionList)
        index = option_list.highlighted
        if index is None or not (0 <= index < len(self._fields)):
            return None
        return self._fields[index]

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._expand_index(event.option_index)

    def action_expand_field(self) -> None:
        option_list = self.query_one("#record-view-list", OptionList)
        if option_list.highlighted is not None:
            self._expand_index(option_list.highlighted)

    def _expand_index(self, index: int) -> None:
        if not (0 <= index < len(self._fields)):
            return
        from sqlit.domains.results.ui.screens.value_view import ValueViewScreen

        name, value = self._fields[index]
        self.app.push_screen(ValueViewScreen(str(value) if value is not None else "NULL", title=name))

    def action_copy_field(self) -> None:
        field = self._highlighted_field()
        if field is None:
            return
        _name, value = field
        copy_text = getattr(self.app, "_copy_text", None)
        if callable(copy_text):
            copy_text(str(value) if value is not None else "NULL")
            from sqlit.shared.ui.widgets import flash_widget

            try:
                flash_widget(self.query_one("#record-view-list"))
            except Exception:
                pass
        else:
            self.notify("Copy unavailable", timeout=2)

    def action_cursor_down(self) -> None:
        self.query_one("#record-view-list", OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#record-view-list", OptionList).action_cursor_up()

    def action_cursor_first(self) -> None:
        option_list = self.query_one("#record-view-list", OptionList)
        if option_list.option_count:
            option_list.highlighted = 0

    def action_cursor_last(self) -> None:
        option_list = self.query_one("#record-view-list", OptionList)
        if option_list.option_count:
            option_list.highlighted = option_list.option_count - 1

    def action_cancel(self) -> None:
        self.dismiss(None)

    def check_action(self, action: str, parameters: Any) -> bool | None:
        if self.app.screen is not self:
            return False
        return super().check_action(action, parameters)
