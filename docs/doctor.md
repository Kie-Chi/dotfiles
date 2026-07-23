# Doctor Knowledge Base

`envy doctor` checks whether the local dotfiles setup is usable after setup or `envy apply`. It covers config/secrets health, app installation, CLI command availability, running state, local state markers, login/auth hints, and macOS privacy permissions.

## Quick Commands

```bash
envy doctor
envy dr
envy doctor config
envy doctor config --only secr
envy doctor apps
envy doctor apps --only chrome,codex,gh,tailscale
envy doctor apps --only codex,vscode --only auth,sync
envy doctor apps --only perm
envy doctor apps --strict
```

`--only` accepts section tokens, canonical app keys, and aliases from `APP_ALIASES`. Values can be repeated or comma-separated. App selections are ORed with other apps; section selections are ORed with other sections; app and section selections are ANDed together.

## File Map

| File | Role |
|---|---|
| `resources/scripts/envy/doctor/app.py` | Typer commands for `envy doctor`, `envy dr`, `all`, `apps`, and `config`. |
| `resources/scripts/envy/doctor/runner.py` | Runs sections, renders the Rich table, computes exit codes. |
| `resources/scripts/envy/doctor/model.py` | Shared `CheckResult` model, section constants, and `ok/warn/error/info` helpers. |
| `resources/scripts/envy/doctor/selection.py` | Unified `--only` parser for section/app filters. |
| `resources/scripts/envy/doctor/policy.py` | Evaluates the selected machine manifest and decides whether an app is expected on this machine. |
| `resources/scripts/envy/schemas/apps.py` | Declarative app registry and app aliases. Start here when adding app coverage. |
| `resources/scripts/envy/doctor/checks/apps/checkers.py` | Generic app checks and custom checker registry. |
| `resources/scripts/envy/doctor/checks/apps/auth.py` | App-specific auth/login checks such as Chrome, Codex, GitHub CLI, and Tailscale. |
| `resources/scripts/envy/doctor/checks/apps/vscode.py` | VS Code Settings Sync, auth, Copilot, and extension checks. |
| `resources/scripts/envy/doctor/probes/` | Low-level filesystem, process, command, TCC, and VS Code probes. |

## Section Semantics

Doctor commands are entrypoint scopes; result row sections are semantic check categories. For example, `envy doctor apps` still runs app checks, but its rows can appear under `apps`, `runs`, `stat`, `auth`, `sync`, `perm`, or `host`.

| Section | Aliases | Meaning |
|---|---|---|
| `self` | `doctor`, `doc` | Doctor tool metadata and invocation input, such as version, source, source priority, or unknown `--only` selections. |
| `conf` | `config`, `cfg` | Non-sensitive config values and dotfiles config files. |
| `secr` | `secrets`, `secret`, `sec` | age, sops, `secrets.yaml`, and decryptability. |
| `apps` | `install`, `inst` | Installed/visible artifacts: app bundles, CLI commands, code CLI, and VS Code extensions. |
| `runs` | `runtime`, `run` | Running processes, daemons, backend states, and unreadable runtime/status APIs. |
| `stat` | `state` | Local app state/config files and readable state markers. |
| `auth` |  | Login, account, API key, identity, and account-like markers such as Copilot state. |
| `sync` |  | Explicit data/settings sync capability, such as Chrome Sync and VS Code Settings Sync. |
| `perm` | `privacy`, `priv`, `permission`, `permissions`, `perms`, `pers` | App-owned macOS TCC permissions such as Camera, Microphone, Screen Recording, and Accessibility. |
| `host` | `system`, `sys` | Global host prerequisites not owned by one app, such as being unable to read the macOS TCC database. |

Use `section:<token>` and `app:<token>` to disambiguate if a future app alias overlaps with a section token.

## AppSpec Fields

`AppSpec` is the contract between the app registry and the doctor engine.

