# Multi-machine Configuration

仓库采用“一个共享分支、一个 machine 文件对应一台设备”的模型。机器差异属于 Nix 配置，不属于 Git 分支结构。

## 文件与求值关系

```text
.device-label: device.machine_id = "work-macbook"  (仅设备身份)
                         │
                         ▼
hosts/machines/work-macbook.nix          (全部非敏感机器配置)
                         │
                         ▼
flake.nix scans hosts/machines/*.nix
                         │
                         ▼
darwinConfigurations.work-macbook
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       nix-darwin modules    Home Manager modules
              └──────────┬──────────┘
                         ▼
                 the same envy.* policy
```

`hosts/machines/work-macbook.nix` 会同时进入 nix-darwin 和该用户的 Home Manager 求值，因此用户、路径、Git、代理、编辑器、LLM endpoint 以及软件选择都只有一个非敏感配置源。

这里没有额外的 profile 层：

- `hosts/default.nix` 只是可选的共享默认 module。
- machine 可以 `import` 它，也可以复制它，甚至可以完全不引用它。
- 最终配置始终由一个具体的 `hosts/machines/<id>.nix` 表示。

## 创建机器配置

交互方式：

```bash
envy host init
```

非交互地给出 Machine ID 和创建模式：

```bash
envy host init work-macbook --mode import
envy host init restricted-mac --mode copy
```

命令只负责创建 Nix 文件，不询问要安装或排除哪些软件。

### import 模式

生成：

```nix
{ ... }:

{
  imports = [ ../default.nix ];

  # `envy config refine` writes non-sensitive machine values here.
  # Add machine-specific envy.* overrides here.
}
```

适合大多数机器。`hosts/default.nix` 的新默认值会自动流入，machine 文件只记录差异。

### copy 模式

把 `hosts/default.nix` 的当前内容复制到 machine 文件。它是独立快照，不会自动继承后续默认策略变更，适合限制严格、希望固定策略的设备。

目标文件已存在时，命令默认拒绝覆盖。`--force` 仍会再次确认，并先创建 `<id>.nix.bak`。

## 选择当前机器

当前设备的身份保存在 Git 忽略的 `.device-label` TOML：

```toml
version = 1

[device]
machine_id = "work-macbook"
sops_label = "work_macbook"
```

修改和检查：

```bash
envy host select work-macbook
envy host status
envy host check
```

`machine_id` 选择 Envy 默认操作的 flake target，`sops_label` 标识 `.sops.yaml` 中属于本设备的 age key。两者可以不同；这个文件不参与 Nix 求值，也不保存用户、路径或软件策略。`envy host init` 创建 machine 文件后会自动更新它，也可以用环境变量 `ENVY_MACHINE` 临时覆盖 target。

`envy config check` 会只读检查 TOML 语法、schema version、两个身份字段及 machine 文件；`envy config refine` 负责补齐字段，并迁移旧单行 `.device-label`、旧 `~/.config/envy/machine` selector 和旧 `config.nix`。

`envy host check` 只求值所选 machine 的 system derivation，不会执行 switch。

Envy 使用 `path:.#<machine-id>` 调用 flake，因此刚由 `envy host init` 创建、尚未提交的 machine 文件也能立即 check、build 或 apply。直接使用 Git worktree flake 的 `.#<machine-id>` 时，Nix 会忽略未跟踪文件。

## 控制机器差异

Machine 文件只记录真实差异；软件定义继续保留在负责该软件的模块中。

用户名、仓库路径、Git identity、代理模式、VS Code 模式和非敏感 LLM endpoint 位于 `envy config` 管理的标记区块。工具只替换这一段，手写的软件 exclusions 和其他策略不会被覆盖：

