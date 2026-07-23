{ lib, machineId ? "unknown", ... }:

let
  inherit (lib) mkOption types;

  packageSelection = description: {
    include = mkOption {
      type = types.listOf types.package;
      default = [ ];
      inherit description;
    };

    exclude = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Package names removed from ${description}; exclusions win over inclusions.";
    };

    effective = mkOption {
      type = types.listOf types.package;
      readOnly = true;
      description = "Final ${description} after de-duplication and exclusions.";
    };
  };

  stringSelection = description: {
    include = mkOption {
      type = types.listOf types.str;
      default = [ ];
      inherit description;
    };

    exclude = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Entries removed from ${description}; exclusions win over inclusions.";
    };

    effective = mkOption {
      type = types.listOf types.str;
      readOnly = true;
      description = "Final ${description} after de-duplication and exclusions.";
    };
  };
in
{
  options.envy = {
    machine.id = mkOption {
      type = types.strMatching "[A-Za-z0-9][A-Za-z0-9_-]*";
      default = machineId;
      readOnly = true;
      description = "Machine identifier derived from the selected hosts/machines file.";
    };

    user = {
      name = mkOption {
        type = types.nonEmptyStr;
        description = "Local account managed by nix-darwin and Home Manager.";
      };

      home = mkOption {
        type = types.nonEmptyStr;
        description = "Absolute home directory for the managed local account.";
      };
    };

    repository.path = mkOption {
      type = types.nonEmptyStr;
      description = "Absolute path to this dotfiles checkout on the selected machine.";
    };

    git = {
      name = mkOption {
        type = types.nonEmptyStr;
        description = "Git author name used on the selected machine.";
      };

      email = mkOption {
        type = types.nonEmptyStr;
        description = "Git author email used on the selected machine.";
      };
    };

    proxy = {
      mode = mkOption {
        type = types.enum [ "none" "manual" "keep" ];
        default = "none";
        description = "Proxy service policy for the selected machine.";
      };

      tun = mkOption {
        type = types.bool;
        default = false;
        description = "Whether the selected machine uses the proxy TUN mode.";
      };
    };

    vscode.mode = mkOption {
      type = types.enum [ "remote" "local" ];
      default = "remote";
      description = "Whether VS Code settings are managed locally or by Settings Sync.";
    };

    llm = {
      steps = {
        url = mkOption {
          type = types.nonEmptyStr;
          description = "Non-sensitive StepFun-compatible API base URL.";
        };

        model = mkOption {
          type = types.nonEmptyStr;
          default = "step-3.7-flash";
          description = "Default StepFun-compatible model.";
        };
      };

      deepseek = {
        url = mkOption {
          type = types.nonEmptyStr;
          default = "https://api.deepseek.com";
          description = "Non-sensitive DeepSeek API base URL.";
        };

        model = mkOption {
          type = types.nonEmptyStr;
          default = "deepseek-v4-pro";
          description = "Default DeepSeek model.";
        };
      };
    };

    machine.manifest = mkOption {
      type = types.attrs;
      readOnly = true;
      description = "Evaluated machine software policy for envy tooling.";
    };

    packages = {
      home = packageSelection "Home Manager packages";
      system = packageSelection "nix-darwin system packages";
      fonts = packageSelection "nix-darwin font packages";
    };

    homebrew = {
      brews = stringSelection "Homebrew formulae";
      casks = stringSelection "Homebrew casks";
      taps = stringSelection "Homebrew taps";
    };
  };
}
