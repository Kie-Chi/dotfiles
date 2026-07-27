# TUI Frontend Boundary

Run the first frontend from an applied profile with:

```bash
envy tui
```

From a repository checkout, the same command falls back to
`cargo run --manifest-path resources/scripts/envy-tui/Cargo.toml` when `cargo` is available.
`tui` is also registered in the Typer command tree, so it appears in
`envy --help`, shell completion, and `envy tui --help`; the shell wrapper keeps
an exact `envy tui` fast path only for launching the installed binary.

Envy keeps policy, Nix evaluation, registry resolution, and mutation safety in
the Python CLI. The TUI is a thin frontend that invokes these commands and
renders their structured output; it does not parse Rich tables or reimplement
software policy.

## Current protocol

Read-only views expose versioned JSON documents through `--json`, including:

```bash
envy config show --json
envy status --json
envy sw ls --details --json
envy sw why firefox --json
envy host status --json
envy host matrix --json
envy history --json
envy plan --json
```

Software desired-state mutations use the frontend envelope from
`resources/scripts/envy/jsonio.py`:

```json
{
  "schemaVersion": 1,
  "command": "software.add",
  "ok": true,
  "data": {
    "result": "dry-run",
    "plan": {
      "group": {"id": "homebrew.system.cask"},
      "item": "firefox",
      "expected": {"effective": true},
      "changed": true
    }
  },
  "warnings": []
}
```

Use a two-step interaction for mutations:

```text
TUI → envy sw add ... --dry-run --json
TUI ← plan
TUI → envy sw add ... --yes --json
TUI ← applied result
```

JSON mutations require `--yes` before writing. A missing `--yes` returns
`ok=false` with `error.code = "confirmation-required"`; registry failures,
policy blocks, and apply failures have separate error codes. Exit status remains
meaningful for scripts and the TUI.

## Frontend rules

- Treat `schemaVersion` as a compatibility boundary and ignore unknown fields.
- Use stable IDs and canonical group IDs as keys; display `name`, `label`, and
  `ref` only as presentation fields.
- Do not invoke registry searches from completion or from the TUI merely to
  populate a list. `sw search` and its exact identity index are the data source.
  The interactive Search screen invokes the complete provider set in a
  background worker; cached queries render quickly without omitting providers.
- Keep mutation confirmation in the frontend, but leave validation and rollback
  in Envy. Never edit `hosts/*` directly from the TUI.
- Read stderr and exit status for process failures; parse stdout only when the
  command was requested with `--json`.

## Current implementation

The first frontend now lives in `resources/scripts/envy-tui/` and is implemented with
Rust/Ratatui and Crossterm. It currently provides Dashboard, Software, Search,
Doctor, and History screens with background command execution, keyboard
navigation, loading/error states, scrolling, and a help overlay. Each page is
loaded only on first visit and then kept in memory for the lifetime of the TUI;
switching tabs does not launch another backend process. Search results are
cached independently for the 12 most recent submitted queries.

Pressing `r` explicitly refreshes the active page. When cached content exists,
the TUI keeps rendering it with a `refreshing` indicator instead of replacing
the entire view with a loading screen. Dashboard uses one `envy status --json`
process so machine, Git, generation, software, and Doctor data come from one
coherent manifest snapshot. Loading also seeds the Doctor page cache because
the dashboard response already contains the complete doctor payload.

The Software page supports guarded availability changes. Move the selected row
with `j`/`k` or the arrow keys and press `Enter`/`Space`. The TUI first calls
`envy sw add/rm ... --dry-run --json`, renders the verified include/exclude plan,
and applies it only after a second `Enter`/`y` confirmation through
`--yes --json`. It never edits a machine file itself. Successful mutations
invalidate Dashboard, Software, Doctor, and search caches before reloading the
Software page; policy blocks are displayed without discarding the cached view.
After a successful policy write, a follow-up overlay offers Preview, Apply,
Doctor, or keep-pending actions. Long workflows temporarily suspend the alternate
screen, inherit the real terminal for sudo and complete command output, then
return to the TUI and refresh affected views.

The interactive inspection workflows are:

- Software `/` filters the already loaded policy locally across group, item,
  reference, version, and state. The filter stays visible as an in-page input
  instead of obscuring the table. `Ctrl-U` resets it and `Esc` clears it.
  `w`/`i` calls `envy sw why <item> --group <group> --json` and shows both
  effective state and machine/external ownership.
- Search rows are selectable. `Enter`/`a` matches the result's ecosystem and
  kind against evaluated manifest group metadata, asks the user to choose a
  compatible group, and sends the canonical registry reference to the same
  guarded dry-run/confirmation workflow. If no manifest group accepts the
  result, search stays read-only and no reference is synthesized. The query is
  always shown in an in-page input, remains available while providers are
  loading, accepts bracketed paste, and can be reset with `Ctrl-U`.
- Doctor `Enter`/`i` shows the complete section, status, result, hint, structured
  details, and proposed action. Pressing `x` may run only the allow-listed
  `envy apply`, macOS `open-app`, or `open-settings` actions after a second
  confirmation; arbitrary doctor payload commands are never executed.
- History `Space` marks a generation and `d`/`Enter` compares it with the
  selected generation. Without a mark, the selected generation is compared
  with the current one. The dialog includes both generation identities and the
  complete closure diff; long detail dialogs scroll with `j`/`k`, the arrows,
  or the mouse wheel and show the current scroll position. Dialog controls stay
  fixed below the scrolling content.

Navigation is consistent across lists: arrows or `j`/`k` move one row,
`PageUp`/`PageDown` move one viewport, and `Home`/`End` or `g`/`G` jump to the
first or last row. The title shows the selected position and total row count,
and scrolling is clamped so a selection cannot disappear beyond an empty
viewport. The mouse wheel moves lists and chooser selections as well as detail
content.

`Esc` is reserved for cancelling the current interaction, clearing a filter or
mark, or closing a dialog; it does not unexpectedly exit from a normal page.
Press `q` to quit. The footer adapts to terminal width, keeping `? help` and
`q quit` visible in narrow terminals while exposing richer page-specific hints
when space permits. Search, Software, Doctor, and History also render explicit
loading and empty states instead of an ambiguous blank table.

The Rust source is separated by responsibility: `main.rs` owns only terminal
lifecycle, `app.rs` owns interaction state, `backend.rs` owns JSON subprocess
boundaries and response validation, `model.rs` owns typed view models, and
`ui.rs` owns Ratatui rendering. This keeps future screens from growing another
single-file frontend while preserving Envy as the only policy authority.

It intentionally remains a separate binary calling the existing `envy`
executable. This keeps the policy engine in Python and makes the frontend a
single native artifact suitable for Nix/Home Manager installation. Ink remains
a reasonable option for a quick prototype, but is no longer the selected
implementation direction.
