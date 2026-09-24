# AUTO-01: анализ строго по PREREG-AUTO-01.md
import json, pickle, glob, os
import numpy as np
from eq01_common import *

rng = np.random.default_rng(999)
XA, _ = sample(2000, rng=rng)
xin = XA[:, :64]
POST, BEL, NLL = forward_filter(xin)
OPT = float(NLL.mean())
POS = np.arange(16, 41)
TR, TE = np.arange(1000), np.arange(1000, 2000)
E6 = np.eye(V)


def inv_sqrt(S):
    w, U = np.linalg.eigh(S)
    return (U / np.sqrt(np.maximum(w, 1e-300))) @ U.T


def cca(X, Y, reg=1e-10):
    n = len(X)
    Sxx, Syy, Sxy = X.T @ X / n, Y.T @ Y / n, X.T @ Y / n
    Sxx = Sxx + reg * np.trace(Sxx) / len(Sxx) * np.eye(len(Sxx))
    Syy = Syy + reg * np.trace(Syy) / len(Syy) * np.eye(len(Syy))
    Wx = inv_sqrt(Sxx)
    U, s, _ = np.linalg.svd(Wx @ Sxy @ inv_sqrt(Syy))
    return s, Wx @ U


def r2(Ftr, Ptr, Fte, Pte):
    A = np.c_[Ftr, np.ones(len(Ftr))]
    Wt, *_ = np.linalg.lstsq(A, Ptr, rcond=None)
    pred = np.c_[Fte, np.ones(len(Fte))] @ Wt
    return float(1 - ((Pte - pred) ** 2).sum() / ((Pte - Pte.mean(0)) ** 2).sum())


fl = lambda A: A.reshape(-1, A.shape[-1])


def metrics(p):
    logp, resid = model_outputs(p, xin)
    nll = float(-np.take_along_axis(logp[:, :63], xin[:, 1:64, None], -1).mean())
    pr = np.exp(logp)
    X = resid[:, POS, :]
    X = X - X[TR].mean(0, keepdims=True)
    ys = sum(np.einsum('npi,npj->npij', E6[xin[:, POS + 16 + j]], pr[:, POS + 16 + j]).reshape(2000, len(POS), 36) for j in range(8)) / 8
    yw = sum(np.einsum('npi,npj->npij', E6[XA[:, POS + 16 + j]], E6[XA[:, POS + 17 + j]]).reshape(2000, len(POS), 36) for j in range(8)) / 8
    ys = ys - ys[TR].mean(0, keepdims=True); yw = yw - yw[TR].mean(0, keepdims=True)
    P = POST[:, POS]
    s_s, A_s = cca(fl(X[TR]), fl(ys[TR]))
    s_w, A_w = cca(fl(X[TR]), fl(yw[TR]))
    Q1, _ = np.linalg.qr(fl(X[TE]) @ A_s[:, :2]); Q2, _ = np.linalg.qr(fl(X[TE]) @ A_w[:, :2])
    cos = np.linalg.svd(Q1.T @ Q2, compute_uv=False)
    ceil = r2(fl(X[TR]), fl(P[TR]), fl(X[TE]), fl(P[TE]))
    psu2 = r2(fl(X[TR]) @ A_s[:, :2], fl(P[TR]), fl(X[TE]) @ A_s[:, :2], fl(P[TE]))
    return dict(excess=nll - OPT, cos_min=float(cos.min()), ceiling=ceil, psu2=psu2,
                rho_self=s_s[:3].tolist(), rho_world=s_w[:3].tolist())


res = {}
for arm in ('A0', 'AW', 'AS', 'AA'):
    for seed in (10, 11, 12):
        d = f'auto/{arm}_s{seed}'
        if not os.path.exists(f'{d}/p_02000.pkl'):
            continue
        traj = []
        for stp in range(0, 2001, 250):
            p = pickle.load(open(f'{d}/p_{stp:05d}.pkl', 'rb'))
            m = metrics(p); m['step'] = stp
            traj.append(m)
        birth = next((t['step'] for t in traj if t['cos_min'] >= 0.95 and t['ceiling'] >= 0.5), None)
        t01 = next((t['step'] for t in traj if t['excess'] < 0.01), None)
        log = json.load(open(f'{d}/log.json'))
        modes = [(l['step'], l['mode']) for l in log if l.get('kind') == 'ctrl']
        res[f'{arm}_{seed}'] = dict(traj=traj, birth=birth, t01=t01, modes=modes)
        print(arm, seed, 'excess@1000=%.5f' % traj[4]['excess'], 'excess@2000=%.5f' % traj[8]['excess'],
              'birth', birth, 't01', t01, 'cos@500/1000 %.3f/%.3f' % (traj[2]['cos_min'], traj[4]['cos_min']),
              'ceil@1000 %.3f' % traj[4]['ceiling'], modes, flush=True)
json.dump(res, open('auto_results.json', 'w'), indent=1)

# ---------- проверка предсказаний ----------
def ex(arm, step_idx):
    return [res[f'{arm}_{s}']['traj'][step_idx]['excess'] for s in (10, 11, 12) if f'{arm}_{s}' in res]


if all(f'{a}_{s}' in res for a in ('A0', 'AW', 'AS', 'AA') for s in (10, 11, 12)):
    out = {}
    m0 = np.mean(ex('A0', 4))
    a1 = {}
    for a in ('AW', 'AS', 'AA'):
        ma = np.mean(ex(a, 4)); wins = sum(x < y for x, y in zip(ex(a, 4), ex('A0', 4)))
        a1[a] = dict(mean=ma, rel=(m0 - ma) / m0, wins=int(wins), ok=bool((m0 - ma) / m0 >= 0.10 and wins >= 2))
    out['A1'] = dict(A0_mean=m0, arms=a1, passed=bool(all(v['ok'] for v in a1.values())))
    maa, maw, mas = np.mean(ex('AA', 4)), np.mean(ex('AW', 4)), np.mean(ex('AS', 4))
    out['A2'] = dict(AA_1000=maa, best_fixed_1000=min(maw, mas), AA_2000=np.mean(ex('AA', 8)), A0_2000=np.mean(ex('A0', 8)),
                     passed=bool(maa <= min(maw, mas) + 0.0005 and np.mean(ex('AA', 8)) <= np.mean(ex('A0', 8)) + 0.0005))
    b = lambda a, s: res[f'{a}_{s}']['birth']
    big = 10 ** 9
    out['A3'] = dict(AS=[b('AS', s) for s in (10, 11, 12)], AW=[b('AW', s) for s in (10, 11, 12)],
                     passed=bool(sum((b('AS', s) or big) >= (b('AW', s) or big) for s in (10, 11, 12)) >= 2))
    out['A4'] = dict(AA=[b('AA', s) for s in (10, 11, 12)], A0=[b('A0', s) for s in (10, 11, 12)],
                     passed=bool(sum((b('AA', s) or big) <= (b('A0', s) or big) - 250 for s in (10, 11, 12)) >= 2))
    out['KILL'] = dict(AA_1000=maa, A0_1000=m0, AA_2000=np.mean(ex('AA', 8)), A0_2000=np.mean(ex('A0', 8)),
                       killed=bool(maa > m0 or np.mean(ex('AA', 8)) > np.mean(ex('A0', 8))))
    for k, v in out.items():
        print(k, v)
    json.dump(out, open('auto_verdict.json', 'w'), indent=1, default=float)
