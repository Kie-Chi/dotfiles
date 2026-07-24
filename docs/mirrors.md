# Mirror Policy

本仓库以 `envy.mirrors.mode` 管理网络镜像。它是跨平台 machine setting，目前支持：

- `china`：使用仓库内审计过的国内镜像，默认值。
- `upstream`：使用上游服务；Linux APT 回到系统已有 sources。

镜像选择写在 `hosts/<platform>/<machine-id>.nix`，不是 device-local 状态：

```nix
{
  envy.mirrors.mode = "china";
}
```

## Two Stages

首次安装时 machine module 还没有求值，镜像分为两个阶段：

1. `install.sh --mirror china|upstream` 设置 `ENVY_MIRROR`。`setup.sh` 加载 `resources/scripts/mirror-env.sh`，在第一次 `nix develop` 前注入临时 Nix、npm、PyPI/uv、Go 和 Rust/Cargo 环境。
2. setup 写入 machine setting；`envy apply` 后由 `modules/mirrors/` 声明式维护长期配置。

直接运行 `bash setup.sh` 时也会读取 `ENVY_MIRROR`，未指定则使用 `china`。bootstrap shell 中的端点必须与 `modules/mirrors/catalog.nix` 保持一致。

## Managed Ecosystems

| Scope | Ecosystem | China endpoint / behavior |
|---|---|---|
| Common | Nix binary cache | USTC，保留 `cache.nixos.org` fallback 与 Nix signature verification |
| Common | npm | npmmirror |
| Common | PyPI / uv | TUNA |
| Common | Go modules | `goproxy.cn,direct` |
| Common | rustup / Cargo | RSProxy |
| Common | Maven Central | Aliyun public repository |
| Common | Conda / conda-forge | TUNA；保留仓库原有 mamba env/package directories |
| Darwin | Homebrew API, bottles, brew/core Git | TUNA，通过 nix-darwin activation environment |
| Linux | Ubuntu / Debian APT | TUNA，Deb822 source owned by Envy |
| Linux | Docker installer | `get.docker.com --mirror Aliyun` |

DNF、pacman 和 zypper 继续使用机器已有 repositories。仓库目前没有为这些发行版选择并验证统一镜像，不能因为它们也安装 system packages 就复用 APT 配置。

## APT Ownership

China mode 在 Ubuntu 或 Debian 上生成：

```text
/etc/apt/sources.list.d/envy-mirror.sources
```

Envy 不覆盖、重命名或删除 `/etc/apt/sources.list` 以及其他软件创建的 source 文件。Envy 自己的 `pkg_update`、`pkg_install` 和本地 `.deb` 安装只读取上述 source，避免被慢速系统源拖累。切换到 `upstream` 时只删除 Envy 自己的文件。

Waydroid 是独立第三方 repository。它的安装仍读取完整系统 source set，因此 `repo.waydro.id` 不会被 TUNA Ubuntu/Debian 源遮蔽。腾讯官方 WeChat `.deb` 也保留原始下载 URL，只把依赖解析交给 APT mirror。

## Inspection

```bash
envy mirror status
envy mirror status --refresh
envy mirror probe
envy mirror probe --timeout 30
```

`status` 展示当前 machine evaluated manifest 中实际生效的平台端点。`probe` 对 catalog 中的 probe URL 做只读 HTTP HEAD 检查，报告状态码和耗时；失败时返回非零，不下载 artifact、不写 machine 配置，也不调用 `chsrc`。

## Bootstrap Limits

Nix binary cache 只提供已经构建的 store paths，不能代替所有 source 下载：

- clone dotfiles 和 flake 的 GitHub inputs 仍需能够访问 GitHub。受限网络可设置 `HTTPS_PROXY`，或用 `ENVY_REPOSITORY_URL` 指向用户信任的 Git remote。
- Determinate Nix Installer 本身在 Nix 可用前下载。没有自动选择第三方副本；需要时显式设置经过审查的 `ENVY_NIX_INSTALLER_URL`。
- 固定哈希的 `fetchurl`、`fetchFromGitHub`、Zotero XPI、GitHub release、KDE artifact 和 Rime source 保持原 URL。把它们透明改写到通用代理会改变供应链边界，即使哈希仍能检测内容变化。
- Docker 与 Waydroid 安装脚本仍来自其官方 endpoint；Docker 的 package repository 通过官方脚本参数选择 Aliyun。

`chsrc` 可以作为用户手动排障和比较镜像的工具，但不是 Envy activation 的依赖。Envy 不应在每次 apply 时修改 application-owned 或 system-owned 配置。

## Security

- 不关闭 Nix signature verification，也不动态接受额外 public key。
- Catalog 与 bootstrap 脚本中的 endpoint 是受版本控制的静态 policy。
- API key、proxy token 和其他 secrets 不属于 mirror config，仍必须经过 sops。
- 新增或替换 endpoint 时，应先验证 metadata、代表性 artifact 与 TLS，再更新 catalog、probe 和文档。
