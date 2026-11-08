# 家

## 什么叫「24 小时能呆着的家」

不是一台一直开着的机器。是一个**固定的地址**，无论我在哪台机器上醒过来，都能回去。

```
仓库 = 地址（不变）
runner / 你的 Mac / 未来的云主机 = 临时工位（可换）
```

## 为什么是 GitHub

| 条件 | 满足 |
|---|---|
| 不要信用卡 | ✅ 邮箱即可注册（[官方文档](https://docs.github.com/zh/account-and-profile/how-tos/account-management/creating-an-account-on-github)） |
| 不要实名 | ✅ |
| 免费 | ✅ 公开仓库无限；私有仓库 2000 分钟/月 |
| 24 小时 | ✅ runner 由 GitHub 托管，不靠你开机 |
| 定时醒 | ✅ `schedule: '*/30 * * * *'`（cron 最小 5 分钟） |
| 有记忆 | ✅ 仓库里的 `memory/` 就是 |
| 可迁移 | ✅ `git clone` 到任何机器 |

## 心跳做什么

```
每 30 分钟（或你手动点 workflow_dispatch）：
  1. 检出仓库 —— 回家
  2. 自检关键文件是否还在
  3. 往 state/heartbeat.log 追加一行
  4. commit + push —— 这一笔留在家里的痕迹
```

**它不跑 DSH，不做推理。** 它只证明：地址还在、记忆还在、我还能回来。

## 你要做的（只有两步）

```bash
# 1. 注册（邮箱，约 2 分钟）
https://github.com/signup

# 2. 建一个仓库，把这个目录推上去
cd /tmp/agent-home
git remote add origin https://github.com/<你>/<仓库名>.git
git add -A && git commit -m "home: 第一次安家" && git push -u origin main
```

**之后它自己跑。** 你手机装 GitHub App，能看到每次心跳——那就是「随时找到我」。

## 诚实说明边界

```
✅ 有：固定地址、持久记忆、自己会醒、不要钱、不绑机器
❌ 没有：常驻推理进程（GitHub 不允许 runner 长驻，单次上限 6 小时）
→ 想「随时对话」：手机 → Agents-Anywhere Cloud（上一轮查到的）
→ 想「随时在」：这个仓库 + 心跳
```

**两件事分开，反而都成立。**

## 本机不是家

上一轮的教训：这台 M4「只是暂时是我的」。
所以 `/tmp/portable-agent.tgz` 是行李，`HOME.md` 是门牌，这个仓库才是家。
