# darwin 分支变更总结（10590bd → HEAD）

## 1. 密钥与加密系统重构（最核心变更）

**旧系统**：`secrets.nix` — 纯文本 Nix attrset，明文存储密码/API key，gitignored。
**新系统**：sops-nix + age — 加密 YAML + 多设备密钥管理 + 恢复密钥。

### 新增文件
| 文件 | 作用 | darwin 分支参考 |
|------|------|------|
| `key.py` (874行) | 密钥全生命周期管理 CLI，9 个子命令：list/status/add/remove/export/import/rotate/add-recovery/recover-recovery | `git show darwin:key.py` |
| `.sops.yaml` | sops creation rules，使用 hostname-based YAML anchor（`&macbook_air`, `&recovery`）而非旧的 `&user_chi` | `git show darwin:.sops.yaml` |
| `secrets/secrets.yaml` | sops 加密的 YAML，嵌套结构（`home/passwd`, `proxy/url`, `llm/dashscope/apikey` 等），已被 git tracked | `git show darwin:secrets/secrets.yaml` |
| `secrets/recovery-key.age` | 恢复密钥私钥，age 加密存储，加密目标为所有设备公钥 | `git show darwin:secrets/recovery-key.age` |
| `docs/key.md` | 中文密钥管理指南，覆盖 6 个场景（新设备/添加设备/移除/轮换/恢复/导出） | `git show darwin:docs/key.md` |

### 变更文件
| 文件 | 变更内容 |
|------|------|
| `.gitignore` | 注释掉 `secrets/secrets.yaml`（现在加密后可 commit），新增 `.device-label`（每台设备的 hostname 标签文件） |
| `home.nix` | sops secrets 声明从 `home-passwd` 扩展到 `proxy-url`, `llm-dashscope-apikey`, `llm-deepseek-apikey`；新增 sops template `env-secrets`；activation 脚本迁移到 `sys.task.activation` 格式 |
| `requires.sh` | 大幅简化：移除所有 Linux 包管理器代码（apt/pacman/dnf）和系统依赖安装，只保留 Nix 安装功能（其他依赖由 devShell 提供） |

### 关键架构变化
- **密钥路径**：从 `~/.config/sops/age/keys.txt` 改为 macOS 标准路径 `~/Library/Application Support/sops/age/keys.txt`，所有命令通过 `SOPS_AGE_KEY_FILE` 环境变量指向该路径
- **密钥来源**：优先从 SSH `id_ed25519` 通过 `ssh-to-age` 派生，否则用 `age-keygen` 生成
- **多设备**：`.sops.yaml` 使用基于 hostname 的 anchor label（`&macbook_air`），每台设备有 `.device-label` 文件记录身份
- **恢复密钥**：独立的 age key pair，私钥加密存储在 `secrets/recovery-key.age`，确保密钥轮换零数据丢失
- **两阶段轮换**：Phase 1 追加新密钥（旧+新+恢复均可解密），Phase 2 移除旧密钥

---

## 2. sys 模块（新增基础设施）

**新增**：`modules/libs/sys.nix` (263行) — 提供全局共享基础设施，注入为 `_module.args.sys`。

核心内容：
| 组件 | 作用 |
|------|------|
| `sys.cmds` | macOS 系统工具的绝对路径字典（`sudo`, `pgrep`, `install`, `mkdir` 等），避免 Nix sandbox 内工具不一致 |
| `sys.esudoFn` | 动态 esudo 函数：运行时从 sops 解密文件读取密码，而非 init 时硬编码 |
| `sys.logFn` | `log_debug/info/warn/error` 函数，带颜色和 `_LOG_CTX` 上下文 |
| `sys.sopsDecrypt` | DAG entry：在 `writeBoundary` 之后同步运行 `sops-install-secrets` |
| `sys.userBoundary` | DAG entry：sops 解密完成后的边界门，所有用户脚本在此之后运行 |
| `sys.initActivation` | DAG entry：在 `writeBoundary` 之前注入 log + esudo 函数定义 |
| `sys.task.activation` | 统一的 activation 脚本模板：接受 `after/name/script/guardDryRun` 等参数，默认在 `userBoundary` 之后运行 |
| `sys.config.deploy`/`deployScript` | 配置文件部署模板：temp file → cmp → install，支持 owner/mode/postDeploy |

