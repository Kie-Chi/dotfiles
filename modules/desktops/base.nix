{ pkgs, config, sys, ... }:

let

in
{
  home.packages = with pkgs; [
    # utils
    xclip
    xsel
    copyq
    slurp
    grim
    swappy
    nixgl.auto.nixGLDefault
    wev

    # apps
    steam-run
    (writeShellScriptBin "waydroid-helper" ''
      exec ${pkgs.steam-run}/bin/steam-run ${waydroid-helper}/bin/waydroid-helper "$@"
    '')    
    waydroid-nftables
    kdePackages.okular
    pavucontrol
    (pkgs.feishu.overrideAttrs (oldAttrs: {
      postFixup = (oldAttrs.postFixup or "") + ''
        wrapProgram $out/bin/bytedance-feishu \
          --add-flags "--no-sandbox" \
          --add-flags "--disable-gpu-sandbox" \
          --set XDG_CURRENT_DESKTOP "niri" \
          --prefix PATH : ${pkgs.lib.makeBinPath [ 
            pkgs.xdg-utils 
            pkgs.google-chrome
          ]}
      '';
    }))
    wemeet
    todesk
    google-chrome
    wpsoffice-cn
    remmina

    # patches
    libcanberra-gtk3
    mesa
  ];

  xdg.autostart.enable = true;
  xdg.desktopEntries = {
    wechat = {
      name = "WeChat";
      comment = "WeChat Desktop App";
      exec = "usr/bin/wechat";
      icon = "wechat"; 
      terminal = false;
      categories = [ "Utility" ];
    };
  };

  xdg.desktopEntries."id.waydro.waydroid_helper" = {
    name = "Waydroid Helper";
    exec = "waydroid-helper";
    icon = "waydroid";
    terminal = false;
    categories = [ "System" ];
  };

  home.activation.installWayDroid = sys.task.root {
    script = ''
      ${sys.cmds.curl} -fsSL https://repo.waydro.id > /tmp/waydroid.sh
      if pkg_installed "waydroid"; then
        echo "Package 'waydroid' is already installed."
      else
        esudo bash /tmp/waydroid.sh
        esudo ${sys.cmds.apt} install -y waydroid
        waydroid prop set persist.waydroid.multi_windows true
        esudo ${sys.cmds.systemctl} restart waydroid-container
      fi
    '';
  };

}
