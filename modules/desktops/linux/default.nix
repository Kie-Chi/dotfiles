{ ... }:

{
  # Every module guards the outer desktop/server boundary. GNOME- and
  # Niri-specific modules also honor envy.linux.desktop.
  imports = [
    ./base.nix
    ./fcitx.nix
    ./rime.nix
    ./font.nix
    ./sunshine.nix
    ./gnome.nix
    ./terminal.nix
    ./niri.nix
    ./niris
  ];
}
