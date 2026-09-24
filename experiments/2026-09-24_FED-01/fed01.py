# FED-01: прибор BOUND-01 при правиле M4 («наружу только числа»). См. PREREG-FED-01.md
import json
import numpy as np
import bound01 as b

TRUTH = {'S1': 'порядок', 'S2': 'порядок', 'S3': 'край', 'S4': 'хаос', 'S5': 'хаос'}
SEEDS = list(range(11, 21))
KS = [4, 40, 200]


def windows(system, L, tau, nseq, noise, seed):
    """Ровно как bound01.run: те же данные при том же сиде; возвращает rng в том же состоянии для FULL."""
    rng = np.random.default_rng(seed)
    T = (L - 1 + b.STRIDE * (b.NPOS - 1)) + tau + L + 1
    x = b.gen(system, nseq, T, rng)
    x = (x - x.mean()) / x.std()
    x = x + noise * rng.normal(size=x.shape)
    ends = L - 1 + b.STRIDE * np.arange(b.NPOS)
    X3 = np.stack([x[:, e - L + 1:e + 1] for e in ends], 1)
    Y3 = np.stack([x[:, e + tau:e + tau + L] for e in ends], 1)
    return X3, Y3, rng


def derangement(m, rng):
    while True:
        p = rng.permutation(m)
        if m < 2 or not (p == np.arange(m)).any():
            return p


def node_message(Xn, Yn, null_pairs):
    """То, что узел отдаёт наружу: только суммы. Xn, Yn: (k, d) — окна узла; null_pairs: список перестановок строк Yn."""
    return dict(n=len(Xn), sx=Xn.sum(0), sy=Yn.sum(0), sxx=Xn.T @ Xn, syy=Yn.T @ Yn, sxy=Xn.T @ Yn,
                null=[Xn.T @ Yn[p] for p in null_pairs])


def center(msgs, reg=1e-10):
    """Центр: складывает суммы и считает спектр и нулевой порог так же, как bound01.spectrum."""
    n = sum(m['n'] for m in msgs)
    mx = sum(m['sx'] for m in msgs) / n; my = sum(m['sy'] for m in msgs) / n
    Sxx = sum(m['sxx'] for m in msgs) / n - np.outer(mx, mx)
    Syy = sum(m['syy'] for m in msgs) / n - np.outer(my, my)
    Sxy = sum(m['sxy'] for m in msgs) / n - np.outer(mx, my)
    Sxx = Sxx + reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx)); Syy = Syy + reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = b.inv_sqrt(Sxx), b.inv_sqrt(Syy)
    s = np.linalg.svd(Wx @ Sxy @ Wy, compute_uv=False)
    null = [np.linalg.svd(Wx @ (sum(m['null'][r] for m in msgs) / n - np.outer(mx, my)) @ Wy, compute_uv=False)[0]
            for r in range(b.NPERM)]
    thr = float(np.percentile(null, 99))
    return s, thr, int((s > thr).sum())


def fed_K(X3, Y3, K, rng):
    ns, npos, d = X3.shape
    groups = np.array_split(np.arange(ns), K)
    msgs = []
    for g in groups:
        k = len(g)
        perms = [derangement(k, rng) for _ in range(b.NPERM)]
        Xn = X3[g].reshape(k * npos, d); Yn3 = Y3[g]
        null_pairs = [(p[:, None] * npos + np.arange(npos)[None, :]).ravel() for p in perms]  # чужая последовательность, та же позиция
        msgs.append(node_message(Xn, Yn3.reshape(k * npos, d), null_pairs))
    return center(msgs)


def life_1(X3, Y3, rng):
    ns, npos, d = X3.shape
    msgs = []
    for i in range(ns):
        perms = [derangement(npos, rng) for _ in range(b.NPERM)]  # своё будущее из другой позиции своей же записи
        msgs.append(node_message(X3[i], Y3[i], perms))
    return center(msgs)


rows = []
for sy in TRUTH:
    for seed in SEEDS:
        res = {}
        for L in (16, 64):
            X3, Y3, rng_full = windows(sy, L, 64, 400, 0.01, seed)
            s_full, thr_full, N_full = b.spectrum(X3, Y3, rng_full)
            rng = np.random.default_rng(10_000 + seed)
            arms = {'FULL': (s_full, thr_full, N_full)}
            for K in KS:
                arms[f'FED-{K}'] = fed_K(X3, Y3, K, rng)
            arms['LIFE-1'] = life_1(X3, Y3, rng)
            for a, (s, thr, N) in arms.items():
                res.setdefault(a, {})[L] = dict(N=N, thr=thr, dev=float(np.abs(s - s_full).max()))
        row = dict(system=sy, seed=seed)
        for a, v in res.items():
            row[a] = dict(N16=v[16]['N'], N64=v[64]['N'], thr16=round(v[16]['thr'], 4), thr64=round(v[64]['thr'], 4),
                          dev=max(v[16]['dev'], v[64]['dev']), verdict=b.classify(v[16]['N'], v[64]['N'] - v[16]['N']))
        rows.append(row)
        print(sy, seed, {a: (row[a]['verdict'], row[a]['N16'], row[a]['N64']) for a in res}, flush=True)

arms = ['FULL'] + [f'FED-{K}' for K in KS] + ['LIFE-1']
agree = {a: sum(r[a]['verdict'] == r['FULL']['verdict'] for r in rows) for a in arms}
correct = {a: sum(r[a]['verdict'] == TRUTH[r['system']] for r in rows) for a in arms}
P0 = max(r[a]['dev'] for r in rows for a in arms)
by_sys = {a: {sy: sum(r[a]['verdict'] == TRUTH[sy] for r in rows if r['system'] == sy) for sy in TRUTH} for a in arms}
life_verdicts = {sy: [r['LIFE-1']['verdict'] for r in rows if r['system'] == sy] for sy in TRUTH}
P1 = {K: ('✓' if agree[f'FED-{K}'] >= 45 else ('провал' if agree[f'FED-{K}'] < 38 else 'разницы нет')) for K in KS}
P2 = 'подтверждено (одной жизни мало)' if agree['LIFE-1'] < 38 else ('убито (одной жизни хватает)' if agree['LIFE-1'] >= 45 else 'разницы нет')
thr_med = {a: float(np.median([r[a]['thr64'] for r in rows])) for a in arms}
out = dict(P0_max_dev=P0, P0_passed=P0 < 1e-8, agree_with_FULL=agree, correct_vs_truth=correct, correct_by_system=by_sys,
           P1=P1, P2=P2, LIFE1_verdicts=life_verdicts, median_thr64=thr_med, rows=rows)
json.dump(out, open('fed01_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, ensure_ascii=False, indent=1))
