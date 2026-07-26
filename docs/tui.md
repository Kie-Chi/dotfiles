# TUI Frontend Boundary

Run the first frontend from an applied profile with:

```bash
envy tui
```

From a repository checkout, the same command falls back to
`cargo run --manifest-path tools/envy-tui/Cargo.toml` when `cargo` is available.

Envy keeps policy, Nix evaluation, registry resolution, and mutation safety in
the Python CLI. A future TUI should be a thin frontend that invokes these
commands and renders their structured output; it should not parse Rich tables
or reimplement software policy.

## Current protocol

Read-only views expose versioned JSON documents through `--json`, including:

```bash
envy config show --json
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

The first frontend now lives in `tools/envy-tui/` and is implemented with
Rust/Ratatui and Crossterm. It currently provides Dashboard, Software, Search,
Doctor, and History screens with background command execution, keyboard
navigation, loading/error states, scrolling, and a help overlay. Each page is
loaded only on first visit and then kept in memory for the lifetime of the TUI;
switching tabs does not launch another backend process. Search results are
cached independently for the 12 most recent submitted queries.

Pressing `r` explicitly refreshes the active page. When cached content exists,
the TUI keeps rendering it with a `refreshing` indicator instead of replacing
the entire view with a loading screen. Dashboard loading also seeds the Doctor
page cache because the dashboard response already contains the complete doctor
payload.

It intentionally remains a separate binary calling the existing `envy`
executable. This keeps the policy engine in Python and makes the frontend a
single native artifact suitable for Nix/Home Manager installation. Ink remains
a reasonable option for a quick prototype, but is no longer the selected
implementation direction.
