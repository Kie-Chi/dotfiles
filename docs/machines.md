# Cross-platform Machine Configuration

仓库采用一个 `master` 和一个 host module 对应一台设备的模型。平台与机器差异属于 Nix policy，不属于 Git 分支结构。

## Host Layout

```text
.device-label
  device.machine_id = "workstation"
          |
          v
hosts/<local-platform>/workstation.nix
          |
          v
flake.nix
  |-- hosts/darwin/*.nix -> darwinConfigurations.<id>
  `-- hosts/linux/*.nix  -> homeConfigurations.<id>
```

Host 必须位于对应平台目录：

```text
hosts/darwin/work-macbook.nix
hosts/linux/workstation.nix
hosts/default.nix
```

没有 registry，也没有 profile 层：

- `hosts/default.nix` 只是可选的公共默认 module。
- Host 可以 import 它、copy 它，或完全独立定义。
- 最终非敏感配置始终由 `hosts/<platform>/<id>.nix` 表达。
- `.device-label` 只选择本机 target 与 sops label，不保存 Nix policy。

## Creating A Host

```bash
envy host init
envy host init work-macbook --mode import
envy host init restricted-mac --mode copy
```

`envy host init` 根据运行平台写入 `hosts/darwin` 或 `hosts/linux`。它只询问 Machine ID 和创建模式，不询问软件选择。

### Import Mode

```nix
{ ... }:

{
  imports = [ ../default.nix ];

  # `envy config refine` writes non-sensitive machine values here.
  # Add machine-specific envy.* overrides here.
}
```

这种模式会继续继承 `hosts/default.nix` 的公共默认值。

### Copy Mode

Copy 会把 `hosts/default.nix` 当前内容写入目标文件，形成不再跟随默认 policy 的快照。目标存在时默认拒绝覆盖；`--force` 会再次确认并创建 `.bak`。

## Device Metadata

`.device-label` 是 Git 忽略的 TOML：

```toml
version = 1

[device]
machine_id = "work-macbook"
sops_label = "work_macbook"
```

常用命令：

```bash
envy host select work-macbook
envy host status
envy host check
envy config check
envy config refine
```

`envy config refine` 可以迁移旧单行 `.device-label`、`~/.config/envy/machine`、旧 `config.nix` 和 Darwin 的旧 `envy.proxy.*`。稳态配置不再读取这些旧来源。

Envy 使用 `path:.#<machine-id>`，所以刚创建且尚未提交的 host 文件也可以立即 check/build/apply。

## Option Boundary

命名由能力是否真正平台专有决定，不由实现文件位于哪个平台目录决定。

### Common Options

两边语义与处理一致时不加平台前缀：

| Option | Meaning |
|---|---|
| `envy.user.*` | 用户名与 Home 目录。 |
| `envy.repository.path` | 当前机器的 checkout 路径。 |
| `envy.git.*` | Git identity。 |
| `envy.llm.*` | 非敏感 Base URL 和模型。 |
| `envy.vscode.mode` | VS Code local/remote policy。 |
| `envy.packages.home.include/exclude/effective` | 公共 Home Manager package 选择机制。 |

同一公共 module 可以在 Darwin 与 Linux 上贡献不同的具体 package；只要选择机制相同，option 仍保持公共。

### Darwin-only Options

| Option | Meaning |
|---|---|
| `envy.darwin.proxy.*` | Darwin proxy service/TUN policy。 |
| `envy.darwin.packages.system.*` | nix-darwin system packages。 |
| `envy.darwin.packages.fonts.*` | nix-darwin fonts。 |
| `envy.darwin.homebrew.brews.*` | Homebrew formulae。 |
| `envy.darwin.homebrew.casks.*` | Homebrew casks。 |
| `envy.darwin.homebrew.taps.*` | Homebrew taps。 |

Linux 没有 proxy option 或 proxy secret declaration。

### Linux-only Options

| Option | Meaning |
|---|---|
| `envy.linux.desktop` | `gnome`、`niri`、`all` 或 `none`。 |
| `envy.linux.option` | 当前 Linux 机器的 `desktop` / `server` 类型。 |

`option = "server"` 是外层能力边界：不会安装 desktop 公共包、VS Code、
GNOME、Niri，也不会生成 Fcitx、Sunshine、Waydroid 或 SwayOSD 服务和
activation。`option = "desktop"` 时，desktop selector 再决定导入 GNOME、
Niri、两者（`all`）或都不导入（`none`）；公共 desktop 工具仍由 desktop
类型统一拥有。

新 option 只有在已经出现真实机器行为差异时才添加。不要为所有共享基础设施制造没有使用场景的 `enable`。

## Managed Config Block

`envy config` 只替换 host 中的标记区块，手写 policy 保留在外部。Darwin 示例：

```nix
# BEGIN ENVY MANAGED CONFIG
envy.user.name = "chi";
envy.user.home = "/Users/chi";
envy.repository.path = "/Users/chi/.dotfiles";
envy.git.name = "Chi";
envy.git.email = "chi@example.com";
envy.llm.steps.url = "https://example.com";
envy.llm.steps.model = "step-3.7-flash";
envy.llm.deepseek.url = "https://api.deepseek.com";
envy.llm.deepseek.model = "deepseek-v4-pro";
envy.vscode.mode = "remote";
envy.darwin.proxy.mode = "none";
envy.darwin.proxy.tun = false;
# END ENVY MANAGED CONFIG
```

Linux managed block 会包含 `envy.linux.*`，不会出现 proxy。

## Software Policy

软件仍由所属功能 module 定义，machine 只通过稳定名称表达差异。

公共 Home package：

```nix
{ pkgs, ... }:

{
  envy.packages.home.exclude = [ "okular" ];
  envy.packages.home.include = with pkgs; [ postgresql ];
}
```

Darwin Homebrew：

```nix
{
  envy.darwin.homebrew.casks.exclude = [
    "uuremote"
    "microsoft-remote-desktop"
  ];
}
```

`envy config software` 和 setup 的 checkbox 只维护 `ENVY MANAGED EXCLUSIONS`。它们不移动 derivation、不修改 module include，也不替用户决定初始软件集合。

`envy config show` 默认只展示非空 exclusions；`--details` 展示 include/exclude/effective。Linux details 只显示公共 Home packages，不伪造 Homebrew 或 Darwin system/font 组。

## Feature-first Modules

Home Manager 调用方优先导入功能入口，平台差异由功能内部选择：

```text
modules/desktops/default.nix
  -> desktops/darwin/default.nix
  -> desktops/linux/default.nix

modules/devps/default.nix
  -> common editor/vscode
  -> devps/linux/default.nix (Linux-only host mutation)
```

仓库只有两个组合根，不再散布 `system.nix` 转发层：

```text
flake.nix
  -> darwin.nix                         (nix-darwin composition)
       -> modules/envy/darwin.nix
       -> modules/agents/darwin.nix
       -> modules/desktops/darwin/nix-darwin.nix

  -> home.nix                           (Home Manager composition)
       -> modules/envy/home.nix
            -> modules/envy/linux.nix   (Linux only)
       -> modules/llm/default.nix
       -> modules/agents/default.nix
       -> modules/cores/default.nix
       -> modules/devps/default.nix
       -> modules/desktops/default.nix
       -> modules/libs/default.nix
```

组合根只负责接线和 Home Manager 最小身份初始化，secret、template、activation
与平台环境归消费它们的 feature 所有。`machinePlatform` 由 flake
作为 special argument 传入，用于选择 imports 和机器策略；不再维护独立的
`isDarwin` special argument。底层包实现可以读取 `pkgs.stdenv.hostPlatform`，
并由 Envy assertion 检查其与 `machinePlatform` 一致。

Python schema 同样拆分为：

```text
resources/scripts/envy/schemas/common/
resources/scripts/envy/schemas/darwin/
resources/scripts/envy/schemas/linux/
```

顶层 dispatcher 组合 common 与当前平台 schema。

## Git Workflow

所有设备使用 `master`：

```bash
envy sync --no-apply
envy host check
envy push --self "feat(host): tune work macbook"
```

Push impact 分类：

- machine-only：所有路径都位于 `hosts/darwin/*.nix` 或 `hosts/linux/*.nix`。
- shared：包含任何其他路径，保守地影响全部 `darwin/<id>` 与 `linux/<id>` target。

`--machine-only` 可以包含多个平台的多个 host；`--self` 只允许当前平台与当前 machine 文件。守卫同时检查 worktree 与 outgoing commits，并在 `git add` 前拒绝越界路径。

`envy push` 会先 fetch 目标 remotes。任一远端领先时，在创建 commit 前停止。`envy sync` 只接受线性兼容历史并 fast-forward，不自动创建 merge commit。

默认 branch 是 `master`。`--branch` 只用于明确操作当前临时分支，不参与 host 或平台选择。
