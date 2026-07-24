# AGENTS.md — Project Guide for Chi's Nix Dotfiles

## Project Overview

Cross-platform Nix dotfiles for Darwin (aarch64-darwin) and Linux (x86_64-linux), using one `master` branch, nix-darwin/Home Manager, and sops-nix.

## Architecture

### Machine configuration and secrets

**Non-sensitive machine config** (`hosts/darwin/<id>.nix` or `hosts/linux/<id>.nix`): the sole source for user name, paths, git info, VS Code mode, local LLM URLs/models, and machine software policy. Darwin hosts additionally own Darwin-only proxy/Homebrew policy; Linux has no proxy schema. Values use the `envy.*` option tree and modules read them through `config.envy.*`.

**Device metadata** (`.device-label`): Gitignored TOML containing `device.machine_id` and `device.sops_label`. It selects the default Envy flake target and labels the device age key, but is not a second Nix configuration source. `envy config check/refine` validates and migrates it.

**Encrypted secrets** (`secrets/secrets.yaml`): passwords, API keys, and proxy URLs with tokens. Managed by sops-nix, encrypted with age key. Referenced as `config.sops.secrets.xxx` (file path) or `config.sops.placeholder.xxx` (for templates). Decrypted only at activation time — **never available as string values at Nix eval time**.

### Key files

| File | Purpose |
|---|---|
| `flake.nix` | Scans `hosts/darwin` and `hosts/linux`, creating `darwinConfigurations` and `homeConfigurations`. |
| `darwin.nix` | Single nix-darwin composition root; imports the Darwin contribution owned by each feature. |
| `secrets/secrets.yaml` | Tracked sops-encrypted YAML with nested structure; plaintext must never be committed. |
| `.sops.yaml` | sops creation rules with age public key(s). |
| `home.nix` | Thin cross-platform Home Manager composition root plus username, home directory, and state-version initialization. |
| `hosts/default.nix` | Optional shared defaults for newly created/importing machine modules. |
| `hosts/<platform>/<id>.nix` | Final per-machine module and sole non-sensitive machine configuration source. |
| `.device-label` | Gitignored device-local TOML identity: machine target and sops key label only. |
| `modules/envy/options.nix` | `envy.*` schema for meaningful machine values, package/Homebrew selections, and metadata. |
| `modules/envy/darwin.nix` / `modules/envy/linux.nix` / `modules/envy/home.nix` | Platform manifest and package/Homebrew aggregators. |
| `modules/llm/default.nix` | Shared LLM sops declarations, environment template, and shell integration. |
| `modules/cores/secrets.nix` | Core password secret required by host-level activation tasks. |
| `modules/agents/` | Agent installers, provider wrappers, declarative skill catalog, and shared skill selection. |
| `docs/agents.md` | Architecture and maintenance guide for agent providers and skill subpackages. |
| `install.sh` | Repository-independent bootstrap: clone/reuse a checkout, then hand off to setup with an interactive terminal. |
| `setup.py` | Python rich + prompt_toolkit sequential CLI for initial setup and config editing. Reuses `envy.config` schema/read-write helpers, manages machine software exclusions, shows a change summary, then saves, encrypts, and offers one scoped Git commit for the selected machine and changed sops files. |
| `resources/scripts/envy/config.py` | Machine managed-block and secret validation/read-write engine used by setup and `envy config`. |
| `resources/scripts/envy/evaluation.py` | Shared reader for the evaluated machine manifest, with process-local and Git-fingerprinted persistent caches used by config views, setup, software policy, and doctor. |
| `resources/scripts/envy/software.py` | Managed machine-exclusion block, checkbox model, CLI, atomic writes, and evaluation rollback. |
| `resources/scripts/envy/host.py` | Creates and inspects per-machine files; init only asks for Machine ID and import/copy mode. |
| `resources/scripts/envy/schemas/{common,darwin,linux}/` | Common and platform-only config/app schemas; top-level schema modules dispatch to the current platform. |
| `resources/scripts/envy/doctor/checks/apps/` | App doctor implementation: generic checks, registry, app-specific auth/login checks, and VS Code checks. |
| `resources/scripts/envy/log.py` | Shared logging helpers for envy commands. |
| `docs/doctor.md` | Knowledge base for `envy doctor`: app detection, login checks, macOS TCC permissions, and maintenance workflow. |
| `docs/machines.md` | Multi-machine option model, host initialization, package overrides, and shared-branch workflow. |
| `docs/install.md` | Remote bootstrap, pinned release, custom target, and existing-checkout behavior. |
| `setup.sh` | Thin launcher: install Nix → enter devShell → exec setup.py. |
| `requires.sh` | Installs Nix if missing. Nothing else — devShell provides all tools. |

