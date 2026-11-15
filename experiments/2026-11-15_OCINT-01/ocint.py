#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCINT-01 «ОЦЕНЩИК-ИНТЕРВАЛ»: какой способ строить интервал для статистик оценщика не обманывается сам.
  python3 ocint.py worlds RESULT.json [--meta SEED] [--worlds 10] [--exp 100] [--truth 2000] [--boot 300] [--workers 4]
  python3 ocint.py real   RESULT.json [--boot 2000] [--half 10000] [--curve 400] [--quarter 200] [--workers 4] SPEC [SPEC ...]
Статистики и оценщики — зарегистрированный код OCSHIFT-01 (analyze_ocshift: select, meas, iso_fit, core; analyze_ocrep.scores).

worlds — миры с известной правдой. Мир — параметрическая модель девяти голов (world_params); выборка мира — среда размера
теста (1000 задач ID и 1200 OOD). Правда θ(n) — среднее статистики по --truth независимым выборкам. В каждом из --exp опытов
на мир считаются точка, --boot повторов бутстрепа с возвращением (как в OCSHIFT-01: выборка ID, затем OOD) и --boot половинных
выборок без возвращения (половина ID и половина OOD). Интервалы M1–M7 (methods) при номиналах 0,90 и 0,98; покрытие θ(n)
в одной среде (все опыты всех миров) и для среднего по мирам (опыт j — выборка j каждого мира).
real — настоящие среды: сдвиг и разброс повторов обоих способов (правило А), зависимость от размера калибровки, проверка
ширины на четвертях, интервалы с центром в точке на уровне 0,0025 для зарегистрированных статистик (таблица устойчивости).
SPEC — как в analyze_ocshift_test: 'new:КАТАЛОГ' или 'old:ИМЯ=КАТАЛОГ'."""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from scipy.stats import beta, norm

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, '2026-11-15_OCSHIFT-01'))
os.environ.setdefault('OCSHIFT_IMPORT_ONLY', '1')
import analyze_ocshift as S  # noqa: E402
import analyze_ocshift_test as A  # noqa: E402

Q, T = S.Q, S.T
H = 9
FAM = np.array([0, 1, 2, 2, 2, 2, 3, 4, 5])            # как у голов Pythia: четыре чекпойнта одной модели — одна семья
N_ID, N_OOD = 1000, 1200
OFFS = np.array([-100, -20, -11, -10, -9, -2, -1, 1, 2, 9, 10, 11, 20, 100])
STATS = ('S2 wc CONF', 'S3 CONF − LR-AGREE', 'S1 ONE-BEST − CONF', 'S4 POST-IN CONF − CONF', 'S5 POST-IN CONF − ONE-BEST')
EV2 = ('CONF', 'LR-AGREE')
METHODS = ('M1 процентильный', 'M2 BC', 'M3 обратный', 'M4 точка ± z·sd (с возвращением)', 'M5 точка ± огибающая (с возвращением)',
           'M6 точка ± z·sd (половинные)', 'M7 точка ± огибающая (половинные)')
NOMINALS = (0.90, 0.98)
LEVEL = 0.0025
META_TEST, META_PILOT = 7_700_000, 7_790_000
# правила на настоящих средах: зарегистрированные разности прежних опытов и статистики этого опыта (ключи analyze_ocshift.core)
REAL = {'R1 ONE-BEST − MIN8': ('ioi ONE-BEST', 'ioi MIN8'), 'R2 wc CONF': ('wc CONF', None), 'R3 CONF − LR-AGREE': ('ioi CONF', 'ioi LR-AGREE'),
        'LR-AGREE − AGREE': ('ioi LR-AGREE', 'ioi AGREE'), 'LR-AGREE − NB-IND': ('ioi LR-AGREE', 'ioi NB-IND'),
        'S1 ONE-BEST − CONF': ('ioi ONE-BEST', 'ioi CONF'), 'S4 POST-IN CONF − CONF': ('ioi POST-IN CONF', 'ioi CONF'),
        'S5 POST-IN CONF − ONE-BEST': ('ioi POST-IN CONF', 'ioi ONE-BEST')}
SEED_REAL = 7_710_000
FRACTIONS = (0.25, 0.5, 0.75)


# ───────────── миры с известной правдой
def world_params(k, meta):
    """Параметры мира k: способности голов на ID и их падение вне диапазона, прибавка сигнала уверенности вне диапазона,
    вес общей трудности задачи, шум сигнала уверенности, доля общих неверных ответов. Тяжёлый режим, как в OCSHIFT-01."""
    g = np.random.default_rng([meta, k])
    mu = g.uniform(-1.55, 0.15, H)                                  # точность на ID: Φ(mu) — от 0,06 до 0,56
    mu[int(g.integers(H))] = g.uniform(-0.25, 0.15)                 # хотя бы одна голова из сильных
    return dict(k=k, mu_id=mu, drop=g.uniform(0.25, 0.9, H), beta=g.uniform(0.0, 0.8, H), lam=float(g.uniform(0.45, 0.7)),
                gam=float(g.uniform(0.3, 0.5)), sig_c=float(g.uniform(0.6, 1.2)), kappa=1.5, p_common=float(g.uniform(0.2, 0.6)))


def agree(ans):
    ag = ans[:, None, :] == ans[None, :, :]
    ag[np.arange(len(ans)), np.arange(len(ans))] = False
    return ag


def draw(par, g, n_id=N_ID, n_ood=N_OOD):
    """Одна выборка мира: st (как analyze_ocshift.prepare), индексы ID и OOD. Головы связаны общей трудностью задачи и семьёй."""
    n = n_id + n_ood
    rid = np.zeros(n, bool)
    rid[:n_id] = True
    d, fl, eps = g.normal(size=n), g.normal(size=(FAM.max() + 1, n)), g.normal(size=(H, n))
    gam = np.where(np.bincount(FAM)[FAM] > 1, par['gam'], 0.0)       # семейный вклад — только у голов, у которых есть родня
    resid = np.sqrt(1 - par['lam'] ** 2 - gam ** 2)
    mu = np.where(rid[None, :], par['mu_id'][:, None], (par['mu_id'] - par['drop'])[:, None])
    u = mu - par['lam'] * d[None, :] + gam[:, None] * fl[FAM] + resid[:, None] * eps
    corr = u > 0
    s = u + np.where(rid[None, :], 0.0, par['beta'][:, None]) + par['sig_c'] * g.normal(size=(H, n))
    logp = -np.logaddexp(0.0, -par['kappa'] * s)
    truth = 1000 + np.arange(n)
    wrong = np.where(g.random((H, n)) < par['p_common'], (truth + g.choice(OFFS, n))[None, :], truth[None, :] + g.choice(OFFS, (H, n)))
    ans = np.where(corr, truth[None, :], wrong)
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    keep = [h for h in range(H) if min(corr[h, idi].sum(), (~corr[h, idi]).sum()) >= S.MIN_EACH]
    fold_of = np.full(n, -1)
    perm = g.permutation(n_id)
    for f in range(S.K_CV):
        fold_of[idi[perm[f::S.K_CV]]] = f
    return dict(ag=agree(ans), corr=corr, logp=logp, fam=[str(x) for x in FAM], keep=keep, fold_of=fold_of), idi, ood


def stats5(st, fit, cols):
    """Пять статистик одной выборки; формулы — как в analyze_ocshift.core (сверяется тестом)."""
    keep = st['keep']
    cs = st['corr'][keep]
    Sc = Q.scores(st['ag'], st['corr'], st['logp'], keep, fit, st['fam'], EV2)
    y_c, y_f = cs[:, cols].astype(float), cs[:, fit].astype(float)
    hb = int(np.argmax(cs[:, fit].mean(1)))
    cal = {e: T.calibrate(Sc[e], cs, fit, cols) for e in EV2}
    sel = {e: S.select(cal[e], y_c)[:2] for e in EV2}
    ioi = {e: S.meas(*sel[e])['ioi'] for e in EV2}
    one = S.meas(y_c[hb], cal['CONF'][hb])['ioi']
    ti, ci, _ = S.select(T.calibrate(Sc['CONF'], cs, fit, fit), y_f)
    post = S.meas(sel['CONF'][0], S.iso_fit(ci, ti).predict(sel['CONF'][1]))['ioi']
    fo = st['fold_of'][fit]
    tt, cc = [], []
    for f in range(S.K_CV):
        tr, te = fit[fo != f], fit[fo == f]
        t, c, _ = S.select(T.calibrate(Sc['CONF'], cs, tr, te), cs[:, te].astype(float))
        tt.append(t)
        cc.append(c)
    wc = float(np.mean(np.concatenate(tt)) - np.mean(np.concatenate(cc)))
    return np.array([wc, ioi['CONF'] - ioi['LR-AGREE'], one - ioi['CONF'], post - ioi['CONF'], post - one])


def half(g, idx):
    return g.choice(idx, len(idx) // 2, replace=False)


# ───────────── способы построить интервал
def methods(point, rb, rh, alpha):
    """Интервалы M1–M7 для одной статистики: point — точка, rb — повторы с возвращением, rh — половинные выборки."""
    iv, _, _, _ = A.intervals(rb, point, alpha)                       # зарегистрированный код OCSHIFT-01: BC, процентильный, обратный
    z = float(norm.ppf(1 - alpha))
    out = [iv['ci_percentile'], iv['ci'], iv['ci_basic']]
    for r in (rb, rh):
        sd, m = float(np.std(r, ddof=1)), float(np.mean(r))
        q = np.quantile(r, (alpha, 1 - alpha))
        w = float(max(m - q[0], q[1] - m))                            # огибающая: большее из двух хвостовых отклонений
        out += [[point - z * sd, point + z * sd], [point - w, point + w]]
    return np.array([out[0], out[1], out[2], out[3], out[4], out[5], out[6]], float)


def cp(x, n, level, side):
    """Односторонняя граница Клоппера — Пирсона для доли x из n: side 'lo' или 'hi'."""
    if side == 'lo':
        return 0.0 if x == 0 else float(beta.ppf(level, x, n - x + 1))
    return 1.0 if x == n else float(beta.ppf(1 - level, x + 1, n - x))


# ───────────── счёт в процессах
_W = {}


def _init(cfg):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _W.clear()
    _W.update(cfg)


def _truth(ki):
    k, i = ki
    g = np.random.default_rng([_W['meta'], 1, k, i])
    st, idi, ood = draw(_W['pars'][k], g)
    return stats5(st, idi, ood)


def _exp(ki):
    k, i = ki
    g = np.random.default_rng([_W['meta'], 2, k, i])
    st, idi, ood = draw(_W['pars'][k], g)
    B = _W['B']
    p = stats5(st, idi, ood)
    rb = np.array([stats5(st, g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B)])
    rh = np.array([stats5(st, half(g, idi), half(g, ood)) for _ in range(B)])
    return p, rb, rh, len(st['keep'])


def _pool(fn, items, cfg, workers):
    if workers <= 1:
        _init(cfg)
        return [fn(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init, initargs=(cfg,)) as pool:
        return pool.map(fn, items, chunksize=1)


def worlds(dst, meta=META_TEST, n_worlds=10, n_exp=100, n_truth=2000, B=300, workers=4):
    t0 = time.time()
    pars = [world_params(k, meta) for k in range(n_worlds)]
    cfg = dict(meta=meta, pars=pars, B=B)
    tr = np.array(_pool(_truth, [(k, i) for k in range(n_worlds) for i in range(n_truth)], cfg, workers)).reshape(n_worlds, n_truth, len(STATS))
    th, sdt = tr.mean(1), tr.std(1, ddof=1)                           # правда θ(n) и истинный разброс статистики в мире
    print(f'правда: {n_worlds} миров по {n_truth} выборок, {time.time() - t0:.0f} с', flush=True)
    ex = _pool(_exp, [(k, i) for k in range(n_worlds) for i in range(n_exp)], cfg, workers)
    P = np.array([e[0] for e in ex]).reshape(n_worlds, n_exp, len(STATS))
    RB = np.array([e[1] for e in ex]).reshape(n_worlds, n_exp, B, len(STATS))
    RH = np.array([e[2] for e in ex]).reshape(n_worlds, n_exp, B, len(STATS))
    crowd = np.array([e[3] for e in ex]).reshape(n_worlds, n_exp)
    print(f'опыты: {n_worlds * n_exp} выборок, {time.time() - t0:.0f} с', flush=True)
    res = dict(meta=meta, n_worlds=n_worlds, n_exp=n_exp, n_truth=n_truth, B=B, n_id=N_ID, n_ood=N_OOD, stats=list(STATS), methods=list(METHODS),
               nominals=list(NOMINALS), level=LEVEL,
               worlds=[dict(k=p['k'], acc_id=[float(norm.cdf(m)) for m in p['mu_id']], acc_ood=[float(norm.cdf(m - d)) for m, d in zip(p['mu_id'], p['drop'])],
                            beta=[float(x) for x in p['beta']], lam=p['lam'], gam=p['gam'], sig_c=p['sig_c'], p_common=p['p_common'],
                            truth=dict(zip(STATS, map(float, th[k]))), sd_true=dict(zip(STATS, map(float, sdt[k]))),
                            truth_se=dict(zip(STATS, map(float, sdt[k] / np.sqrt(n_truth)))), crowd_min=int(crowd[k].min()), crowd_max=int(crowd[k].max()))
                       for k, p in enumerate(pars)])
    PM, RBM, RHM, THM = P.mean(0), RB.mean(0), RH.mean(0), th.mean(0)  # среднее по мирам: опыт j — выборка j каждого мира
    sdm = np.sqrt((sdt ** 2).sum(0)) / n_worlds                       # истинный разброс среднего по мирам
    res['mean_truth'], res['mean_sd_true'] = dict(zip(STATS, map(float, THM))), dict(zip(STATS, map(float, sdm)))
    cov = {}
    for nom in NOMINALS:
        a = (1 - nom) / 2
        one = np.zeros((n_worlds, n_exp, len(METHODS), len(STATS)), bool)
        wid = np.zeros((n_worlds, n_exp, len(METHODS), len(STATS)))
        for k in range(n_worlds):
            for i in range(n_exp):
                for s in range(len(STATS)):
                    iv = methods(P[k, i, s], RB[k, i, :, s], RH[k, i, :, s], a)
                    one[k, i, :, s] = (iv[:, 0] <= th[k, s]) & (th[k, s] <= iv[:, 1])
                    wid[k, i, :, s] = (iv[:, 1] - iv[:, 0]) / sdt[k, s]
        mean = np.zeros((n_exp, len(METHODS), len(STATS)), bool)
        widm = np.zeros((n_exp, len(METHODS), len(STATS)))
        for j in range(n_exp):
            for s in range(len(STATS)):
                iv = methods(PM[j, s], RBM[j, :, s], RHM[j, :, s], a)
                mean[j, :, s] = (iv[:, 0] <= THM[s]) & (THM[s] <= iv[:, 1])
                widm[j, :, s] = (iv[:, 1] - iv[:, 0]) / sdm[s]
        cov[str(nom)] = dict(
            one_env={m: {st_: dict(covered=int(one[:, :, mi, si].sum()), n=n_worlds * n_exp, coverage=float(one[:, :, mi, si].mean()),
                                   by_world=[float(x) for x in one[:, :, mi, si].mean(1)], width_in_sd=float(wid[:, :, mi, si].mean()))
                         for si, st_ in enumerate(STATS)} for mi, m in enumerate(METHODS)},
            mean_of_worlds={m: {st_: dict(covered=int(mean[:, mi, si].sum()), n=n_exp, coverage=float(mean[:, mi, si].mean()),
                                          width_in_sd=float(widm[:, mi, si].mean())) for si, st_ in enumerate(STATS)} for mi, m in enumerate(METHODS)})
    res['coverage'] = cov
    # сдвиг и разброс повторов против правды
    sb, sh = RB.std(2, ddof=1), RH.std(2, ddof=1)
    res['replicates'] = {st_: dict(
        shift_boot_in_sd=float(np.mean((RB[..., si].mean(2) - P[..., si]) / sb[..., si])), shift_half_in_sd=float(np.mean((RH[..., si].mean(2) - P[..., si]) / sh[..., si])),
        shift_boot=float(np.mean(RB[..., si].mean(2) - P[..., si])), shift_half=float(np.mean(RH[..., si].mean(2) - P[..., si])),
        sd_ratio_boot=float(np.sqrt(np.mean(sb[..., si] ** 2 / sdt[:, None, si] ** 2))), sd_ratio_half=float(np.sqrt(np.mean(sh[..., si] ** 2 / sdt[:, None, si] ** 2))),
        point_bias_in_sd=float(np.mean((P[..., si].mean(1) - th[:, si]) / (sdt[:, si] / np.sqrt(n_exp)))),
        mean_shift_boot_in_sd=float(np.mean((RBM[..., si].mean(1) - PM[:, si]) / RBM[..., si].std(1, ddof=1))),
        mean_shift_half_in_sd=float(np.mean((RHM[..., si].mean(1) - PM[:, si]) / RHM[..., si].std(1, ddof=1))),
        mean_sd_ratio_boot=float(np.sqrt(np.mean(RBM[..., si].var(1, ddof=1)) / sdm[si] ** 2)),
        mean_sd_ratio_half=float(np.sqrt(np.mean(RHM[..., si].var(1, ddof=1)) / sdm[si] ** 2))) for si, st_ in enumerate(STATS)}
    res['rules'] = rules_worlds(res)
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(res['rules'], ensure_ascii=False, indent=1))
    print('время', res['seconds'], 'с')
    return res


def rules_worlds(res):
    """Правила Б1, Б2 и выбор способа (HYPOTHESIS, PREREG §5) — по покрытию при номинале 0,90."""
    c = res['coverage']['0.9']
    b1 = c['mean_of_worlds'][METHODS[0]][STATS[0]]
    hi, lo = cp(b1['covered'], b1['n'], LEVEL, 'hi'), cp(b1['covered'], b1['n'], LEVEL, 'lo')
    r1 = dict(coverage=b1['coverage'], covered=b1['covered'], n=b1['n'], upper=hi, lower=lo,
              verdict='подтверждено' if hi < 0.5 else ('опровергнуто' if lo > 0.8 else 'не решено'))
    lev = LEVEL / 3
    b2 = {}
    for st_ in STATS[:3]:
        e = c['one_env'][METHODS[6]][st_]
        b2[st_] = dict(coverage=e['coverage'], covered=e['covered'], n=e['n'], lower=cp(e['covered'], e['n'], lev, 'lo'), upper=cp(e['covered'], e['n'], lev, 'hi'))
    r2 = dict(by_stat=b2, level_each=lev, verdict='подтверждено' if all(v['lower'] > 0.85 for v in b2.values())
              else ('опровергнуто' if any(v['upper'] < 0.85 for v in b2.values()) else 'не решено'))
    elig = {}
    for m in METHODS[3:]:
        one = [c['one_env'][m][s]['coverage'] for s in STATS]
        mean = [c['mean_of_worlds'][m][s]['coverage'] for s in STATS]
        elig[m] = dict(min_one_env=min(one), min_mean=min(mean), eligible=bool(min(one) >= 0.88 and min(mean) >= 0.85),
                       width_in_sd=float(np.mean([c['one_env'][m][s]['width_in_sd'] for s in STATS])))
    ok = [m for m in METHODS[3:] if elig[m]['eligible']]
    best = None
    if ok:
        wmin = min(elig[m]['width_in_sd'] for m in ok)
        best = METHODS[6] if (METHODS[6] in ok and elig[METHODS[6]]['width_in_sd'] <= wmin + 1e-12) else min(ok, key=lambda m: elig[m]['width_in_sd'])
    return dict(B1=r1, B2=r2, choice=dict(candidates=elig, chosen=best, note='годен: покрытие в одной среде не ниже 0,88 и среднего по мирам не ниже 0,85 для всех пяти статистик; из годных — самый узкий'))


# ───────────── настоящие среды
def limit_fit(curve, point, fractions=FRACTIONS):
    """Описательно: θ(m) = a + b·(n / m) по точкам долей ID и полной выборке (метод наименьших квадратов); a — оценка предела
    при бесконечной калибровке. Возвращает a, b и долю точки, которая остаётся в пределе (a / точка)."""
    x = np.array([1.0 / q for q in fractions] + [1.0])
    y = np.array([curve[str(q)] for q in fractions] + [point])
    b, a = np.polyfit(x, y, 1)
    return dict(limit=float(a), slope=float(b), share_left=(float(a / point) if abs(point) > 1e-12 else None))


def val(d, pair):
    return d[pair[0]] - (d[pair[1]] if pair[1] else 0.0)


def real(dst, specs, B_boot=2000, B_half=10000, B_curve=400, B_q=200, workers=4):
    t00 = time.time()
    envs = {}
    for spec in specs:
        d, e = S.load_spec(spec)
        if d is not None:
            e = {k: v for k, v in e.items() if v['meta'].get('kind') == 'test'}
        envs.update(e)
    res = dict(specs=list(specs), level=LEVEL, B_boot=B_boot, B_half=B_half, B_curve=B_curve, B_quarter=B_q, fractions=list(FRACTIONS), envs={})
    keep_reps, n_old = {}, 0
    for name, env in envs.items():
        t0 = time.time()
        meta = env['meta']
        if 'X' in meta:
            off = 10 * meta['X'] + meta['p']                           # как в analyze_ocshift_test.main
        else:
            off, n_old = n_old, n_old + 1                              # как в цепочке на готовых сдвигах: номер среди сред прежнего вида
        st, info = S.prepare(env, A.SEED_CV + off)
        idi, ood = info['idi'], info['ood']
        pt = S.core(st, idi, ood)
        keys = sorted(pt)
        g = np.random.default_rng([SEED_REAL, off])
        rb = np.array(A._pmap([(g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B_boot)], dict(st=st, keys=keys), workers), float)
        rh = np.array(A._pmap([(half(g, idi), half(g, ood)) for _ in range(B_half)], dict(st=st, keys=keys), workers), float)
        col = {k: j for j, k in enumerate(keys)}
        rep = lambda r, pair: r[:, col[pair[0]]] - (r[:, col[pair[1]]] if pair[1] else 0.0)   # noqa: E731
        out = dict(meta=meta, n_id=int(len(idi)), n_ood=int(len(ood)), crowd=len(info['keep']), stats={})
        # зависимость от размера калибровки: доля задач ID без возвращения, OOD — все
        curve = {}
        for q in FRACTIONS:
            rc = np.array(A._pmap([(g.choice(idi, int(q * len(idi)), replace=False), ood) for _ in range(B_curve)], dict(st=st, keys=keys), workers), float)
            curve[q] = {n_: float(rep(rc, p_).mean()) for n_, p_ in REAL.items()}
        # проверка ширины: четыре непересекающиеся четверти; внутри четверти — половинные выборки и бутстреп
        pi, po = g.permutation(idi), g.permutation(ood)
        qf, qvh, qvb = [], [], []
        for qq in range(4):
            fi, co = pi[qq::4], po[qq::4]
            fq = S.core(st, fi, co)
            qf.append({n_: val(fq, p_) for n_, p_ in REAL.items()})
            rqh = np.array(A._pmap([(half(g, fi), half(g, co)) for _ in range(B_q)], dict(st=st, keys=keys), workers), float)
            rqb = np.array(A._pmap([(g.choice(fi, len(fi)), g.choice(co, len(co))) for _ in range(B_q)], dict(st=st, keys=keys), workers), float)
            qvh.append({n_: float(rep(rqh, p_).var(ddof=1)) for n_, p_ in REAL.items()})
            qvb.append({n_: float(rep(rqb, p_).var(ddof=1)) for n_, p_ in REAL.items()})
        for n_, p_ in REAL.items():
            b, h, p0 = rep(rb, p_), rep(rh, p_), float(val(pt, p_))
            sb, sh = float(b.mean() - p0), float(h.mean() - p0)
            out['stats'][n_] = dict(point=p0, boot_mean=float(b.mean()), boot_sd=float(b.std(ddof=1)), half_mean=float(h.mean()), half_sd=float(h.std(ddof=1)),
                                    shift_boot=sb, shift_half=sh, ratio=(sb / sh if abs(sh) > 1e-12 else None),
                                    shift_boot_in_sd=sb / float(b.std(ddof=1)), shift_half_in_sd=sh / float(h.std(ddof=1)),
                                    sd_ratio_boot_to_half=float(b.std(ddof=1) / h.std(ddof=1)),
                                    curve={str(q): curve[q][n_] for q in FRACTIONS},
                                    limit=limit_fit({str(q): curve[q][n_] for q in FRACTIONS}, p0),
                                    running=dict(boot={str(m): float(b[:m].mean() - p0) for m in (len(b) // 4, len(b) // 2, len(b))},
                                                 half={str(m): float(h[:m].mean() - p0) for m in (len(h) // 4, len(h) // 2, len(h))}),
                                    quarters=dict(var_true=float(np.var([x[n_] for x in qf], ddof=1)), var_half=float(np.mean([x[n_] for x in qvh])),
                                                  var_boot=float(np.mean([x[n_] for x in qvb]))))
        keep_reps[name] = dict(pt=pt, rb=rb, rh=rh, col=col)
        out['seconds'] = round(time.time() - t0, 1)
        res['envs'][name] = out
        print(f"{name}: ID {out['n_id']}, OOD {out['n_ood']}, толпа {out['crowd']}, {out['seconds']} с", flush=True)
    names = list(envs)
    # правило А: S2 — сдвиг повторов бутстрепа против сдвига половинных выборок, по средам
    r = [res['envs'][n]['stats']['R2 wc CONF'] for n in names]
    same = int(sum(1 for x in r if x['shift_boot'] * x['shift_half'] > 0))
    ratios = [x['ratio'] for x in r if x['ratio'] is not None]
    med = float(np.median(ratios)) if ratios else None
    res['rule_A'] = dict(n_envs=len(names), same_sign=same, ratios={n: x['ratio'] for n, x in zip(names, r)}, median_ratio=med,
                         verdict=('подтверждено' if (same == len(names) and med is not None and 0.67 <= med <= 1.5)
                                  else ('опровергнуто' if (med is None or med < 0.5 or med > 2 or len(names) - same >= 4) else 'не решено')))
    res['rule_A_other_stats'] = {n_: dict(same_sign=int(sum(1 for n in names if res['envs'][n]['stats'][n_]['shift_boot'] * res['envs'][n]['stats'][n_]['shift_half'] > 0)),
                                          median_ratio=float(np.median([res['envs'][n]['stats'][n_]['ratio'] for n in names if res['envs'][n]['stats'][n_]['ratio'] is not None])))
                                 for n_ in REAL}
    # проверка ширины по всем средам: отношение предсказанной дисперсии к разбросу между четвертями
    res['quarters'] = {n_: dict(ratio_half=float(sum(res['envs'][n]['stats'][n_]['quarters']['var_half'] for n in names) / sum(res['envs'][n]['stats'][n_]['quarters']['var_true'] for n in names)),
                                ratio_boot=float(sum(res['envs'][n]['stats'][n_]['quarters']['var_boot'] for n in names) / sum(res['envs'][n]['stats'][n_]['quarters']['var_true'] for n in names)),
                                df=3 * len(names)) for n_ in REAL}
    # таблица устойчивости: интервалы с центром в точке на уровне LEVEL — среднее по средам с X (OCSHIFT-01) и каждая среда прежнего вида
    z = float(norm.ppf(1 - LEVEL))

    def table(group, label):
        tab = {}
        for n_, p_ in REAL.items():
            pt = float(np.mean([val(keep_reps[n]['pt'], p_) for n in group]))
            b = np.mean([keep_reps[n]['rb'][:, keep_reps[n]['col'][p_[0]]] - (keep_reps[n]['rb'][:, keep_reps[n]['col'][p_[1]]] if p_[1] else 0.0) for n in group], 0)
            h = np.mean([keep_reps[n]['rh'][:, keep_reps[n]['col'][p_[0]]] - (keep_reps[n]['rh'][:, keep_reps[n]['col'][p_[1]]] if p_[1] else 0.0) for n in group], 0)
            iv = methods(pt, b, h, LEVEL)
            tab[n_] = dict(point=pt, intervals={m: [float(iv[mi, 0]), float(iv[mi, 1])] for mi, m in enumerate(METHODS)},
                           verdicts={m: A.R.verdict(float(iv[mi, 0]), float(iv[mi, 1])) for mi, m in enumerate(METHODS)},
                           boot_sd=float(b.std(ddof=1)), half_sd=float(h.std(ddof=1)), shift_boot=float(b.mean() - pt), shift_half=float(h.mean() - pt), z=z)
        return dict(group=label, envs=list(group), stats=tab)
    new = [n for n in names if 'X' in envs[n]['meta']]
    res['robustness'] = ([table(new, 'среднее по средам OCSHIFT-01')] if new else []) + [table([n], n) for n in names if 'X' not in envs[n]['meta']]
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('правило А:', json.dumps({k: v for k, v in res['rule_A'].items() if k != 'ratios'}, ensure_ascii=False), '| время', res['seconds'], 'с')
    return res


if __name__ == '__main__':
    a = sys.argv[1:]

    def opt(name, default):
        return int(a[a.index(name) + 1]) if name in a else default
    flags = ('--meta', '--worlds', '--exp', '--truth', '--boot', '--half', '--curve', '--quarter', '--workers')
    skip = set()
    for f in flags:
        if f in a:
            skip |= {a.index(f), a.index(f) + 1}
    pos = [x for i, x in enumerate(a) if i not in skip]
    if pos[0] == 'worlds':
        worlds(pos[1], opt('--meta', META_TEST), opt('--worlds', 10), opt('--exp', 100), opt('--truth', 2000), opt('--boot', 300), opt('--workers', 4))
    else:
        real(pos[1], pos[2:], opt('--boot', 2000), opt('--half', 10000), opt('--curve', 400), opt('--quarter', 200), opt('--workers', 4))
