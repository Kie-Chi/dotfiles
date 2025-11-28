# 🚀 Chi's Linux Dotfiles

> Automated Linux environment setup powered by **DotBuilder**.

这个仓库包含了我的 Linux 开发环境配置（Dotfiles）。通过 `DotBuilder` 自动化工具，支持一键配置 Shell、开发工具以及桌面环境（GNOME）

## ✨ Features

### 🛠 Core & Terminal
- **Shell**: Zsh + Oh My Zsh + Powerlevel10k (Instant Prompt).
- **Editors**: Vim (Vundle plugins), VS Code.
- **Tools**: Git, Tmux, Htop, Curl, Wget.
- **SSH**: 自动生成 Ed25519 密钥并配置 config

### 💻 Development
- **Docker**: 自动安装并配置免 sudo 权限
- **Python**: Miniconda3 自动安装与初始化
- **Build**: Build-essential / GCC tools.

### 🖥 Desktop (GNOME Optimized)
*仅在 `profile: desktop` 模式下启用*
- **Terminal**: Tilix (配置了 Dracula 主题 & F12 Quake 模式快捷键)
- **Apps**: Google Chrome, WeChat (微信), Snipaste, Sunshine (串流服务), YesPlayMusic (网易云音乐)
- **Input**: Fcitx5 + Rime (雾凇拼音/小鹤双拼支持)
- **Fonts**: Maple Mono NF CN (自动下载并配置为系统等宽字体)
- **Shortcuts**: 一键绑定 Chrome (F11), Tilix (Ctrl+Alt+T) 等快捷键

## 📦 Compatibility

脚本内部适配了各个包管理器：
- **Debian/Ubuntu** (`apt`)
- **Arch Linux** (`pacman` / `yay`)
- **Fedora** (`dnf`)
- ...

## 🚀 Usage

### 1. Prerequisites

bin目录下已经预先配置了dotb，完整项目源码如下
[DotBuilder](https://github.com/Kie-Chi/dotbuiler)

### 2. Install

```bash
# 1. 克隆仓库
git clone https://github.com/Kie-Chi/dotfiles.git ~/.dotfiles

# 2. 链接执行文件 (如果 dotb 在系统路径中可跳过)
ln -s /usr/local/bin/dotb ~/.dotfiles/bin/dotb

# 3. 自定义配置
# 你可以修改 username, email 或选择 profile (desktop/server)
vim ~/.dotfiles/configs/config.yml

# 4. 执行安装
dotb -c ~/.dotfiles/configs/config.yml
