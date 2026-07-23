{ ... }:

{
  imports = [ ../default.nix ];

  # BEGIN ENVY MANAGED CONFIG
  # `envy config` updates only this block. Other machine policy stays intact.

  # --- BASE CONFIG ---
  envy.user.name = "jyxc-dz-0101541";
  envy.user.home = "/Users/jyxc-dz-0101541";

  # --- ENV CONFIG ---
  envy.repository.path = "/Users/jyxc-dz-0101541/.dotfiles";

  # --- GIT CONFIG ---
  envy.git.name = "Kie-Chi";
  envy.git.email = "137579437@qq.com";

  # --- LLM CONFIG ---
  envy.llm.steps.url = "https://models-proxy.stepfun-inc.com";
  envy.llm.steps.model = "claude-opus-4-6";
  envy.llm.deepseek.url = "https://api.deepseek.com";
  envy.llm.deepseek.model = "deepseek-v4-pro";

  # --- PROXY CONFIG ---
  envy.proxy.mode = "none";
  envy.proxy.tun = false;

  # --- VSCODE CONFIG ---
  envy.vscode.mode = "remote";
  # END ENVY MANAGED CONFIG

  # Add hand-maintained machine-specific envy.* policy below this line.
}
