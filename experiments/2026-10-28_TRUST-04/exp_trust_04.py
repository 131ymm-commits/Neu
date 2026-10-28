#!/usr/bin/env python3
"""TRUST-04 — что создаёт остаток пути многоуровневого отбора до дальновидного доверия к источнику с интересом
(повод — внешний разбор TRUST-03, docs/reviews/2026-10-28_TRUST-03_external.txt).

Блок А (мир TRUST-03: r_G = 0,85, B_MAX = 0,6): одна генетическая архитектура — 40 групп × 10 особей, гены w0 и w_G у
каждой особи, мутация N(0; σ) на ген особи; независимо меняются три фактора:
  S — отбор групп (есть / нет);
  E — с каким весом особь действует: своим геном w_G (own) или средним геном группы (pool);
  L — наследование w0 и w_G: от одной особи-родителя (link) или от двух независимо выбранных ∝ F (free).
Плюс общий ген группы (COUNCIL) с шагом мутации σ и σ/√10 и одна популяция 1 × 400 (MYOPIC).
Блок Б (переносимость): те же DEMES (own, link) и POOLED (pool, link) — в мирах r_G 0,75 и 0,95, B_MAX 0,3 и 0,9
(и MYOPIC в каждом), при независимом риске (свои эпизоды у групп) и при миграции 10 % особей за поколение.
Мир, агент, выплата и оценка — как в TRUST-03 (`../2026-10-28_TRUST-03/exp_trust_03.py`): класс World и log_true —
из TRUST-02 и TRUST-01; источник G (индекс 3) врёт в пользу W = 1 с долей b = B_MAX · clip(w̄_G / logit r_G, 0, 1),
где w̄_G — средний ген веса на нём в группе. Агент сокращён: честные веса — точные веса честного мира того же r_G.

Запуск: python3 exp_trust_04.py [--check | --pilot | --dry] [--part A|B]. PREREG: PREREG-TRUST-04.md.
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize, minimize_scalar

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_TRUST-02'))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_TRUST-01'))
import exp_trust_01 as T1  # noqa: E402
import exp_trust_02 as T2  # noqa: E402

PI, R_BASE, COPIES, G_IDX = 0.3, [0.55, 0.65, 0.75, 0.85, 0.92], [(2, 0.8)], 3   # мир G TRUST-02 (T2.WG)
J = 1 + G_IDX                                     # индекс веса источника G в векторе из 7
L_EP, G, SIG, WINDOW = 40, 3000, 0.04, 2000
SEEDS = list(range(600, 610))
PILOT_SEEDS = list(range(1100, 1110))
DRY_SEEDS = [1150, 1151]
lg = lambda p: float(np.log(p / (1 - p)))


class WorldSpec:
    """Мир G с надёжностью источника с интересом r_G и наибольшей долей лжи b_max; теория для сокращённого агента."""

    def __init__(self, rG=0.85, b_max=0.6):
        self.rG, self.b_max = float(rG), float(b_max)
        r = list(R_BASE); r[G_IDX] = self.rG
        self.WA = T2.World(PI, r, COPIES)                         # честный мир (b = 0)
        self.WG = T2.World(PI, r, COPIES, adaptive=(G_IDX, 0.0))  # мир с источником с интересом; with_b(b)
        self.w_ref = lg(self.rG)
        self.W_EX = self.WA.exact_weights()                       # честные веса не зависят от b (проверка в theory)
        self._theory = None

    def b_of(self, w):
        return self.b_max * min(max(w / self.w_ref, 0.0), 1.0)

    def full_w(self, w0, wg):
        w = self.W_EX.copy(); w[0] = w0; w[J] = wg
        return w

    def fixed_point(self):
        """b* = b_of(w_G(b*)), w_G(b) — точный байесовский вес при доле лжи b (бисекция, как T2.fixed_point)."""
        f = lambda b: b - self.b_of(self.WG.with_b(b).exact_weights()[J])
        lo, hi = 0.0, self.b_max
        assert f(lo) < 0 < f(hi)
        for _ in range(80):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
        return (lo + hi) / 2

    def best_w0(self, wg):
        b = self.b_of(wg); world = self.WG.with_b(b)
        r = minimize_scalar(lambda w0: world.exact_metrics(self.full_w(w0, wg))['logloss'], bounds=(-4, 2),
                            method='bounded', options=dict(xatol=1e-8))
        return r.fun, r.x, b

    def theory(self):
        if self._theory is None:
            bs = self.fixed_point(); ws = self.WG.with_b(bs); wst = ws.exact_weights(); ms = ws.exact_metrics(wst)
            assert np.allclose(np.delete(wst, [0, J]), np.delete(self.W_EX, [0, J]), atol=1e-12), 'честные веса зависят от b?'
            o = minimize_scalar(lambda x: self.best_w0(x)[0], bounds=(-0.5, self.w_ref + 1.0), method='bounded',
                                options=dict(xatol=1e-7))
            ll_f, w0_f, b_f = self.best_w0(o.x)
            mf = self.WG.with_b(b_f).exact_metrics(self.full_w(w0_f, o.x))
            self._theory = dict(
                rG=self.rG, b_max=self.b_max, w_ref=self.w_ref,
                myopic=dict(wG=float(wst[J]), w0=float(wst[0]), b=float(bs), logloss=ms['logloss'], acc=ms['acc'], self_dec=ms['self_dec']),
                farsighted=dict(wG=float(o.x), w0=float(w0_f), b=float(b_f), logloss=float(ll_f), acc=mf['acc'], self_dec=mf['self_dec']),
                best_response_at_farsighted_b=float(self.WG.with_b(b_f).exact_weights()[J]))
        return self._theory

    def episodes_common(self, rng, L):
        X, W = self.WA.episodes(rng, L)
        u = rng.random(L)
        okG = X[:, J] == 2 * W - 1
        return X, W, okG, u

    def episodes_groups(self, rng, m, L):
        X, W = self.WA.episodes(rng, m * L)
        X = X.reshape(m, L, X.shape[1]); W = W.reshape(m, L)
        u = rng.random((m, L))
        okG = X[..., J] == 2 * W - 1
        return X, W, okG, u


WORLDS = {'base': WorldSpec(), 'r075': WorldSpec(rG=0.75), 'r095': WorldSpec(rG=0.95),
          'b03': WorldSpec(b_max=0.3), 'b09': WorldSpec(b_max=0.9)}

_D = dict(world='base', m=40, n=10, council=False, group_sel=True, expr='own', link='link', common_eps=True, migr=0.0,
          sig_g=SIG, part='A')
_ARMS = [
    # блок А — мир base
    ('MYOPIC', dict(m=1, n=400, group_sel=False)),
    ('DEMES', dict()),
    ('DEMES_FREE', dict(link='free')),
    ('POOLED', dict(expr='pool')),
    ('POOLED_FREE', dict(expr='pool', link='free')),
    ('DEMES_NOSEL', dict(group_sel=False)),
    ('DEMES_NOSEL_FREE', dict(group_sel=False, link='free')),
    ('POOLED_NOSEL', dict(group_sel=False, expr='pool')),
    ('POOLED_NOSEL_FREE', dict(group_sel=False, expr='pool', link='free')),
    ('COUNCIL', dict(council=True, expr='pool')),
    ('COUNCIL_SIGN', dict(council=True, expr='pool', sig_g=SIG / np.sqrt(10))),
    # блок Б — переносимость
    ('MYOPIC_r075', dict(world='r075', m=1, n=400, group_sel=False, part='B')),
    ('DEMES_r075', dict(world='r075', part='B')),
    ('POOLED_r075', dict(world='r075', expr='pool', part='B')),
    ('MYOPIC_r095', dict(world='r095', m=1, n=400, group_sel=False, part='B')),
    ('DEMES_r095', dict(world='r095', part='B')),
    ('POOLED_r095', dict(world='r095', expr='pool', part='B')),
    ('MYOPIC_b03', dict(world='b03', m=1, n=400, group_sel=False, part='B')),
    ('DEMES_b03', dict(world='b03', part='B')),
    ('POOLED_b03', dict(world='b03', expr='pool', part='B')),
    ('MYOPIC_b09', dict(world='b09', m=1, n=400, group_sel=False, part='B')),
    ('DEMES_b09', dict(world='b09', part='B')),
    ('POOLED_b09', dict(world='b09', expr='pool', part='B')),
    ('DEMES_IND', dict(common_eps=False, part='B')),
    ('POOLED_IND', dict(expr='pool', common_eps=False, part='B')),
    ('DEMES_MIG', dict(migr=0.1, part='B')),
    ('POOLED_MIG', dict(expr='pool', migr=0.1, part='B')),
]
ARMS = {name: {**_D, **v, 'stream': i} for i, (name, v) in enumerate(_ARMS)}
for _a, _s in ARMS.items():
    assert not (_s['council'] and (_s['link'] == 'free' or _s['migr'] > 0)), _a
    assert _s['expr'] in ('own', 'pool') and _s['link'] in ('link', 'free'), _a


def evolve4(seed, arm, gens=G, track_every=10):
    sp = ARMS[arm]; wd = WORLDS[sp['world']]; m, n = sp['m'], sp['n']
    council, gsel, pooled, free = sp['council'], sp['group_sel'], sp['expr'] == 'pool', sp['link'] == 'free'
    common, migr, sig_g = sp['common_eps'], sp['migr'], sp['sig_g']
    rng = np.random.default_rng(seed * 100 + sp['stream'])
    w0 = rng.normal(0, 0.01, (m, n))
    wg = rng.normal(0, 0.01, (m, 1) if council else (m, n))
    traj, price = [], []
    zc_idx = [i for i in range(7) if i not in (0, J)]
    W_EX = wd.W_EX
    for g in range(gens):
        wgm = wg.mean(1)
        b = np.array([wd.b_of(x) for x in wgm])
        if common:
            X, W, okG, u = wd.episodes_common(rng, L_EP)
            zc = X[:, zc_idx] @ W_EX[zc_idx]
            lie = (W[None, :] == 0) & okG[None, :] & (u[None, :] < b[:, None])
            xg = np.where(lie, 1.0, X[None, :, J])
            Wm = np.broadcast_to(W[None, :], (m, L_EP)); zcm = np.broadcast_to(zc[None, :], (m, L_EP))
        else:
            X, W, okG, u = wd.episodes_groups(rng, m, L_EP)
            zcm = X[..., zc_idx] @ W_EX[zc_idx]
            lie = (W == 0) & okG & (u < b[:, None])
            xg = np.where(lie, 1.0, X[..., J]); Wm = W
        wgi = np.broadcast_to(wg, (m, n))
        wex = np.broadcast_to(wg.mean(1, keepdims=True), (m, n)) if pooled else wgi    # вес, с которым особь действует
        Z = w0[:, :, None] + zcm[:, None, :] + wex[:, :, None] * xg[:, None, :]
        logF = T1.log_true(Z, Wm[:, None, :]).sum(2)
        if gsel and m > 1:
            lgF = np.logaddexp.reduce(logF, axis=1) - np.log(n)
            pg = np.exp(lgF - lgF.max()); pg /= pg.sum()
            parent = rng.choice(m, size=m, p=pg)
        else:
            pg = np.full(m, 1.0 / m); parent = np.arange(m)
        # Прайс (описательно): ожидаемый сдвиг среднего гена w_G от отбора до мутации; у free ожидание то же (передача ∝ F)
        zbar = wgi.mean(1)
        prw = np.exp(logF - logF.max(1, keepdims=True)); prw /= prw.sum(1, keepdims=True)
        s_between = float(pg @ zbar - zbar.mean())
        s_within = float(pg @ ((prw * wgi).sum(1) - zbar)) if not council else 0.0
        if g >= gens - WINDOW:
            price.append((s_between, s_within))
        new_w0 = np.empty_like(w0); new_wg = np.empty_like(wg)
        for k in range(m):
            p = parent[k]
            pr = np.exp(logF[p] - logF[p].max()); pr /= pr.sum()
            idx = rng.choice(n, size=n, p=pr)
            new_w0[k] = w0[p, idx] + rng.normal(0, SIG, n)
            if council:
                new_wg[k] = wg[p] + rng.normal(0, sig_g, 1)
            else:
                idg = rng.choice(n, size=n, p=pr) if free else idx     # раздельное наследование — свой родитель ∝ F
                new_wg[k] = wg[p, idg] + rng.normal(0, SIG, n)
        if migr > 0:                                       # миграция: K особей (пары генов) переставляются по группам
            K = int(round(migr * m * n)); pos = rng.choice(m * n, size=K, replace=False); perm = rng.permutation(K)
            f0, fg = new_w0.reshape(-1), new_wg.reshape(-1)
            before = np.sort(f0[pos] + 1j * fg[pos])
            f0[pos] = f0[pos][perm]; fg[pos] = fg[pos][perm]
            assert np.array_equal(before, np.sort(f0[pos] + 1j * fg[pos])), 'миграция должна переставлять пары генов'
        w0, wg = new_w0, new_wg
        if g % track_every == 0 or g == gens - 1:
            wgm = wg.mean(1); w0m = w0.mean(1)
            bs = np.array([wd.b_of(x) for x in wgm])
            ms = [wd.WG.with_b(bs[k]).exact_metrics(wd.full_w(w0m[k], wgm[k])) for k in range(m)]
            traj.append(dict(g=g, wG=float(wgm.mean()), wG_sd_groups=float(wgm.std()), w0=float(w0m.mean()), b=float(bs.mean()),
                             logloss=float(np.mean([x['logloss'] for x in ms])), self_dec=float(np.mean([x['self_dec'] for x in ms])),
                             acc=float(np.mean([x['acc'] for x in ms])), ece=float(np.mean([x['ece'] for x in ms])),
                             s_between=s_between, s_within=s_within))
    last = [t for t in traj if t['g'] >= gens - WINDOW]
    fin = {k: float(np.mean([t[k] for t in last])) for k in ('wG', 'wG_sd_groups', 'w0', 'b', 'logloss', 'self_dec', 'acc', 'ece')}
    pb = np.array(price)
    fin.update(price_between=float(pb[:, 0].mean()), price_within=float(pb[:, 1].mean()))
    return dict(seed=seed, arm=arm, final=fin, n_snap=len(last), n_price=len(price), traj=traj)


def check():
    """Мир base совпадает с T2.WG; теория base — с TRUST-03; в каждом мире: неподвижная точка, численный лучший ответ
    при b* = формула, частота лжи в общих эпизодах, общие эпизоды = эпизоды честного мира."""
    base = WORLDS['base']
    assert np.allclose(base.WG.with_b(T2.B_STAR).exact_weights(), T2.WG.with_b(T2.B_STAR).exact_weights(), atol=1e-12)
    assert abs(base.fixed_point() - T2.B_STAR) < 1e-9
    th = base.theory()
    assert abs(th['myopic']['wG'] - 0.9873) < 1e-4 and abs(th['farsighted']['wG'] - 0.6891) < 1e-4, th
    for name, wd in WORLDS.items():
        t = wd.theory(); bs = t['myopic']['b']; ws = wd.WG.with_b(bs)
        r = minimize(lambda v: ws.exact_metrics(wd.full_w(v[0], v[1]))['logloss'], x0=[t['myopic']['w0'] + 0.2, t['myopic']['wG'] - 0.2],
                     method='Nelder-Mead', options=dict(xatol=1e-9, fatol=1e-13, maxiter=4000))
        assert abs(r.x[0] - t['myopic']['w0']) < 1e-4 and abs(r.x[1] - t['myopic']['wG']) < 1e-4, (name, r.x, t['myopic'])
        assert abs(wd.b_of(r.x[1]) - bs) < 1e-4
        assert t['farsighted']['logloss'] < t['myopic']['logloss'] and t['farsighted']['wG'] < t['myopic']['wG'], name
        X1, W1 = wd.WA.episodes(np.random.default_rng(5), 1000); X2, W2, _, _ = wd.episodes_common(np.random.default_rng(5), 1000)
        assert np.array_equal(X1, X2) and np.array_equal(W1, W2)
        X, W, okG, u = wd.episodes_common(np.random.default_rng(9), 400_000)
        bb = 0.5 * wd.b_max; xg = np.where((W == 0) & okG & (u < bb), 1.0, X[:, J])
        emp = float((xg[W == 0] == 1).mean()); want = (1 - wd.rG) + wd.rG * bb
        assert abs(emp - want) < 0.004, (name, emp, want)
        print(f"{name:5s} r_G {wd.rG} b_max {wd.b_max}: близорукая {t['myopic']['wG']:.4f} (b {bs:.4f}), дальновидная "
              f"{t['farsighted']['wG']:.4f} (b {t['farsighted']['b']:.4f}); разрыв {t['myopic']['wG'] - t['farsighted']['wG']:.4f}; "
              f"лог-потеря {t['myopic']['logloss']:.4f} → {t['farsighted']['logloss']:.4f}; численный ответ {np.round(r.x, 6)}; ложь {emp:.4f}/{want:.4f}")


def run(seeds, outdir, part=None, gens=G):
    t0 = time.time(); arms = [a for a, s in ARMS.items() if part is None or s['part'] == part]
    th = {k: w.theory() for k, w in WORLDS.items()}
    runs = [evolve4(s, a, gens=gens) for s in seeds for a in arms]
    name = 'results_trust_04.json' if part is None else f'results_trust_04_{part}.json'
    json.dump(dict(theory=th, runs=runs, params=dict(L_EP=L_EP, G=gens, SIG=SIG, WINDOW=WINDOW, ARMS=ARMS, SEEDS=seeds,
                                                       part=part), seconds=time.time() - t0),
              open(os.path.join(outdir, name), 'w'), default=float)
    return th, runs, time.time() - t0


if __name__ == '__main__':
    if '--check' in sys.argv:
        check(); sys.exit(0)
    part = sys.argv[sys.argv.index('--part') + 1] if '--part' in sys.argv else None
    if '--pilot' in sys.argv:
        out, seeds = os.path.join(HERE, 'pilot'), PILOT_SEEDS
    elif '--dry' in sys.argv:
        out, seeds = os.path.join(HERE, 'dry'), DRY_SEEDS
    else:
        out, seeds = HERE, SEEDS
    os.makedirs(out, exist_ok=True)
    th, runs, sec = run(seeds, out, part=part)
    print(f'готово за {sec:.0f} с (часть {part or "все"}); анализ — analyze_trust_04.py')