### Module structure

```
modules/
  envy/      — machine value/selection schema, final aggregators, and manifest
  llm/       — shared LLM credentials, environment template, and shell integration
  agents/    — LLM agent installers, wrappers, and skill discovery
  cores/     — base packages, shell, git, ssh, utils
  devps/     — common editor/VS Code features plus linux/ implementation
  desktops/  — public feature entry plus darwin/ and linux/ implementations
```

`machinePlatform` is an externally supplied module argument used for platform
imports and machine policy. Do not add a second `isDarwin` special argument.
`pkgs.stdenv.hostPlatform` is used inside low-level package implementations and
to assert that the selected machine platform matches the Nix target platform.
Platform-specific implementation files do not repeat the platform check; their
composition root or cross-platform dispatcher owns that boundary.

### Naming conventions

| Context | Format | Example |
|---|---|---|
| Non-sensitive machine config | `envy.xxx.yyy` (Nix option) | `envy.llm.steps.url` |
| sops secret name | `xxx-yyy-zzz` (hyphen-separated) | `sops.secrets.llm-steps-apikey` |
| sops secret key in YAML | `xxx/yyy/zzz` (slash-separated) | `llm/steps/apikey` |
| sops placeholder | Same as secret name | `config.sops.placeholder.llm-steps-apikey` |

### Secret flow

1. `setup.py` collects values → writes the managed blocks in the selected machine file + temporary plaintext `secrets.yaml` → encrypts secrets with sops → offers a scoped commit for that machine file and changed sops files
2. The platform apply command evaluates `hosts/<platform>/<id>.nix`; sops-nix decrypts secrets during activation
3. Decrypted secrets available as file paths (`config.sops.secrets.xxx.path`) or in rendered templates (`config.sops.placeholder.xxx`)
4. Owning features declare their secrets and templates: `llm` owns `env-secrets`, Darwin proxies own `mihomo-config`, and Raycast owns `raycast-providers`

### age key management

Hybrid approach (in `setup.py`):
- If `~/.ssh/id_ed25519` exists → `ssh-to-age` converts it to age key
- Else → `age-keygen` generates new key
- Key stored at `~/Library/Application Support/sops/age/keys.txt` on Darwin or `~/.config/sops/age/keys.txt` on Linux
- New device: add age public key to `.sops.yaml`, then `sops updatekeys secrets/secrets.yaml`

## Commands

