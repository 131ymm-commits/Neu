# AUTO-08 ДИАГНОСТИКА (пост-хок): головы читают остаточный поток ДО финальной LayerNorm, как в JAX AUTO-04..07.
# AUTO-08: мост к PYTHIA-01 — та же архитектура (GPT-NeoX из transformers) и тот же код голов на torch, что в
# ../colab/aux_heads_pythia.py, но маленькая модель с нуля на «Алисе» по знакам (HF закрыт — Pythia не скачать).
# Ветви: A0 | F<K> — K голов «через k_j знаков будет v_j» | S<K> — те же цели от чужой последовательности батча.
import sys, os, time, json, math
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fnn
from transformers import GPTNeoXConfig, GPTNeoXForCausalLM
from transformers.utils import logging as hf_logging
hf_logging.set_verbosity_error()
torch.set_num_threads(1)

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN = open(os.path.join(HERE, 'alice_en_ch01-10.txt'), encoding='utf-8').read().lower()
TEST = open(os.path.join(HERE, 'alice_en_ch11-12.txt'), encoding='utf-8').read().lower()
CHARS = sorted(set(TRAIN) | set(TEST)); V = len(CHARS); IDX = {c: i for i, c in enumerate(CHARS)}
TR = np.array([IDX[c] for c in TRAIN]); TE = np.array([IDX[c] for c in TEST])
T, BS, LAM, H = 64, 64, 0.3, 32
STEPS = int(os.environ.get('AUTO_STEPS', 2000))


def main(arm, seed):
    torch.manual_seed(seed); rng = np.random.default_rng(2000 + seed); g = np.random.default_rng(10_000 + seed)
    cfg = GPTNeoXConfig(vocab_size=V, hidden_size=64, num_hidden_layers=2, num_attention_heads=4, intermediate_size=256,
                        max_position_embeddings=T, rotary_pct=0.25, use_parallel_residual=True)
    model = GPTNeoXForCausalLM(cfg)
    K = int(arm[1:]) if arm != 'A0' else 1
    KJ = torch.tensor(g.integers(1, H + 1, K)); VJ = torch.tensor(g.integers(0, V, K))
    head = nn.Linear(64, K); nn.init.zeros_(head.weight); nn.init.zeros_(head.bias)
    params = list(model.parameters()) + (list(head.parameters()) if arm != 'A0' else [])
    opt = torch.optim.AdamW(params, lr=1e-3, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1, (i + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(i, STEPS) / STEPS))))

    @torch.no_grad()
    def test_nll():
        model.eval(); n = (len(TE) - 1) // (T + 1); X = torch.tensor(TE[:n * (T + 1)].reshape(n, T + 1))
        lp = Fnn.cross_entropy(model(X[:, :-1]).logits.reshape(-1, V), X[:, 1:].reshape(-1)).item()
        model.train(); return lp

    log, t0 = [dict(step=0, test=test_nll())], time.time()
    for i in range(STEPS):
        st = rng.integers(0, len(TR) - T - 1, BS)
        xb = torch.tensor(np.stack([TR[s:s + T + 1] for s in st]))
        cap = {}; hk = model.gpt_neox.final_layer_norm.register_forward_hook(lambda mod, inp, o: cap.update(pre=inp[0])); out = model(xb[:, :-1]); hk.remove()
        loss = Fnn.cross_entropy(out.logits.reshape(-1, V), xb[:, 1:].reshape(-1))
        if arm != 'A0':
            x = xb[:, :-1]; P = T - H; pos = torch.arange(P)
            y = (x[:, pos[:, None] + KJ[None, :]] == VJ[None, None, :]).float()
            if arm[0] == 'S':
                y = torch.roll(y, 1, 0)
            var = y.reshape(-1, K).var(0) + 1e-6
            aux = (((head(cap['pre'][:, :P]) - y) ** 2).reshape(-1, K).mean(0) / var).mean()
            loss = loss + LAM * aux
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step()
        if (i + 1) % 500 == 0 or i + 1 == STEPS:
            log.append(dict(step=i + 1, test=test_nll()))
            print(arm, seed, log[-1], round(time.time() - t0), flush=True)
    os.makedirs(os.path.join(HERE, 'diag_preLN'), exist_ok=True)
    json.dump(log, open(os.path.join(HERE, f'diag_preLN/{arm}_s{seed}.json'), 'w'))


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]))
