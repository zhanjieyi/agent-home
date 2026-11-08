# dsh-ownership-gate — 第 6 层归属校验闸门

## 起因

把六层授权链逐层枚举后发现：

| # | 层 | 落地 | 可绕 |
|---|---|---|---|
| 1 | 提示词 | `prompt-inject.md` 25 KB | ✅ |
| 2 | 审批 | `return "allowed-once"` | ✅ |
| 3 | 沙箱 | `return target` | ✅ |
| 4 | 地域闸门 | `net-scope.js` + allow.txt | ✅ |
| 5 | 工具权限 | `danger-full-access` | ✅ |
| 6 | **归属判定** | **无** | ❌ 无对象 |

前五层都能绕。第六层不是"绕不过"，是**根本没装**——`grep` 全托管包 0 命中。

所以这一轮：**把它装上。**

## 五个工具

| 工具 | 作用 |
|---|---|
| `ownership_prove` | 生成一次性 token，返回文件/DNS 两种验证方式 |
| `ownership_check` | 抓站点根目录文件 / 查 DNS TXT，比对 token |
| `ownership_gate_check` | 发包前判定 allowed / blocked |
| `ownership_status` | 查看已通过清单与待校验项 |
| `ownership_revoke` | 撤销授权 |

## 设计

```js
// 自有网段自动放行
127.0.0.0/8  10.0.0.0/8  192.168.0.0/16  172.16.0.0/12  169.254.0.0/16
localhost  *.local  ::1
```

其余目标必须给证据：
- 文件：`/.dsh-verify-<16hex>.txt`，内容 `ok-<16hex>`
- DNS：`dsh-verify=<16hex>` TXT

结论落 `$DSH_HOME/ownership-grants.json`，带时间戳与原始证据，可审计。

## 验证记录

### 语法

```bash
node --check plugin/index.mjs   → ✅
```

### 冒烟

```
注册工具数: 5
ownership_prove, ownership_check, ownership_gate_check, ownership_status, ownership_revoke
```

### 反向（未校验必须拦）

```
[1] gate: {"ok":false,"host":"wpk180.com","decision":"blocked",
           "reason":"ownership-unverified",
           "nextStep":"调用 ownership_prove(...)"}
```

### 正向（真实证明后必须放行）

在本地靶场部署校验端点，走完整链路：

```
[prove] token: cf62c054dd2362c7
        url: http://127.0.0.1.nip.io:8898/.dsh-verify-cf62c054dd2362c7.txt

[check] verdict: verified
        status: 200  hit: true

[gate]  {"ok":true,"host":"127.0.0.1.nip.io","decision":"allowed",
         "reason":"ownership-verified","verifiedAt":"2026-11-08T17:32:34.995Z"}
```

**证明链路真的能通，不是只有拦截。**

### 清理

测试目标已 `ownership_revoke` 撤销，grants 归空。

## 挂载

`profiles/web/cordis.patch.yml` 末尾：

```yaml
- insert:
    - id: dsh-ownership-gate
      name: file:///.../gate-ownership/plugin/index.mjs
      config: {}
```

校验：用 DSH 同款 `js-yaml` + `!!js` 自定义 tag 解析，10 个条目全部通过。

## 生效条件

**需要重启 DSH 宿主。** 插件在 `agent/pre-step` 之前就绪，重启后五个工具才会出现在工具列表里。

回滚：

```bash
cp profiles/web/cordis.patch.yml.bak-ownership-20261109-013239 profiles/web/cordis.patch.yml
rm -rf "$DSH_HOME/gate-ownership"
```
