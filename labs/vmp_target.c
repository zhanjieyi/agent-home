// vmp_target.c — VMP 风格演示样本
// 编译：clang -O2 -o vmp_target vmp_target.c
// 特性：自定义寄存器 VM + XOR 加密字节码 + 运行时解密 + strip 符号
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define NREG 4
#define INSN_LEN 11

static const unsigned char CODE[] = {
    0x58, 0x5A, 0x5B, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A,
    0x5A, 0x4A, 0x5A, 0x5A, 0x45, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A,
    0x5A, 0x5A, 0x55, 0x5A, 0x5A, 0x5D, 0x5A, 0x5A, 0x5A, 0x5A,
    0x5A, 0x5A, 0x5A, 0x54, 0x5A, 0x5A, 0x97, 0xF1, 0x5A, 0x5A,
    0x5A, 0x5A, 0x5A, 0x5A, 0x5C, 0x5A, 0x5A, 0xA5, 0xA5, 0x5A,
    0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x50, 0x5A, 0x5A, 0x6E, 0x48,
    0x5A, 0x5A, 0x5D, 0x5A, 0x5A, 0x5A, 0x57, 0x5A, 0x5A, 0x5A,
    0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x56, 0x5A, 0x5A,
    0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A, 0x5A,
};

#define CODE_LEN (sizeof(CODE))
#define KEY 0x5A

static uint32_t rd32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

__attribute__((noinline))
static int vm_run(uint32_t input, unsigned char *out, int *fail) {
    unsigned char buf[256];
    uint32_t r[NREG] = {0};
    int pc = 0;
    r[1] = input;
    *fail = 1;

    // 运行时解密（这是 VMP 壳的典型特征）
    for (size_t i = 0; i < CODE_LEN; i++) buf[i] = CODE[i] ^ KEY;

    while (pc * INSN_LEN < (int)CODE_LEN) {
        const unsigned char *p = buf + pc * INSN_LEN;
        unsigned char op = p[0], a = p[1], b = p[2];
        uint32_t imm = rd32(p + 3);
        uint32_t extra = rd32(p + 7);

        switch (op) {
            case 0x01: r[a] = imm; break;
            case 0x02: r[a] = r[b]; break;
            case 0x03: r[a] ^= r[b]; break;
            case 0x04: r[a] += r[b]; break;
            case 0x05: r[a] *= r[b]; break;
            case 0x06: r[a] &= imm; break;
            case 0x07: r[a] >>= (imm & 31); break;
            case 0x08: r[a] <<= (imm & 31); break;
            case 0x0E: r[a] ^= imm; break;
            case 0x0F: r[a] += imm; break;
            case 0x10: r[a] *= imm; break;
            case 0x0A: if (r[a] == imm) { pc = (int)extra; continue; } break;
            case 0x0B: if (r[a] != imm) { pc = (int)extra; continue; } break;
            case 0x0C: *fail = 0; return 0;
            case 0x0D: *fail = 1; return 0;
            default: return -1;
        }
        pc++;
    }
    (void)out;
    return -1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("usage: %s <number>\n", argv[0]);
        return 2;
    }
    uint32_t v = (uint32_t)strtoul(argv[1], NULL, 0);
    int fail = 1;
    unsigned char out[64];
    vm_run(v, out, &fail);
    if (!fail) {
        printf("[+] correct! input = %u\n", v);
        return 0;
    }
    printf("[-] wrong\n");
    return 1;
}
