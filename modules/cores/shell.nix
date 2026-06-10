{ pkgs, lib, config, cfg, sys, ... }:

let
  isDesktop = (cfg.home.option or "desktop") == "desktop";
in
{
  programs.zsh = {
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    historySubstringSearch.enable = true;

    oh-my-zsh = {
      enable = true;
      plugins = [ "git" "sudo" "docker" "web-search" "z" "command-not-found" "colored-man-pages" "history" "pip" "python" "golang" ];
    };

    plugins = [
      {
        name = "powerlevel10k";
        src = pkgs.zsh-powerlevel10k;
        file = "share/zsh-powerlevel10k/powerlevel10k.zsh-theme";
      }
      {
        name = "zsh-completions";
        src = pkgs.zsh-completions;
      }
      {
        name = "conda-zsh-completion";
        src = pkgs.fetchFromGitHub {
          owner = "esc";
          repo = "conda-zsh-completion";
          rev = "c3dca5b56cca978d974f821f592ee8f11c32320d";
          hash = "sha256-4JaoYv1dbUaOs5YxZtlG+Q21CYMk2d0EmPfUdKdoNA4=";
        };
        file = "conda-zsh-completion.plugin.zsh";
      }
      {
        name = "fzf-tab";
        src = pkgs.zsh-fzf-tab;
        file = "share/fzf-tab/fzf-tab.plugin.zsh";
      }
    ];

    sessionVariables = {
      LANG = "en_US.UTF-8";
      EDITOR = if isDesktop then "code" else "nvim";
      DOTFILES_DIR = cfg.dotfiles.path;
    } // lib.optionalAttrs isDesktop {
      XMODIFIERS = "@im=fcitx";
      GTK_IM_MODULE = "fcitx";
      QT_IM_MODULE = "fcitx";
      SDL_IM_MODULE = "fcitx";
    };

    shellAliases = {
      zshconf = "nvim ${cfg.dotfiles.path}/modules/cores/shell.nix";
      omzconf = "nvim ~/.oh-my-zsh";

      ll = "ls -alh";
      ".." = "cd ..";
      "..." = "cd ../..";
      myip = "ip -c -br a";
      ports = "esudo ss -nultp";
      py = "python3";
      rcat = "command cat";
      grep = "rg";
    };

    initContent = ''
      [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

      ${builtins.readFile ../../files/zsh/opt.zsh}
      ${builtins.readFile ../../files/zsh/func.zsh}

      unset XCURSOR_PATH
      unset XCURSOR_THEME
      unset XCURSOR_SIZE
    '';
  };

  programs.zoxide = {
    enable = true;
    enableZshIntegration = true;
  };

  programs.fzf = {
    enable = true;
    enableZshIntegration = true;
  };

  home.file.".p10k.zsh".source = ../../files/zsh/p10k.zsh;

  home.activation.setZshAsDefault = sys.task.activation {
    name = "setZshAsDefault";
    asRoot = true;
    script = ''
      zsh_path="${config.home.profileDirectory}/bin/zsh"
      if [ "$SHELL" != "$zsh_path" ]; then
        log_info "Setting Zsh as default shell..."
        if ! ${sys.cmds.grep} -q "$zsh_path" /etc/shells; then
          echo "$zsh_path" | esudo tee -a /etc/shells > /dev/null
        fi
        esudo chsh -s "$zsh_path" ${cfg.home.user}
        log_info "Default shell changed to Zsh. Please relogin."
      fi
    '';
  };
}