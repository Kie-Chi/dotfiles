# in the macos, most of gui software are installed via homebrew cask

# except for nix-better-supported like vscode,

{...} :

{
  imports = [
    ./apps.nix
    ./karabiner.nix
    ./linearmouse.nix
    ./dmgs.nix
    ./zips.nix
    ./clash-verge.nix
    ./proxies.nix
    ./wallpaper.nix
    ./squirrel.nix
    ./raycast-ai.nix
  ];
}
