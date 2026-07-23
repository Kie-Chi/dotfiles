{ pkgs, config, lib, ... }:

let
  profile-uuid = "2b7c4080-0ddd-46c5-8f23-563fd3ba789d";
  desktop = config.envy.linux.desktop;
  enabled = config.envy.linux.option == "desktop"
    && (desktop == "gnome" || desktop == "all");
in
{
  config = lib.mkIf enabled {
    envy.packages.home.include = with pkgs; [ tilix ];

    dconf.settings = {
      "com/gexperts/Tilix" = {
        default-profile = profile-uuid;
      };

      "com/gexperts/Tilix/profiles/${profile-uuid}" = {
        use-system-font = false;
        font = "Maple Mono NF CN 12";
        visible-name = "Default (Dracula)";
        background-color = "#282A36";
        foreground-color = "#F8F8F2";
        cursor-background-color = "#F8F8F2";
        palette = [
          "#21222C" "#FF5555" "#50FA7B" "#F1FA8C" "#BD93F9" "#FF79C6" "#8BE9FD" "#F8F8F2"
          "#6272A4" "#FF6E6E" "#69FF94" "#FFFFA5" "#D6ACFF" "#FF92DF" "#A4FFFF" "#FFFFFF"
        ];
        use-theme-colors = false;
      };
    };
  };
}