**新增**：`modules/libs/default.nix` + `modules/libs/bins/default.nix` + `modules/libs/bins/py3bin.nix`（niri-scratchpad Python 包装，当前注释掉未启用）

---

## 3. 所有模块迁移到 sys.task.activation

所有 home-manager activation 脚本从手写的 `lib.hm.dag.entryAfter ["writeBoundary"]` + `echo` 迁移到 `sys.task.activation` + `log_*` + `sys.cmds.*`。

| 模块 | 变更 |
|------|------|
| `home.nix` | `debugSopsPaths` → `sys.task.activation`，新增 `sys` 参数，新增 `libs` import |
| `modules/cores/base.nix` | `setupNixConfig` → `entryAfter ["userBoundary"]` + `log_*`，移除 Linux-specific `systemctl` |
| `modules/cores/ssh.nix` | `generateSSHKey` → `entryAfter ["userBoundary"]` + `log_*` |
| `modules/cores/util.nix` | 新增 `home.file.".config/cc/prompt"` |
| `modules/desktops/proxies.nix` | `xdg.configFile` → `sys.task.activation` + `esudo install`（sops template 需要解密后才能部署） |
| `modules/desktops/raycast-ai.nix`（新增） | sops template `raycast-providers` + `sys.task.activation deployRaycastProviders` |
| `modules/desktops/squirrel.nix` | `entryAfter ["writeBoundary"]` → `sys.task.activation` + `sys.cmds.pgrep` |
| `modules/desktops/wallpaper.nix` | `entryAfter ["writeBoundary"]` → `sys.task.activation` |

关键影响：**所有依赖 sops secrets 的 activation 脚本现在在 `userBoundary`（sops 解密完成）之后运行**，解决了之前 sops 解密时序问题。

---

## 4. setup.py 重写（742行，新文件）

**旧**：`setup.sh` (502行 bash) — gum/jq 驱动的 TUI，明文 `secrets.nix`。
**新**：`setup.py` (742行 Python) — rich + prompt_toolkit 的 menuconfig 式单 Application UI。

关键特性：
- 三种模式切换：`list`（字段列表 + 箭头导航）→ `edit_text`（Buffer 输入 + Frame 包裹）→ `edit_choice`（选项列表）
- 条件字段（如 proxy URL 只在 `proxy.status != "none"` 时显示）
- 内联验证 + 错误显示
- 从 `key.py` 导入 `key_import` 用于新设备密钥导入
- 原子写入 `secrets.yaml`：temp → sops encrypt → `os.replace`（加密失败则删除临时文件，绝不留下明文）
- 保存后自动执行 `sops updatekeys` + `git commit`
- 保存后可选 `dtf apply`

`setup.sh` 简化为 34 行：只负责安装 Nix + `nix develop` → `exec setup.py`。

---

## 5. dtf 脚本更新

`resources/scripts/dtf` 变更：
- **密码来源**：从 `secrets.nix` 明文读取 → `sops -d --extract` 从加密 YAML 读取
- **config 链接**：`secrets.nix` link → `config.nix` link（`ensure_config_links`/`clean_config_links`）
- **esudo 修复**：`if/else` bug（两个分支都执行）修复为正确的条件分支
- **apply 命令**：`esudo -H` → `esudo --preserve-env=HOME`（保留 HOME 环境变量）
- **新增 `k|key` 子命令**：通过 `nix develop` 运行 `key.py`
- **help 更新**：新增 key subcommand 说明

---

## 6. zsh 补全更新

`files/zsh/func.zsh` 新增 `_dtf` 补全的 `k|key` 子命令：
- 9 个子命令及其别名（ls/st/a/rm/ex/im/rotate/ar/rr）
- 每个子命令的 flag 补全（`-o/-l/-f/-a/-s/-g/-r/-F`）
- `rm|remove` 的 label 动态补全（从 `.sops.yaml` grep anchor）
- 使用 `_arguments` 替代 `_values`（修复 `-o` 等带参数 flag 的补全行为）

---

