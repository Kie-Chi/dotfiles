{ pkgs, config, cfg, lib, sys, ... }:

{
  # --- sops template: raycast AI providers with encrypted keys ---
  sops.templates."raycast-providers" = {
    content = ''
      providers:
        - id: anthropic-dashscope
          name: Anthropic (DashScope)
          base_url: ${cfg.llm.dashscope.url}
          api_keys:
            dashscope: ${config.sops.placeholder.llm-dashscope-apikey}
          models:
            - id: ${cfg.llm.dashscope.model}
              name: GLM 5.1
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
            - id: deepseek-v4-pro
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