#!/usr/bin/env python3
"""TRUST-03 — может ли группа или «совет» прийти к дальновидному доверию к источнику с интересом, к которому не
приходит отбор отдельных оценщиков (TRUST-02, пост-хок 4: близорукая точка w_G 0,9873 против дальновидной около 0,69).

Мир — G из TRUST-02 (`../2026-10-28_TRUST-02/exp_trust_02.py`): источник 0,85 врёт в пользу W = 1 с долей
b = 0,6 · clip(w̄_G / W_REF, 0, 1), где w̄_G — средний вес на нём В ЕГО ГРУППЕ (у каждой группы свой такой источник).
Агент сокращён: веса честных источников закреплены на точных значениях (они от b не зависят); эволюционируют только w0
и вес на источнике G. Выплата — Райт–Фишер ∝ F = Π P(истины) на 40 общих для группы эпизодах (как KELLY).
Эпизоды — общие для всех групп поколения (общие случайные числа): одни и те же W, сигналы честных источников и
равномерные u для лжи; группы различаются только весами и долей лжи своего источника.

Руки (m групп × n особей, всего 400):
  MYOPIC        — 1 группа × 400, вес на G — ген особи (как KELLY_G TRUST-02, но агент сокращён);
  DEMES_NOSEL   — 40 × 10, вес — ген особи, групп не отбирают (контроль: структура групп сама по себе);
  DEMES         — 40 × 10, вес — ген особи, многоуровневый отбор: группы размножаются ∝ средней F группы;
  COUNCIL       — 40 × 10, вес на G — общий ген группы («совет» обязуется за всех), отбор групп как в DEMES;
  COUNCIL_NOSEL — 40 × 10, общий ген группы, групп не отбирают (контроль: обязательство без отбора);
  DEMES_10x40, COUNCIL_10x40 — то же при 10 группах по 40 (доза n/m: 4 против 0,25).
Оценка — точным перебором 64 узоров для среднего генотипа каждой группы в её мире (своё b), среднее по группам.

Запуск: python3 exp_trust_03.py [--check | --pilot | --dry]. PREREG: PREREG-TRUST-03.md.
"""
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize_scalar

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_TRUST-02'))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_TRUST-01'))
import exp_trust_01 as T1  # noqa: E402
import exp_trust_02 as T2  # noqa: E402

WG, WA, J = T2.WG, T2.WA, 1 + T2.G_IDX         # J = 4: индекс веса источника G в векторе из 7
W_EX = WA.exact_weights()                        # точные веса честного мира A (честные источники от b не зависят)
N_TOT, L_EP, G, SIG, WINDOW = 400, 40, 1500, 0.04, 300
SEEDS = list(range(500, 510))
PILOT_SEEDS = [970, 971, 972]
DRY_SEEDS = [960, 961]
ARMS = {'MYOPIC': dict(m=1, n=400, council=False, group_sel=False, stream=0),
        'DEMES_NOSEL': dict(m=40, n=10, council=False, group_sel=False, stream=1),
        'DEMES': dict(m=40, n=10, council=False, group_sel=True, stream=2),
        'COUNCIL': dict(m=40, n=10, council=True, group_sel=True, stream=3),
        'COUNCIL_NOSEL': dict(m=40, n=10, council=True, group_sel=False, stream=4),
        # доза n/m (после пилота ручки): мало больших групп, n/m = 4 против 0,25
        'DEMES_10x40': dict(m=10, n=40, council=False, group_sel=True, stream=5),
        'COUNCIL_10x40': dict(m=10, n=40, council=True, group_sel=True, stream=6)}


def full_w(w0, wg):
    """Вектор из 7 весов: w0 и w_G свои, честные — точные."""
    w = W_EX.copy(); w[0] = w0; w[J] = wg
    return w


def best_w0(wg):
    """Лучший w0 при весе wg в мире, который этот вес создаёт (b = b_of(wg)); → (лог-потеря, w0, b)."""
    b = T2.b_of(wg); world = WG.with_b(b)
    r = minimize_scalar(lambda w0: world.exact_metrics(full_w(w0, wg))['logloss'], bounds=(-4, 2), method='bounded',
                        options=dict(xatol=1e-8))
    return r.fun, r.x, b


