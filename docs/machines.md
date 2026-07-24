# Cross-platform Machine Configuration

仓库采用一个 `master` 和一个 host module 对应一台设备的模型

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


- `hosts/default.nix` 只是可选的公共默认 module
- Host 可以 import 它、copy 它，或完全独立定义
- 最终非敏感配置始终由 `hosts/<platform>/<id>.nix` 表达
- `.device-label` 只选择本机 target 与 sops label

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
| `envy.user.*` | 用户名与 Home 目录 |
| `envy.repository.path` | 当前机器的 checkout 路径 |
| `envy.git.*` | Git identity |
| `envy.llm.*` | 非敏感 Base URL 和模型 |
| `envy.vscode.mode` | VS Code local/remote policy |
| `envy.packages.home.include/exclude/effective` | 公共 Home Manager package 选择机制 |

同一公共 module 可以在 Darwin 与 Linux 上贡献不同的具体 package；只要选择机制相同，option 仍保持公共。

### Darwin-only Options

| Option | Meaning |
|---|---|
| `envy.darwin.proxy.*` | Darwin proxy service/TUN policy |
| `envy.darwin.packages.system.*` | nix-darwin system packages |
| `envy.darwin.packages.fonts.*` | nix-darwin fonts |
| `envy.darwin.homebrew.brews.*` | Homebrew formulae |
| `envy.darwin.homebrew.casks.*` | Homebrew casks |
| `envy.darwin.homebrew.taps.*` | Homebrew taps |

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
类型统一拥有

新 option 只有在已经出现真实机器行为差异时才添加。不要为所有共享基础设施制造没有使用场景的 `enable`

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

软件列表状态含义：

| State | Source | Meaning |
|---|---|---|
| `[x]` | `included` | 来自 module include，当前机器会安装。 |
| `[ ]` | `machine exclusion` | 当前 host 的 managed exclusions 主动禁用。 |
| `[-]` | `external exclusion` | managed block 之外的 Nix policy 禁用；setup 不会覆盖。 |
| `[ ]` | `stale exclusion` | exclusion 中仍有名称，但当前 include 已不再提供它。 |

setup 中按 Space 只修改内存里的 pending 状态；按 `s` 退出才进入变更确认与写入。按 `q` 或 Esc 退出不会修改 host 文件。`pending` 表示它与打开 setup 时的 machine exclusion 不同，不表示已经写盘。

`envy config show` 默认只展示非空 exclusions；`--details` 展示 include/exclude/effective。Linux details 只显示公共 Home packages，不伪造 Homebrew 或 Darwin system/font 组。

## Mirror Policy

镜像模式是跨平台 machine setting；平台差异由 feature 内部处理：

```nix
{
  envy.mirrors.mode = "china"; # or "upstream"
}
```

公共语言生态使用同一 catalog，Darwin 额外配置 Homebrew，Linux 额外配置 Ubuntu/Debian APT 与 Docker installer。检查最终求值结果使用 `envy mirror status`，连通性检查使用 `envy mirror probe`。完整 ownership 与 bootstrap 边界见 [mirrors.md](mirrors.md)。

新机器可以先通过 [install.md](install.md) 的远程 bootstrap 取得仓库。Bootstrap 只进入现有 setup 流程，不决定 Machine ID、import/copy 或任何软件 policy。

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

仓库只有两个组合根

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
envy check
envy push --self "feat(host): tune work macbook"
```

提交共享模块前使用跨平台检查：

```bash
envy check --all
envy check --changed
envy check --platform linux
envy check --all --build
```

`--changed` 中只有 machine 文件变化时只选这些 targets；出现任意 shared 路径时保守地
选择全部 machines。`--build` 只构建当前平台 target，外平台仍执行 derivation 求值。
CI 在 `aarch64-darwin` 与 `x86_64-linux` 分别运行 Python、shell 和 secret-safety checks。

Push impact 分类：

- machine-only：所有路径都位于 `hosts/darwin/*.nix` 或 `hosts/linux/*.nix`。
- shared：包含任何其他路径，保守地影响全部 `darwin/<id>` 与 `linux/<id>` target。

`--machine-only` 可以包含多个平台的多个 host；`--self` 只允许当前平台与当前 machine 文件。守卫同时检查 worktree 与 outgoing commits，并在 `git add` 前拒绝越界路径。

`envy push` 会先 fetch 目标 remotes。任一远端领先时，在创建 commit 前停止。`envy sync` 只接受线性兼容历史并 fast-forward，不自动创建 merge commit。

Push 在 staging 前验证 worktree、index 与 `HEAD` 都保留加密的
`secrets/secrets.yaml`，并逐个检查所有 outgoing commits 中对应 Git object。任何
现存版本不是 sops 密文，或当前三层缺失该文件时都会拒绝 push；这项
检查独立于 `--self`、`--machine-only` 和 `--yes`，不能被确认选项跳过。多 remote
push 会分别报告 succeeded、failed、unchanged；部分失败时保留已成功结果并输出每个
失败 remote 的精确重试命令。

默认 branch 是 `master`。`--branch` 只用于明确操作当前临时分支，不参与 host 或平台选择。
