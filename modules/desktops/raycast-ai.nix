{ pkgs, config, cfg, lib, sys, ... }:

{
  # --- sops template: raycast AI providers with encrypted keys ---
  sops.templates."raycast-providers" = {
    content = ''
      providers:
        - id: stepfun
          name: StepFun
          base_url: ${cfg.llm.steps.url}
          api_keys:
            stepfun: ${config.sops.placeholder.llm-steps-apikey}
          models:
            - id: ${cfg.llm.steps.model}
              name: Step 3.7 Flash
              context: 256000
              abilities:
                temperature:
                  supported: true
                vision:
                  supported: true
                system_message:
                  supported: true
                tools:
                  supported: true
        - id: deepseek
          name: DeepSeek
          base_url: ${cfg.llm.deepseek.url}
          api_keys:
            raycast: ${config.sops.placeholder.llm-deepseek-apikey}
          models:
            - id: ${cfg.llm.deepseek.model}
              name: DeepSeek V4 Pro
              context: 200000
              abilities:
                temperature:
                  supported: true
                vision:
                  supported: true
                system_message:
                  supported: true
                tools:
                  supported: true
    '';
  };

  home.activation.deployRaycastProviders = sys.task.activation {
    name = "deployRaycastProviders";
    pre = ''
      mkdir -p "$HOME/.config/raycast/ai/backups"
    '';
    script = ''
      TARGET="$HOME/.config/raycast/ai/providers.yaml"
      ${sys.cmds.mkdir} -p "$(dirname "$TARGET")"
      esudo ${sys.cmds.install} -m 0644 "${config.sops.templates."raycast-providers".path}" "$TARGET"
    '';
  };
}