```nix
# BEGIN ENVY MANAGED CONFIG
envy.user.name = "chi";
envy.user.home = "/Users/chi";
envy.repository.path = "/Users/chi/.dotfiles";
envy.git.name = "Chi";
envy.git.email = "chi@example.com";
envy.proxy.mode = "none";
envy.proxy.tun = false;
envy.vscode.mode = "remote";
envy.llm.steps.url = "https://example.com";
envy.llm.steps.model = "step-3.7-flash";
envy.llm.deepseek.url = "https://api.deepseek.com";
envy.llm.deepseek.model = "deepseek-v4-pro";
# END ENVY MANAGED CONFIG
```

常用入口：

```bash
envy config show
envy config software
envy config software disable homebrew.casks uuremote
envy config software enable packages.home okular
envy config edit
envy config set envy.vscode.mode local
envy config refine
```

`envy config show` 不直接把 machine 文件当作最终结果。它会求值当前
`darwinConfigurations.<machine-id>`，因此展示的标量已经融合
`hosts/default.nix`、machine overrides 和共享模块；软件策略则分别展示
`include`、`exclude` 与应用排除后的 `effective`。只有 Nix 求值失败时才退回
直接读取 machine 文件，并明确显示 fallback 警告。

运行 `setup.py` 时，标量初始值也来自同一个求值后 manifest。主界面按 `p`
打开 machine 软件复选框：左右键切换六个软件组、上下键移动、空格切换、`/`
搜索、`r` 撤销本次软件修改。取消勾选会加入当前 machine 的 exclusion，重新
勾选会移除该 exclusion；共享业务模块中的 `include` 和 derivation 不会被改写。

Envy 把这些选择写入单独的 `BEGIN/END ENVY MANAGED EXCLUSIONS` 区块，只生成
非空列表，最后一个 exclusion 被移除时整个区块也会消失。保存前会检查
machine 文件没有被其他进程修改，保存后重新执行 Nix 求值；若求值失败则原子
恢复原文件。受控区块外或继承而来的 exclusion 显示为 `[-]`，必须在其来源处
修改，TUI 不会覆盖手写策略。

setup 保存并通过求值后，会把当前 machine 文件以及本次发生变化的 `.sops.yaml`、
加密 secrets 和 recovery key 加入同一次 Git 提交确认。候选文件使用显式 pathspec，
不会包含工作区内其他未完成修改；拒绝提交或提交失败时文件仍保留在暂存区，之后
可以先运行 `envy git diff --cached` 检查，再手动提交。setup 不会自动 push，跨远端
同步仍由 `envy push` 负责。

Nix package 的 `include` 可能包含 derivation、局部变量和任意 Nix 表达式，
因此复选框只管理 exclusions。新增 derivation 仍通过所属业务模块完成；Homebrew
或 Nix 的单项 exclusion 也可以用 `envy config software enable/disable` 管理。

### 排除 Nix package

Nix package 的 exclude 使用 `lib.getName` 得到的稳定名称字符串。这样自定义 derivation 不需要暴露成 `pkgs.<name>`，也不需要额外的 enable option：

```nix
{
  envy.packages.home.exclude = [
    "okular"
    "sing-box"
    "wireguard-macos-app"
    "wireshark-qt"
  ];
}
```

软件关联的配置会跟随选择结果。例如排除 `desktoppr` 会同时停止 wallpaper activation；排除 `claude` 会同时去掉 Claude wrapper、`ccli` 和对应 prompt 文件。

### 排除 Homebrew 条目

```nix
{
  envy.homebrew.casks.exclude = [
    "telegram-desktop"
    "tencent-meeting"
  ];

  envy.homebrew.brews.exclude = [
    "java"
  ];
}
```

`exclude` 优先于所有模块贡献的 `include`。依赖该应用的配置根据同一个排除项自动停止，例如 `zotero`、`raycast`、`karabiner-elements`、`squirrel-app` 和 `clash-verge-rev`。

### 增加机器独有 package

```nix
{ pkgs, ... }:

{
  envy.packages.home.include = with pkgs; [
    postgresql
  ];
}
```

## Options 分类

