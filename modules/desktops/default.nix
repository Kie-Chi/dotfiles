# in the macos, most of gui software are installed via homebrew cask

# except for nix-better-supported like vscode,

{...} :

{
  imports = [
    ./apps.nix
    ./dmgs.nix
    ./zips.nix
    ./proxies.nix
    ./wallpaper.nix
  ];
}