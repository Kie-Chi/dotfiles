# Key Management (dtf key)

sops-nix 使用 age 加密管理 dotfiles 中的私密信息。`dtf key` 提供密钥全生命周期管理——从导入、轮换、添加/移除设备，到恢复密钥的生成与提取。

## 快速诊断

```bash
dtf key status    # 检查当前设备密钥状态：是否存在、是否在 .sops.yaml 中、能否解密
dtf key list      # 查看 .sops.yaml 中所有密钥及当前设备标记
```

## 密钥架构

密钥体系由两部分组成：

| 类型 | 作用 | 位置 |
|------|------|------|
| **设备密钥** | 每台设备拥有独立的 age 私钥，用于日常解密 | `~/Library/Application Support/sops/age/keys.txt` |
| **恢复密钥** | 独立于任何设备，用于密钥轮换和设备丢失时恢复访问 | 私钥加密存储在 `secrets/recovery-key.age`，公钥在 `.sops.yaml` 中 |

`.sops.yaml` 使用设备标签（基于 hostname）作为 YAML anchor：

```yaml
keys:
  - &macbook_air age1xxx...    # 设备密钥
  - &recovery age1yyy...       # 恢复密钥
creation_rules:
  - path_regex: secrets/secrets\.yaml$
    key_groups:
      - age:
          - *macbook_air
          - *recovery
```

每台设备的身份标签存储在 gitignored 的 `.device-label` 文件中（默认为 hostname 的 sanitized 版本）。

## 常见场景

### 场景 1：新设备配置

在新设备上克隆 dotfiles 后，sops 无法解密 `secrets.yaml`。有两种方式：

**方式 A — 从旧设备复制密钥：**

1. 在旧设备上导出密钥：
   ```bash
   dtf key export --output /Volumes/USB/age-key.txt
   ```
2. 在新设备上导入：
   ```bash
   dtf key import --age /Volumes/USB/age-key.txt --label new_macbook
   ```

**方式 B — 从 SSH 密钥派生（如果旧设备也用 SSH 派生）：**

```bash
dtf key import --ssh ~/.ssh/id_ed25519 --label new_macbook
```

**方式 C — 全新密钥 + 重新输入所有秘密：**

```bash
dtf key import --generate --label new_macbook
dtf config   # 重新填写所有秘密值
```

导入后 `dtf key import` 会自动将新密钥加入 `.sops.yaml` 并运行 `sops updatekeys`，使新设备能解密已有秘密。

也可以通过 `dtf config`（即 setup.py）交互式完成——如果解密失败，它会自动进入密钥导入流程。

### 场景 2：添加另一台设备的密钥

如果你想在另一台设备上也能解密 secrets，需要把那台设备的公钥加入 `.sops.yaml`：

1. 在另一台设备上查看公钥：
   ```bash
   dtf key status   # 查看 Public key
   ```
2. 在任意设备上添加：
   ```bash
   dtf key add age1xxx... --label work_desktop
   ```

这会自动 re-encrypt secrets 和 recovery key 给新设备。

### 场景 3：移除丢失设备的密钥

如果一台设备丢失或不再需要：

```bash
dtf key remove work_desktop
```

移除后会 re-encrypt secrets，被移除的设备将不再能解密。

注意：不能移除 `recovery` 密钥、不能移除当前设备密钥（除非 `--force`）、不能移除最后一个设备密钥。

### 场景 4：密钥轮换

如果怀疑密钥泄露，或想定期更换：

```bash
dtf key rotate
```

轮换流程（两阶段，确保零数据丢失）：

1. **Phase 1**: 在 `keys.txt` 中追加新密钥（保留旧密钥），`.sops.yaml` 同时包含新旧密钥，`sops updatekeys` re-encrypt 给旧+新+恢复
2. **Phase 2**: 从 `.sops.yaml` 和 `keys.txt` 中移除旧密钥，再次 `sops updatekeys`

整个过程中，恢复密钥始终在场，确保即使旧密钥出问题也不会丢失秘密。

轮换恢复密钥：
```bash
dtf key rotate --recovery
```

### 场景 5：恢复密钥

**生成恢复密钥**（首次 setup 时如果没有，需要手动生成）：
```bash
dtf key add-recovery
```

恢复密钥的私钥会被 age 加密后存储在 `secrets/recovery-key.age`，加密目标为 `.sops.yaml` 中的所有设备公钥。任何已有设备都能解密它。

**提取恢复密钥私钥**（用于离线保存或紧急恢复）：
```bash
dtf key recover-recovery               # 打印到终端
dtf key recover-recovery --output /tmp/recovery.txt   # 保存到文件
```

强烈建议将恢复密钥私钥额外保存在离线位置（USB、纸质、密码管理器），作为设备全部丢失时的终极备份。

### 场景 6：导出密钥用于传输

```bash
dtf key export                  # 输出 age 私钥到 stdout
dtf key export --output key.txt # 保存到文件
dtf key export --format ssh     # 导出 SSH 私钥（仅适用于 SSH 派生的设备）
```

私钥是敏感数据，请使用安全传输方式（USB、scp、加密信道）。

## 内部机制

### SOPS_AGE_KEY_FILE

sops 默认在 `~/.config/sops/age/keys.txt` 查找密钥，但 dotfiles 使用 macOS 标准路径 `~/Library/Application Support/sops/age/keys.txt`。`key.py` 和 `setup.py` 的 `run_cmd()` 函数会在所有 sops/age 命令中设置 `SOPS_AGE_KEY_FILE` 环境变量。

### write_secrets_yaml 安全机制

`setup.py` 的 `write_secrets_yaml()` 使用原子写入策略：
1. 写到临时文件
2. 在临时文件上执行 sops encrypt
3. `os.replace` 原子重命名到最终位置
4. 如果加密失败 → 删除临时文件 → 抛出异常 → **绝不留下未加密数据**

### 密钥文件多行支持

age 的 `keys.txt` 可以包含多行 `AGE-SECRET-KEY-...`（多个私钥）。密钥轮换时利用此特性：Phase 1 在文件中追加新私钥，使 sops 可以同时用旧密钥和新密钥解密。

## 子命令速查

| 命令 | 简写 | 用途 |
|------|------|------|
| `dtf key list` | `ls` | 显示所有密钥 |
| `dtf key status` | `st` | 诊断当前设备状态 |
| `dtf key add PUBKEY` | `a` | 添加设备公钥 |
| `dtf key remove LABEL` | `rm` | 移除设备密钥 |
| `dtf key export` | `ex` | 导出当前设备私钥 |
| `dtf key import` | `im` | 导入/生成密钥 |
| `dtf key rotate` | — | 轮换密钥 |
| `dtf key add-recovery` | `ar` | 生成恢复密钥 |
| `dtf key recover-recovery` | `rr` | 提取恢复密钥私钥 |

常用选项简写：`-o` 输出文件，`-l` 标签，`-f` 强制，`-a` age 密钥路径，`-s` SSH 路径，`-g` 生成新密钥，`-r` 轮换恢复密钥，`-F` 导出格式。

示例：
```bash
dtf key ls                          # 查看密钥列表
dtf key st                          # 诊断状态
dtf key ex -o USB/key.txt           # 导出到 USB
dtf key im -a USB/key.txt -l laptop # 从 USB 导入
dtf key rm work_desktop             # 移除密钥
dtf key rr -o /tmp/recovery.txt     # 提取恢复密钥