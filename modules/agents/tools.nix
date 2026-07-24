{ pkgs, sys, ... }:

{
  # Registry-installed agent helpers are platform-neutral. Their installation
  # lifecycle belongs to modules/software; this feature owns only selection and
  # the CodeGraph-specific MCP registration step.
  envy.software.npm.tools.include = [
    {
      id = "codegraph";
      name = "@colbymchenry/codegraph";
      version = "0.9.7";
      ref = "npm:@colbymchenry/codegraph";
    }
  ];

  envy.software.pypi.tools.include = [
    {
      id = "headroom";
      name = "headroom-ai";
      ref = "pypi:headroom-ai";
      parameters."with" = [ "fastapi" ];
    }
  ];

  home.activation.installCodegraphMCP = sys.task.activation {
    name = "codegraph-install";
    after = [ "installNpmTools" ];
    script = ''
      ${pkgs.nodejs_26}/bin/node \
        "$HOME/.npm-global/lib/node_modules/@colbymchenry/codegraph/npm-shim.js" \
        install -y
    '';
  };
}
