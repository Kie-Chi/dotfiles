{ pkgs, lib, config, ... }:

{
    programs.zsh = {
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    
    oh-my-zsh = {
      enable = true;
      plugins = [ "git" "sudo" "web-search" "copyfile" "dirhistory" "golang" ];
    };

    plugins = [
      {
        name = "powerlevel10k";
        src = pkgs.zsh-powerlevel10k;
        file = "share/zsh-powerlevel10k/powerlevel10k.zsh-theme";
      }
    ];

    sessionVariables = {
      LANG = "en_US.UTF-8";
      EDITOR = "vim";
    };

    shellAliases = {
      zshconf = "vim ~/.dotfiles/modules/core.nix";
      omzconf = "vim ~/.oh-my-zsh";
      
      ll = "ls -alh";
      ".." = "cd ..";
      "..." = "cd ../..";
      myip = "ip -c -br a";
      ports = "sudo ss -nultp";
      py = "python3";
      rcat = "command cat";
      grep = "rg";
      
    };


    initContent = ''
      [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
      
      ${builtins.readFile ../../files/zsh/opt.zsh}
      ${builtins.readFile ../../files/zsh/func.zsh}
    '';
  };
  
  home.file.".p10k.zsh".source = ../../files/zsh/p10k.zsh;

}
