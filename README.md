# Chi's Cross-platform Dotfiles

基于 Nix Flakes、nix-darwin、Home Manager 与 sops-nix 的声明式 Darwin/Linux 配置

## Architecture

```text
flake.nix
├── darwin.nix                       # 唯一 nix-darwin 组合入口
├── home.nix                         # 唯一 Home Manager 组合入口
├── hosts/default.nix
├── hosts/darwin/<machine-id>.nix
├── hosts/linux/<machine-id>.nix
├── modules/envy/                  # option、聚合和 machine manifest
├── modules/mirrors/               # 公共 catalog 与 Darwin/Linux 镜像实现
├── modules/llm/                   # 公共 LLM secrets、环境模板与 shell 接入
├── modules/cores/                 # 公共 shell、Git、SSH 和工具
├── modules/desktops/
│   ├── default.nix                # 公共功能入口
│   ├── darwin/                    # Darwin 专有实现
│   └── linux/                     # Linux 专有实现
├── modules/devps/                 # 公共编辑器；Linux 实现在 linux/
└── modules/agents/                # 公共 agent 功能及 Darwin/Linux 分发实现
```

`flake.nix` 分别扫描两个 host 目录：

- `hosts/darwin/*.nix` 生成 `darwinConfigurations.<machine-id>`。
- `hosts/linux/*.nix` 生成 `homeConfigurations.<machine-id>`。

检测到旧 `~/.config/dotfiles/config.nix` 或 `/etc/dotfiles/config.nix` 时，flake
还会按其中的身份与 Linux policy 生成临时 `homeConfigurations.default`，仅用于
旧 `master` 第一次同步时兼容原来的 `.#default`。没有旧配置时不会猜测某个
versioned host 作为默认机器。

flake 不再分别拼装散落的系统模块。Darwin 配置只导入 `darwin.nix`，Linux
和 Darwin 的用户配置都由 `home.nix` 组合；具体平台实现仍归各功能目录所有。
`home.nix` 本身只保留 Home Manager 身份初始化，secret、template 和平台环境均由消费它们的 feature 声明。

每台机器的 host module 是全部非敏感机器配置的唯一来源。Git 忽略的 `.device-label` 只保存本机选择的 `machine_id` 与 sops key label，不参与 Nix policy。

Option 遵循公共优先原则：

- 多平台语义和处理方式一致时使用 `envy.user.*`、`envy.git.*`、`envy.llm.*`、`envy.vscode.mode`、`envy.software.nix.packages.*`
- 只有平台专有能力使用 `envy.darwin.*` 或 `envy.linux.*`

## Quick Start

一键取得仓库并进入交互式 setup：

```bash
curl --proto '=https' --tlsv1.2 -fsSL \
  https://raw.githubusercontent.com/Kie-Chi/dotfiles/master/install.sh | bash
```

或者手动 clone：

```bash
git clone https://github.com/Kie-Chi/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
bash setup.sh
```

远程命令会执行当前 `master` 上的脚本。需要先审查内容、固定 release tag、自定义 clone 目标或只下载仓库时，请看 [docs/install.md](docs/install.md)。

当当前 Machine ID 尚无 host 文件时，可以选择：

- `import`：创建小型 host module 并导入 `hosts/default.nix`，持续继承公共默认值。
- `copy`：复制当前默认 policy，形成不随默认值变化的独立快照。

初始化只创建文件，不替用户决定安装或排除哪些软件：

```bash
envy host init <machine-id>
envy host list
envy host status
envy host check <machine-id>
envy host select <machine-id>
```

## Daily Workflow