| Field | Use |
|---|---|
| `name` | Human-readable name in output. |
| `bundles` | `.app` bundle names. Relative names are searched in `/Applications`, `~/Applications`, `~/Applications/Home Manager Apps`, and `/Library/Input Methods`. Absolute paths are also accepted. |
| `bundle_id` | macOS bundle identifier used for AppleScript running-state checks and default TCC lookup. |
| `commands` | Expected CLI commands checked with `shutil.which`. |
| `processes` | Process names checked with `pgrep -x` and `ps`. |
| `should_run` | Marks background/menu-bar apps that should warn when inactive. |
| `state_paths` | Local state/config markers that should exist after the app has been opened or configured. |
| `login_hint` | Human instruction shown when login cannot be verified automatically. |
| `permissions` | `PermissionReq` entries for macOS TCC checks. |
| `checkers` | Custom checker names loaded by `_load_custom_checkers()`. |
| `casks` | Homebrew cask names that make this app expected on the selected machine. |
| `brews` | Homebrew formula names that make this command expected on the selected machine. |
| `packages` | Nix package names, as exposed by the evaluated machine manifest. |

Prefer declarative fields first. Write a custom checker only when the app has a reliable local status API or file format that generic checks cannot express.

## Machine Policy

Before running an app check, doctor evaluates:

```text
darwinConfigurations.<envy.machine.id>.config.envy.machine.manifest
```

The manifest contains effective Home Manager, system, font, brew, cask, and tap lists together with the explicit machine exclusions. If all selectors for an app are explicitly excluded, doctor emits an `INFO` row explaining that the app is disabled for the selected machine and skips its install/runtime/auth checks.

This distinction is important on restricted machines: excluding Zotero, Okular, WireGuard, or another app is intentional policy, not a failed installation. If manifest evaluation fails or times out, doctor falls back to the previous conservative behavior and runs the normal checks.

## Adding A New App Check

1. Confirm how the app is installed:

   ```bash
   brew info --cask <token>
   defaults read /Applications/<App>.app/Contents/Info CFBundleIdentifier
   defaults read /Applications/<App>.app/Contents/Info CFBundleExecutable
   ```

2. Add an `AppSpec` to `ALL_APP_SPECS` in `resources/scripts/envy/schemas/apps.py`.

   Also declare `casks`, `brews`, or `packages` when the app is controlled by machine software policy.

3. Add aliases to `APP_ALIASES` for Homebrew cask names, common shorthand, or legacy names.

4. Run a focused check:

   ```bash
   envy doctor apps --only <app-key>
   ```

5. If the app has TCC permissions, add `PermissionReq` entries and validate with:

   ```bash
   envy doctor apps --only perm
   envy doctor apps --only <app-key>
   ```

6. Keep warnings meaningful. Do not warn only because a foreground app is not running.

## Login And Auth Checks

Generic `login_hint` is intentionally weak. It is useful only when the app has no stable local signal. For apps with reliable markers, use a custom checker.

Current custom auth checks:

| App | Checker | Signal |
|---|---|---|
| Google Chrome | `chrome_account` | Reads local Chrome profile preferences and Local State markers for signed-in account and sync state. |
| Codex | `codex_auth` | Checks `OPENAI_API_KEY` or marker presence in `~/.codex/auth.json`. |
| GitHub CLI | `github_cli_auth` | Runs `gh auth status`. |
| Lark CLI | `lark_cli_auth` | Runs `lark-cli config show` and `lark-cli auth status`, reading only structured status fields. |
| Tailscale | `tailscale_auth` | Runs `tailscale status --json` with a timeout and checks backend/self state. |
| VS Code | `vscode_sync` | Reads VS Code state database keys for Settings Sync, auth, and Copilot markers. |

Rules for auth checkers:

- Never print emails, account names, access tokens, refresh tokens, cookies, API keys, raw JSON, or raw database rows.
- Prefer "marker present/missing" language over exposing values.
- Use short command timeouts. A doctor check must not hang because a daemon is wedged.
- Treat absent markers as a warning only when the user should act. Otherwise use info.
- Keep app-specific logic out of the generic checker list.

## Chrome Login Detection

