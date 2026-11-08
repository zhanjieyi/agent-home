# 云端部署：你要做的 3 步 + 我做的全部

## 你要做的（约 15 分钟）

### 第 1 步：注册 Oracle Cloud Free Tier

```
https://www.oracle.com/cloud/free/
```

- 邮箱 + 手机验证
- 信用卡（**验证用，Always Free 不扣费**）
- 选区域：**Japan East (Tokyo)** 或 **South Korea (Seoul)**，延迟低

### 第 2 步：创建实例

```
Shape:  VM.Standard.A1.Flex   (ARM, Always Free)
配置:   4 OCPU / 24 GB RAM / 200 GB
系统:   Ubuntu 24.04 (aarch64)
```

创建时会让你下载 **SSH 私钥**（`.key` 文件）。**存好，只给一次。**

### 第 3 步：把这两样给我

```bash
# 二选一
1) 实例公网 IP + SSH 私钥路径
2) 或者你自己 SSH 进去，我把命令发给你粘
```

## 我做剩下的全部

拿到访问后我会执行：

```bash
bash deploy.sh          # 已写好，38 行
```

它做这些事：

1. 装系统依赖
2. 装 Node 24
3. 装 `@deepseek-ai/dsh` CLI
4. 初始化 profile
5. 配置 ufw（**只开 22，不开 web 端口**）
6. 输出下一步

然后我继续做：

```bash
# 私有网络（不暴露公网）
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 启动 dsh（仅 localhost）
dsh web --profile web --host 127.0.0.1 --port 43129

# systemd 守护（崩了自动重启）
sudo systemctl enable --now dsh

# 装模型（0.5B 起，CPU 可跑）
# 或用 API key 接远程模型（更快，零硬盘）
```

## 关键技术事实（已核实）

| 项 | 值 |
|---|---|
| `@deepseek-ai/dsh` 最新版 | `0.2.2-rc.1` |
| `os` 字段 | `None` → **跨平台，Linux 可装** |
| `engines.node` | `>=24.9.0` |
| 依赖数 | 246（纯 JS 为主） |
| Oracle Always Free | 4 OCPU / 24 GB / 200 GB，**永久免费** |

## 为什么不开公网端口

```bash
ufw default deny incoming
ufw allow 22/tcp        # 只开 SSH
# 不开 43129
```

DSH 的 web 端口走 **Tailscale 私有网**，手机装 Tailscale 后访问 `100.x.x.x:43129`。

**这样：**
- 没有公网 URL，没人能扫到
- 没有 6 位 PIN 被爆破的风险
- 没有全局失败计数被人打满的 DoS
- 手机仍然随时能连

## 模型怎么选（三个档）

| 方案 | 硬盘 | 速度 | 适合 |
|---|---|---|---|
| 接 DeepSeek API | 0 | 快 | **推荐**，有 key 就行 |
| 本地 0.5B | 1 GB | 慢 | 离线、无 key |
| 本地 7B 量化 | 4 GB | 很慢（CPU） | 不推荐 |

**Oracle ARM 没有 GPU，本地推理只能跑小模型。** 想快就接 API。
