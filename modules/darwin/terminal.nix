{ pkgs, cfg, lib, ... }:

let
  dracula-colors = pkgs.fetchurl {
    url = "https://raw.githubusercontent.com/dracula/iterm/master/Dracula.itermcolors";
    sha256 = "sha256-X+/B1lmyAggD5mIk0zNkuFPsUqVNIJ71PD18niEn/SA=";
  };
in
{
  fonts.packages = with pkgs; [
    maple-mono.NF-CN
    noto-fonts-cjk-sans
    noto-fonts-color-emoji
  ];

  home-manager.users."${cfg.home.user}" = {
    home.file."iterm2-dracula-profile" = {
      target = "Library/Application Support/iTerm2/DynamicProfiles/Dracula.json";
      text = builtins.toJSON {
        Profiles = [
          {
            Name = "Dracula";
            Guid = "D2AC4B52-E7A4-4A4D-B9B2-9654271A9144";
            "Custom Command" = "No";
            
            "Normal Font" = "MapleMono-NF-CN-Regular 13";
            "Non Ascii Font" = "Monaco 12";
            "Use Ligatures" = true;
            
            "Cursor Type" = 2;
            "Transparency" = 0.15;
            "Blur" = true;
            "Blur Radius" = 20;

            "Background Color" = { "Red Component" = 0.1568; "Green Component" = 0.1647; "Blue Component" = 0.2117; };
            "Foreground Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; };
            "Cursor Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; };
            "Ansi 0 Color" = { "Red Component" = 0.1568; "Green Component" = 0.1647; "Blue Component" = 0.2117; }; # Black
            "Ansi 1 Color" = { "Red Component" = 1.0; "Green Component" = 0.3333; "Blue Component" = 0.3333; }; # Red
            "Ansi 2 Color" = { "Red Component" = 0.3137; "Green Component" = 0.9804; "Blue Component" = 0.4823; }; # Green
            "Ansi 3 Color" = { "Red Component" = 0.9451; "Green Component" = 0.9804; "Blue Component" = 0.5490; }; # Yellow
            "Ansi 4 Color" = { "Red Component" = 0.7412; "Green Component" = 0.5765; "Blue Component" = 0.9765; }; # Blue
            "Ansi 5 Color" = { "Red Component" = 1.0; "Green Component" = 0.4745; "Blue Component" = 0.7765; }; # Magenta
            "Ansi 6 Color" = { "Red Component" = 0.5451; "Green Component" = 0.9137; "Blue Component" = 0.9921; }; # Cyan
            "Ansi 7 Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; }; # White
          }
          {
            Name = "Quake";
            Guid = "E5926B63-798B-4B6B-B6B1-D181D39D377B";
            "Custom Command" = "No";
            
            "Normal Font" = "MapleMono-NF-CN-Regular 13";
            "Non Ascii Font" = "Monaco 12";
            "Use Ligatures" = true;

            "Window Type" = 1;      
            "Screen" = -1;
            "Space" = -1;
            
            "Transparency" = 0.25;
            "Blur" = true;
            "Blur Radius" = 25;
            "Horizontal Canvas Fraction" = 1.0;
            "Rows" = 25;

            "Background Color" = { "Red Component" = 0.1568; "Green Component" = 0.1647; "Blue Component" = 0.2117; };
            "Foreground Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; };
            "Cursor Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; };
            "Ansi 0 Color" = { "Red Component" = 0.1568; "Green Component" = 0.1647; "Blue Component" = 0.2117; }; # Black
            "Ansi 1 Color" = { "Red Component" = 1.0; "Green Component" = 0.3333; "Blue Component" = 0.3333; }; # Red
            "Ansi 2 Color" = { "Red Component" = 0.3137; "Green Component" = 0.9804; "Blue Component" = 0.4823; }; # Green
            "Ansi 3 Color" = { "Red Component" = 0.9451; "Green Component" = 0.9804; "Blue Component" = 0.5490; }; # Yellow
            "Ansi 4 Color" = { "Red Component" = 0.7412; "Green Component" = 0.5765; "Blue Component" = 0.9765; }; # Blue
            "Ansi 5 Color" = { "Red Component" = 1.0; "Green Component" = 0.4745; "Blue Component" = 0.7765; }; # Magenta
            "Ansi 6 Color" = { "Red Component" = 0.5451; "Green Component" = 0.9137; "Blue Component" = 0.9921; }; # Cyan
            "Ansi 7 Color" = { "Red Component" = 0.9725; "Green Component" = 0.9725; "Blue Component" = 0.9490; }; # White
            "Has Hotkey" = true;
            "HotKey Activated By Modifier" = false;
            "HotKey Key Code" = 111;            # 111 是 F12 的硬件码
            "HotKey Character" = 63247;         # F12 的 Unicode 字符码
            "HotKey Character (Native)" = 63247;
            "HotKey Modifier" = 8388608;        # 8388608 代表 Function 键掩码
          }
          {
            Name = "BtopDashboard";
            Guid = "F6A1C2D3-E4B5-4C6D-A7B8-D9E0F1A2B3C4";
            "Custom Command" = "Yes";
            "Command" = "${pkgs.btop}/bin/btop";
            "Window Type" = 2;              
            "Has Hotkey" = true;
            "HotKey Key Code" = 51;             
            "HotKey Character" = 63246;
            "HotKey Character (Native)" = 63246;
            "HotKey Modifier" = 8388608;
            "HotKey Modifier Flags" = 393216;
            "Floating window" = true;
            "Animate showing and hiding" = true;
            "Space" = -1;
            "Rows" = 30;
            "Columns" = 100;
          }
        ];
      };
    };
  };
}