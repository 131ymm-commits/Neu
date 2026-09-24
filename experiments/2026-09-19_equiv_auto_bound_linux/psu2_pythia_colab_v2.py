# ============================================================================
#  ПСУ-2 на настоящей языковой модели (Pythia-70m-deduped) — версия 2, быстрая.
#  Colab: «Среда выполнения» → «Сменить среду выполнения» → T4 GPU. Вставить в одну ячейку и выполнить.
#  На GPU весь расчёт занимает минуты. После каждой контрольной точки результат пишется в
#  psu2_pythia_rows.json; если ячейку запустить снова, посчитанные точки пропускаются.
#  Отличия от версии 1: вероятности классов токенов считаются на GPU (в версии 1 — на CPU в float64,
#  это и было узким местом), сохранение после каждой точки, печать времени. Данные, классы токенов,
#  слой, окна, шкалы, нулевая модель и предрегистрация — те же.
#  ПРЕДРЕГИСТРАЦИЯ (записана до первого запуска; пороги не менялись):
#    PY1: на step0 меньший косинус между 4 ведущими своими и мировыми направлениями < 0.5 (τ = 16).
#    PY2: на step143000 он ≥ 0.9 при τ = 16.
#    PY3: на step143000 ρ₁(своя) > ρ₁(мир) при τ = 16.
#    PY4: число обнаружимых мод (своя цель) при τ = 1 больше, чем при τ = 64, на step143000.
#  Убийство: PY2 не выполнено — «рождение как поворот» на реальной модели не подтверждается.
# ============================================================================
import subprocess, sys, os, json, time
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'transformers', 'datasets', 'scikit-learn'])
import numpy as np, torch
from transformers import GPTNeoXForCausalLM, AutoTokenizer
from datasets import load_dataset
from sklearn.cluster import KMeans

MODEL = 'EleutherAI/pythia-70m-deduped'
STEPS = [0, 512, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 143000]
L, NSEQ, LAYER, KCLS, W = 256, 600, -2, 16, 8       # длина, число последовательностей, слой, классы токенов, окно
TAUS = [1, 16, 64]
BATCH = 16
OUT = 'psu2_pythia_rows.json'
dev = 'cuda' if torch.cuda.is_available() else 'cpu'
print('устройство:', dev, flush=True)
if dev == 'cpu':
    print('ВНИМАНИЕ: GPU не найден. На CPU расчёт займёт несколько часов. '
          '«Среда выполнения» → «Сменить среду выполнения» → T4 GPU.', flush=True)
T_START = time.time()

tok = AutoTokenizer.from_pretrained(MODEL)
ds = load_dataset('NeelNanda/pile-10k', split='train')
ids = []
for t in ds['text']:
    x = tok(t)['input_ids']
    if len(x) >= L + 1:
        ids.append(x[:L + 1])
    if len(ids) >= NSEQ:
        break
ids = np.array(ids)                                   # (NSEQ, L+1)
print('последовательностей:', len(ids), flush=True)

# классы токенов (одни для всех контрольных точек): k-means по входным эмбеддингам финальной модели
final = GPTNeoXForCausalLM.from_pretrained(MODEL, revision='step143000')
E = final.gpt_neox.embed_in.weight.detach().float().numpy()
km = KMeans(KCLS, n_init=4, random_state=0).fit(E[:len(tok)])
cls = np.zeros(E.shape[0], dtype=int); cls[:len(tok)] = km.labels_
M = np.eye(KCLS)[cls]                                 # (V, K) — токен → класс
Mt = torch.tensor(M, dtype=torch.float32, device=dev)
del final
print(f'подготовка: {(time.time() - T_START) / 60:.1f} мин', flush=True)


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def cca(X, Y, reg=1e-10):
    X = X - X.mean(0); Y = Y - Y.mean(0); n = len(X)
    Sxx, Syy, Sxy = X.T @ X / n, Y.T @ Y / n, X.T @ Y / n
    Sxx += reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx)); Syy += reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = inv_sqrt(Sxx), inv_sqrt(Syy)
    U, s, _ = np.linalg.svd(Wx @ Sxy @ Wy)
    return s, Wx @ U, Wx, Wy, X, Y


