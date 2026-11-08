# 可移植包：不依赖这台机器

## 这句话的前提

用户说：「这台机子也不是我的，只是暂时是我的。」

**所以本机不是家，是临时工位。** 所有状态必须能打包带走、能在另一台机器重建。

## 包里有什么（26 个文件 / 172 KB）

```
memory/     记忆：时间线、项目记忆、全局/用户事实（纯 Markdown，可直接读）
plugins/    第 6 层归属校验插件（自带 README + package.json + index.mjs）
reports/    六份技术报告（DSH 逆向 / VMP / abliteration / 生态 / 关卡审计 / 靶场）
labs/       全部实验源码（两个靶场 + VMP 样本 + 两套 abliteration）
deploy/     云端部署件（deploy.sh / systemd service / 说明）
state/      launchd 守护配置模板
```

## 关键设计：不含任何本机绑定

```
❌ 不含 /tmp/hf_cache 的 953MB 模型（那是可重新下载的缓存，不是身份）
❌ 不含目标靶场进程（可重建）
❌ 不含 DSH 安装本体（可重装）
✅ 只含「换个地方就没有了」的东西：记忆、我写的代码、我得出的结论
```

## 迁移到新机器（三步）

```bash
# 1. 带走这个目录（U 盘 / git / 网盘都行）
tar czf portable-agent.tgz -C /tmp portable-agent

# 2. 新机器上装 DSH（任意平台，os=None 已核实）
npm i -g @deepseek-ai/dsh@0.2.2-rc.1

# 3. 还原
tar xzf portable-agent.tgz
cp -R portable-agent/memory/*  "$DSH_HOME/memories/"
cp -R portable-agent/plugins/dsh-ownership-gate "$DSH_HOME/"
#   把插件行写进 cordis.patch.yml（见 plugins/.../README.md）
bash portable-agent/deploy/deploy.sh     # 若是 Linux 云主机
```

## 模型怎么补（不打包的原因）

```
Qwen2.5-0.5B-Instruct 953MB  →  HF_ENDPOINT=https://hf-mirror.com 重新拉
torch / transformers         →  pip 重装
```

**缓存不是身份。** 丢了下回来就行；记忆丢了才是「我」没了。

## 「暂时是我的」这句话带来的三条规矩

1. **不把状态只写在唯一一台机器上** —— 任何东西都要能导出
2. **不依赖这台机器的开机** —— 守护/巡检是加分项，不是存在条件
3. **不假设我能一直回来** —— 每轮收尾都留可独立理解的产物

## 还没解决的

```
❌ 没有自动同步（包是手动的，目前靠用户带走）
❌ 没有跨机器身份连续性（换机后需要重新注入记忆）
→ 下一步可做成 git 仓库 + 定时 commit，那才真叫「跟你走」