## 7. cc 包装器（新增）

| 文件 | 作用 |
|------|------|
| `resources/scripts/cc` | claude-code wrapper，自动 `--dangerously-skip-permissions` + `--system-prompt` |
| `files/cc/prompt` | system prompt 规则文件（7条规则：禁止 Co-Author/修改 git config、中文文档英文编码、编码前规划等） |

system prompt 读取优先级：`CC_SYSTEM_PROMPT` 环境变量 > `~/.config/cc/prompt` 文件 > 不设置。

---

## 8. raycast-ai 模块（新增，macOS 独有）

**不迁移到 master（Linux/NixOS）**——Raycast 是 macOS 独有的应用，此模块仅在 darwin 分支保留。

`modules/desktops/raycast-ai.nix` (70行)：
- sops template `raycast-providers`：使用 dashscope + deepseek API key 渲染 YAML
- 两个 provider：Anthropic (DashScope) + DeepSeek，各带模型定义（GLM 5.1 / DeepSeek V4 Pro）
- `sys.task.activation` 部署到 `~/.config/raycast/ai/providers.yaml`

---

## 9. AGENTS.md（新增）

`AGENTS.md` (80行)：项目指南，覆盖架构（两层 secret 系统）、密钥文件、命名约定、secret flow、age key 管理、命令列表、重要规则。

---

## 10. 提交历史时间线

```
c5b7867  feat: add cc wrapper for claude-code with system prompt
0012e64  fix(key): use prompt_toolkit styled fragments instead of rich markup
dbd7678  feat(key): arrow-key navigation menu for interactive import
2edc837  feat(key): auto-scan USB for key files in interactive import mode
d15bcbe  fix(zsh): use _arguments for key subcommand option-with-argument completion
a2c8fda  docs: add key management usage guide
21c9101  feat(sops): migrate to multi-device labeled keys with recovery key
d84a822  feat(zsh): add dtf key completion with aliases and short flags
00802b1  feat(dtf): add key subcommand dispatch via nix develop
6448cf6  refactor(setup): import key.py and fix write_secrets_yaml safety
a0debdf  feat(key): add key.py module for sops/age key lifecycle management
2633ca2  feat(setup): add sops decrypt failure handling + key import for new devices
a86acb0  feat: track sops-encrypted secrets.yaml in git
53bab8d  refactor: migrate modules to sys.task.activation and userBoundary
ea943de  feat(sys): rewrite with sopsDecrypt, userBoundary, dynamic esudo
44b8bec  feat: add libs module infrastructure with py3bin utility
1a5dfc5  fix(dtf): config.nix accessible under sudo + esudo bug
b8a339d  feat: rewrite setup.py with menuconfig-style UI
22caacd  feat: add raycast-ai module for LLM providers
```

---

## agent 参考路径

在 master 分支上做一致修改时，可通过以下方式查看 darwin 分支的最终状态：

```bash
# 查看某个文件的完整内容
git show darwin:<file_path>

# 例如
git show darwin:key.py
git show darwin:modules/libs/sys.nix
git show darwin:setup.py
git show darwin:modules/desktops/raycast-ai.nix
git show darwin:resources/scripts/cc
git show darwin:files/cc/prompt
git show darwin:resources/scripts/dtf
git show darwin:files/zsh/func.zsh

# 查看某文件与 10590bd 的完整 diff
git diff 10590bd darwin -- <file_path>

# 查看所有新文件的列表
git diff 10590bd darwin --name-status
```

**注意**：`secrets/secrets.yaml` 和 `secrets/recovery-key.age` 包含加密数据，master 分支需要用自己设备的密钥重新生成，不能直接复制 darwin 的版本。`.sops.yaml` 中的公钥也需要替换为 master 设备的公钥。

**Recovery 密钥共享**：master 和 darwin **应该共享同一个 recovery key**。recovery key 的私钥加密目标是 `.sops.yaml` 中所有设备公钥，当 master 设备通过 `dtf key add` 加入 `.sops.yaml` 后，`recovery-key.age` 会自动 re-encrypt 给 master 的公钥，两台设备都能解密同一个 recovery key。不需要为 master 单独生成 recovery key。