def theory():
    """Близорукая неподвижная точка (байесовский ответ на свою же ложь) и дальновидный оптимум для сокращённого агента."""
    o = minimize_scalar(lambda x: best_w0(x)[0], bounds=(0.2, 1.6), method='bounded', options=dict(xatol=1e-7))
    ll_f, w0_f, b_f = best_w0(o.x)
    mf = WG.with_b(b_f).exact_metrics(full_w(w0_f, o.x))
    ws = WG.with_b(T2.B_STAR); wst = ws.exact_weights()
    ms = ws.exact_metrics(wst)
    assert np.allclose(np.delete(wst, [0, J]), np.delete(W_EX, [0, J]), atol=1e-12), 'честные веса зависят от b?'
    br = WG.with_b(b_f).exact_weights()[J]                 # лучший ответ особи при b дальновидной точки
    return dict(myopic=dict(wG=float(wst[J]), w0=float(wst[0]), b=float(T2.B_STAR), logloss=ms['logloss'], acc=ms['acc'],
                            self_dec=ms['self_dec']),
                farsighted=dict(wG=float(o.x), w0=float(w0_f), b=float(b_f), logloss=float(ll_f), acc=mf['acc'],
                                self_dec=mf['self_dec']),
                best_response_at_farsighted_b=float(br), w_ref=T2.W_REF, b_max=T2.B_MAX)


def episodes_common(rng, L):
    """Общие для всех групп эпизоды поколения: W, честные сигналы x (L × 6, столбец G — честный ответ), okG и u для лжи."""
    X, W = WA.episodes(rng, L)                           # мир A: источник G честен (b = 0)
    u = rng.random(L)                                    # общие равномерные для решения «врать»
    s = 2 * W - 1
    okG = X[:, J] == s                                   # честный ответ источника G верен
    return X, W, okG, u


def evolve3(seed, arm, gens=G, track_every=10):
    spec = ARMS[arm]; m, n = spec['m'], spec['n']; council, gsel = spec['council'], spec['group_sel']
    rng = np.random.default_rng(seed * 100 + spec['stream'])
    w0 = rng.normal(0, 0.01, (m, n))                    # ген w0 у каждой особи
    wg = rng.normal(0, 0.01, (m, 1) if council else (m, n))   # вес на G: ген группы (совет) или ген особи
    traj, price = [], []
    zc_idx = [i for i in range(7) if i not in (0, J)]
    for g in range(gens):
        wgm = wg.mean(1)                                  # средний вес на G в каждой группе (у совета — сам ген)
        b = np.array([T2.b_of(x) for x in wgm])           # доля лжи источника каждой группы
        X, W, okG, u = episodes_common(rng, L_EP)
        zc = X[:, zc_idx] @ W_EX[zc_idx]                  # вклад честных источников (общий)
        lie = (W[None, :] == 0) & okG[None, :] & (u[None, :] < b[:, None])     # m × L: где источник группы врёт
        xg = np.where(lie, 1.0, X[None, :, J])            # m × L: сигнал источника G в каждой группе
        wgi = np.broadcast_to(wg, (m, n))                 # вес на G у каждой особи
        Z = w0[:, :, None] + zc[None, None, :] + wgi[:, :, None] * xg[:, None, :]   # m × n × L
        logF = T1.log_true(Z, W[None, None, :]).sum(2)    # m × n
        # отбор групп: родитель новой группы ∝ средней F группы (Райт–Фишер на уровне групп)
        if gsel and m > 1:
            lg = np.logaddexp.reduce(logF, axis=1) - np.log(n)
            pg = np.exp(lg - lg.max()); pg /= pg.sum()
            parent = rng.choice(m, size=m, p=pg)
        else:
            pg = np.full(m, 1.0 / m)
            parent = np.arange(m)
        # Прайс (после пилота 2; случайных чисел не тратит): ожидаемый сдвиг среднего w_G за поколение до мутации =
        # межгрупповая часть Σ pg·z̄_k − mean z̄_k + внутригрупповая Σ pg·(Σ_i pr_ki·z_ki − z̄_k)
        zbar = wgi.mean(1)
        prw = np.exp(logF - logF.max(1, keepdims=True)); prw /= prw.sum(1, keepdims=True)
        s_between = float(pg @ zbar - zbar.mean())
        s_within = float(pg @ ((prw * wgi).sum(1) - zbar))
        if g >= gens - WINDOW:
            price.append((s_between, s_within))
        # отбор внутри группы: n потомков ∝ F особей родительской группы; мутация
        new_w0 = np.empty_like(w0); new_wg = np.empty_like(wg)
        for k in range(m):
            p = parent[k]
            pr = np.exp(logF[p] - logF[p].max()); pr /= pr.sum()
            idx = rng.choice(n, size=n, p=pr)
            new_w0[k] = w0[p, idx] + rng.normal(0, SIG, n)
            if council:
                new_wg[k] = wg[p] + rng.normal(0, SIG, 1)
            else:
                new_wg[k] = wg[p, idx] + rng.normal(0, SIG, n)
        w0, wg = new_w0, new_wg
        if g % track_every == 0 or g == gens - 1:
            wgm = wg.mean(1); w0m = w0.mean(1)
            bs = np.array([T2.b_of(x) for x in wgm])
            ms = [WG.with_b(bs[k]).exact_metrics(full_w(w0m[k], wgm[k])) for k in range(m)]
            traj.append(dict(g=g, wG=float(wgm.mean()), wG_sd_groups=float(wgm.std()), w0=float(w0m.mean()), b=float(bs.mean()),
                             logloss=float(np.mean([x['logloss'] for x in ms])), self_dec=float(np.mean([x['self_dec'] for x in ms])),
                             acc=float(np.mean([x['acc'] for x in ms])), ece=float(np.mean([x['ece'] for x in ms])),
                             s_between=s_between, s_within=s_within))
    last = [t for t in traj if t['g'] >= gens - WINDOW]
    fin = {k: float(np.mean([t[k] for t in last])) for k in ('wG', 'wG_sd_groups', 'w0', 'b', 'logloss', 'self_dec', 'acc', 'ece')}
    pb = np.array(price)                                   # все поколения окна, не только снимки
    fin.update(price_between=float(pb[:, 0].mean()), price_within=float(pb[:, 1].mean()))
    return dict(seed=seed, arm=arm, final=fin, n_snap=len(last), n_price=len(price), traj=traj)


