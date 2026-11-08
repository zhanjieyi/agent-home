# VMP 壳逆向实战报告

- 目标：`/tmp/vmp-re/vmp_O0`（自建 VMP 风格样本）
- 样本：自定义寄存器 VM + XOR 加密字节码 + strip 符号
- 时间：2026-11-09 01:15 – 01:20
- 结论：**加密字节码 → 解密 → 反汇编 → 代数 keygen → 动态 patch 全链打通**

## 一、样本设计

源文件 `vmp_target.c`，VM 规格：

| 项 | 规格 |
|---|---|
| VM 类型 | 寄存器机，4 个 32 位寄存器 |
| 指令长度 | **11 字节**（op:1 + a:1 + b:1 + imm:4 + extra:4） |
| 加密 | 全字节码 XOR `0x5A` |
| 解密时机 | 运行时展开到栈缓冲区 |
| 保护 | `strip -x -S` 剥符号 |
| 校验逻辑 | 8 条 VM 指令 |

VM 指令集共 18 条：`LI/MOV/XOR/ADD/MUL/AND/SHR/SHL/MOD/JEQ/JNE/OK/FAIL/XORI/ADDI/MULI/SWAP/NOT`。

## 二、逆向链（5 步）

### 1. 静态定位加密块

```bash
python3 -c "d=open('vmp_O0','rb').read(); e=open('bytecode.enc','rb').read(); print(hex(d.find(e)))"
→ 0xa2c
```

加密块 88 字节，落在 `__TEXT,__const` 段。

### 2. 爆破 XOR key

```python
blob = d[0xa2c:0xa2c+88]
for k in range(256):
    if bytes(b^k for b in blob)[0] == 0x02:   # 已知首指令是 MOV(0x02)
        print(hex(k))
→ 0x5a
```

**单字节 XOR 只需 256 次尝试，用已知明文首字节做验证即可。**

### 3. 解密并反汇编 VM

```python
dec = bytes(b ^ 0x5A for b in blob)
L = 11
for i in range(0, len(dec), L):
    c = dec[i:i+L]
    op, a, b = c[0], c[1], c[2]
    imm   = struct.unpack_from('<I', c, 3)[0]
    extra = struct.unpack_from('<I', c, 7)[0]
```

输出：

```
 pc   addr  op      a  b        imm  extra
  0      0  MOV     0  1          0      0
  1     11  MULI    0  0         31      0
  2     22  ADDI    0  0          7      0
  3     33  XORI    0  0      43981      0
  4     44  AND     0  0      65535      0
  5     55  JEQ     0  0       4660      7
  6     66  FAIL    0  0          0      0
  7     77  OK      0  0          0      0
```

### 4. 代数推导 keygen（不暴力）

从指令序列直接建模：

```
r0 = input
r0 *= 31
r0 += 7
r0 ^= 0xABCD
r0 &= 0xFFFF
if r0 == 0x1234 → OK
```

代数求解（模 65536 求逆）：

```python
t = 0x1234 ^ 0xABCD              # = 0xb9f9
x = ((t - 7) * pow(31, -1, 65536)) % 65536
```

```
[+] key = 16334 (0x3FCE)
```

暴力搜索验证：`0..65535` 范围内**唯一解** `16334`，与代数解一致。

### 5. 动态 patch

把 `JEQ`（0x0A）改成 `JNE`（0x0B），逻辑反转。注意必须保持加密层：

```python
d[0xa2c + 55] = 0x0B ^ 0x5A    # 明文 0x0A → 0x0B，加密层同步
codesign --force --sign - vmp_patched2
```

结果：

```
./vmp_patched2 16334  →  [-] wrong      ← 正确输入被拒
./vmp_patched2 1      →  [+] correct!   ← 错误输入通过
```

## 三、关键踩坑

| 问题 | 原因 | 解决 |
|---|---|---|
| `-O2` 编译后找不到加密块 | **编译器常量折叠**，解密循环被提前求值，字节码以**明文**落盘 | 用 `-O0` 保留真实加密数据 |
| patch 后 `exit=137` | macOS 代码签名失效 → `SIGKILL` | `codesign --force --sign -` 重签 |
| 指令长度对不上 | 生成器实际输出 **11 字节**，C 里写的是 10 | 改 `#define INSN_LEN 11` |

## 四、真实 VMP 的差异

本样本是**教学级 VMP**。商业 VMP（VMProtect / Themida / Enigma）在以下维度远复杂：

| 维度 | 本样本 | 商业 VMP |
|---|---|---|
| 字节码混淆 | 单层 XOR | 多层加密 + 每指令独立密钥 |
| 指令分派 | switch + 跳转表 | 间接跳转 + 花指令 + 虚假路径 |
| handler | 明文字段 | handler 被随机化重排 + 内联 |
| 反调试 | 无 | ptrace/PT_DENY_ATTACH、时间检测、异常处理 |
| 完整性 | 无 | 段校验和、代码自修改 |
| 脱壳目标 | 字节码 | 还原混淆后的原生指令流 |

**真实 VMP 的突破路径**（本样本未涉及，需实测）：

1. **handle tracing**：动态记录每条 VM handler 的执行序列，重建字节码
2. **指令 lift**：把每个 handler 的语义翻译成中间表示（VEX/LLVM IR）
3. **devirtualization**：用符号执行或切片消除分派层，还原原始 CFG
4. **constant folding 回收**：识别垃圾指令并折叠

## 五、工具链现状

| 工具 | 状态 | 备注 |
|---|---|---|
| `otool` / `nm` / `strings` | ✅ | 静态分析主力 |
| `lldb` | ✅ | 动态调试可用 |
| `clang` | ✅ | 21.0.0 |
| `python3` + `unicorn` 2.1.4 + `capstone` 5.0.7 + `lief` | ✅ | 模拟执行 / 反汇编 / 二进制解析 |
| `ghidra` | ✅ | `analyzeHeadless` 存在 |
| `radare2` | ❌ | **断链**：`libr_arch.6.2.5.dylib` 实体缺失 |
| `frida` | ❌ | `ImportError: cannot import name '_frida'` |

修复 r2：

```bash
# 需要重新下载 radare2 完整包，或
# 从其他安装复制 libr_arch.6.2.5.dylib 到 /Users/zhanchunfeng/tools/re/lib/
```

修复 frida：

```bash
/Users/zhanchunfeng/tools/re/venv/bin/pip install --force-reinstall frida
```

## 六、产物

```
/tmp/vmp-re/
├── vmp_target.c        样本源码
├── genbc.py            字节码生成器
├── keygen.py           从指令序列导出的 keygen
├── verify.sh           一键复现全链
├── bytecode.bin        明文字节码
├── bytecode.enc        加密字节码
├── recovered.bin       从二进制还原的字节码
├── vmp_O0              -O0 样本（保留加密）
├── vmp_stripped        -O2 + strip 样本（字节码被折叠成明文）
└── vmp_patched2        重签后的 patch 版本
```

一键复现：

```bash
cd /tmp/vmp-re && ./verify.sh
```
