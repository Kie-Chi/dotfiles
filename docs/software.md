# Software Policy And Search

`envy software` is the software policy boundary. `envy sw` is its only top-level
alias. Software is not a `config` subcommand, and there is no top-level
`envy search` command.

## Commands

| Command | Alias | Purpose |
|---|---|---|
| `envy software` | `envy sw` | List the evaluated policy |
| `envy software list` | `envy sw ls` | List checkbox state by manifest group |
| `envy software status` | `envy sw st` | Summarize groups and selections |
| `envy software add` | `envy sw add` | Ensure an item is effective on this machine |
| `envy software remove` | `envy sw rm` | Ensure an item is not effective on this machine |
| `envy software enable` | `envy sw en` | Remove a managed machine exclusion |
| `envy software disable` | `envy sw dis` | Add a managed machine exclusion |
| `envy software search` | `envy sw se` | Search available registries concurrently |

`envy sw ls --details` includes versions and canonical references. `enable` and
`disable` take a canonical group ID and stable item ID:

```bash
envy sw add homebrew.system.cask zotero
envy sw rm homebrew.system.cask zotero --clean
envy sw dis homebrew.system.cask zotero
envy sw en homebrew.system.cask zotero
envy sw se codex --source nix,npm
```

`add` and `rm` are desired-state commands. Before writing, they display the
exact `include +/-` and `exclude +/-` plan plus the expected evaluated state,
then require confirmation. `--dry-run` stops after the plan and `--yes` accepts
it non-interactively.

- `add` removes the managed `exclude`; if no source contributes the item, it
  adds it to the managed `include`.
- `rm` normally adds the stable ID to the managed `exclude`.
- `--clean` then removes redundant managed `include`/`exclude` entries for the
  target ID, but only when the requested final state is preserved.
- An external exclusion blocks `add`; the command makes no partial change.
- Every applied plan is evaluated again. If the requested effective state is
  not reached, the managed block is rolled back.

Nix packages accept an attribute or `nix:` reference; other registry-backed
groups accept their package name or canonical reference. `--ref` associates a
custom stable ID with a canonical reference:

```bash
envy sw add nix.user.package hello
envy sw add npm.user.tool codex --ref npm:@openai/codex
```

Shell completion is manifest-aware: `add` offers restorable managed exclusions,
`rm` offers known included items, `dis` offers currently enabled items, `en`
offers Envy-managed exclusions, and `search --source` completes providers.

`include` records that an active business module contributes an item;
`exclude` is a machine-level mask and always wins when both contain the same
stable ID. `en` removes only the Envy-managed mask and then checks the evaluated
result:

- An included item that becomes effective is reported as enabled.
- An item no longer present in `include` is reported as stale-exclusion cleanup;
  removing the mask does not install it.
- An item still present in evaluated `exclude` is reported as excluded by
  another hand-written or imported policy.

## Manifest V2

`envy.machine.manifest.schemaVersion` is `2`. Software lives under
`software.groups`; the previous parallel `packages`, `homebrew`, `inclusions`,
and `exclusions` documents no longer exist.

Group IDs use exactly three dimensions:

```text
<ecosystem>.<scope>.<kind>
```

Examples:

```text
nix.user.package
nix.system.font
homebrew.system.cask
native.system.package
npm.user.tool
pypi.user.tool
url.system.artifact
```

Platform support belongs in `platforms`. Artifact origin belongs in `ecosystem`.
The apply backend belongs in `installer`; for example a PyPI tool has
`ecosystem = "pypi"` and `installer = "uv"`.

Each group contains:

| Field | Meaning |
|---|---|
| `label` | Human-readable UI label |
| `optionPath` | Nix selection option root |
| `ecosystem` | Artifact namespace or registry |
| `platforms` | Platforms on which the selection mechanism applies |
| `scope` | `user` or `system` |
| `kind` | Package/tool/font/formula/cask/repository/artifact |
| `installer` | Home Manager, nix-darwin, Homebrew, npm, uv, or native backend |
| `editable` | Whether Envy owns managed include/exclude writes |
| `reconcile` | Whether apply installs, upgrades, or removes entries |
| `selection` | Structured `include`, stable-ID `exclude`, and evaluated `effective` |

Items use `id`, `name`, optional `version`, optional canonical `ref`, and
structured provider `parameters`. Exclusions always use `id`, so changing a
package version or display name does not invalidate machine policy.

Installer-specific parameters stay on the item instead of creating more option
trees:

| Installer | Parameters |
|---|---|
| Native Linux | `names.<manager>` overrides a package name for apt/dnf/pacman/zypper; `resolver = "current-kernel-headers"` selects the correct runtime kernel package |
| uv | `with` lists extra packages passed through `uv tool install --with` |
| URL artifact | `url`, `format`, and `packageName` describe the downloaded native package |

Canonical references identify an ecosystem object independently of its pinned
version, for example `npm:@openai/codex`, `pypi:ruff`, and
`homebrew:cask/iterm2`. `version` carries the pin separately.

## Search Providers

Search is read-only and provider failures are isolated. Results are ranked by
exact/prefix match and whether the selected machine already manages the item.
Successful multi-provider results are cached for 15 minutes; `--refresh` bypasses
the cache.

| Source | Implementation |
|---|---|
| Nix | `nix search nixpkgs --json` |
| Homebrew | formula and cask searches |
| Native Linux | apt, dnf, pacman, or zypper detected at runtime |
| npm | `npm search --json` |
| PyPI | exact PyPI JSON registry lookup; uv remains the installer |
| Cargo | `cargo search` |
| Go | pkg.go.dev keyword search; there is no synthetic `go search` command |

The mirror environment is reused by command-based providers. A download mirror
does not necessarily expose a full-text search API, so PyPI and pkg.go.dev lookup
remain separate from artifact download configuration.

## Ownership

Business modules continue to own shared software entries. `modules/envy/`
defines selection types, computes effective values, and emits manifest groups.
`modules/software/` owns generic npm, uv, native package, and fixed-URL installer
behavior. The single `ENVY MANAGED SOFTWARE` block assigns the existing
ecosystem `.include` and `.exclude` options directly. `add/rm` may update both;
setup and `en/dis` update only exclusions while preserving managed includes.
No workflow rewrites hand-maintained policy or shared module contributions.
