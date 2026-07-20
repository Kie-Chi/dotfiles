# AGENTS.md — Project Guide for Chi's Nix Dotfiles

## Project Overview

Nix-based dotfiles for macOS (aarch64-darwin), using nix-darwin + home-manager + sops-nix for system/user configuration with encrypted secret management.

## Architecture

### Two-layer secret system

**Non-sensitive config** (`config.nix`): user name, paths, git info, proxy status, and local LLM URLs/models. Referenced as `cfg.xxx` in all modules. Loaded at Nix eval time from `~/.config/dotfiles/config.nix` (symlinked from repo). Passed via `extraSpecialArgs` and `_module.args`.

**Encrypted secrets** (`secrets/secrets.yaml`): passwords, API keys, and proxy URLs with tokens. Managed by sops-nix, encrypted with age key. Referenced as `config.sops.secrets.xxx` (file path) or `config.sops.placeholder.xxx` (for templates). Decrypted only at activation time — **never available as string values at Nix eval time**.

### Key files

| File | Purpose |
|---|---|
| `flake.nix` | Entry point: darwinConfigurations + devShell. Loads config.nix as `cfg`, imports sops-nix modules. |
| `config.nix` | Non-sensitive Nix attrset. Gitignored, symlinked to `~/.config/dotfiles/config.nix`. |
| `secrets/secrets.yaml` | sops-encrypted YAML with nested structure. Gitignored. |
| `.sops.yaml` | sops creation rules with age public key(s). |
| `home.nix` | Home-manager config: sops secrets declarations, templates, activation debug. |
| `modules/agents/` | Agent installers, provider wrappers, declarative skill catalog, and per-machine skill selection. |
| `docs/agents.md` | Architecture and maintenance guide for agent providers and skill subpackages. |
| `setup.py` | Python rich + prompt_toolkit sequential CLI for initial setup and config editing. Reuses `envy.config` schema/read-write helpers, prompts each field in order, shows changes summary, then saves + encrypts + commits .sops.yaml. |
| `resources/scripts/envy/config.py` | Single source of truth for config/secret fields, validation, local refine/check commands, and safe config.nix/secrets.yaml I/O. |
| `resources/scripts/envy/schemas/apps.py` | Single source of truth for app doctor specs: bundles, commands, processes, state paths, login hints, permissions, aliases, and custom checkers. |
| `resources/scripts/envy/doctor/checks/apps/` | App doctor implementation: generic checks, registry, app-specific auth/login checks, and VS Code checks. |
| `resources/scripts/envy/log.py` | Shared logging helpers for envy commands. |
| `docs/doctor.md` | Knowledge base for `envy doctor`: app detection, login checks, macOS TCC permissions, and maintenance workflow. |
| `setup.sh` | Thin launcher: install Nix → enter devShell → exec setup.py. |
| `requires.sh` | Installs Nix if missing. Nothing else — devShell provides all tools. |

### Module structure

```
modules/
  agents/    — LLM agent installers, wrappers, and skill discovery
  cores/     — base packages, shell, git, ssh, utils
  devps/     — editor (neovim)
  desktops/  — apps, proxies, raycast-ai, wallpaper, squirrel
  darwin/    — system-level: base, apps, terminal, proxies
```

### Naming conventions

| Context | Format | Example |
|---|---|---|
| Non-sensitive config | `cfg.xxx.yyy` (Nix dot path) | `cfg.llm.steps.url` |
| sops secret name | `xxx-yyy-zzz` (hyphen-separated) | `sops.secrets.llm-steps-apikey` |
| sops secret key in YAML | `xxx/yyy/zzz` (slash-separated) | `llm/steps/apikey` |
| sops placeholder | Same as secret name | `config.sops.placeholder.llm-steps-apikey` |

### Secret flow

1. `setup.py` sequential CLI collects values → writes `config.nix` + unencrypted `secrets.yaml` → encrypts with `sops --encrypt --in-place` → commits `.sops.yaml`
2. `darwin-rebuild switch` evaluates `flake.nix` → loads `config.nix` as `cfg` → sops-nix decrypts `secrets.yaml` at activation
3. Decrypted secrets available as file paths (`config.sops.secrets.xxx.path`) or in rendered templates (`config.sops.placeholder.xxx`)
4. Templates: `env-secrets` (API_KEY env vars), `mihomo-config` (proxy config), `raycast-providers` (LLM providers YAML)

