{ pkgs, config, sys, lib, nixGLDefault ? null, ... }:

let
  isDesktop = config.envy.linux.option == "desktop";
  waydroidEnabled = isDesktop && !(builtins.elem "waydroid" config.envy.packages.home.exclude);
  xresourceDesktop = pkgs.runCommand "xresource-desktop" {} ''
    mkdir -p $out/share/applications
    cp ${../../../files/desktop/xresource.desktop} $out/share/applications/xresource.desktop
  '';
  waydroidHelper = pkgs.writeShellScriptBin "waydroid-helper" ''
    exec ${pkgs.steam-run}/bin/steam-run ${pkgs.waydroid-helper}/bin/waydroid-helper "$@"
  '';
in
{
  config = lib.mkIf isDesktop {
  envy.packages.home.include = (with pkgs; [
    # utils
    xclip
    xsel
    copyq
    slurp
    grim
    swappy
    wev

    # apps
    steam-run
    waydroid-nftables
    kdePackages.okular
    pavucontrol
    (pkgs.feishu.overrideAttrs (oldAttrs: {
      postFixup = (oldAttrs.postFixup or "") + ''
        wrapProgram $out/bin/bytedance-feishu \
          --add-flags "--no-sandbox" \
          --add-flags "--disable-gpu-sandbox" \
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
  ])
  ++ lib.optionals waydroidEnabled [ waydroidHelper ]
  ++ lib.optionals (nixGLDefault != null) [ nixGLDefault ];

  home.pointerCursor = {
    name = "Yaru";
    package = pkgs.yaru-theme;
    size = 24;
    x11.enable = true;
    gtk.enable = true;
  };

  home.sessionVariables.XDG_DATA_DIRS = "$GSETTINGS_SCHEMAS_PATH:$XDG_DATA_DIRS";

  xresources.properties = {
    # 144 (1.5x), 168 (1.75x), 192 (2x)
    "Xft.dpi" = 144;
  };
  xsession.enable = true;

  systemd.user.services.xresources-wayland = {
    Unit = {
      Description = "Load Xresources for XWayland";
      PartOf = [ "graphical-session.target" ];
    };
    Install = {
      WantedBy = [ "graphical-session.target" ];
    };
    Service = {
      Type = "oneshot";
      ExecStart = "/usr/bin/xrdb -merge %h/.Xresources";
    };
  };

  xdg.autostart.enable = true;
  xdg.autostart.entries = [
    xresourceDesktop
  ];
  xdg.desktopEntries = {
    wechat = {
      name = "WeChat";
      comment = "WeChat Desktop App";
      exec = "/usr/bin/wechat";
      icon = "wechat";
      terminal = false;
      categories = [ "Utility" ];
    };
  };

  xdg.desktopEntries."id.waydro.waydroid_helper" = lib.mkIf waydroidEnabled {
    name = "Waydroid Helper";
    exec = "waydroid-helper";
    icon = "waydroid";
    terminal = false;
    categories = [ "System" ];
  };

  home.activation.installWayDroid = lib.mkIf waydroidEnabled (sys.task.activation {
    name = "installWayDroid";
    after = [ "configureAptMirror" ];
    asRoot = true;
    script = ''
      ${sys.cmds.curl} -fsSL https://repo.waydro.id > /tmp/waydroid.sh
      if pkg_installed "waydroid"; then
        log_info "Package 'waydroid' is already installed."
      else
        esudo bash /tmp/waydroid.sh
        esudo ${sys.cmds.apt} install -y waydroid
        waydroid prop set persist.waydroid.multi_windows true
        esudo ${sys.cmds.systemctl} restart waydroid-container
      fi
    '';
  });

  };
}
