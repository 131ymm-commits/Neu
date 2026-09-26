# Вспомогательные головы на Pythia — продолжение AUTO-04…07 на настоящей языковой модели (для Колаба с GPU).
# Ветви: A0 — только LM; F — K голов «через k_j токенов будет токен v_j»; S — те же цели от чужой последовательности батча;
#        N — K голов на свежий шум. Общий вес λ при любом K. Метрика — лосс на отложенном тексте.
# Запуск в Колабе: Runtime → GPU; затем ячейки ноутбука aux_heads_pythia.ipynb (она же вызывает run_all()).
# 26.09: головы читают остаточный поток до final_layer_norm (исправлено до первого запуска, см. ERRORS № 25).
# Местная проверка без интернета: SMOKE=1 python3 aux_heads_pythia.py (крошечная случайная GPT-NeoX, случайные данные).
import os, json, time, math, random
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fnn

CFG = dict(
    model='EleutherAI/pythia-160m',      # или pythia-70m / pythia-410m
    mode='finetune',                      # 'finetune' — с обученных весов; 'scratch' — случайная инициализация той же архитектуры
    data_url='https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt',
    seq=256, batch=16, steps=1000, lr=1e-4, lam=0.3, K=1024, horizon=16,
    arms=['A0', 'F', 'S', 'N'], seeds=[0, 1, 2, 3, 4], eval_every=250, out='results.json')
SMOKE = os.environ.get('SMOKE') == '1'
dev = 'cuda' if torch.cuda.is_available() else 'cpu'


def load_model_and_data(seed):
    from transformers import AutoTokenizer, AutoModelForCausalLM, GPTNeoXConfig, GPTNeoXForCausalLM
    torch.manual_seed(seed)
    if SMOKE:
        cfg = GPTNeoXConfig(vocab_size=100, hidden_size=32, num_hidden_layers=2, num_attention_heads=2, intermediate_size=64,
                            max_position_embeddings=128)
        model = GPTNeoXForCausalLM(cfg)
        ids = np.random.default_rng(0).integers(0, 100, 20000)
    else:
        tok = AutoTokenizer.from_pretrained(CFG['model'])
        if CFG['mode'] == 'scratch':
            from transformers import AutoConfig
            model = AutoModelForCausalLM.from_config(AutoConfig.from_pretrained(CFG['model']))
        else:
            model = AutoModelForCausalLM.from_pretrained(CFG['model'])
        import urllib.request
        text = urllib.request.urlopen(CFG['data_url']).read().decode('utf-8')
        ids = np.array(tok(text)['input_ids'])
    cut = int(len(ids) * 0.9)
    return model.to(dev), ids[:cut], ids[cut:]


def aux_targets(x, arm, KJ, VJ, gen):
    """x: (B, T) токены. Цели на позициях t = 0..T-H-1: (B, P, K)."""
    B, T = x.shape
    H = CFG['horizon']; P = T - H
    if arm == 'N':
        return torch.randn(B, P, len(KJ), device=x.device, generator=gen)
    pos = torch.arange(P, device=x.device)
    fut = x[:, pos[:, None] + KJ[None, :]]                       # (B, P, K)
    y = (fut == VJ[None, None, :]).float()
    return torch.roll(y, 1, 0) if arm == 'S' else y