def spectrum(X3, Y3, rng, nperm=20):
    X3 = X3 - X3.mean(0, keepdims=True); Y3 = Y3 - Y3.mean(0, keepdims=True)
    ns, npos = X3.shape[:2]
    s, A, Wx, Wy, Xc, Yc = cca(X3.reshape(ns * npos, -1), Y3.reshape(ns * npos, -1))
    null = [np.linalg.svd(Wx @ (Xc.T @ (Y3[rng.permutation(ns)].reshape(ns * npos, -1)) / len(Xc)) @ Wy, compute_uv=False)[0]
            for _ in range(nperm)]
    thr = np.percentile(null, 99)
    return s, A, float(thr), int((s > thr).sum()), Xc


rows = json.load(open(OUT)) if os.path.exists(OUT) else []
for step in STEPS:
    if any(r['step'] == step for r in rows):
        print(f'step {step}: уже посчитан, пропускаю', flush=True)
        continue
    t0 = time.time()
    m = GPTNeoXForCausalLM.from_pretrained(MODEL, revision=f'step{step}').to(dev).eval()
    H, P = [], []
    with torch.inference_mode():
        for i in range(0, len(ids), BATCH):
            x = torch.tensor(ids[i:i + BATCH, :L], device=dev)
            o = m(x, output_hidden_states=True)
            H.append(o.hidden_states[LAYER].float().cpu().numpy())
            P.append((torch.softmax(o.logits.float(), -1) @ Mt).cpu().numpy())   # вероятность по классам токенов
    del m, o
    if dev == 'cuda':
        torch.cuda.empty_cache()
    H, P = np.concatenate(H), np.concatenate(P).astype(np.float64)   # (N, L, d), (N, L, K)
    C = M[ids]                                                        # (N, L+1, K) — класс увиденного токена
    nll = float(-np.log(np.take_along_axis(P[:, :L], cls[ids[:, 1:L + 1]][..., None], -1) + 1e-12).mean())
    for tau in TAUS:
        rng = np.random.default_rng(1_000_003 * tau + step)
        pos = np.arange(16, L - tau - W - 1)[::8]
        Ys = sum(np.einsum('npi,npj->npij', C[:, pos + tau + j], P[:, pos + tau + j]).reshape(len(ids), len(pos), -1) for j in range(W)) / W
        Yw = sum(np.einsum('npi,npj->npij', C[:, pos + tau + j], C[:, pos + tau + j + 1]).reshape(len(ids), len(pos), -1) for j in range(W)) / W
        X3 = H[:, pos]
        ss, As, ts, ds_, Xc = spectrum(X3, Ys, rng)
        sw, Aw, tw, dw, _ = spectrum(X3, Yw, rng)
        k = 4
        Q1, _ = np.linalg.qr(Xc @ As[:, :k]); Q2, _ = np.linalg.qr(Xc @ Aw[:, :k])
        cos = np.linalg.svd(Q1.T @ Q2, compute_uv=False)
        rows.append(dict(step=step, tau=tau, rho_self=np.round(ss[:6], 3).tolist(), rho_world=np.round(sw[:6], 3).tolist(),
                         det_self=ds_, det_world=dw, cos_min=float(cos.min()), class_nll=nll))
        print(rows[-1], flush=True)
    json.dump(rows, open(OUT, 'w'), ensure_ascii=False, indent=1)
    dt = time.time() - t0
    left = sum(1 for s in STEPS if not any(r['step'] == s for r in rows))
    print(f'step {step}: {dt / 60:.1f} мин; осталось точек {left}, это ещё примерно {left * dt / 60:.0f} мин', flush=True)

r = {(x['step'], x['tau']): x for x in rows}
print('\nИТОГ (скопируйте всё отсюда и ниже)')
print('step     tau  cos_min  rho1_своя  rho1_мир  мод_своя  мод_мир  nll_классов')
for x in sorted(rows, key=lambda z: (z['step'], z['tau'])):
    print(f"{x['step']:>6} {x['tau']:>6} {x['cos_min']:8.3f} {x['rho_self'][0]:10.3f} {x['rho_world'][0]:9.3f} "
          f"{x['det_self']:9d} {x['det_world']:8d} {x['class_nll']:11.3f}")
print('\nPY1 (step0, τ=16, cos<0.5):', r[(0, 16)]['cos_min'] < 0.5)
print('PY2 (step143000, τ=16, cos≥0.9):', r[(143000, 16)]['cos_min'] >= 0.9)
print('PY3 (ρ₁ своя > мировая):', r[(143000, 16)]['rho_self'][0] > r[(143000, 16)]['rho_world'][0])
print('PY4 (мод при τ=1 больше, чем при τ=64):', r[(143000, 1)]['det_self'] > r[(143000, 64)]['det_self'])
print(f'всего: {(time.time() - T_START) / 60:.1f} мин')
