# Chi's Darwin Dotfiles

基于 Nix Flakes、nix-darwin、Home Manager 与 sops-nix 的声明式 macOS 配置。所有机器共享 `darwin` 分支，但每台机器拥有独立的 `hosts/machines/<machine-id>.nix`，因此不需要维护一组长期存在的机器分支。

## 设计概览

配置分成三类：

- `hosts/machines/<machine-id>.nix` 是单台设备所有非敏感配置的唯一来源，包括用户、路径、Git identity、代理模式、编辑器模式、LLM Base URL 和软件差异。
- `secrets/secrets.yaml` 保存密码和 API Key，由 sops 加密；密钥只在激活阶段解密。
- 仓库内的 Nix 模块保存可共享策略。软件及自定义 derivation 仍在原业务模块中定义，`modules/envy/` 只声明最小的选择 schema、聚合最终安装列表并生成 machine manifest。

```text
flake.nix
├── hosts/default.nix                     # 可继承的共享默认策略
├── hosts/machines/<machine-id>.nix       # 单台机器的全部非敏感 envy.* 配置
├── modules/envy/                         # options、聚合与验证
├── modules/cores/                        # CLI、Shell、Git、SSH
├── modules/darwin/                       # macOS、Homebrew、终端、代理
├── modules/desktops/                     # 桌面应用及自定义 app derivation
├── modules/devps/                        # 编辑器与开发环境
└── modules/agents/                       # Agent、包装器与 skills
```

`flake.nix` 会自动扫描 `hosts/machines/*.nix`，并为每个文件生成同名的 `darwinConfigurations.<machine-id>`。Git 忽略的 `.device-label` 是本机 TOML 元数据，只保存所选 machine ID 和 sops key label，不保存机器策略。

## 快速开始

```bash
git clone -b darwin https://github.com/Kie-Chi/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
bash setup.sh
```

首次设置会收集本地配置与 secrets。若所选 Machine ID 尚无配置文件，只会继续询问如何创建该文件：

- `import`：创建一个很小的 machine 文件并导入 `hosts/default.nix`，以后自动继承共享默认值更新。
- `copy`：复制当前默认策略作为独立快照，以后不自动继承 `hosts/default.nix` 的变化。

创建 machine 文件不会替用户选择软件。package、brew 和 cask 的增减都由用户随后在该 machine 文件中填写。

也可以单独创建或检查机器配置：

```bash
envy host init <machine-id>
envy host list
envy host status
envy host check <machine-id>
envy host select <machine-id>
envy config edit
```

完整说明和示例见 [docs/machines.md](docs/machines.md)。

## 日常维护

| 命令 | 说明 |
|---|---|
| `envy apply` | refine 当前版本化 machine 配置并应用所选 target。 |
| `envy sync` | 要求工作区干净，检查所有远端的 `darwin`，快进到最新兼容提交后应用当前机器。 |
| `envy sync --no-apply` | 只同步共享分支。 |
| `envy sync --build-only` | 同步后只构建当前机器，不激活。 |
| `envy push "<message>"` | 分析工作区和 outgoing commits，展示 shared/machine 影响后确认并推送；远端领先时提前拒绝。 |
| `envy push --machine-only "<message>"` | 只允许一个或多个 `hosts/machines/*.nix`，遇到 shared 文件立即停止。 |
| `envy push --self "<message>"` | 只允许当前 `.device-label` 选中的 machine 文件。 |
| `envy doctor` / `envy dr` | 检查配置、secrets、应用、登录状态和 macOS 权限。 |
| `envy config check` | 只读检查 `.device-label`、所选 machine 文件和 secrets。 |
| `envy config refine` | 迁移/补全设备元数据、machine 受控区块和 secret schema。 |
| `envy config edit` | 用 `$EDITOR` 打开所选 machine 文件。 |
| `envy config show` | 显示 Nix 求值后的最终 machine 值，以及 package/Homebrew 的 include、exclude、effective。 |
| `envy config software` | 查看 machine 软件复选框；`enable/disable` 子命令管理单项 exclusion。 |
| `envy update` | 更新 flake inputs 和 Homebrew 元数据。 |

所有机器都在同一个 `darwin` 分支上同步。只修改 `hosts/machines/<id>.nix` 时，影响范围仅为该机器；修改共享模块或 `hosts/default.nix` 时，影响所有继承它的机器。`envy push` 会同时检查未提交文件和各目标远端的 `remote/darwin..HEAD`；即使工作区已经干净，仍会显示 outgoing commits 的影响并确认。`--branch` 只是显式选择 Git 分支的逃生口，不参与 machine 选择。

## Machine 覆盖示例

```nix
{ ... }:

{
  imports = [ ../default.nix ];

  # 按稳定名称排除原业务模块声明的软件。
  envy.packages.home.exclude = [
    "okular"
    "sing-box"
    "wireguard-macos-app"
    "wireshark-qt"
  ];
  envy.homebrew.casks.exclude = [
    "telegram-desktop"
    "tencent-meeting"
  ];
}
```

安装源没有被搬到 machine 配置：例如 Okular 仍在 `modules/desktops/dmgs.nix` 定义，WireGuard 仍在 `modules/desktops/zips.nix` 定义，Lark CLI 仍在 `modules/libs/bins/lark-cli.nix` 定义。

## Secrets

- 非敏感值：`hosts/machines/<id>.nix` 中的 `envy.*` options，通过 `config.envy.*` 在 Nix 求值阶段使用。
- 敏感值：`secrets/secrets.yaml`，通过 `config.sops.secrets.*.path` 或 sops template 在激活阶段使用。
- age key：macOS 下位于 `~/Library/Application Support/sops/age/keys.txt`。

不要把 API Key、密码或带 token 的 URL 放进 Nix eval-time expression。新设备需要把 age public key 加入 `.sops.yaml`，再运行：

```bash
sops updatekeys secrets/secrets.yaml
```

## 诊断

```bash
envy doctor
envy doctor apps --only chrome,chatgpt,zotero
envy doctor apps --only perm
```

Doctor 会读取当前 machine 的求值后 manifest。明确排除的应用显示为 `INFO`，不会被误报为缺失。详细维护说明见 [docs/doctor.md](docs/doctor.md)。

`setup.py` 的可视化界面同样读取求值后的值，因此会包含 `hosts/default.nix` 和共享模块。按 `p` 打开软件复选框，使用左右键切换 package/Homebrew 组、空格启用或禁用、`/` 搜索。界面只写当前 machine 的 exclusion，不会重写业务模块中的 Nix package derivation 或 `include`。

保存并通过 Nix 求值后，setup 会把当前 machine 文件和本次有变化的 sops 文件放入一次 Git 提交确认；其他工作区修改不会被加入，push 仍需使用 `envy push`。

## License

[MIT License](LICENSE) © 2026 Kie-Chi
