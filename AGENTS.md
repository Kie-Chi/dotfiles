# AGENTS.md — Project Guide for Chi's Nix Dotfiles

## Project Overview

Nix-based dotfiles for macOS (aarch64-darwin), using nix-darwin + home-manager + sops-nix for system/user configuration with encrypted secret management.

## Architecture

### Two-layer secret system

**Non-sensitive config** (`config.nix`): user name, paths, git info, proxy status, LLM URLs/models. Referenced as `cfg.xxx` in all modules. Loaded at Nix eval time from `~/.config/dotfiles/config.nix` (symlinked from repo). Passed via `extraSpecialArgs` and `_module.args`.

**Encrypted secrets** (`secrets/secrets.yaml`): passwords, API keys, proxy URLs with tokens. Managed by sops-nix, encrypted with age key. Referenced as `config.sops.secrets.xxx` (file path) or `config.sops.placeholder.xxx` (for templates). Decrypted only at activation time — **never available as string values at Nix eval time**.

### Key files

| File | Purpose |
|---|---|
| `flake.nix` | Entry point: darwinConfigurations + devShell. Loads config.nix as `cfg`, imports sops-nix modules. |
| `config.nix` | Non-sensitive Nix attrset. Gitignored, symlinked to `~/.config/dotfiles/config.nix`. |
| `secrets/secrets.yaml` | sops-encrypted YAML with nested structure. Gitignored. |
| `.sops.yaml` | sops creation rules with age public key(s). |
| `home.nix` | Home-manager config: sops secrets declarations, templates, activation debug. |
| `setup.py` | Python rich + prompt_toolkit sequential CLI for initial setup and config editing. Reads existing config.nix/secrets.yaml as defaults, prompts each field in order, shows changes summary, then saves + encrypts + commits .sops.yaml. |
| `setup.sh` | Thin launcher: install Nix → enter devShell → exec setup.py. |
| `requires.sh` | Installs Nix if missing. Nothing else — devShell provides all tools. |

### Module structure

```
modules/
  cores/     — base packages, shell, git, ssh, utils
  devps/     — editor (neovim)
  desktops/  — apps, proxies, raycast-ai, wallpaper, squirrel
  darwin/    — system-level: base, apps, terminal, proxies
```

### Naming conventions

| Context | Format | Example |
|---|---|---|
| Non-sensitive config | `cfg.xxx.yyy` (Nix dot path) | `cfg.llm.dashscope.url` |
| sops secret name | `xxx-yyy-zzz` (hyphen-separated) | `sops.secrets.llm-dashscope-apikey` |
| sops secret key in YAML | `xxx/yyy/zzz` (slash-separated) | `llm/dashscope/apikey` |
| sops placeholder | Same as secret name | `config.sops.placeholder.llm-dashscope-apikey` |

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
| `nix develop` | Enter devShell (jq, sops, age, ssh-to-age, python3, textual) |
| `darwin-rebuild switch --flake .` | Apply system config |
| `sops --decrypt secrets/secrets.yaml` | View encrypted secrets |
| `sops updatekeys secrets/secrets.yaml` | Re-encrypt with updated .sops.yaml keys |

## Important rules

- **Never** put sensitive values in Nix eval-time expressions. They must go through sops (file path or template).
- **Never** commit `config.nix` or `secrets/secrets.yaml` unencrypted. They are gitignored.
- The `.sops.yaml` file CAN be committed once it has real age public keys.
- When adding new secret fields: add to `SECRET_FIELDS` in `setup.py`, declare in `home.nix` under `sops.secrets`, and add the `yaml_path` entry to `secrets.yaml`.
- When adding new non-sensitive config: add to `CONFIG_FIELDS` in `setup.py`, and it will auto-appear in `config.nix`.
- Module function signatures use `cfg` (not `secrets`) for non-sensitive config values.
- sops-nix on darwin uses activation scripts (not systemd), so secrets are decrypted during `darwin-rebuild switch`.