| Option | 用途 |
|---|---|
| `envy.user.*` / `envy.repository.path` | 本机账号、Home 目录和仓库路径。 |
| `envy.git.*` | 本机 Git identity。 |
| `envy.proxy.*` / `envy.vscode.mode` | 确实存在机器差异的行为模式。 |
| `envy.llm.*` | 非敏感 Base URL 与模型；API Key 仍属于 sops。 |
| `envy.packages.home.include` | Home Manager package derivations。 |
| `envy.packages.home.exclude` | 按稳定名称排除 Home Manager packages。 |
| `envy.packages.system.include/exclude` | nix-darwin system packages；exclude 同样使用名称。 |
| `envy.packages.fonts.include/exclude` | 字体 packages；exclude 同样使用名称。 |
| `envy.homebrew.brews.include/exclude` | Homebrew formulae。 |
| `envy.homebrew.casks.include/exclude` | Homebrew casks。 |
| `envy.homebrew.taps.include/exclude` | Homebrew taps。 |

每一类还有只读的 `effective`，由聚合层去重并应用 exclude 后产生。`envy.machine.manifest` 把最终安装项和显式 exclusions 暴露给 `envy doctor`。

这里刻意没有 `envy.features.*.enable`。Nix trusted-users、Shell、Git、SSH、macOS defaults、utility scripts 等属于所有机器共享的仓库基础能力，无需制造一个理论上可以关闭、实际上没有机器差异的 option。未来只有出现已经确认的行为差异时才新增 option，并优先表达具体值，例如模式、路径或设备参数，而不是通用 enable。

代码中仍会出现 `programs.git.enable = true`、`programs.zsh.enable = true` 或 `homebrew.enable = true`。这些是 Home Manager/nix-darwin 上游模块自身的激活接口，不是暴露给 machine 的 Envy 开关，也不表示每台机器都需要一份可覆盖的 option。

## 添加新的共享软件

不要把完整 package 清单移入 `hosts/default.nix` 或 `modules/envy/`。按所属职责维护：

```nix
# modules/desktops/example.nix
{ pkgs, ... }:

let
  example = pkgs.stdenv.mkDerivation {
    # ...原模块继续拥有 derivation...
  };
in
{
  envy.packages.home.include = [ example ];
}
```

只要 derivation 的 `pname`/name 稳定，machine 就能通过 `envy.packages.home.exclude = [ "example" ];` 排除它。若模块还管理该软件的配置或 activation，应让那部分根据同一个 exclusion 或最终 effective selection 自动停止。

不要为新软件在 `modules/envy/options.nix` 新增 enable，也不要把 package 移入 `hosts/default.nix`。中央层只拥有通用选择 schema、聚合和 manifest，不拥有各业务模块的 package 定义。

## Git 工作流

所有机器继续使用 `darwin`：

```bash
envy sync --no-apply
# 编辑 hosts/machines/work-macbook.nix 或共享模块
envy host check
envy push "feat(host): tune work macbook"
```

`envy push` 会把变更分成：

- machine-only：全部路径都位于 `hosts/machines/*.nix`，只列出相应 machine target。
- shared：包含其他任何路径，保守地列出仓库中的所有 machine target。

确认前会显示文件和影响范围。它先 fetch 所有目标 remote；任一远端领先时，在创建本地 commit 之前停止，避免把共享分支变成需要手工 merge 的分叉。

默认情况下 `envy push` 也要求当前分支为 `darwin`，防止新设备无意中继续使用机器专属分支。确实需要推送临时开发分支时，必须显式传入 `--branch <current-branch>`。

`envy sync` 要求 clean worktree，并执行 `git fetch` 与 `git merge --ff-only origin/darwin`。Git 同步失败时不会继续 build 或 apply。

## 从旧 config.nix 迁移

升级期间，Envy 只会把旧 selector/config 当作一次性迁移来源：它读取旧 Machine ID 和非敏感字段，写入对应的版本化 machine 文件，并把设备身份统一写入 TOML `.device-label`。之后 Nix 与 Envy 都不再依赖旧 selector/config：

```bash
envy config refine
envy host status
```
