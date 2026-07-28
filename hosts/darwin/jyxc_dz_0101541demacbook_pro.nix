{ ... }:

{
  imports = [ ../default.nix ];

  # BEGIN ENVY MANAGED CONFIG
  # `envy config` updates only this block. Other machine policy stays intact.

  # --- BASE CONFIG ---
  envy.user.name = "jyxc-dz-0101541";
  envy.user.home = "/Users/jyxc-dz-0101541";

  # --- ENV CONFIG ---
  envy.repository.path = "/Users/jyxc-dz-0101541/.envy";

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

  # --- DARWIN PROXY CONFIG ---
  envy.darwin.proxy.mode = "none";
  envy.darwin.proxy.tun = false;

  # --- VSCODE CONFIG ---
  envy.vscode.mode = "remote";
  # END ENVY MANAGED CONFIG

  # BEGIN ENVY MANAGED SOFTWARE
  # `envy setup` and `envy software` own only these machine-local selections.

  envy.darwin.software.homebrew.casks.exclude = [
    "uuremote"
    "microsoft-remote-desktop"
    "ticktick"
    "trae"
    "moonlight"
    "dingtalk"
    "neteasemusic"
    "skim"
    "iina"
  ];

  envy.darwin.software.homebrew.formulae.include = [
    "maven"
  ];

  envy.software.pypi.tools.include = builtins.fromJSON "[{\"id\":\"browser-use\",\"name\":\"browser-use\",\"ref\":\"pypi:browser-use\"}]";
  # END ENVY MANAGED SOFTWARE

  # Add hand-maintained machine-specific envy.* policy below this line.
}
