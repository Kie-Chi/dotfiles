{ lib, pkgs, machineId ? "unknown", machinePlatform ? "unknown", machineSystem ? "unknown", ... }:

let
  inherit (lib) mkOption types;
  inherit (import ./selection-options.nix { inherit lib; }) packageSelection;
  targetPlatform =
    if pkgs.stdenv.hostPlatform.isDarwin then "darwin"
    else if pkgs.stdenv.hostPlatform.isLinux then "linux"
    else "unknown";

in
{
  options.envy = {
    machine = {
      id = mkOption {
        type = types.strMatching "[A-Za-z0-9][A-Za-z0-9_-]*";
        default = machineId;
        readOnly = true;
        description = "Machine identifier derived from the host module filename.";
      };
      platform = mkOption {
        type = types.enum [ "darwin" "linux" "unknown" ];
        default = machinePlatform;
        readOnly = true;
        description = "Platform selected by the hosts/darwin or hosts/linux directory.";
      };
      system = mkOption {
        type = types.str;
        default = machineSystem;
        readOnly = true;
        description = "Nix system selected for this platform configuration.";
      };
      manifest = mkOption {
        type = types.attrs;
        readOnly = true;
        description = "Normalized evaluated machine policy for Envy tooling.";
      };
    };

    user = {
      name = mkOption {
        type = types.nonEmptyStr;
        description = "Local account managed by nix-darwin or Home Manager.";
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

    vscode.mode = mkOption {
      type = types.enum [ "remote" "local" ];
      default = "remote";
      description = "Whether VS Code settings are managed locally or by Settings Sync.";
    };

    packages.home = packageSelection "cross-platform Home Manager packages";

    mirrors.mode = mkOption {
      type = types.enum [ "upstream" "china" ];
      default = "china";
      description = "Network mirror policy used by bootstrap and managed package ecosystems.";
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
  };

  config.assertions = [
    {
      assertion = machinePlatform == "unknown" || machinePlatform == targetPlatform;
      message = "machinePlatform '${machinePlatform}' does not match target platform '${targetPlatform}'";
    }
    {
      assertion = machineSystem == "unknown" || machineSystem == pkgs.stdenv.hostPlatform.system;
      message = "machineSystem '${machineSystem}' does not match target system '${pkgs.stdenv.hostPlatform.system}'";
    }
  ];
}