| Command | Purpose |
|---|---|
| `bash install.sh` | Clone/reuse the configured checkout and hand off to setup; intended to work as a raw GitHub bootstrap. |
| `bash setup.sh` | Run setup TUI (auto-enters devShell) |
| `envy config check` | Check `.device-label`, the selected machine file, and secrets.yaml without writing |
| `envy config refine` | Migrate/refine device metadata, the machine managed block, and secret paths before apply |
| `envy config show` | Show evaluated scalar values plus package/Homebrew include, exclude, and effective lists |
| `envy config software` | List software checkbox state; use `enable/disable <group> <name>` for machine exclusions |
| `envy config edit` | Open the selected versioned machine file in `$EDITOR` |
| `envy host init [id]` | Create a machine module by importing or copying `hosts/default.nix`; never selects software |
| `envy host list` / `envy host status` | List repository machines or show the locally selected target |
| `envy host select <id>` | Change `.device-label`'s machine ID without changing machine policy |
| `envy host check [id]` | Evaluate one machine system derivation without applying it |
| `envy sync --no-apply` | Fast-forward the shared `master` branch without applying |
| `envy sync --build-only` | Fast-forward and build only the selected machine |
| `envy push` | Classify worktree plus outgoing commits, confirm shared impact, and push only after remote-ahead checks |
| `envy push --machine-only` / `--self` | Restrict a push to machine files or to the selected machine file, respectively |
| `envy doctor` / `envy dr` | Check platform config, app install/running/state/login hints, and Darwin TCC where applicable |
| `envy doctor apps --only chrome,codex` | Check selected apps only. Values can be repeated or comma-separated; aliases are defined in `APP_ALIASES`. |
| `envy doctor apps --only perm` | Check only declared macOS TCC permissions |
| `nix develop` | Enter devShell (jq, sops, age, ssh-to-age, Python, Typer, Rich, and prompt_toolkit) |
| `envy apply` | Apply the locally selected `path:.#<machine-id>` target |
| `sops --decrypt secrets/secrets.yaml` | View encrypted secrets |
| `sops updatekeys secrets/secrets.yaml` | Re-encrypt with updated .sops.yaml keys |

## Doctor architecture

`envy doctor` is intentionally declarative first. Shared app coverage belongs in `schemas/common/apps.py`; platform-only coverage belongs in `schemas/darwin/apps.py` or `schemas/linux/apps.py`; `schemas/apps.py` is only the dispatcher.

| Field | Meaning |
|---|---|
| `bundles` | `.app` bundle names to find in `/Applications`, `~/Applications`, `~/Applications/Home Manager Apps`, and `/Library/Input Methods`. |
| `commands` | CLI commands that should exist on `PATH`, checked with `shutil.which`. |
| `processes` + `bundle_id` | Running-state signals. `bundle_id` is checked with AppleScript, process names with `pgrep`/`ps`. |
| `should_run` | Marks background apps that should warn when not running. |
| `state_paths` | Local config/state markers that prove the app has been opened or configured. |
| `login_hint` | Human follow-up hint when login cannot be verified automatically. Do not use this for sensitive values. |
| `permissions` | TCC permissions to verify from macOS' TCC database. |
| `checkers` | Names of app-specific custom checks loaded by `resources/scripts/envy/doctor/checks/apps/checkers.py`. |
| `casks` / `brews` / `packages` | Installation entries used to compare the app against the evaluated machine manifest. |

Generic app checks live in `resources/scripts/envy/doctor/checks/apps/checkers.py` and should remain boring: installed bundle, command availability, running state, expected local state, login hint, and permissions. App-specific checks belong in focused modules such as `auth.py` or `vscode.py`.

Current custom app checks:

- Chrome: reads local profile preference markers for signed-in account and sync state; it never prints email/account values.
- Codex: checks `OPENAI_API_KEY` or `~/.codex/auth.json` marker presence without printing secrets.
- GitHub CLI: runs `gh auth status` and reports only authenticated/not authenticated.
- Tailscale: runs `tailscale status --json` with a timeout and checks backend/auth state.
- VS Code: checks Settings Sync, account markers, Copilot markers, and local extension visibility when `envy.vscode.mode = "local"`.

See `docs/doctor.md` before changing app doctor behavior.

## macOS permissions / TCC

macOS privacy permissions are demand-driven. Camera, Microphone, Screen Recording, Accessibility, Automation, and similar entries usually appear in System Settings only after the target app actually requests the protected capability. `envy doctor` can detect declared permissions only after macOS has written a TCC record, and reading the TCC database itself usually requires Full Disk Access for the terminal app.

For meeting apps such as Tencent Meeting or Feishu, open the app and actually start the protected feature once:

