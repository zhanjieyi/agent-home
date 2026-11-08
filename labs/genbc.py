#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 VMP 风格字节码 + C 源码

自定义 VM：寄存器机，固定 10 字节指令
[op:1][a:1][b:1][imm:4 LE][extra:4 LE] + 2 字节填充 = 10
"""
import struct

OPS = {
    "LI": 0x01, "MOV": 0x02, "XOR": 0x03, "ADD": 0x04, "MUL": 0x05,
    "AND": 0x06, "SHR": 0x07, "SHL": 0x08, "MOD": 0x09,
    "JEQ": 0x0A, "JNE": 0x0B, "OK": 0x0C, "FAIL": 0x0D,
    "XORI": 0x0E, "ADDI": 0x0F, "MULI": 0x10, "SWAP": 0x11, "NOT": 0x12,
}


def ins(op, a=0, b=0, imm=0, extra=0):
    return bytes([OPS[op], a, b]) + struct.pack("<I", imm & 0xFFFFFFFF) + struct.pack("<I", extra & 0xFFFFFFFF)


# 程序：
#   INPUT 在 r1
#   r0 = r1
#   r0 *= 31
#   r0 += 7
#   r0 ^= 0xABCD
#   r0 &= 0xFFFF
#   if r0 == 0x1234 -> OK else FAIL
prog = []
prog.append(ins("MOV", 0, 1))            # r0 = r1
prog.append(ins("MULI", 0, 0, 31))       # r0 *= 31
prog.append(ins("ADDI", 0, 0, 7))        # r0 += 7
prog.append(ins("XORI", 0, 0, 0xABCD))   # r0 ^= 0xABCD
prog.append(ins("AND", 0, 0, 0xFFFF))    # r0 &= 0xFFFF
# JEQ r0, 0x1234, target=OK 位置
OK_INDEX = 7
prog.append(ins("JEQ", 0, 0, 0x1234, OK_INDEX))
prog.append(ins("FAIL"))
prog.append(ins("OK"))

bytecode = b"".join(prog)
KEY = 0x5A
enc = bytes(b ^ KEY for b in bytecode)

print(f"// bytecode len = {len(bytecode)} bytes, {len(prog)} instructions")
print(f"// XOR key = 0x{KEY:02X}")
print("static const unsigned char CODE[] = {")
for i in range(0, len(enc), 10):
    chunk = ", ".join(f"0x{b:02X}" for b in enc[i:i + 10])
    print(f"    {chunk},")
print("};")

# 同时写出明文与反汇编，供后面比对
with open("/tmp/vmp-re/bytecode.bin", "wb") as f:
    f.write(bytecode)
with open("/tmp/vmp-re/bytecode.enc", "wb") as f:
    f.write(enc)
