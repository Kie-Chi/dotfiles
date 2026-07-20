# Agents module

`modules/agents` owns command-line/desktop agent installation, provider-specific wrappers, and reusable skills. Authentication files, history, caches, sessions, and plugin runtime state remain application-owned.

## Layout

```text
modules/agents/
├── default.nix          # machine profile: enabled providers and skills
├── darwin.nix           # system-level agent installers (Homebrew casks)
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

This keeps machine capabilities declarative while preserving progressive, task-driven context loading. Changing the physically discoverable set requires a rebuild; ordinary task-level loading does not.

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

## Provider boundary

Each provider gets its own module (`claude.nix`, later `codex.nix`, `gemini.nix`, and so on). A provider module may install packages, create a stable command wrapper, and link non-secret configuration. API keys and tokens continue to flow through sops-nix activation-time files/templates and must never become Nix evaluation-time strings.

The Claude wrapper deliberately invokes nixpkgs' `claude` wrapper, not its internal `.claude-wrapped` binary. Nixpkgs uses the outer wrapper to set required runtime environment variables and `PATH`; bypassing it would make this repository responsible for duplicating upstream packaging details.

## Agent profile configuration

The provider modules use Home Manager's `config.agents.*` option tree internally. Agent installation, wrapper behavior, security-sensitive arguments, and skill discovery are repository-owned machine profile settings; they are configured in `modules/agents/default.nix`, not in the external `config.nix` managed by `envy`.

The current profile is intentionally explicit:

```nix
agents = {
  claude = {
    enable = true;
    extraArgs = [ "--dangerously-skip-permissions" ];
    ccliAlias = true;
  };

  skills = {
    enable = true;
    active = [ ];
  };
};
```

The Claude package selection, prompt path, and skill catalog remain Nix-only implementation settings. Authentication, history, caches, sessions, and other application-owned state are not managed by this module.
