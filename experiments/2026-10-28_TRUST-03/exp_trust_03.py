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
После проверки по трём линзам: 3000 поколений, окно 2000; руки DEMES_NOWITHIN (вмешательство: вес на G внутри группы
наследуется без отбора), COUNCIL_IND и DEMES_IND (свои эпизоды у каждой группы — независимый риск).
После сухого прогона: DEMES_POOLED (вмешательство на выражении: особь действует со средним весом группы).
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
# после проверки по трём линзам: 3000 поколений, окно 2000 (было 1500 и 300 — ошибка среднего по окну 0,03–0,05)
N_TOT, L_EP, G, SIG, WINDOW = 400, 40, 3000, 0.04, 2000
SEEDS = list(range(500, 510))
PILOT_SEEDS = list(range(970, 980))      # после сухого прогона: 10 зёрен (было 970–977)
DRY_SEEDS = [960, 961]
_BASE = dict(within_sel=True, common_eps=True, pooled=False)
ARMS = {k: {**_BASE, **v} for k, v in {
    'MYOPIC': dict(m=1, n=400, council=False, group_sel=False, stream=0),
    'DEMES_NOSEL': dict(m=40, n=10, council=False, group_sel=False, stream=1),
    'DEMES': dict(m=40, n=10, council=False, group_sel=True, stream=2),
    'COUNCIL': dict(m=40, n=10, council=True, group_sel=True, stream=3),
    'COUNCIL_NOSEL': dict(m=40, n=10, council=True, group_sel=False, stream=4),
    # после пилота ручки: мало больших групп, n/m = 4 против 0,25
    'DEMES_10x40': dict(m=10, n=40, council=False, group_sel=True, stream=5),
    'COUNCIL_10x40': dict(m=10, n=40, council=True, group_sel=True, stream=6),
    # после проверки по трём линзам: вмешательство (вес на G внутри группы наследуется без отбора — родитель
    # равновероятен) и разведка со своими эпизодами у каждой группы (независимый риск)
    'DEMES_NOWITHIN': dict(m=40, n=10, council=False, group_sel=True, stream=7, within_sel=False),
    'COUNCIL_IND': dict(m=40, n=10, council=True, group_sel=True, stream=8, common_eps=False),
    'DEMES_IND': dict(m=40, n=10, council=False, group_sel=True, stream=9, common_eps=False),
    # после сухого прогона: вмешательство на выражении — гены w_G у особей, но каждая особь действует с весом,
    # равным среднему гена в группе (свой ген на свою F не влияет); передача — как в DEMES
    'DEMES_POOLED': dict(m=40, n=10, council=False, group_sel=True, stream=10, pooled=True)}.items()}


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


def episodes_groups(rng, m, L):
    """Свои эпизоды у каждой группы (независимый риск): X (m × L × 7), W, okG, u (m × L)."""
    X, W = WA.episodes(rng, m * L)
    X = X.reshape(m, L, X.shape[1]); W = W.reshape(m, L)
    u = rng.random((m, L))
    okG = X[..., J] == 2 * W - 1
    return X, W, okG, u


def evolve3(seed, arm, gens=G, track_every=10):
    spec = ARMS[arm]; m, n = spec['m'], spec['n']; council, gsel = spec['council'], spec['group_sel']
    wsel, common = spec['within_sel'], spec['common_eps']
    assert not (council and not wsel), 'у общего гена группы нет отбора внутри группы по построению'
    pooled = spec['pooled']
    assert not (pooled and (council or not wsel)), 'выражение по среднему — только для гена особи с обычной передачей'
    rng = np.random.default_rng(seed * 100 + spec['stream'])
    w0 = rng.normal(0, 0.01, (m, n))                    # ген w0 у каждой особи
    wg = rng.normal(0, 0.01, (m, 1) if council else (m, n))   # вес на G: ген группы (совет) или ген особи
    traj, price = [], []
    zc_idx = [i for i in range(7) if i not in (0, J)]
    for g in range(gens):
        wgm = wg.mean(1)                                  # средний вес на G в каждой группе (у совета — сам ген)
        b = np.array([T2.b_of(x) for x in wgm])           # доля лжи источника каждой группы
        if common:
            X, W, okG, u = episodes_common(rng, L_EP)
            zc = X[:, zc_idx] @ W_EX[zc_idx]              # вклад честных источников (общий)
            lie = (W[None, :] == 0) & okG[None, :] & (u[None, :] < b[:, None])     # m × L: где источник группы врёт
            xg = np.where(lie, 1.0, X[None, :, J])        # m × L: сигнал источника G в каждой группе
            Wm = np.broadcast_to(W[None, :], (m, L_EP))   # m × L: истина
            zcm = np.broadcast_to(zc[None, :], (m, L_EP))
        else:
            X, W, okG, u = episodes_groups(rng, m, L_EP)
            zcm = X[..., zc_idx] @ W_EX[zc_idx]           # m × L
            lie = (W == 0) & okG & (u < b[:, None])
            xg = np.where(lie, 1.0, X[..., J])
            Wm = W
        wgi = np.broadcast_to(wg, (m, n))                 # ген веса на G у каждой особи
        wex = np.broadcast_to(wg.mean(1, keepdims=True), (m, n)) if pooled else wgi   # вес, с которым особь действует
        Z = w0[:, :, None] + zcm[:, None, :] + wex[:, :, None] * xg[:, None, :]   # m × n × L
        logF = T1.log_true(Z, Wm[:, None, :]).sum(2)      # m × n
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
        if not wsel:
            prw = np.full((m, n), 1.0 / n)                # вес на G наследуется без отбора внутри группы
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
            elif wsel:
                new_wg[k] = wg[p, idx] + rng.normal(0, SIG, n)
            else:                                          # DEMES_NOWITHIN: родитель гена w_G равновероятен
                idw = rng.choice(n, size=n)
                new_wg[k] = wg[p, idw] + rng.normal(0, SIG, n)
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
    # лучший ответ сокращённого агента на мир при b* — численно (минимум точной лог-потери по w0 и w_G, честные веса
    # закреплены), против формулы exact_weights; и неподвижная точка: b_of(лучший ответ) = b*
    from scipy.optimize import minimize
    ws = WG.with_b(T2.B_STAR)
    r = minimize(lambda v: ws.exact_metrics(full_w(v[0], v[1]))['logloss'], x0=[-1.0, 0.8], method='Nelder-Mead',
                 options=dict(xatol=1e-9, fatol=1e-13, maxiter=4000))
    assert abs(r.x[0] - th['myopic']['w0']) < 1e-4 and abs(r.x[1] - th['myopic']['wG']) < 1e-4, (r.x, th['myopic'])
    assert abs(T2.b_of(r.x[1]) - T2.B_STAR) < 1e-4
    print('численный лучший ответ при b*:', np.round(r.x, 6))
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
    if '--pilot' in sys.argv:                      # пилот 5 (окончательное устройство); пилоты 1–3 — в pilot/, пилот 4 — в pilot4/
        os.makedirs(os.path.join(HERE, 'pilot5'), exist_ok=True)
        th, runs, sec = run(PILOT_SEEDS, os.path.join(HERE, 'pilot5')); print(f'пилот: {sec:.0f} с'); sys.exit(0)
    dry = '--dry' in sys.argv
    outdir = os.path.join(HERE, 'dry') if dry else HERE
    os.makedirs(outdir, exist_ok=True)
    th, runs, sec = run(DRY_SEEDS if dry else SEEDS, outdir)
    print(f'готово за {sec:.0f} с; анализ — analyze_trust_03.py')
