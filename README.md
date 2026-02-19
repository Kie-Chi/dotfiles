# Chi's Darwin Dotfiles

> 基于 **Nix Flakes**、**nix-darwin** 与 **Home Manager** 构建的声明式 macOS 开发环境

## Features

### Core
- **pkg management**: 使用 [Nix Flakes](https://nixos.wiki/wiki/Flakes) 进行包管理
- **system management**: 使用 [nix-darwin](https://github.com/LnL7/nix-darwin) 管理 macOS 系统配置
- **environment management**: [Home Manager](https://github.com/nix-community/home-manager) 管理用户环境配置
- **Shell**: Zsh + [Powerlevel10k](https://github.com/romkatv/powerlevel10k)
- **SSH**: 自动化生成 SSH 密钥对与配置

### DevOps
- **Editor**: 
    - **Vim**: 轻量化配置，集成 NERDTree, Airline, ALE 
    - **VS Code**: 声明式安装与配置
- **Env**: 开发环境与工具链管理

### macOS Applications & Services
- **Terminal**: iTerm2 + 自定义配色与字体配置
- **Proxy**: Mihomo (Clash Meta) 代理服务自动化配置
- **Apps**: 声明式安装常用 macOS 应用程序
- **System**: macOS 系统偏好设置与快捷键配置

---

## Tree

```text
.
├── flake.nix           # 项目入口，定义 nix-darwin 与 Home Manager 配置
├── home.nix            # Home Manager 主配置
├── setup.sh            # 引导脚本：安装依赖、生成密钥与 Secrets
├── secrets.nix         # 个人身份信息 (由 setup.sh 生成，Git 忽略)
├── modules/            # 模块化配置
│   ├── cores/          # 基础工具、Git、Shell、SSH
│   ├── darwin/         # macOS 系统配置、应用程序、终端、代理
│   ├── desktops/       # 桌面环境相关配置
│   └── devps/          # 开发工具与编辑器
├── files/              # 原始配置文件模板 (vimrc, mihomo.yaml 等)
└── resources/          # 脚本工具与静态资源 (dtf, ppack, spk 等)
```

---

## Quick Start

### 1. Git installation

在干净的 macOS 系统上运行以下命令，脚本会自动安装 Nix、配置环境依赖并生成个人信息：

```bash
git clone https://github.com/Kie-Chi/.dotfiles.git ~/.dotfiles
cd ~/.dotfiles
chmod +x setup.sh
./setup.sh
```

### 2. Curl installation

```bash
curl -fsSL https://kie-chi.com/files/dotfiles.sh | bash -s -- -b darwin
```
- `-r/--remote`: 指定远程仓库，默认本仓库的 https 地址
- `-b/--branch`: 指定分支，默认 `master`（此处使用`darwin`分支）
- `-g/--git`: 使用本仓库的 git 地址进行安装

### Setup

安装完成后，使用以下命令应用配置：

```bash
./setup.sh # bash ./setup.sh
```

### Maintenance

项目内置了包装脚本 `dtf`，方便管理 Home Manager 状态：

| 命令 | 说明 |
| :--- | :--- |
| `dtf apply` | 应用当前配置状态  |
| `dtf apply` | 应用当前配置（darwin-rebuild switch） |
| `dtf sync` | 拉取 Git 远程更新并应用配置 |
| `dtf edit` | 使用 $EDITOR 快速编辑配置文件 |
| `dtf update` | 更新 `flake.lock` (升级软件包) |
## Modules

### `secrets.nix`
为了保证仓库模板的通用性，所有敏感/个性化信息（如用户名、Git Email）都从 `secrets.nix` 读取。该文件在 `setup.sh` 运行期间生成，存储位置为 `~/.dotfiles/secrets.nix`：

```nix
# secrets.nix 示例
{
  home.user = "chi";
  home.dir = "/Users/chi";  # macOS 用户目录
  git.name = "Kie-Chi";
  git.email = "example@email.com";
  proxy.url = "https://xxx";
  proxy.status = "keep"; # "keep" | "manual" | "none"
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