def run(arm, seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model, tr, te = load_model_and_data(seed)
    V = model.config.vocab_size; D = model.config.hidden_size
    T = 64 if SMOKE else CFG['seq']; Bsz = 4 if SMOKE else CFG['batch']; steps = 20 if SMOKE else CFG['steps']
    K = 64 if SMOKE else CFG['K']; H = CFG['horizon']
    g = np.random.default_rng(10_000 + seed)
    # F/S: частые токены отложенной части — чтобы индикаторы не были почти всегда нулём
    common = np.bincount(tr, minlength=V).argsort()[::-1][:max(K, 1)]
    KJ = torch.tensor(g.integers(1, H + 1, K), device=dev)
    VJ = torch.tensor(g.choice(common, K), device=dev)
    head = nn.Linear(D, K).to(dev); nn.init.zeros_(head.weight); nn.init.zeros_(head.bias)
    params = list(model.parameters()) + (list(head.parameters()) if arm != 'A0' else [])
    opt = torch.optim.AdamW(params, lr=CFG['lr'], weight_decay=0.01)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1, (i + 1) / 50) * 0.5 * (1 + math.cos(math.pi * min(i, steps) / steps)))
    gen = torch.Generator(device=dev).manual_seed(50_000 + seed)
    rng = np.random.default_rng(2000 + seed)

    @torch.no_grad()
    def evaluate():
        model.eval(); n = (len(te) - 1) // (T + 1); X = torch.tensor(te[:n * (T + 1)].reshape(n, T + 1), device=dev)
        tot = 0.0
        for i in range(0, n, 8):
            xb = X[i:i + 8]
            tot += Fnn.cross_entropy(model(xb[:, :-1]).logits.reshape(-1, V), xb[:, 1:].reshape(-1), reduction='sum').item()
        model.train(); return tot / (n * T)

    log = [dict(step=0, test=evaluate())]
    for i in range(steps):
        st = rng.integers(0, len(tr) - T - 1, Bsz)
        xb = torch.tensor(np.stack([tr[s:s + T + 1] for s in st]), device=dev)
        cap = {}                                                    # остаточный поток ДО финальной нормализации (как в JAX AUTO-04…07)
        hk = model.gpt_neox.final_layer_norm.register_forward_hook(lambda mod, inp, o: cap.update(pre=inp[0]))
        out = model(xb[:, :-1]); hk.remove()
        lm = Fnn.cross_entropy(out.logits.reshape(-1, V), xb[:, 1:].reshape(-1))
        loss = lm
        if arm != 'A0':
            h = cap['pre'][:, :T - H]
            y = aux_targets(xb[:, :-1], arm, KJ, VJ, gen)
            var = y.reshape(-1, K).var(0) + 1e-6
            aux = (((head(h) - y) ** 2).reshape(-1, K).mean(0) / var).mean()
            loss = lm + CFG['lam'] * aux
        opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step()
        if (i + 1) % (10 if SMOKE else CFG['eval_every']) == 0:
            log.append(dict(step=i + 1, test=evaluate(), lm=lm.item()))
            print(arm, seed, log[-1], flush=True)
    return log


def run_all():
    res = json.load(open(CFG['out'])) if os.path.exists(CFG['out']) else {}
    for seed in CFG['seeds'][:1] if SMOKE else CFG['seeds']:
        for arm in CFG['arms']:
            key = f'{arm}_s{seed}'
            if key in res:
                continue
            t0 = time.time(); res[key] = run(arm, seed)
            print(key, 'готово за', round(time.time() - t0), 'с', flush=True)
            json.dump(res, open(CFG['out'], 'w'), indent=1)      # сохраняем после каждого прогона: Колаб может отключиться
    return res


def summary(res):
    seeds = sorted({int(k.split('_s')[1]) for k in res})
    last = {k: v[-1]['test'] for k, v in res.items()}
    for a in CFG['arms']:
        if a == 'A0':
            continue
        d = [last[f'A0_s{s}'] - last[f'{a}_s{s}'] for s in seeds if f'{a}_s{s}' in last and f'A0_s{s}' in last]
        print(f'{a}: лучше A0 в {sum(x > 0 for x in d)} из {len(d)}, медиана выигрыша {np.median(d):+.4f}')
    d = [last[f'S_s{s}'] - last[f'F_s{s}'] for s in seeds if f'F_s{s}' in last and f'S_s{s}' in last]
    if d:
        print(f'F против S (специфичность): F лучше в {sum(x > 0 for x in d)} из {len(d)}, медиана {np.median(d):+.4f}')


if __name__ == '__main__':
    if SMOKE:
        CFG['out'] = '/tmp/smoke_results.json'
        if os.path.exists(CFG['out']):
            os.remove(CFG['out'])
    summary(run_all())