| Command | Purpose |
|---|---|
| `envy apply` | Refine 并应用当前平台的 machine target |
| `envy sync` | 从远端快进共享 `master`，成功后应用当前机器 |
| `envy sync --no-apply` | 仅同步，不应用 |
| `envy sync --build-only` | 同步后只构建当前平台 target |
| `envy push "<message>"` | 分析 worktree 与 outgoing commits，确认影响范围后提交并 push |
| `envy push --machine-only` | 只允许 `hosts/darwin/*.nix` 与 `hosts/linux/*.nix` |
| `envy push --self` | 只允许当前平台、当前 `.device-label` 所选 host 文件 |
| `envy check` | 求值当前 machine target |
| `envy check --all` | 求值仓库中全部 Darwin/Linux machine targets |
| `envy check --changed` | 根据 worktree 路径检查受影响的 machine targets |
| `envy check --build` | 在本机平台构建所选 targets；外平台仍只求值 |
| `envy update` | 更新全部 flake inputs、检查全部 machines，并在 Darwin 更新 Homebrew metadata |
| `envy update inputs [name]` | 更新全部或指定 flake input；验证失败自动恢复 `flake.lock` |
| `envy clean --older-than 30d` | 经确认后只清理指定期限以前的 generations |
| `envy config check` | 只读检查 device metadata、host module 与 secrets |
| `envy config refine` | 迁移并补全本平台 machine/schema |
| `envy config show` | 展示求值后的 machine scalar 与 secret 设置状态 |
| `envy software` / `envy sw` | 展示当前机器的 evaluated software policy |
| `envy sw ls --details` | 展示软件版本、引用以及 include/exclude/effective 状态 |
| `envy sw add/rm <group> <id-or-ref>` | 预览 include/exclude 计划后，确保软件在当前机器生效或不生效；`--clean` 清理目标的冗余受管状态 |
| `envy sw en/dis <group> <id>` | 启用或排除一个稳定 software ID |
| `envy sw search <query>` / `envy sw se <query>` | 并发搜索当前可用的软件 registry |
| `envy sw status` / `envy sw st` | 汇总当前机器的软件 group 和 selection 状态 |
| `envy mirror status` | 展示当前 machine 求值后生效的镜像端点 |
| `envy mirror probe` | 只读探测镜像 HTTP 状态与延迟 |
| `envy doctor` | 检查本平台配置、应用、状态与登录信息；TCC 仅在 Darwin 加载 |
| `envy doctor system` | 检查运行依赖、apply runner、Git 状态与中断残留 |
| `envy doctor network` | 只读探测求值后的镜像端点 |
| `envy key repair` | 修复中断的 key rotation 标记、权限并重新验证密文 |

`envy push` 和 `envy sync` 默认要求当前分支为 `master`。`--branch` 只是显式操作临时分支。
共享变更 push 前建议运行 `envy check --all`；push 会同时检查 worktree、index 和 outgoing commits，拒绝任何明文 `secrets/secrets.yaml`。

国内网络默认使用 `envy.mirrors.mode = "china"`。首次 setup 的临时环境、APT/Homebrew 行为、探针及不能透明镜像的下载见 [docs/mirrors.md](docs/mirrors.md)。

## Machine Policy

公共 Home Manager 软件在两边使用同一 option：

```nix
{ pkgs, ... }:

{
  imports = [ ../default.nix ];

  envy.vscode.mode = "remote";

  envy.software.nix.packages.exclude = [
    "okular"
  ];

  envy.software.nix.packages.include = with pkgs; [
    postgresql
  ];
}
```

Darwin 专有 policy 只出现在 Darwin host：

```nix
{
  envy.darwin.proxy.mode = "none";
  envy.darwin.proxy.tun = false;
  envy.darwin.software.homebrew.casks.exclude = [ "uuremote" ];
}
```

Linux 专有 policy 只出现在 Linux host：

```nix
{
  envy.linux.desktop = "gnome";
  envy.linux.option = "desktop";
}
```

`envy.linux.option = "server"` 会禁用整个 Linux desktop 层，忽略 desktop
selector。`option = "desktop"` 时，`envy.linux.desktop` 分别使用 `gnome`、
`niri`、`all`（两者）或 `none`

软件 group 统一使用 `<ecosystem>.<scope>.<kind>`，例如
`nix.user.package`、`homebrew.system.cask`、`native.system.package`、
`npm.user.tool` 和 `pypi.user.tool`。完整 schema、搜索来源和生命周期语义见
[docs/software.md](docs/software.md)。

## Secrets

- 非敏感值：`hosts/<platform>/<id>.nix` 中的 `envy.*` options。
- 敏感值：sops 加密的 `secrets/secrets.yaml`。
- Darwin age key：`~/Library/Application Support/sops/age/keys.txt`。
- Linux age key：`~/.config/sops/age/keys.txt`。

!!!不要把 API key、密码或带 token 的 URL 放进 Nix 求值期表达式
新增设备的 age public key 加入 `.sops.yaml` 后运行：

```bash
sops updatekeys secrets/secrets.yaml
```

- 完整安装说明见 [docs/install.md](docs/install.md)
- machine 设计见 [docs/machines.md](docs/machines.md)
- age/sops 密钥生命周期见 [docs/key.md](docs/key.md)
- doctor 维护说明见 [docs/doctor.md](docs/doctor.md)

## License

[MIT License](LICENSE) © 2026 Kie-Chi
