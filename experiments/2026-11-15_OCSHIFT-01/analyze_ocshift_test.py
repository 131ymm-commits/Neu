#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: анализ теста по PREREG.
  python3 analyze_ocshift_test.py RESULT.json [--boot B] [--workers W] SPEC [SPEC ...]
SPEC — 'new:КАТАЛОГ' (answers.json вида ocshift_extract.py, MODE = 'test': берутся среды вида test, блок сверки
проверяется против вывода OCREP-01) или 'old:ИМЯ=КАТАЛОГ' (каталог прежнего вида как одна среда — для проверки цепочки
на готовых сдвигах и на заглушках). Счёт по среде — analyze_ocshift.core (оценщики — код OCCOR-01 и OCMIX-01).

Среда годна, если проверку метода прошли не меньше 6 голов; толпа среды — прошедшие головы. Опыт определён, если годных
сред не меньше 80 % (8 из 10) и сверка цепочки прошла. Средние — по годным средам с равными весами.
Бутстреп — вложенный, по средам независимо: выборка ID с возвращением (переподгонка оценщиков и калибровки, ONE-BEST
выбирается заново), затем выборка OOD; B повторов (по умолчанию 10000); зерно среды — 7 630 000 + 10·X + p (у сред
прежнего вида — 7 630 000 + номер). Части кросс-подгонки закреплены за исходными задачами ID (зерно 7 620 000 + 10·X + p):
копии задачи в выборке остаются в одной части.
Правила (уровень LEVEL на сторону; вердикт — по ДИ BC и процентильному вместе, analyze_ocrep_test.verdict_conj):
  R1: D1 = среднее [ИОИ(ONE-BEST) − наименьший ИОИ среди восьми оценщиков толпы]. Подтверждено — верхняя граница < 0.
      Опровергнуто — нижняя граница > 0 И проверка, верная после отбора (max-T по восьми фиксированным оценщикам, уровень
      LEVEL): лучший задним числом оценщик выбран по тем же данным, и без этой проверки «опровергнуто» было бы завышено.
      Если нижняя граница > 0, а max-T не значим — «не решено (фора отбора)».
  R2: D2 = среднее [T − C у CONF на ID с кросс-подгонкой]. Подтверждено — верхняя граница < 0.
  R3: D3 = среднее [ИОИ(CONF) − ИОИ(LR-AGREE)]. Подтверждено — верхняя < 0 (CONF лучше); опровергнуто — нижняя > 0.
  R4: неоднородность D3 по средам: Q = Σ w (D3 − среднее с весами w)², w = 1 / s² (s — ст. отклонение бутстрепа среды).
      Подтверждено — p < LEVEL и по бутстрепу с центрированием (нулевая гипотеза: одна общая разность), и по χ²(m − 1).