Chrome can have a full local profile directory while the user is not signed in. The custom checker therefore looks for account markers in:

- `~/Library/Application Support/Google/Chrome/Local State`
- `~/Library/Application Support/Google/Chrome/<profile>/Preferences`

The checker counts signed-in profile markers and sync markers. It reports only counts, not identity fields.

Expected states:

- `OK Google Chrome account`: at least one profile has a signed-in marker.
- `OK Google Chrome sync`: at least one profile has a sync completion/transport marker.
- `INFO Google Chrome sync`: signed in, but sync does not look completed.
- `WARN Google Chrome account`: no signed-in marker, or sign-in appears disabled.

## macOS TCC Permissions

TCC is macOS' privacy permission database. Apps normally enter System Settings only after they request a protected capability.

Important implications:

- `envy doctor` cannot force macOS to grant permissions.
- `tccutil` can reset decisions, but cannot grant permissions.
- Directly editing TCC databases is unsupported and may be blocked by SIP. Do not do it in this repo.
- MDM PPPC profiles can pre-approve some permissions in managed environments, but that is outside this personal dotfiles flow.
- Reading the user's TCC database usually requires Full Disk Access for the terminal app running `envy`.

Common services used here:

| Service | System Settings Label | Typical Trigger |
|---|---|---|
| `kTCCServiceCamera` | Camera | Start/join a meeting and enable camera. |
| `kTCCServiceMicrophone` | Microphone | Start/join a meeting and unmute. |
| `kTCCServiceScreenCapture` | Screen Recording | Start screen sharing or screenshot capture. |
| `kTCCServiceAccessibility` | Accessibility | App requests accessibility control, global input hooks, or the user manually enables it. |

For Tencent Meeting and Feishu, it is normal not to see Camera, Microphone, or Screen Recording entries until the relevant feature is used inside a meeting. Open the app, trigger the feature once, accept the macOS prompt, then rerun:

```bash
envy doctor apps --only tencent-meeting
envy doctor apps --only tencent-meeting --only perm
```

If doctor reports `TCC database: Full Disk Access required`, enable Full Disk Access for the terminal app you use to run `envy`:

```text
System Settings -> Privacy & Security -> Full Disk Access
```

Then restart the terminal and rerun the check.

## Can Doctor Trigger macOS Permission Prompts?

In general, no. macOS prompts are tied to the requesting process and the actual protected API call.

Examples:

- A camera prompt is triggered when Tencent Meeting itself asks for camera capture, not when a separate Python doctor process checks for the bundle.
- A screen recording prompt is triggered when the app calls a screen capture API.
- Accessibility can be requested programmatically only by the app/process that needs trust, and many apps still require the user to approve in System Settings.

Doctor could launch an app, but it should not try to drive meetings, turn on cameras, share screens, or simulate UI to force prompts. That would be brittle, privacy-invasive, and app-version dependent. The safe workflow is to tell the user which feature to open and then verify the resulting TCC record.

## Troubleshooting

`app bundle not found`

Check the cask artifact name and bundle identifier:

```bash
brew info --cask <token>
ls -1 /Applications ~/Applications ~/Applications/"Home Manager Apps"
```

`expected background app is not running`

Open the app once and enable launch-at-login if it is supposed to be a menu-bar/background tool.

`expected state/config path is missing`

Open the app once. If the file is managed by Home Manager or dotfiles activation, rerun `envy apply`.

`command missing`

Check whether the command is provided by Homebrew, Home Manager, or a cask artifact. Rerun `envy apply` and open a new shell.

`auth check timed out`

The app's local daemon or CLI is not responding. Open the app, restart the daemon if needed, and rerun a focused check.

## Maintenance Checklist

Before committing doctor changes:

```bash
python3 -m compileall -q resources/scripts/envy
envy doctor apps --only <changed-app>
envy doctor apps --only chrome,codex,gh,tailscale
envy doctor apps --only perm
git diff --check
```

For broad app registry changes, also run:

```bash
envy doctor apps
```
