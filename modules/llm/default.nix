{ config, lib, ... }:

{
  sops.secrets = {
    llm-steps-apikey = {
      sopsFile = ../../secrets/secrets.yaml;
      key = "llm/steps/apikey";
    };
    llm-deepseek-apikey = {
      sopsFile = ../../secrets/secrets.yaml;
      key = "llm/deepseek/apikey";
    };
  };

  sops.templates."env-secrets".content = ''
    export STEPFUN_BASE_URL=${lib.escapeShellArg config.envy.llm.steps.url}
    export API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
    export STEPFUN_API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
    export ANTHROPIC_BASE_URL=${lib.escapeShellArg config.envy.llm.steps.url}
    export ANTHROPIC_API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
    export ANTHROPIC_AUTH_TOKEN=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
    export ANTHROPIC_MODEL=${lib.escapeShellArg config.envy.llm.steps.model}
  '';

  programs.zsh.initContent = lib.mkAfter ''
    if [ -f "${config.sops.templates."env-secrets".path}" ]; then
      source "${config.sops.templates."env-secrets".path}"
    else
      echo "[WARN] sops env-secrets template not found at ${config.sops.templates."env-secrets".path}"
    fi
  '';
}
