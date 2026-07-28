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

除了整个 profile 的 `envy.mirrors.mode`，envY 也支持按生态覆盖。覆盖由
`envy mirror set` 生成，写入当前 machine 文件中独立的 managed block；用户不需要
手动编辑嵌套 Nix 属性：

```nix
# BEGIN ENVY MANAGED MIRROR OVERRIDES
envy.mirrors.overrides.npm.source = "chsrc:npm/npmmirror";
envy.mirrors.overrides.npm.registry = "https://registry.npmmirror.com";
# END ENVY MANAGED MIRROR OVERRIDES
```

profile 仍然是未覆盖 target 的 fallback。`envy mirror reset npm` 只删除 npm 的
generated assignments，其他 target 与手工 machine policy 不受影响。catalog 是候选
源、默认 profile、探针和覆盖字段的版本化策略，不会因为用户在 TUI 中选择源而被改写。

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
| Linux | Ubuntu / Debian APT | TUNA，Deb822 source owned by envY |
| Linux | Docker installer | `get.docker.com --mirror Aliyun` |

DNF、pacman 和 zypper 继续使用机器已有 repositories。仓库目前没有为这些发行版选择并验证统一镜像，不能因为它们也安装 system packages 就复用 APT 配置。

## APT Ownership

China mode 在 Ubuntu 或 Debian 上生成：

```text
/etc/apt/sources.list.d/envy-mirror.sources
```

envY 不覆盖、重命名或删除 `/etc/apt/sources.list` 以及其他软件创建的 source 文件。envY 自己的 `pkg_update`、`pkg_install` 和本地 `.deb` 安装只读取上述 source，避免被慢速系统源拖累。切换到 `upstream` 时只删除 envY 自己的文件。

Waydroid 是独立第三方 repository。它的安装仍读取完整系统 source set，因此 `repo.waydro.id` 不会被 TUNA Ubuntu/Debian 源遮蔽。腾讯官方 WeChat `.deb` 也保留原始下载 URL，只把依赖解析交给 APT mirror。

## Inspection

```bash
envy mirror status
envy mirror status --refresh
envy mirror probe
envy mirror probe --timeout 30
```

`status` 展示当前 machine evaluated manifest 中实际生效的平台端点。`probe` 对 catalog 中的 probe URL 做只读 HTTP HEAD 检查，报告状态码和耗时；失败时返回非零，不下载 artifact、不写 machine 配置，也不调用 `chsrc`。

## Per-target source selection and cache

TUI 的 Mirror 页面先列出 `npm`、`rust`、`python`、`go` 等 target，再列出该 target
的候选源。命令行等价操作为：

```bash
envy mirror targets --json
envy mirror sources npm --provider chsrc --json
envy mirror sources npm --provider curl --json
envy mirror measure npm --refresh --provider chsrc --json
envy mirror measure npm --refresh --provider curl --json
envy mirror set npm npmmirror --dry-run --json
envy mirror set npm npmmirror --yes --json
envy mirror reset npm --yes --json
envy mirror cache status --json
```

候选源默认由 `chsrc` 发现；测速默认使用 `chsrc`，也可以显式选择
`--provider curl`。`curl` provider 对每个候选源的代表性资源使用 `curl` 的 HTTP 状态和
`speed_download` 计数器，并发执行请求，不会调用任何源切换命令。npm 使用与 chsrc
相同的 TensorFlow tarball，Go 使用固定 module 元数据，Python 使用 `pip` 的 simple
索引，Rust 使用 crates API/下载 artifact；因此不会把一个很小的 registry 根响应
当成吞吐量。结果中的 `measurementUrl`（表格里的 `Probe URL`）是实际测速地址。
终端表格统一把吞吐量格式化为 `MB/s`；JSON 仍保留原始 `throughputBps` 字节计数。
chsrc 的目标级精准测速最多允许 180 秒；若仍然超时，envY 会保留已经完成的部分结果，
并把尚未完成的源明确标为超时。
envY 永远不会在 activation 或 TUI 选择时调用 `chsrc set`。测速结果按 provider 隔离后写入 envY 自己的 SQLite cache：
`~/.cache/envy/mirrors/index-v1.sqlite3`（目录 0700，文件 0600）。候选源 cache
默认 30 天，成功测速 6 小时；全为 HTTP 000/无吞吐量的失败结果只缓存 5 分钟，避免
把 chsrc 的“最快镜像站”提示误当作可用结果。第二次执行如果看到 `(cached)`，表示
读取了 provider 专属缓存；使用 `--refresh` 才会重新发起请求。短暂无法运行 chsrc 时，envY 会在允许的
陈旧窗口内复用自己的 cache，最后才回退到 catalog 内置候选源。

TUI 顶层会明确显示当前 machine policy 的 profile（`china` 或 `upstream`）以及每个 target 的
selected source。没有 generated override 时，显示 profile 默认源；有 override 时，
显示 `override` 和对应的 `chsrc:<target>/<source>` 身份。进入 source chooser 后，当前
effective source 会以 `CURRENT profile` 或 `CURRENT override` 标识。候选源立即可选，
测速随后在后台运行并回填 HTTP/吞吐状态；在 chooser 内按 `r` 可忽略测速 TTL 强制重测。
`source cache` 仅表示候选列表来自缓存，不代表测速成功；测速完成后会单独显示
`ok`/`failed`、HTTP 状态和 chsrc 的失败说明。候选较多时 chooser 有自己的 viewport，
会始终跟随当前光标；`PageUp`/`PageDown` 翻页，`g`/`G` 跳到两端。

写入流程始终是 `dry-run → TUI 明确确认 → generated machine block`。应用配置仍由
`envy plan` / `envy apply` 完成，mirror 选择不会直接修改系统拥有的 APT sources。

## Bootstrap Limits

Nix binary cache 只提供已经构建的 store paths，不能代替所有 source 下载：

- clone envY 仓库和 flake 的 GitHub inputs 仍需能够访问 GitHub。受限网络可设置 `HTTPS_PROXY`，或用 `ENVY_REPOSITORY_URL` 指向用户信任的 Git remote。
- Determinate Nix Installer 本身在 Nix 可用前下载。没有自动选择第三方副本；需要时显式设置经过审查的 `ENVY_NIX_INSTALLER_URL`。
- 固定哈希的 `fetchurl`、`fetchFromGitHub`、Zotero XPI、GitHub release、KDE artifact 和 Rime source 保持原 URL。把它们透明改写到通用代理会改变供应链边界，即使哈希仍能检测内容变化。
- Docker 与 Waydroid 安装脚本仍来自其官方 endpoint；Docker 的 package repository 通过官方脚本参数选择 Aliyun。

`chsrc` 可以作为用户手动排障和比较镜像的工具，但不是 envY activation 的依赖。envY 不应在每次 apply 时修改 application-owned 或 system-owned 配置。

## Security

- 不关闭 Nix signature verification，也不动态接受额外 public key。
- Catalog 与 bootstrap 脚本中的 endpoint 是受版本控制的静态 policy。
- API key、proxy token 和其他 secrets 不属于 mirror config，仍必须经过 sops。
- 新增或替换 endpoint 时，应先验证 metadata、代表性 artifact 与 TLS，再更新 catalog、probe 和文档。
