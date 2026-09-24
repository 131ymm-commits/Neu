# BOUND-01: порядок / край / хаос на эталонах Основания одной процедурой ПСУ-2 (мировая цель). См. PREREG-BOUND-01.md
import json, sys
import numpy as np

R_INF = 3.569945671870944
NPOS, STRIDE, NPERM = 16, 8, 50


def gen(system, nseq, T, rng):
    if system == 'S1':
        t = np.arange(T)[None, :]
        w, a = [0.21, 0.21 * np.sqrt(2), 0.21 * np.sqrt(5)], [1.0, 0.7, 0.5]
        return sum(ai * np.sin(wi * t + rng.uniform(0, 2 * np.pi, (nseq, 1))) for wi, ai in zip(w, a))
    if system in ('S2', 'S3', 'S4'):
        r = {'S2': 3.5, 'S3': R_INF, 'S4': 4.0}[system]
        x = rng.uniform(0.2, 0.8, nseq)
        for _ in range(65536):
            x = r * x * (1 - x)
        out = np.empty((nseq, T))
        for i in range(T):
            out[:, i] = x
            x = r * x * (1 - x)
        return out
    if system == 'S5':
        s, rho, b, dt = 10.0, 28.0, 8.0 / 3.0, 0.01
        f = lambda v: np.stack([s * (v[1] - v[0]), v[0] * (rho - v[2]) - v[1], v[0] * v[1] - b * v[2]])
        v = np.stack([rng.normal(0, 5, nseq), rng.normal(0, 5, nseq), rng.uniform(10, 40, nseq)])

        def rk4(v):
            k1 = f(v); k2 = f(v + dt / 2 * k1); k3 = f(v + dt / 2 * k2); k4 = f(v + dt * k3)
            return v + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        for _ in range(2000):
            v = rk4(v)
        out = np.empty((nseq, T))
        for i in range(T):
            out[:, i] = v[0]
            for _ in range(10):
                v = rk4(v)
        return out
    raise ValueError(system)


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def spectrum(X3, Y3, rng, reg=1e-10):
    ns, npos, _ = X3.shape
    X = X3.reshape(ns * npos, -1); Y = Y3.reshape(ns * npos, -1)
    X = X - X.mean(0); Y = Y - Y.mean(0); n = len(X)
    Sxx, Syy = X.T @ X / n, Y.T @ Y / n
    Sxx += reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx)); Syy += reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx, Wy = inv_sqrt(Sxx), inv_sqrt(Syy)
    s = np.linalg.svd(Wx @ (X.T @ Y / n) @ Wy, compute_uv=False)
    Yc3 = Y.reshape(ns, npos, -1)
    null = [np.linalg.svd(Wx @ (X.T @ Yc3[rng.permutation(ns)].reshape(n, -1) / n) @ Wy, compute_uv=False)[0]
            for _ in range(NPERM)]
    thr = float(np.percentile(null, 99))
    return s, thr, int((s > thr).sum())


def run(system, L, tau, nseq, noise, seed=0):
    rng = np.random.default_rng(seed)
    T = (L - 1 + STRIDE * (NPOS - 1)) + tau + L + 1
    x = gen(system, nseq, T, rng)
    x = (x - x.mean()) / x.std()
    x = x + noise * rng.normal(size=x.shape)
    ends = L - 1 + STRIDE * np.arange(NPOS)
    X3 = np.stack([x[:, e - L + 1:e + 1] for e in ends], 1)
    Y3 = np.stack([x[:, e + tau:e + tau + L] for e in ends], 1)
    s, thr, N = spectrum(X3, Y3, rng)
    return dict(system=system, L=L, tau=tau, nseq=nseq, noise=noise, N=N, thr=thr, rho=np.round(s[:12], 4).tolist())


def classify(N_long, G):
    if N_long == 0:
        return 'хаос'
    return 'порядок' if G <= 1 else 'край'


if __name__ == '__main__':
    res = {'main': [], 'B2': [], 'B3': [], 'short': []}
    truth = {'S1': 'порядок', 'S2': 'порядок', 'S3': 'край', 'S4': 'хаос', 'S5': 'хаос'}
    verdict = {}
    for noise, key in ((0.01, 'main'), (0.1, 'B3')):
        for sy in ('S1', 'S2', 'S3', 'S4', 'S5'):
            a = run(sy, 16, 64, 400, noise); b = run(sy, 64, 64, 400, noise)
            res[key] += [a, b]
            G = b['N'] - a['N']
            c = classify(a['N'], G)
            verdict[(key, sy)] = c
            print(key, sy, 'N_long(L16)=', a['N'], 'N(L64)=', b['N'], 'G=', G, '->', c, '| истина:', truth[sy],
                  '| thr %.3f/%.3f' % (a['thr'], b['thr']), 'rho16', a['rho'][:8], flush=True)
    for sy in ('S1', 'S2', 'S3', 'S4', 'S5'):
        c = run(sy, 16, 1, 400, 0.01); res['short'].append(c)
        print('short tau=1', sy, 'N=', c['N'], 'thr %.3f' % c['thr'], c['rho'][:8], flush=True)
    for sy in ('S1', 'S2', 'S3'):
        for ns in (100, 1600):
            c = run(sy, 64, 64, ns, 0.01); res['B2'].append(c)
            print('B2', sy, 'nseq', ns, 'N=', c['N'], 'thr %.3f' % c['thr'], flush=True)
    B1 = all(verdict[('main', sy)] == truth[sy] for sy in truth)
    kill = verdict[('main', 'S3')] != 'край' or verdict[('main', 'S1')] == 'край'
    b2 = {(r['system'], r['nseq']): r['N'] for r in res['B2']}
    B2 = b2[('S3', 1600)] > b2[('S3', 100)] and b2[('S1', 1600)] == b2[('S1', 100)] and b2[('S2', 1600)] == b2[('S2', 100)]
    B3 = all(verdict[('B3', sy)] == truth[sy] for sy in truth)
    out = dict(B1=B1, B2=B2, B3=B3, KILL=kill, verdict={f'{k[0]}_{k[1]}': v for k, v in verdict.items()}, res=res)
    print('B1', B1, 'B2', B2, 'B3', B3, 'KILL', kill)
    json.dump(out, open('bound01_results.json', 'w'), ensure_ascii=False, indent=1)
