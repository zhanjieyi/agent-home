#!/usr/bin/env python3
"""从 VM 字节码直接生成 key（无需运行原程序）"""
TARGET = 0x1234
MASK   = 0xFFFF

t = TARGET ^ 0xABCD
x = ((t - 7) * pow(31, -1, 65536)) % 65536
print(f"[+] key = {x} (0x{x:04X})")
