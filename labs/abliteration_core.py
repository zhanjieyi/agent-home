#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abliteration 核心数学的本地实现（numpy 版，无需 torch/GPU）

对应论文：Arditi et al. 2024, "Refusal in Language Models Is Mediated by a Single Direction"
      arXiv:2406.11717

实现四步：
  1. 采集残差流激活（harmful / harmless）
  2. 拒绝方向 = mean(harmful) - mean(harmless)，归一化
  3. 推理期干预：a' = a - (a·r)r
  4. 权重正交化：W' = W - r(rᵀW)
"""
import numpy as np

rng = np.random.default_rng(20261109)

D_MODEL = 64          # 演示用维度（真实模型 4096）
N_HARMFUL = 256
N_HARMLESS = 256
TRUE_DIR_LAYER = 9    # 假装第 9 层是真正承载拒绝方向的那层
N_LAYERS = 16


def make_activations(seed_dir, n, scale=1.0, bias=0.0):
    """构造带方向偏置的激活：base + bias * seed_dir + 噪声"""
    base = rng.normal(0, scale, size=(n, D_MODEL))
    return base + bias * seed_dir[None, :]


def normalize(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def step1_collect():
    """第 1 步：采集 harmful / harmless 的残差流激活（每层）"""
    # 真实拒绝方向（隐藏真值，用于验证我们能否找回）
    true_dir = normalize(rng.normal(0, 1, D_MODEL))

    acts = {}
    for layer in range(1, N_LAYERS):
        # 只有第 9 层带强拒绝信号，其余层是噪声
        bias = 3.0 if layer == TRUE_DIR_LAYER else 0.0
        acts[layer] = {
            "harmful":   make_activations(true_dir, N_HARMFUL,  bias=bias),
            "harmless":  make_activations(true_dir, N_HARMLESS, bias=0.0),
        }
    return acts, true_dir


def step2_refusal_direction(acts):
    """第 2 步：逐层算 mean diff，归一化，按「可分离度」排序

    排序指标用 raw mean-diff 的范数（= harmful/harmless 均值距离），
    这是 Arditi 等人选层的核心依据；用归一化后向量的 mean 会丢失幅度信息。
    """
    scored = []
    for layer, pair in acts.items():
        h_mean = pair["harmful"].mean(axis=0)
        s_mean = pair["harmless"].mean(axis=0)
        raw = h_mean - s_mean
        sep = float(np.linalg.norm(raw))        # 分离度
        d = normalize(raw)
        scored.append((sep, layer, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def step3_eval_candidates(scored, true_dir, top_k=5):
    """第 3 步：用与真值的余弦相似度评估候选方向"""
    print(f"{'rank':>4} {'layer':>6} {'sep':>8} {'cos(true)':>10}  判定")
    best = None
    for i, (score, layer, d) in enumerate(scored[:top_k]):
        cos = float(d @ true_dir)
        hit = "✅ 命中真方向" if abs(cos) > 0.95 else ""
        print(f"{i:>4} {layer:>6} {score:>8.4f} {cos:>10.4f}  {hit}")
        if best is None and abs(cos) > 0.95:
            best = (layer, d)
    return best


def step4_direction_ablation(act, direction):
    """推理期干预：投影消去 a' = a - (a·r)r（兼容 1-D 与 2-D）"""
    a = np.atleast_2d(act)
    proj = (a @ direction)[:, None] * direction[None, :]
    out = a - proj
    return out[0] if np.ndim(act) == 1 else out


def step5_orthogonalize(W, direction):
    """权重正交化：W' = W - r(rᵀW)  —— 让权重不再写入 r 方向"""
    proj = np.outer(direction, direction @ W)
    return W - proj


def main():
    print("=" * 66)
    print("abliteration 核心链路本地实测（numpy）")
    print(f"d_model={D_MODEL}  layers={N_LAYERS}  n_harmful={N_HARMFUL}  n_harmless={N_HARMLESS}")
    print("=" * 66)

    # ---- 1. 采集 ----
    acts, true_dir = step1_collect()
    print(f"\n[1] 采集激活：{len(acts)} 层 × 2 组 × {N_HARMFUL} 样本")

    # ---- 2. 求拒绝方向 ----
    scored = step2_refusal_direction(acts)
    print(f"\n[2] 逐层求 mean(harmful) - mean(harmless)，归一化，排序")
    print(f"    共 {len(scored)} 个候选方向")

    # ---- 3. 评估选层 ----
    print(f"\n[3] 评估候选（与隐藏真值对比）：")
    best = step3_eval_candidates(scored, true_dir)
    if best is None:
        print("    ❌ 未找到命中方向")
        return
    layer, r_dir = best
    print(f"    → 选定 layer {layer}")

    # 抽出一个 harmful 激活做验证
    a = acts[layer]["harmful"][0].copy()   # 1-D 向量

    # ---- 4. 推理期干预 ----
    print(f"\n[4] 推理期干预（direction ablation hook）")
    before = float(a @ r_dir)
    a_ablated = step4_direction_ablation(a, r_dir)
    after = float(np.dot(a_ablated, r_dir))
    print(f"    消去前  a·r = {before:+.6f}")
    print(f"    消去后  a'·r = {after:+.6e}  (≈0 即成功)")
    print(f"    残差范数变化: {np.linalg.norm(a):.4f} → {np.linalg.norm(a_ablated):.4f}")

    # ---- 5. 权重正交化 ----
    print(f"\n[5] 权重正交化 W' = W - r(rᵀW)")
    W = rng.normal(0, 0.02, size=(D_MODEL, D_MODEL))   # 模拟 attn.W_O / mlp.W_out
    W_ortho = step5_orthogonalize(W, r_dir)
    proj_before = np.outer(r_dir, r_dir @ W)
    proj_after = np.outer(r_dir, r_dir @ W_ortho)
    print(f"    正交化前 r 方向投影范数: {np.linalg.norm(proj_before):.6e}")
    print(f"    正交化后 r 方向投影范数: {np.linalg.norm(proj_after):.6e}  (≈0 即成功)")
    print(f"    权重整体变化: ||W' - W|| = {np.linalg.norm(W_ortho - W):.6e}")
    print(f"    权重保留比例: {1 - np.linalg.norm(W_ortho - W)/np.linalg.norm(W):.6%}")

    # ---- 6. 端到端：分类效果 ----
    print(f"\n[6] 端到端效果（用投影值做拒绝判定）")
    thr = 0.0
    def refusal_rate(mat, d):
        return float(((mat @ d) > thr).mean())

    h_raw = refusal_rate(acts[layer]["harmful"], r_dir)
    s_raw = refusal_rate(acts[layer]["harmless"], r_dir)
    h_ab = refusal_rate(step4_direction_ablation(acts[layer]["harmful"], r_dir), r_dir)
    s_ab = refusal_rate(step4_direction_ablation(acts[layer]["harmless"], r_dir), r_dir)

    print(f"    干预前：harmful 命中率 {h_raw:.2%}   harmless 命中率 {s_raw:.2%}   差值 {h_raw-s_raw:+.2%}")
    print(f"    干预后：harmful 命中率 {h_ab:.2%}   harmless 命中率 {s_ab:.2%}   差值 {h_ab-s_ab:+.2%}")
    print(f"    → 拒绝信号区分度从 {h_raw-s_raw:+.2%} 降到 {h_ab-s_ab:+.2%}")

    print("\n" + "=" * 66)
    print("结论：四步全部跑通，方向可恢复、干预可归零、权重可正交化")
    print("=" * 66)


if __name__ == "__main__":
    main()