### age key management

Hybrid approach (in `setup.py`):
- If `~/.ssh/id_ed25519` exists → `ssh-to-age` converts it to age key
- Else → `age-keygen` generates new key
- Key stored at `~/Library/Application Support/sops/age/keys.txt` (macOS standard path)
- New device: add age public key to `.sops.yaml`, then `sops updatekeys secrets/secrets.yaml`

## Commands

| Command | Purpose |
|---|---|
| `bash setup.sh` | Run setup TUI (auto-enters devShell) |
| `envy config check` | Check config.nix and secrets.yaml without writing |
| `envy config refine` | Complete/migrate local config.nix and secret paths before apply |
| `envy doctor` / `envy dr` | Check config, app install/running/state/login hints, and macOS permissions |
| `envy doctor apps --only chrome,codex` | Check selected apps only. Values can be repeated or comma-separated; aliases are defined in `APP_ALIASES`. |
| `envy doctor permissions` | Check only declared macOS TCC permissions |
| `nix develop` | Enter devShell (jq, sops, age, ssh-to-age, python3, textual) |
| `darwin-rebuild switch --flake .` | Apply system config |
| `sops --decrypt secrets/secrets.yaml` | View encrypted secrets |
| `sops updatekeys secrets/secrets.yaml` | Re-encrypt with updated .sops.yaml keys |

## Doctor architecture

`envy doctor` is intentionally declarative first. App coverage starts in `resources/scripts/envy/schemas/apps.py`:

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

Generic app checks live in `resources/scripts/envy/doctor/checks/apps/checkers.py` and should remain boring: installed bundle, command availability, running state, expected local state, login hint, and permissions. App-specific checks belong in focused modules such as `auth.py` or `vscode.py`.

Current custom app checks:

- Chrome: reads local profile preference markers for signed-in account and sync state; it never prints email/account values.
- Codex: checks `OPENAI_API_KEY` or `~/.codex/auth.json` marker presence without printing secrets.
- GitHub CLI: runs `gh auth status` and reports only authenticated/not authenticated.
- Tailscale: runs `tailscale status --json` with a timeout and checks backend/auth state.
- VS Code: checks Settings Sync, account markers, Copilot markers, and local extension visibility when `vscode.mode = "local"`.

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
- **Never** commit `config.nix` or `secrets/secrets.yaml` unencrypted. They are gitignored.
- The `.sops.yaml` file CAN be committed once it has real age public keys.
- When adding new secret fields: add to `SECRET_FIELDS` in `resources/scripts/envy/config.py`, declare in `home.nix` under `sops.secrets`, and let `envy config refine` create the `yaml_path` entry in `secrets.yaml`.
- When adding new non-sensitive config: add to `CONFIG_FIELDS` in `resources/scripts/envy/config.py`, and it will be used by setup plus `envy config refine`.
- When adding an LLM agent/provider: keep its installer and stable command wrapper in `modules/agents`; never manage application-owned auth, history, cache, or session files declaratively.
- When adding a reusable skill: create `modules/agents/skills/<skill-name>/SKILL.md`, register it in `skills/catalog.nix`, and select it through `agents.skills.active`. Keep detailed references and scripts inside the skill and load them only when needed.
- When adding a new app doctor target: add an `AppSpec` in `resources/scripts/envy/schemas/apps.py`, add aliases in `APP_ALIASES` when useful, and prefer generic fields before writing a custom checker.
- When adding a new login/auth check: implement it in `resources/scripts/envy/doctor/checks/apps/auth.py` or another focused module, register it in `_load_custom_checkers()`, and never print account names, emails, tokens, API keys, cookies, or raw secret values.
- When adding a new app permission check: add `PermissionReq` entries in `AppSpec.permissions`. Remember that missing TCC records may mean "not requested yet", not necessarily "denied".
- Module function signatures use `cfg` (not `secrets`) for non-sensitive config values.
- sops-nix on darwin uses activation scripts (not systemd), so secrets are decrypted during `darwin-rebuild switch`.
