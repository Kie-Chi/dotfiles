{ pkgs, lib, secrets, config, ... }:

{
  programs.git = {
    enable = true;
    settings = {
      user = {
        name = secrets.git.name or "Somebody";
        email = secrets.git.email or "example@email.com";
      };

      alias = {
        st = "status";
        ci = "commit";
        co = "checkout";
        br = "branch";
        df = "diff";
        dif = "diff";
        rt = "remote";
        pl = "pull";
        ps = "push";
        cm = "commit -m";
        lg = "log --color --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit";
      };

      color = {
        ui = true;
      };
      
    };
  };
}