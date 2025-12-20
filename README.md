# Chi's Linux Dotfiles

> 自动化 Linux 开发环境配置方案，由 **[DotBuilder](https://github.com/Kie-Chi/dotbuiler)** 驱动

本仓库旨在通过声明式配置（YAML），实现 Linux 环境的一键部署。支持从零配置 Shell、开发工具链、到完整的 GNOME 桌面环境

## Features

### Cores
- **Shell**: Zsh + Oh My Zsh + Powerlevel10k (即时提示符)
- **Editors**: Vim (集成 Vundle, NERDTree, Airline), VS Code (自动安装并配置源)
- **Tools**: Git, Tmux, Htop, Curl, Wget, Tree, Jq
- **SSH**: 自动生成 Ed25519 密钥并配置 GitHub Alias

### Development
- **Docker**: 自动安装，配置用户组（免 sudo），启用服务
- **Python**: Miniconda3 自动安装、初始化 Conda 环境
- **Java**: 集成 SDKMan 管理多版本 JDK
- **Build**: Build-essential / GCC / Make

### Desktop@GNOME
*仅在 `profile: desktop` 模式下启用*
- **Terminal**: Tilix (Dracula 主题 + F12 Quake 模式 + 快捷键绑定)
- **Input**: Fcitx5 + Rime (雾凇拼音 / 小鹤双拼 / 自动同步配置)
- **Apps**: Google Chrome, WeChat (微信), Snipaste (截图), YesPlayMusic (网易云音乐)
- **Remote**: Sunshine (串流服务，自动配置 Systemd/Udev)
- **Fonts**: Maple Mono NF CN (自动下载并设为系统等宽字体)
- **Optimization**: 自动移除并阻断 Snap (Ubuntu)

### Optional
- **DDNS**: 集成 DDNS-Go，支持通过环境变量配置阿里云/腾讯云解析，支持飞书 Webhook 通知

## Usage

### 1. 下载仓库
```bash
git clone https://github.com/Kie-Chi/dotfiles.git ~/.dotfiles
cd ~/.dotfiles
```

### 2. 安装
运行 `setup.sh`，脚本会自动检测环境并启动配置向导：

```bash
./setup.sh
```

**向导可能会询问以下信息：**
1.  **Username**: 用户名（用于 Git 配置等，默认为当前用户）
2.  **Email**: 邮箱地址（用于 SSH Key 生成和 Git 配置）
3.  **Profile**:
    - `desktop`: 完整安装（适合个人电脑/工作站，包含 GUI 软件）
    - `server`: 最小化安装（适合服务器，仅包含 Shell/Vim/Docker 等）
4.  **DDNS**: 是否启用动态域名解析服务

安装完成后，脚本会自动调用 `dotb` 二进制文件开始构建环境

### 3. 更新等
项目自带包装命令`dtf`，用于简化常用命令
```
dtf sync        # 更新 Dotfiles 仓库，并部署
dtf apply       # 重新应用当前配置

```

---

## ⚙️ Configuration

项目配置为 **分层机制**，优先级从高到低如下：

1.  **系统环境变量** (CI/CD 或 `export` 注入)
2.  **`my.env`/`.env` 文件** (可由 `setup.sh` 生成，可包含基本敏感信息)
3.  **`config.yml` 文件** (项目默认值)

### `my.env` (recommended)
`setup.sh` 运行后会在项目根目录生成 `my.env`。该文件被 `.gitignore` 忽略，适合存放个人配置和密钥

如果你启用了 **DDNS**，请在 `setup.sh` 运行后手动编辑 `my.env` 填入密钥：

```bash
# vim ~/.dotfiles/my.env

# 基础配置
username=user
email=example@email.com
profile=desktop
if_ddns=true

# DDNS 敏感配置 (如启用)
DDNS_ID=你的阿里云AccessKey
DDNS_SECRET=你的阿里云Secret
DDNS_DOMAIN=example.com
DDNS_PREFIX=home
DDNS_WEBHOOK=https://open.feishu.cn/...
```

### `config.yml`
位于 `.dotfiles/config.yml`。这是 DotBuilder 的入口文件，定义了任务图的结构。如果你需要修改默认安装的软件列表或依赖关系，可以修改此文件或其引用的子配置文件 (`.dotfiles/configs/**/*.yml`)

## 🛠 File Tree

```text
.
├── bin/              # 二进制执行文件
├── conf/             # 配置文件模板 (vimrc, zshrc, desktop entries...)
├── configs/          # DotBuilder 任务分块配置
│   ├── cores/        # 基础包 (git, ssh, utils...)
│   ├── devs/         # 开发工具 (docker, conda, vscode...)
│   ├── desktops/     # 桌面软件 (gnome, fcitx, apps...)
│   └── optionals/    # 可选服务 (ddns...)
├── my.env            # 本地环境变量，不提交到 git
├── setup.sh          # 入口脚本，负责引导和环境检查
└── config.yml        # 主配置文件
```

## 📦 Support

目前主要适配并测试于：
- **Ubuntu 22.04 / 24.04 LTS** (主要开发环境)
- **Debian 11 / 12**
- **Arch Linux** (部分支持 Pacman/Yay)

## ⚠️ Notes 

1.  **重启生效**: 安装完成后（特别是 Docker 用户组、GNOME 扩展、Fcitx5 输入法、字体），建议注销或重启系统
2.  **Snap**: 如果选择 `desktop` 模式，脚本默认会 **卸载并阻断 Snap**。如果你依赖 Snap，请在 `configs/desktops/likes.yml` 中移除相关任务
3.  **Sudo**: 安装过程会请求 Sudo 权限以安装系统包

## 📄 License

MIT License © 2024 Kie-Chi
