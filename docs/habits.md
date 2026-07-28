# Habit contracts

`envy habit` manages stable personal interaction semantics through versioned
machine policy. A desired gesture lives in `hosts/<platform>/<id>.nix`; the
desktop module for each backend renders its native binding from that value.
Machine policy continues to select software through the existing envY
package/cask options.

```bash
envy habit list
envy habit show terminal-scratchpad
envy habit check
envy habit list --json
envy habit set terminal-scratchpad F12
envy habit set global-launcher Option+Space --apply
envy habit repair
```

## Current contracts

| Habit | Canonical gesture | Darwin | Linux |
|---|---|---|---|
| `terminal-scratchpad` | `F12` | iTerm2 Quake Hotkey Window | Tilix Quake in GNOME; `nscratch` + Alacritty in Niri |
| `global-launcher` | `Option+Space` | Raycast global hotkey | Fuzzel in Niri (`Super+Space` native binding) |

The canonical gesture is the machine's desired state. `binding` is the
platform-native rendering: your Niri session uses the logical `Super` key for
the same Option+Space habit. envY shows both rather than flattening them into
one misleading key string.

`F11` is intentionally not a contract. macOS reserves it for Show Desktop,
while Linux desktop sessions use it differently. Platform-native actions do
not need artificial cross-platform equivalence.

## Ownership and checks

Each implementation declares one of two ownership modes:

- `declarative`: the corresponding Nix desktop module uses one local value for
  both the native binding and its Habit contract. `envy habit set` changes the
  selected machine's value, and `envy habit repair` (or `set --apply`) runs the
  normal envY apply path to render and activate that desired state. The two
  cannot drift apart; `envy habit check` also verifies that required software
  is effective in the evaluated manifest.
- `application`: the application owns the setting. Raycast's global hotkey is
  recorded as part of the contract but never overwritten by envY; the check
  verifies that Raycast is selected and explicitly reports that its expected
  hotkey still needs manual verification.

`envy habit check` detects malformed or inconsistent contracts, duplicate
contexts, and software disabled by machine policy. It never edits a host file,
application preferences, or keyboard settings.

## Policy values

The managed machine block persists the two current desired values:

```nix
envy.habits.terminalScratchpad.gesture = "F12";
envy.habits.globalLauncher.gesture = "Option+Space";
```

`terminal-scratchpad` accepts `F2` through `F10`, or `F12`. F1 stays reserved
for Niri screenshots and F11 intentionally remains platform-specific.
`global-launcher` accepts `Option+<key>`; Niri renders the modifier as `Super`.

`envy habit set` changes only versioned desired state. Use `--apply` for a
single write-and-activate operation, or use `envy habit repair` later to
re-render the selected machine. Like `envy apply`, repair deliberately does
not rewrite Raycast's application-owned preference.

## Adding a contract

Declare an implementation next to the module that owns its backend:

```nix
envy.machine.habits = [
  {
    id = "terminal-scratchpad";
    label = "Terminal scratchpad";
    gesture = config.envy.habits.terminalScratchpad.gesture;
    semantic = "Toggle a reusable Quake-style terminal overlay.";
    context = "niri";
    backend = "nscratch + Alacritty quake-term";
    binding = "F12";
    ownership = "declarative";
    requirements = [
      { group = "nix.user.package"; item = "niri-scratchpad"; }
      { group = "nix.user.package"; item = "alacritty"; }
    ];
  }
];
```

The generic `envy.machine.habits` option only supplies a typed aggregation
surface. `envy.habits.*` is the machine-managed desired state; detailed
behavior and software ownership remain in the implementation module.