- Camera: join/start a meeting and enable camera.
- Microphone: join/start a meeting and unmute.
- Screen Recording: start screen sharing.

`tccutil` can reset permission decisions, but it cannot grant permissions. Do not edit TCC databases directly; it is unsupported and can be blocked by SIP. For managed fleets, pre-approval belongs in MDM PPPC profiles, not this dotfiles repo.

## Important rules

- **Never** put sensitive values in Nix eval-time expressions. They must go through sops (file path or template).
- Setup may show whether a secret is set, but its lists, edit context, input, and summaries must never display secret values.
- Keep `install.sh` repository-independent and policy-free: it may clone/reuse a checkout and hand off to setup, but machine creation, software selection, config, and secrets belong to `setup.py`.
- Keep all machines on the shared `master` branch. Machine differences belong in `hosts/<platform>/<id>.nix`, not long-lived platform or machine branches.
- Do not introduce a required profile layer. A machine module is the final unit of configuration; `hosts/default.nix` is only an optional imported default.
- Keep package lists and custom derivations in their owning business modules. `modules/envy/` may declare the generic selection schema, aggregate `include`/`exclude`, and expose the manifest, but must not become a central software catalog.
- Cross-platform values stay unprefixed (`envy.vscode.mode`, `envy.packages.home.*`). Only genuinely platform-exclusive values use `envy.darwin.*` or `envy.linux.*`; Linux must not gain proxy options.
- Modules contribute cross-platform Home packages through `envy.packages.home.include`; Darwin system/font/Homebrew contributions use `envy.darwin.*`. Only the envy aggregators assign final package lists.
- `envy setup` owns only the marked `ENVY MANAGED EXCLUSIONS` block. Never move package derivations into it or rewrite hand-maintained policy outside its markers.
- Push scope checks must include both worktree paths and outgoing commits. `--machine-only` may cover several machine files; `--self` may cover only the selected machine file. Both must fail before staging when out-of-scope paths exist.
- Do not add an `enable` option merely because a setting could theoretically differ by machine. Shared infrastructure is unconditional; software is selected by package/cask/brew names; new machine options require a demonstrated behavioral difference.
- Every non-sensitive machine value belongs in `hosts/<platform>/<id>.nix`; do not recreate an ignored local Nix config layer.
- **Never** commit `secrets/secrets.yaml` unencrypted. The encrypted file is tracked.
- The `.sops.yaml` file CAN be committed once it has real age public keys.
- When adding secret fields, place the field in the common or platform config schema, declare it in the consuming feature module (not `home.nix`), gate platform-only declarations to the same platform, and let `envy config refine` create its YAML path.
- When adding a genuinely machine-specific value, decide common vs platform-only first, declare the Nix option, add the matching Python schema field, expose it in the relevant manifest, and consume it through `config.envy.*`.
- When adding an LLM agent/provider: keep its installer and stable command wrapper in `modules/agents`; never manage application-owned auth, history, cache, or session files declaratively.
- When adding a reusable skill: create `modules/agents/skills/<skill-name>/SKILL.md`, register it in `skills/catalog.nix`, and select it through `agents.skills.active`. Keep detailed references and scripts inside the skill and load them only when needed.
- When adding an app doctor target, place it in common only if its signals are platform-neutral; otherwise add it to the relevant platform app schema. Prefer generic fields before a custom checker.
- When adding a new login/auth check: implement it in `resources/scripts/envy/doctor/checks/apps/auth.py` or another focused module, register it in `_load_custom_checkers()`, and never print account names, emails, tokens, API keys, cookies, or raw secret values.
- When adding a new app permission check: add `PermissionReq` entries in `AppSpec.permissions`. Remember that missing TCC records may mean "not requested yet", not necessarily "denied".
- Modules read non-sensitive machine values from `config.envy.*`; do not reintroduce a separate `cfg` argument.
- sops-nix on darwin uses activation scripts (not systemd), so secrets are decrypted during `darwin-rebuild switch`.