def check():
    """MYOPIC с полным агентом недоступен; проверяем: общие эпизоды совпадают с миром A, ложь даёт нужную частоту,
    точная теория согласуется с TRUST-02 (близорукая точка), сокращённый агент воспроизводит её как лучший ответ."""
    X1, W1 = WA.episodes(np.random.default_rng(5), 1000); X2, W2, okG, u = episodes_common(np.random.default_rng(5), 1000)
    assert np.array_equal(X1, X2) and np.array_equal(W1, W2)
    rng = np.random.default_rng(9); X, W, okG, u = episodes_common(rng, 400_000)
    b = 0.34; lie = (W == 0) & okG & (u < b); xg = np.where(lie, 1.0, X[:, J])
    emp = float((xg[W == 0] == 1).mean()); want = 0.15 + 0.85 * b
    assert abs(emp - want) < 0.004, (emp, want)
    th = theory()
    assert abs(th['myopic']['wG'] - 0.9873) < 1e-3 and abs(th['myopic']['b'] - 0.3415) < 1e-3
    # лучший ответ особи на мир при b*: байесовский вес — и это неподвижная точка
    assert abs(WG.with_b(T2.B_STAR).exact_weights()[J] - th['myopic']['wG']) < 1e-9
    print('проверка: общие эпизоды = мир A; частота лжи', round(emp, 4), 'при', round(want, 4), '; теория:',
          {k: {kk: round(vv, 4) for kk, vv in v.items()} if isinstance(v, dict) else round(v, 4) for k, v in th.items()})


def run(seeds, outdir, arms=None, gens=G):
    t0 = time.time(); th = theory(); arms = arms or list(ARMS)
    runs = [evolve3(s, a, gens=gens) for s in seeds for a in arms]
    json.dump(dict(theory=th, runs=runs, params=dict(N_TOT=N_TOT, L_EP=L_EP, G=gens, SIG=SIG, WINDOW=WINDOW, ARMS=ARMS,
                                                       SEEDS=seeds), seconds=time.time() - t0),
              open(os.path.join(outdir, 'results_trust_03.json'), 'w'))
    return th, runs, time.time() - t0


if __name__ == '__main__':
    if '--check' in sys.argv:
        check(); sys.exit(0)
    if '--pilot' in sys.argv:
        th, runs, sec = run(PILOT_SEEDS, os.path.join(HERE, 'pilot')); print(f'пилот: {sec:.0f} с'); sys.exit(0)
    dry = '--dry' in sys.argv
    outdir = os.path.join(HERE, 'dry') if dry else HERE
    os.makedirs(outdir, exist_ok=True)
    th, runs, sec = run(DRY_SEEDS if dry else SEEDS, outdir)
    print(f'готово за {sec:.0f} с; анализ — analyze_trust_03.py')
