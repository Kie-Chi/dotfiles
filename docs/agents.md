# Agents module

`modules/agents` owns command-line/desktop agent installation, provider-specific wrappers, and reusable skills. Authentication files, history, caches, sessions, and plugin runtime state remain application-owned.

## Layout

```text
modules/agents/
├── default.nix          # shared provider defaults and skill selection
├── darwin.nix           # Darwin application distribution for nix-darwin
├── linux.nix            # Linux CLI/IDE distribution and runtime plugins
├── linux/rtk.nix        # Linux-only RTK package
├── claude.nix           # Claude package, wrapper defaults, and ccli alias
├── skills.nix           # skill catalog/selection Home Manager module
└── skills/
    ├── catalog.nix      # skill registry and target agents
    └── <skill-name>/
        ├── SKILL.md
        ├── agents/openai.yaml  # recommended for Codex UI metadata
        ├── scripts/            # optional deterministic helpers
        ├── references/         # optional, read only when needed
        └── assets/             # optional output resources
```

## Skill loading model

There are two distinct selection stages:

1. `agents.skills.active` controls which catalog entries are linked into `~/.codex/skills` and/or `~/.claude/skills` during Home Manager activation.
2. For a discovered skill, the agent sees its `name` and `description` metadata first. It reads the `SKILL.md` body only when the task triggers that skill, then reads referenced resources as needed.

This keeps agent capabilities declarative while preserving progressive, task-driven context loading. Changing the physically discoverable set requires a rebuild; ordinary task-level loading does not.

## Adding a skill subpackage

Create `modules/agents/skills/<skill-name>/SKILL.md`. Use lowercase letters, digits, and hyphens for the directory and frontmatter name. Keep `SKILL.md` concise; place detailed variants in one-level-deep `references/`, repeatable code in `scripts/`, and output templates in `assets/`.

Register it in `skills/catalog.nix`:

```nix
{
  dotfiles-maintainer = {
    source = ./dotfiles-maintainer;
    targets = [ "codex" "claude" ];
  };
}
```

Then activate it in `modules/agents/default.nix`:

```nix
agents.skills.active = [ "dotfiles-maintainer" ];
```

Use a single shared source when both agents accept the same workflow. Split it into provider-specific skills only when frontmatter or behavior genuinely differs.

External skill repositories should be pinned as non-flake inputs in `flake.nix`,
passed to Home Manager through `extraSpecialArgs`, and registered from their
store paths in `skills/catalog.nix`. Keep provider-native packaging intact: for
example, Academic Research Skills exposes four coordinated Claude skills, while
its Codex sibling exposes one `academic-research-suite` router skill. Updating an
external skill is then an explicit `nix flake update <input-name>` operation.

## Provider boundary

Each provider gets its own module (`claude.nix`, later `codex.nix`, `gemini.nix`, and so on). A provider module may install packages, create a stable command wrapper, and link non-secret configuration. Shared LLM API keys and their shell template are owned by `modules/llm`; provider modules consume the activation-time environment and must never turn secrets into Nix evaluation-time strings.

The Claude wrapper deliberately invokes nixpkgs' `claude` wrapper, not its internal `.claude-wrapped` binary. Nixpkgs uses the outer wrapper to set required runtime environment variables and `PATH`; bypassing it would make this repository responsible for duplicating upstream packaging details.

## Shared agent configuration

The provider modules use Home Manager's `config.agents.*` option tree internally. Wrapper behavior, security-sensitive arguments, and skill discovery are shared repository settings configured in `modules/agents/default.nix`, not machine-specific values managed by `envy config`.

The two files contribute to different module systems. `default.nix` is imported
through the cross-platform `home.nix` composition root. `darwin.nix` is imported
through the repository's `darwin.nix` composition root and contributes only
Darwin Homebrew distribution policy. `flake.nix` does not import either feature
implementation directly.

The current shared configuration is intentionally explicit:

```nix
agents = {
  claude = {
    extraArgs = [ "--dangerously-skip-permissions" ];
    ccliAlias = true;
  };

  skills = {
    active = [
      "academic-research-suite"
      "academic-paper"
      "academic-paper-reviewer"
      "academic-pipeline"
      "deep-research"
    ];
  };
};
```

The Claude package selection, prompt path, and skill catalog remain Nix-only implementation settings. A machine that cannot install Claude excludes the stable package name with `envy.software.nix.packages.exclude = [ "claude" ];`; no provider-specific enable option is needed. Authentication, history, caches, sessions, and other application-owned state are not managed by this module.

CodeGraph and Headroom are shared agent tools on Darwin and Linux. The feature
contributes them through `envy.software.npm.tools` and
`envy.software.pypi.tools`; `modules/software/` owns their cross-platform
installation lifecycle, while CodeGraph MCP registration remains agent-owned.
Linux additionally installs Codex and RTK on both server and desktop machines,
and Cursor only when `envy.linux.option = "desktop"`. Darwin continues to
distribute Codex and ChatGPT through Homebrew casks.