Защита LR: в какой-то среде повторов с одним классом у головы в выборке ID больше 1 % — R1, R3, R4 «не решено».
Предохранитель знака (R1–R3): «подтверждено» требует точечной оценки < 0, «опровергнуто» — > 0; иначе «не решено (точка и ДИ расходятся)».
Описательно (вес 0; ДИ BC 99 %): ONE-BEST против каждого из восьми; Брайер; контроль AGREE; POST-IN; FUSE-MIN;
ONE-BEST+MIN; таблицы по средам; разложение различий «диапазон — подсказка»; extras по средам (только точка);
R2 вторым способом — среднее по задачам ID и нормальное приближение, без бутстрепа (R2.normal_descr);
связь D1 среды с отрывом лучшей головы от второй на ID (ранговая корреляция по средам; dominance_descr)."""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from scipy.stats import chi2, spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocshift as S  # noqa: E402

sys.path.insert(0, os.path.join(S.EXP, '2026-11-15_OCREP-01'))
import analyze_ocrep_test as R  # noqa: E402  (ci_entry, tails, verdict_conj)

LEVEL, DESCR_LEVEL = 0.0025, 0.005
SEED_CV, SEED_BOOT = 7_620_000, 7_630_000
MIN_VALID_FRAC = 0.8
LR_FAIL_MAX = 0.01
CHECK_TOL = 1e-3                      # допуск сверки logp (закрепляется в PREREG по пилоту)
EV = S.EVALS
RULES = {'R1': ('ioi ONE-BEST', 'ioi MIN8'), 'R2': ('wc CONF', None), 'R3': ('ioi CONF', 'ioi LR-AGREE')}
DESCR = dict({f'ONE-BEST − {e}': ('ioi ONE-BEST', f'ioi {e}') for e in EV},
             **{'Брайер ONE-BEST − MIN8': ('brier ONE-BEST', 'brier MIN8'), 'T ONE-BEST − T LR-AGREE': ('T ONE-BEST', 'T LR-AGREE'),
                'T ONE-BEST − T CONF': ('T ONE-BEST', 'T CONF'), 'CONF − AGREE': ('ioi CONF', 'ioi AGREE'),
                'LR-AGREE − AGREE': ('ioi LR-AGREE', 'ioi AGREE'), 'LR-AGREE − NB-IND': ('ioi LR-AGREE', 'ioi NB-IND'),
                'POST-IN CONF − CONF': ('ioi POST-IN CONF', 'ioi CONF'), 'POST-IN CONF − ONE-BEST': ('ioi POST-IN CONF', 'ioi ONE-BEST'),
                'POST-IN LR-AGREE − LR-AGREE': ('ioi POST-IN LR-AGREE', 'ioi LR-AGREE'), 'FUSE-MIN − ONE-BEST': ('ioi FUSE-MIN', 'ioi ONE-BEST'),
                'Брайер FUSE-MIN − ONE-BEST': ('brier FUSE-MIN', 'brier ONE-BEST'), 'ONE-BEST+MIN − ONE-BEST': ('ioi ONE-BEST+MIN', 'ioi ONE-BEST'),
                'Брайер ONE-BEST+MIN − ONE-BEST': ('brier ONE-BEST+MIN', 'brier ONE-BEST'),
                'wc ONE-BEST': ('wc ONE-BEST', None), 'wc CONF − wc ONE-BEST': ('wc CONF', 'wc ONE-BEST')})
U = 'не определено (проверка метода)'
UL = 'не решено (LR: один класс в выборке ID больше чем в 1 % повторов)'

_ST = {}


def _init(st):
    _ST.clear()
    _ST.update(st)


def _init_worker(st):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _init(st)


def _rep(fc):
    r = S.core(_ST['st'], fc[0], fc[1])
    return [r[k] for k in _ST['keys']]


def _pmap(items, st, workers):
    if workers <= 1:
        _init(st)
        return [_rep(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(st,)) as pool:
        return pool.map(_rep, items, chunksize=max(1, len(items) // (8 * workers)))


def val(d, pair):
    """Значение разности по плоскому словарю (или по словарю векторов бутстрепа)."""
    return d[pair[0]] - (d[pair[1]] if pair[1] else 0.0)


def heterogeneity(pt, bt):
    """Q Кохрена по средам и два p: χ²(m − 1) и бутстреп с центрированием под нулевую гипотезу одной общей разности."""
    pt, bt = np.asarray(pt, float), np.asarray(bt, float)               # bt — (среды, B)
    m, B = bt.shape
    s = bt.std(1, ddof=1)
    w = 1.0 / np.maximum(s, 1e-12) ** 2
    mean_w = float((w * pt).sum() / w.sum())
    Q = float((w * (pt - mean_w) ** 2).sum())
    b0 = bt - bt.mean(1, keepdims=True)                                   # среды центрированы: общая разность (её значение Q не меняет)
    mw = (w[:, None] * b0).sum(0) / w.sum()
    Qb = (w[:, None] * (b0 - mw[None, :]) ** 2).sum(0)
    return dict(Q=Q, df=m - 1, mean_weighted=mean_w, sd_env=[float(x) for x in s], p_chi2=float(chi2.sf(Q, m - 1)),
                p_boot=float((1 + (Qb >= Q).sum()) / (B + 1)), q_boot_q9975=float(np.quantile(Qb, 1 - LEVEL)))


def sign_guard(v, point):
    """Предохранитель: вывод выносится, только если знак точечной оценки совпадает со стороной ДИ. При сильном смещении
    бутстрепа оба ДИ могут лечь по другую сторону нуля, чем сама оценка; такой исход — «не решено (точка и ДИ расходятся)»."""
    if (v == 'подтверждено' and not point < 0) or (v == 'опровергнуто' and not point > 0):
        return 'не решено (точка и ДИ расходятся)'
    return v


def max_t(points, boots, level=LEVEL):
    """Проверка, верная после отбора: есть ли среди фиксированных оценщиков такой, у кого средний ИОИ ниже, чем у ONE-BEST.
    points[e], boots[e] — точка и повторы средней по средам разности ИОИ(ONE-BEST) − ИОИ(e). Статистика — наибольшее
    t = разность / ст. отклонение бутстрепа; нулевое распределение — наибольшее по оценщикам центрированное t повторов."""
    es = list(points)
    sd = {e: float(np.std(boots[e], ddof=1)) for e in es}
    t = {e: float(points[e] / max(sd[e], 1e-12)) for e in es}
    null = np.max([(np.asarray(boots[e]) - np.mean(boots[e])) / max(sd[e], 1e-12) for e in es], 0)
    best = max(es, key=lambda e: t[e])
    crit = float(np.quantile(null, 1 - level))
    return dict(t=t, best=best, t_max=t[best], crit=crit, p=float((1 + (null >= t[best]).sum()) / (len(null) + 1)), significant=bool(t[best] > crit))


def main(dst, specs, B=10000, workers=1):
    t00 = time.time()
    envs, check, src = {}, None, []
    for spec in specs:
        d, e = S.load_spec(spec)
        if d is not None:                                                 # новый вид: сверка цепочки и только среды теста
            check = S.check_block(e)
            src.append(dict(spec=spec, mode=d.get('mode'), info=d.get('info'), design=d.get('design'),
                            head_errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h]))
            e = {k: v for k, v in e.items() if v['meta'].get('kind') == 'test'}
        else:
            src.append(dict(spec=spec))
        envs.update(e)
    names = list(envs)
    res = dict(sources=src, level=LEVEL, descr_level=DESCR_LEVEL, B=B, check=check, check_tol=CHECK_TOL, envs={})
    check_ok = True if check is None else bool(check['answers_equal'] and check['max_abs_dlogp'] <= CHECK_TOL and check['n_heads'] == 9)
    res['check_ok'] = check_ok
    pts, boots, valid = {}, {}, []
    for i, name in enumerate(names):
        t0 = time.time()
        meta = envs[name]['meta']
        off = (10 * meta['X'] + meta['p']) if 'X' in meta else i
        st, info = S.prepare(envs[name], SEED_CV + off)
        r = dict(meta=meta, n_id=int(len(info['idi'])), n_ood=int(len(info['ood'])), method=info['method'],
                 crowd=[info['names'][k] for k in info['keep']], valid=info['valid'], seed_cv=SEED_CV + off, seed_boot=SEED_BOOT + off)
        if info['valid']:
            valid.append(name)
            pt = S.core(st, info['idi'], info['ood'])
            keys = sorted(pt)
            g = np.random.default_rng(SEED_BOOT + off)
            draws = [(g.choice(info['idi'], len(info['idi'])), g.choice(info['ood'], len(info['ood']))) for _ in range(B)]
            bt = np.array(_pmap(draws, dict(st=st, keys=keys), workers), float).T      # (ключи, B)
            del draws
            pts[name], boots[name] = pt, {k: bt[j] for j, k in enumerate(keys)}
            r['point'] = pt
            r['extras'] = S.extras(st, info)
            r['lr_one_class_share'] = float(np.mean(boots[name]['lr_one_class'] > 0))
            r['rules_env'] = {k: dict(point=float(val(pt, p)), sd=float(val(boots[name], p).std(ddof=1)),
                                      ci99=[float(x) for x in np.quantile(val(boots[name], p), (0.005, 0.995))]) for k, p in RULES.items()}
        r['seconds'] = round(time.time() - t0, 1)
        res['envs'][name] = r
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}, толпа {len(r['crowd'])}, годна {r['valid']}, {r['seconds']} с", flush=True)
    m = len(valid)
    method_ok = bool(check_ok and m >= int(np.ceil(MIN_VALID_FRAC * len(names))) and m >= 1)
    res['method'] = dict(ok=method_ok, n_envs=len(names), n_valid=m, valid=valid)
    if m == 0:
        res['verdicts'] = {k: U for k in ('R1', 'R2', 'R3', 'R4')}
        res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
        json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('вердикт:', res['verdict'])
        return res
    lr_bad = any(res['envs'][n]['lr_one_class_share'] > LR_FAIL_MAX for n in valid)
    res['lr_one_class'] = dict(max_share=max(res['envs'][n]['lr_one_class_share'] for n in valid), bad=bool(lr_bad))

    def mean_entry(pair, level):
        pt = float(np.mean([val(pts[n], pair) for n in valid]))
        bt = np.mean([val(boots[n], pair) for n in valid], 0)
        return R.ci_entry(bt, pt, level), bt, pt
    for k, pair in RULES.items():
        e, bt, pt = mean_entry(pair, LEVEL)
        e['tails'] = R.tails(bt, pt, LEVEL)
        e['monte_carlo_note'] = 'граница по Монте-Карло неустойчива' if e['tails']['unstable'] else ''
        e['verdict_bc'], e['verdict_percentile'] = R.verdict(*e['ci']), R.verdict(*e['ci_percentile'])
        v = sign_guard(R.verdict_conj(e['ci'], e['ci_percentile']), pt)
        e['verdict'] = U if not method_ok else (UL if (lr_bad and k != 'R2') else v)
        e['by_env'] = {n: float(val(pts[n], pair)) for n in valid}
        res[k] = e
    # R1, сторона «опровергнуто»: проверка, верная после отбора
    fx_pt = {x: float(np.mean([val(pts[n], ('ioi ONE-BEST', f'ioi {x}')) for n in valid])) for x in EV}
    fx_bt = {x: np.mean([val(boots[n], ('ioi ONE-BEST', f'ioi {x}')) for n in valid], 0) for x in EV}
    mt = max_t(fx_pt, fx_bt)
    res['R1']['max_t'] = mt
    if method_ok and not lr_bad and res['R1']['verdict'] == 'опровергнуто' and not mt['significant']:
        res['R1']['verdict'] = 'не решено (фора отбора)'
    h = heterogeneity([val(pts[n], RULES['R3']) for n in valid], [val(boots[n], RULES['R3']) for n in valid]) if m >= 2 else None
    if h is not None:
        h['verdict_raw'] = 'подтверждено' if (h['p_chi2'] < LEVEL and h['p_boot'] < LEVEL) else 'не решено'
        h['verdict'] = U if not method_ok else (UL if lr_bad else h['verdict_raw'])
        h['descr_R1'] = heterogeneity([val(pts[n], RULES['R1']) for n in valid], [val(boots[n], RULES['R1']) for n in valid])
    res['R4'] = h if h is not None else dict(verdict=U)
    wn = [res['envs'][n]['extras']['wc_conf_normal'] for n in valid]       # R2 вторым способом (описательно): без бутстрепа
    wm, ws = float(np.mean([w_['mean'] for w_ in wn])), float(np.sqrt(sum(w_['se'] ** 2 for w_ in wn)) / len(wn))
    res['R2']['normal_descr'] = dict(mean=wm, se=ws, z=wm / max(ws, 1e-12), by_env={n: w_['mean'] for n, w_ in zip(valid, wn)},
                                     note='нормальное приближение по задачам ID; среды независимы; на вердикт не влияет')
    for k, pair in DESCR.items():
        res[f'descr_{k}'] = dict(mean_entry(pair, DESCR_LEVEL)[0], by_env={n: float(val(pts[n], pair)) for n in valid})
    # разложение различий между средами: диапазон и подсказка (точки; только если у сред есть X и p)
    if all('X' in envs[n]['meta'] for n in valid):
        dec = {}
        for k, pair in RULES.items():
            byx = {}
            for n in valid:
                byx.setdefault(envs[n]['meta']['X'], []).append(val(pts[n], pair))
            full = [v for v in byx.values() if len(v) == 2]
            if len(full) >= 2:
                within = float(np.mean([(v[0] - v[1]) ** 2 / 2 for v in full]))           # дисперсия между подсказками внутри диапазона
                between = float(np.var([np.mean(v) for v in full], ddof=1))                # дисперсия средних по диапазонам
                dec[k] = dict(var_prompt_within_range=within, var_range_means=between, var_range_component=between - within / 2,
                              n_ranges=len(full))
        res['range_prompt_decomposition_descr'] = dec
    # Когда толпа не помогает (описательно, задано до данных теста): связь D1 среды с отрывом лучшей головы от второй на ID.
    # Ожидаемый знак — минус: чем сильнее одна голова выделяется на ID, тем больше её преимущество над толпой.
    if m >= 4:
        gap = [res['envs'][n]['extras']['one_best']['id_gap'] for n in valid]
        d1 = [val(pts[n], RULES['R1']) for n in valid]
        rho = spearmanr(gap, d1)
        res['dominance_descr'] = dict(spearman=float(rho[0]), p=float(rho[1]), n=m, id_gap={n: g_ for n, g_ in zip(valid, gap)},
                                      note='n мало; описательно, без вердикта')
    res['verdicts'] = {k: res[k]['verdict'] for k in ('R1', 'R2', 'R3', 'R4')}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    for k in RULES:
        print(f"{k}: Δ {res[k]['delta']:+.4f} ДИ BC [{res[k]['ci'][0]:+.4f}; {res[k]['ci'][1]:+.4f}] процентильный "
              f"[{res[k]['ci_percentile'][0]:+.4f}; {res[k]['ci_percentile'][1]:+.4f}] z0 {res[k]['z0']:+.3f} {res[k]['monte_carlo_note']}")
    if h is not None:
        print(f"R4: Q {h['Q']:.2f} (df {h['df']}), p χ² {h['p_chi2']:.2e}, p бутстрепа {h['p_boot']:.2e}")
    print('сверка цепочки:', None if check is None else dict(answers_equal=check['answers_equal'], max_abs_dlogp=check['max_abs_dlogp']),
          '| годных сред', m, 'из', len(names), '| LR, один класс: наибольшая доля', res['lr_one_class']['max_share'], '| время', res['seconds'], 'с')
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 10000
    W = int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 1)
    skip = set()
    for f in ('--boot', '--workers'):
        if f in a:
            skip |= {a.index(f), a.index(f) + 1}
    pos = [x for i, x in enumerate(a) if i not in skip]
    main(pos[0], pos[1:], B, W)
