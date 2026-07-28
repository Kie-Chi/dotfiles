{ ... }:

{
  imports = [ ../default.nix ];

  # BEGIN ENVY MANAGED CONFIG
  # `envy config` updates only this block. Other machine policy stays intact.

  # --- BASE CONFIG ---
  envy.user.name = "chi";
  envy.user.home = "/home/chi";

  # --- ENV CONFIG ---
  envy.repository.path = "/home/chi/.envy";

  # --- GIT CONFIG ---
  envy.git.name = "Kie-Chi";
  envy.git.email = "137579437@qq.com";

  # --- HABITS CONFIG ---
  envy.habits.terminalScratchpad.gesture = "F12";
  envy.habits.globalLauncher.gesture = "Option+Space";

  # --- LLM CONFIG ---
  envy.llm.steps.url = "https://models-proxy.stepfun-inc.com";
  envy.llm.steps.model = "claude-opus-4-6";
  envy.llm.deepseek.url = "https://api.deepseek.com";
  envy.llm.deepseek.model = "deepseek-v4-pro";

  # --- MIRRORS CONFIG ---
  envy.mirrors.mode = "china";

  # --- VSCODE CONFIG ---
  envy.vscode.mode = "remote";

  # --- LINUX SPECIFIC ---
  envy.linux.desktop = "all";
  envy.linux.option = "desktop";
  # END ENVY MANAGED CONFIG
}
