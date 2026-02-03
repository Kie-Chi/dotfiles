# Chi's Linux Dotfiles

> 基于 **Nix Flakes** 与 **Home Manager** 构建的声明式 Linux 桌面/开发环境

## Features

### Core
- **pkg management**: Using [Nix Flakes](https://nixos.wiki/wiki/Flakes)
- **environment management**: [Home Manager](https://github.com/nix-community/home-manager) manages home directory configuration files
- **Shell**: Zsh + [Powerlevel10k](https://github.com/romkatv/powerlevel10k)
- **SSH**: 自动化生成 SSH 密钥对与配置

### DevOps
- **Editor**: 
    - **Vim**: 轻量化服务器配置，集成 NERDTree, Airline, ALE 
    - **VS Code**: 声明式安装与配置
- **Docker**: **Docker Rootless** 模式（免 Sudo，自动配置 subuid/subgid）
- **Env**: **Mamba (Conda)** 环境支持

### Desktop@GNOME
- **Terminal**: Tilix (声明式配色/字体) + **Quake 模式**。
- **Input**: Fcitx5 + **Rime (雾凇拼音)**，支持自动化部署与配置同步。
- **Automation**: GNOME 快捷键绑定、壁纸设置、系统扩展自动配置。
- **Remote**: Sunshine 串流服务自动化配置。
- **Font**: Maple Mono NF CN (等宽) + Noto Sans CJK。

---

## Tree

```text
.
├── flake.nix           # 项目入口，定义输入与配置输出
├── home.nix            # Home Manager 主逻辑
├── setup.sh            # 引导脚本：安装依赖、生成密钥与 Secrets
├── secrets.nix         # 个人身份信息 (由 setup.sh 生成，Git 忽略)
├── modules/            # 模块化配置
│   ├── cores/          # 基础工具、Git、Shell、SSH
│   ├── desktops/       # GNOME、Fcitx5、字体、终端
│   └── devps/          # Docker、编辑器、Mamba
├── files/              # 原始配置文件模板 (vimrc, rime.yaml 等)
└── resources/          # 脚本工具与静态资源 (dtf, scrctl 等)
```

---

## Quick Start

### 1. Git installation

在干净的系统上运行以下命令，脚本会自动安装 Nix、配置环境依赖并生成个人信息：

```bash
git clone https://github.com/Kie-Chi/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
chmod +x setup.sh
./setup.sh
```

### 2. Curl installation

```bash
curl -fsSL https://kie-chi.com/files/dotfiles.sh | bash -s
```
- `-r/--remote`: 指定远程仓库，默认本仓库的https地址
- `-b/--branch`: 指定分支，默认 `master`
- `-g/--git`: 默认使用本仓库的 git 地址进行安装

### Maintenance

项目内置了包装脚本 `dtf`，方便管理 Home Manager 状态：

| 命令 | 说明 |
| :--- | :--- |
| `dtf apply` | 应用当前 Nix 配置（重新构建） |
| `dtf sync` | 拉取 Git 远程更新并应用 |
| `dtf edit` | 使用 $EDITOR 快速编辑配置文件 |
| `dtf update` | 更新 `flake.lock` (升级软件版本) |
| `dtf rollback` | 回滚到之前的配置版本 |
| `dtf push` | 快速提交并推送到远程仓库 |

---

## Modules

### `secrets.nix`
为了保证仓库模板的通用性，所有敏感/个性化信息（如用户名、Git Email）都从 `secrets.nix` 读取。该文件在 `setup.sh` 运行期间生成：

```nix
# secrets.nix 示例
{
  home.user = "chi";
  home.dir = "/home/chi";
  git.name = "Kie-Chi";
  git.email = "example@email.com";
}
```

### home modules
只需修改 `home.nix` 中的 `imports` 列表，即可实现功能模块的插拔：

```nix
# home.nix
imports = [
  ./modules/cores     # 必须
  ./modules/desktops  # 如果是服务器环境可注释此行
  ./modules/devps     # 开发工具
];
```

---

## Tools

- **`scrctl`**: 屏幕分辨率与缩放控制工具（支持 GNOME 整数缩放）。
- **`quake`**: 窗口呼出/隐藏辅助脚本，支持将 Tilix 等终端变为 Quake 模式。
- **`spk`**: 快速将本地公钥推送至远程服务器的授权列表。

---

## License

[MIT License](LICENSE) © 2026 Kie-Chi