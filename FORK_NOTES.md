# Fork notes

Brad's fork of [Maxteabag/sqlit](https://github.com/Maxteabag/sqlit) (`origin` = bradstewart/sqlit, `upstream` = Maxteabag). Working notes for future sessions. Do not open upstream PRs or comment on upstream issues without Brad's explicit go-ahead.

## Branches

| Branch | Contents |
| --- | --- |
| `record-view` | Stacks directly on upstream main. Fork-original features: whole-row record view (`i`), FK column chrome (header markers + value tint), pinned-record multi-inspect (`p` pin / `I` inspect), and cmd+c/ctrl+c cell copy. `FORK_NOTES.md` lives here only. |
| `main` | Mirrors upstream main. |
| `fk-nav-rebased`, `fk-nav-239` | **Obsolete** — upstream merged PR #239 (FK navigation) on 2026-08-06 (merge commit `41aa451`, released in v1.6.0), including extra fix commits we never had (`17005cd`..`62c44d3`). The stack was rebased onto post-merge upstream main and these branches were dropped from it; safe to delete. |

## The #239 merge rebase (2026-08-18)

When upstream merged #239, `record-view`'s ten fork-original commits were rebased onto upstream main (`28d73ed`, v1.6.0), dropping the old PR commits and our test fixup (upstream's merged version resolved the default-schema test its own way). One conflict, in `sqlit/domains/results/ui/mixins/results.py::_apply_result_table_foreign_keys`: upstream's merged fk-nav added a footer-bindings refresh at the end of the method where our commit added the `_apply_fk_column_chrome` call. Kept both (footer refresh first, then chrome).

## Fork-original material (on `record-view`)
- Record view: `i` in results opens the selected row as a dense vertical field list (`sqlit/domains/results/ui/screens/record_view.py`, `action_view_record` in the results mixin, keymap + `ResultsFocusedState` wiring). ModalScreen following the `ColumnPickerScreen` pattern; Enter/v expands a field into `ValueViewScreen`, y copies, NULLs dim-italic.
- FK column chrome: FK column headers get a dim ` →` (columns referenced by other tables' FKs get ` ←`), forward-FK values render italic (`set_foreign_key_columns` on `SqlitDataTable` in `sqlit/shared/ui/widgets_tables.py`, applied from `_apply_fk_column_chrome` in the results mixin when async FK metadata lands and on re-render when cached).
- Pinned records: `p` in results toggles a pin on the selected row (captures values at pin time + table + connection; session-only, in-memory, gone on exit); footer shows `Pins (n): I` while any exist; `I` opens the inspector (`sqlit/domains/results/ui/screens/pinned_records.py`, model + diff logic in `sqlit/domains/results/pins.py`). Same-table pins render as a side-by-side compare (identical values dimmed, differing field names marked with a dim `≠`); mixed-table pins stack per record with `table (connection)` headings — pins from other connections stay attributable rather than auto-clearing. Inside the inspector: Enter/v expand into `ValueViewScreen`, `y` copy, `x` unpin record under cursor, `X` clear all. Content is bounded at `70vh` so long pin lists scroll internally (a `max-height: 100%` never binds inside the auto-height Dialog).

- Cmd+C cell copy: `super+c` in results copies the cell directly (keymap + `ResultsFocusedState` allow). Works because Ghostty's default `super+c=copy_to_clipboard:mixed` forwards the key to the app (via the kitty keyboard protocol, which Textual enables) when the terminal has no text selection. Also added `on_data_table_selection_copied` in the results mixin: textual-fastdatatable's own `ctrl+c` binding only posts `SelectionCopied` — upstream never handled it, so plain ctrl+c copied nothing.

## Upstream re-check list

- **Pre-existing test failure**: `tests/test_install_strategy.py::test_detect_strategy_pip_user_fallback` fails on this machine (env-dependent uv-install detection). Fails identically on upstream main — not ours. Baseline: expect exactly this one failure from the CI-style unit run. (`tests/ui/test_telescope_fresh_start.py` is occasionally flaky in full runs; passes in isolation.)
- **OptionList wrap limitation**: Textual's `OptionList` ignores Rich `no_wrap` and the `text-wrap` CSS on option prompts, so the record view truncates lines to the dialog's fixed interior width (84 cells, `_MAX_LINE_LENGTH` in `record_view.py`). If upstream Textual starts honoring nowrap on options, this can become width-independent.
- **FastDataTable render cache**: label/style changes after first paint need `_clear_caches()` before `refresh()` (see `set_foreign_key_columns`) — private API, re-check on textual-fastdatatable upgrades.

## Install / revert

```sh
# install the fork build (postgres driver isn't a base dep)
uv tool install --force --reinstall ~/repositories/sqlit --with psycopg2-binary

# revert to the upstream release
uv tool install --force --reinstall sqlit-tui --with psycopg2-binary
```

Gotcha: without `--reinstall`, uv can reuse a stale cached wheel of the local build (version string `sqlit x.y.z.devN+g<sha>` won't match `git log -1`); always pass `--reinstall` and check `sqlit --version` against the current commit.

Tests: CI-style unit run is `uv run pytest tests/ --timeout=60` with the per-engine `tests/test_<engine>.py` files ignored (see `.github/workflows/ci.yml`). Postgres integration: throwaway `postgres:16-alpine` container with CI's env (testuser / TestPassword123! / test_sqlit), then `tests/test_postgresql.py` and `tests/integration/test_foreign_keys.py::TestPostgresForeignKeysIntegration`. Don't run integration tests against Brad's live localhost:2345 DB.

## Future candidates

- **Per-connection theme**: Brad wants red-on-prod styling that survives *in-app* connection switching (dbpair-style launch-time theming only covers startup). Would hook wherever the active connection changes and re-apply a per-connection theme from `connections.json` config.
