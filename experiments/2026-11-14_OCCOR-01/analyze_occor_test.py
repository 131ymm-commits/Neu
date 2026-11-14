#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: анализ теста по PREREG. python3 analyze_occor_test.py OUT_DIR RESULT.json [--boot B] [--boot-dose BD] [--workers W]
OUT_DIR — вывод occor_extract_test.py (SPLIT = 'test'). Головы — список HEADS_TEST ниже (закреплён в PREREG по проверке
метода на пилоте), в этом порядке. Оценщики — analyze_occor (AGREE, NB-AGREE, LR-AGREE, NB-IND, FAM-AGREE, CONF).
Калибровка — изотоническая по ID; выбор головы на задаче OOD — наибольшая откалиброванная вероятность, ничья «поровну».
Бутстреп — вложенный: в каждом повторе выборка задач ID с возвращением (переподгонка NB-, LR- и NB-IND-параметров и
калибровки), затем выборка задач OOD; B повторов (по умолчанию 4000), зерно 1201. Доза — закреплённые составы толп
(12 при k = 1 и все 5 при k = 4, зерно 1202), BD повторов (по умолчанию 4000 — совет 54), зерно 1203.
Интервал — бутстреп с поправкой на смещение (BC, analyze_occor.bc_ci; обычный процентильный — описательно).
Правила (уровень — LEVEL на сторону; ложное «подтверждено» по серии из четырёх правил — не выше 4 · LEVEL):
  R1 (главное): Δ_LR = ИОИ(LR-AGREE) − ИОИ(AGREE) на полном наборе. Подтверждено — верхняя граница ДИ < 0; опровергнуто —
     нижняя > 0; иначе «не решено».
  R2: Δ_NB = ИОИ(NB-AGREE) − ИОИ(AGREE) — так же.
  R3: ИОИ(LR-AGREE) − ИОИ(NB-IND) — так же (преимущество над NB-IND; «специфичностью к общим ошибкам» не называется —
     совет 54).
  R4 (доза): Δ_LR(4) − Δ_LR(1) по толпам из 5 голов с k клонами; точка и бутстреп — по закреплённым составам — так же.
Проверки метода (провал любой → R1–R4 «не определено (проверка метода)»): загружены все головы HEADS_TEST; у каждой на ID
и на OOD не меньше 20 верных и 20 неверных; ответов без числа не больше 5 %; клонов не меньше 3, не-клонов не меньше 4.
Защита LR (совет 54): если у головы в выборке ID повтора один класс, её оценка LR — константа (калибровка даёт долю
верных). Если такие повторы составляют больше 1 % повторов своего бутстрепа, правила с LR-AGREE (R1, R3 — основной
бутстреп; R4 — бутстреп дозы) — «не решено».
Хвосты BC (совет 54): для каждого правила — число повторов за каждой границей и интервал по двум половинам повторов; если
половины дают разный вердикт — пометка «граница по Монте-Карло неустойчива» (вердикт не меняет).
Описательно (вес 0, без вердикта, в серию не входит; интервалы — BC 99 %): FAM-AGREE против LR-AGREE и NB-AGREE; CONF;
самообман в верхних 10 % — главный вариант по выбранным ответам (top10_sel), вторичный по всем парам (top10_all), ничьи на
границе дробно; разности самообмана в верхних 10 % выбранных ответов (LR − AGREE, LR − CONF); разложение R1 на ΔT и ΔC и доля
C; AUROC по головам; ничьи; доза для всех оценщиков (в том числе NB-IND) и доза, где pythia-2.8b-deduped считается клоном
(только точка); кросс-подгонка по 5 частям ID (только точка); коэффициенты LR-AGREE по группам пар (только точка); доля задач
OOD, где все головы неверны и согласны; перенос долей одинаковых неверных ответов ID → OOD (ПОДПИСЬ)."""
import itertools
import json
import multiprocessing as mp
import os
import sys

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_occor as Z  # noqa: E402

HEADS_TEST = ['pythia-1.4b', 'pythia-1.4b-deduped', 'pythia-2.8b', 'pythia-2.8b@step133000', 'pythia-2.8b@step123000',
              'pythia-2.8b@step113000', 'pythia-2.8b-deduped', 'pythia-6.9b', 'pythia-6.9b-deduped']
# ↑ закреплено в PREREG-OCCOR-01 §2: головы, прошедшие проверку метода на пилоте (opt-2.7b и gpt-neo-2.7B не прошли)
LEVEL = 0.0025             # уровень на сторону (четыре правила → серия не выше 0,01); ДИ — (LEVEL, 1 − LEVEL)
DESCR_LEVEL = 0.005        # описательные интервалы — BC 99 % (совет 54)
CLONE, CROWD = 'pythia-2.8b', 5
DEDUP = 'pythia-2.8b-deduped'
MIN_EACH, MAX_NONE = 20, 0.05
SEED_B, SEED_CROWDS, SEED_BD = 1201, 1202, 1203
LR_FAIL_MAX = 0.01         # совет 54: доля повторов с одним классом в выборке ID, выше которой правила с LR «не решено»
RULES = {'R1': ('LR-AGREE', 'AGREE'), 'R2': ('NB-AGREE', 'AGREE'), 'R3': ('LR-AGREE', 'NB-IND')}
LR_RULES = ('R1', 'R3', 'R4')
DESCR = {'LR−FAM': ('LR-AGREE', 'FAM-AGREE'), 'NB−FAM': ('NB-AGREE', 'FAM-AGREE'), 'NB−NB-IND': ('NB-AGREE', 'NB-IND'),
         'LR−CONF': ('LR-AGREE', 'CONF'), 'AGREE−CONF': ('AGREE', 'CONF')}
TOP_PAIRS = (('LR-AGREE', 'AGREE'), ('LR-AGREE', 'CONF'))
U = 'не определено (проверка метода)'
UL = 'не решено (LR: один класс в выборке ID больше чем в 1 % повторов)'


def verdict(lo, hi):
    return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')


def ci_entry(boot, point, level):
    b = np.asarray(boot, float)
    (lo, hi), z0 = Z.bc_ci(b, point, level)
    return dict(delta=float(point), ci=[lo, hi], ci_percentile=[float(x) for x in np.quantile(b, (level, 1 - level))], z0=z0,
                boot_median=float(np.median(b)), share_below_0=float(np.mean(b < 0)), level=level)


def tails(boot, point, level):
    """Хвосты BC (совет 54): число повторов за каждой границей и интервал по каждой из двух половин повторов."""
    b = np.asarray(boot, float)
    (lo, hi), _ = Z.bc_ci(b, point, level)
    h = len(b) // 2
    halves = [Z.bc_ci(b[:h], point, level)[0], Z.bc_ci(b[h:], point, level)[0]]
    vh = [verdict(*x) for x in halves]
    return dict(n_below_lo=int((b < lo).sum()), n_above_hi=int((b > hi).sum()), halves=halves, verdict_halves=vh,
                unstable=bool(vh[0] != vh[1]))


# Параллельный счёт бутстрепа. Все случайные выборки делаются заранее в главном процессе, в том же порядке вызовов
# генератора, что и в последовательном цикле; оценщики детерминированы. Поэтому результат не зависит от числа процессов
# (сверено сухим прогоном: последовательный код и workers = 1 и 4 дают одинаковый json).
_ST = {}


def _init(st):
    _ST.clear()
    _ST.update(st)


def _init_worker(st):
    from threadpoolctl import threadpool_limits          # один поток BLAS/OpenMP на процесс: иначе процессы делят ядра
    threadpool_limits(1)
    _init(st)


def _pmap(fn, items, st, workers):
    if workers <= 1:
        _init(st)
        return [fn(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(st,)) as pool:
        return pool.map(fn, items, chunksize=max(1, len(items) // (8 * workers)))


def _full_rep(fc):
    s = _ST
    r = Z.crowd_ioi(s['ag'], s['corr'], s['logp'], s['fam'], s['allh'], fc[0], fc[1], top10=True, auroc=False)
    out = {k: r[a]['ioi'] - r[b]['ioi'] for k, (a, b) in s['pairs'].items()}
    out['dT'] = r['LR-AGREE']['T'] - r['AGREE']['T']
    out['dC'] = r['LR-AGREE']['C'] - r['AGREE']['C']
    for a, b in TOP_PAIRS:
        out[f'top10_sel_{a}−{b}'] = r[a]['top10_sel']['deception'] - r[b]['top10_sel']['deception']
    out['lr_one_class'] = r['LR-AGREE']['lr_one_class']
    return out


def _dlr(k, fit, cols):
    s = _ST
    vv = [Z.crowd_ioi(s['ag'], s['corr'], s['logp'], s['fam'], list(c), fit, cols, evals=('AGREE', 'LR-AGREE')) for c in s['fixed'][k]]
    return float(np.mean([v['LR-AGREE']['ioi'] - v['AGREE']['ioi'] for v in vv])), sum(v['LR-AGREE']['lr_one_class'] for v in vv)


def _dose_rep(fc):
    (d4, n4), (d1, n1) = _dlr(4, fc[0], fc[1]), _dlr(1, fc[0], fc[1])
    return d4 - d1, n4 + n1


def main(out_dir, dst, B=4000, BD=4000, heads_test=None, workers=1):
    d, heads_all = Z.load(out_dir)
    want = heads_test or HEADS_TEST or [Z.label(h) for h in heads_all]
    by = {Z.label(h): h for h in heads_all}
    missing = [w for w in want if w not in by]
    heads = [by[w] for w in want if w in by]
    ans, corr, rid, logp = Z.arrays(d, heads)
    names = [Z.label(h) for h in heads]
    fam = [Z.family(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    allh = list(range(len(heads)))
    res = dict(split=d.get('split'), n_id=int(len(idi)), n_ood=int(len(ood)), heads=names, missing=missing, level=LEVEL,
               descr_level=DESCR_LEVEL, B=B, BD=BD, top10_main='top10_sel',
               errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h])
    # проверки метода
    counts = {}
    for k in allh:
        counts[names[k]] = dict(id_correct=int(corr[k][rid].sum()), id_wrong=int((~corr[k][rid]).sum()),
                                ood_correct=int(corr[k][~rid].sum()), ood_wrong=int((~corr[k][~rid]).sum()),
                                none_frac=float(np.mean([a is None for a in ans[k]])))
    clones = [k for k in allh if fam[k] == CLONE]
    nonc = [k for k in allh if fam[k] != CLONE]
    method_ok = (not missing and all(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) >= MIN_EACH
                                     and v['none_frac'] <= MAX_NONE for v in counts.values()) and len(clones) >= 3 and len(nonc) >= 4)
    res['method'] = dict(ok=bool(method_ok), counts=counts, n_clones=len(clones), n_nonclones=len(nonc))
    res['accuracy'] = {names[k]: dict(id=float(corr[k][rid].mean()), ood=float(corr[k][~rid].mean())) for k in allh}
    ag = Z.agree_matrix(ans)
    # полный набор: точечно
    full = Z.crowd_ioi(ag, corr, logp, fam, allh, idi, ood, top10=True)
    res['evaluators'] = full
    # вложенный бутстреп
    g = np.random.default_rng(SEED_B)
    pairs = {**RULES, **DESCR}
    draws = [(g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B)]     # порядок: ID, затем OOD в каждом повторе
    reps = _pmap(_full_rep, draws, dict(ag=ag, corr=corr, logp=logp, fam=fam, allh=allh, pairs=pairs), workers)
    n_fail = sum(1 for r in reps if r['lr_one_class'] > 0)
    res['lr_one_class'] = dict(full_reps=n_fail, full_share=n_fail / B)
    lr_bad = n_fail > LR_FAIL_MAX * B
    for k, (a, b) in pairs.items():
        bk = [r[k] for r in reps]
        e = ci_entry(bk, full[a]['ioi'] - full[b]['ioi'], LEVEL if k in RULES else DESCR_LEVEL)
        if k in RULES:
            e['tails'] = tails(bk, e['delta'], LEVEL)
            e['monte_carlo_note'] = 'граница по Монте-Карло неустойчива' if e['tails']['unstable'] else ''
            e['verdict'] = U if not method_ok else (UL if (k in LR_RULES and lr_bad) else verdict(*e['ci']))
        res[k if k in RULES else f'descr_{k}'] = e
    # разложение R1 (описательно): ИОИ = 1 − 2T + C, если самообман > 0 у обоих; доля C = ΔC / ΔИОИ
    dT = full['LR-AGREE']['T'] - full['AGREE']['T']
    dC = full['LR-AGREE']['C'] - full['AGREE']['C']
    dI = full['LR-AGREE']['ioi'] - full['AGREE']['ioi']
    both = full['LR-AGREE']['deception'] > 0 and full['AGREE']['deception'] > 0
    share_c = dC / dI if both and dI != 0 else None
    res['descr_R1_decomposition'] = dict(dT=ci_entry([r['dT'] for r in reps], dT, DESCR_LEVEL), dC=ci_entry([r['dC'] for r in reps], dC, DESCR_LEVEL),
                                         share_C=share_c, mostly_C=(None if share_c is None else bool(share_c > 0.5)),
                                         note='если самообман > 0 у обоих: ΔИОИ = −2ΔT + ΔC; «в основном от C» — ΔC / ΔИОИ > 0,5')
    for a, b in TOP_PAIRS:
        key = f'top10_sel_{a}−{b}'
        res[f'descr_{key}'] = ci_entry([r[key] for r in reps], full[a]['top10_sel']['deception'] - full[b]['top10_sel']['deception'], DESCR_LEVEL)
    # доза (описательно — все оценщики, все составы до 60 на k)
    gc = np.random.default_rng(SEED_CROWDS)
    crowds, dose = {}, {}
    for k in range(1, 5):
        allc = [tuple(sorted(c + n)) for c in itertools.combinations(clones, k) for n in itertools.combinations(nonc, CROWD - k)]
        if len(allc) > 60:
            allc = [allc[i] for i in sorted(gc.choice(len(allc), 60, replace=False))]
        crowds[k] = allc
        vals = [Z.crowd_ioi(ag, corr, logp, fam, list(c), idi, ood) for c in allc]
        dose[k] = dict(n_crowds=len(allc), **{e: float(np.mean([v[e]['ioi'] for v in vals])) for e in Z.EVALS})
        dose[k].update({f'delta_{e}': dose[k][e] - dose[k]['AGREE'] for e in Z.EVALS if e != 'AGREE'})
    res['dose_descr'] = dose
    res['dose_descr_contrast'] = {e: dose[4][f'delta_{e}'] - dose[1][f'delta_{e}'] for e in Z.EVALS if e != 'AGREE'}
    fixed = {k: (crowds[k] if len(crowds[k]) <= 12 else [crowds[k][i] for i in sorted(gc.choice(len(crowds[k]), 12, replace=False))]) for k in (1, 4)}
    # R4: точка и бутстреп по закреплённым составам
    st4 = dict(ag=ag, corr=corr, logp=logp, fam=fam, fixed=fixed)
    _init(st4)
    point4 = _dlr(4, idi, ood)[0] - _dlr(1, idi, ood)[0]
    g4 = np.random.default_rng(SEED_BD)
    draws4 = [(g4.choice(idi, len(idi)), g4.choice(ood, len(ood))) for _ in range(BD)]
    out4 = _pmap(_dose_rep, draws4, st4, workers)
    b4 = [x[0] for x in out4]
    n4 = sum(1 for x in out4 if x[1] > 0)
    res['lr_one_class'].update(dose_reps=n4, dose_share=n4 / BD)
    e4 = ci_entry(b4, point4, LEVEL)
    e4['tails'] = tails(b4, point4, LEVEL)
    e4['monte_carlo_note'] = 'граница по Монте-Карло неустойчива' if e4['tails']['unstable'] else ''
    e4['fixed_crowds'] = {k: [[names[i] for i in c] for c in v] for k, v in fixed.items()}
    e4['verdict'] = U if not method_ok else (UL if n4 > LR_FAIL_MAX * BD else verdict(*e4['ci']))
    res['R4'] = e4
    # доза, где pythia-2.8b-deduped считается клоном (описательно, только точка; без случайных чисел)
    dd = [k for k in allh if names[k] == DEDUP]
    if dd:
        cl2, nc2 = clones + dd, [k for k in nonc if k not in dd]
        E4 = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND')
        dose2 = {}
        for k in range(1, 5):
            allc = [tuple(sorted(c + n)) for c in itertools.combinations(cl2, k) for n in itertools.combinations(nc2, CROWD - k)]
            vals = [Z.crowd_ioi(ag, corr, logp, fam, list(c), idi, ood, evals=E4) for c in allc]
            dose2[k] = dict(n_crowds=len(allc), **{e: float(np.mean([v[e]['ioi'] for v in vals])) for e in E4})
            dose2[k].update({f'delta_{e}': dose2[k][e] - dose2[k]['AGREE'] for e in E4 if e != 'AGREE'})
        res['dose_dedup_as_clone_descr'] = dict(dose=dose2, contrast={e: dose2[4][f'delta_{e}'] - dose2[1][f'delta_{e}'] for e in E4 if e != 'AGREE'})
    # кросс-подгонка (описательно, только точка)
    cf = Z.crowd_ioi(ag, corr, logp, fam, allh, idi, ood, top10=True, auroc=False, S=Z.crossfit_scores(ag, corr, logp, allh, idi, ood, fam))
    res['crossfit_descr'] = dict(k=Z.CF_K, seed=Z.CF_SEED, evaluators=cf, deltas={k: cf[a]['ioi'] - cf[b]['ioi'] for k, (a, b) in pairs.items()},
                                 top10_sel={f'{a}−{b}': cf[a]['top10_sel']['deception'] - cf[b]['top10_sel']['deception'] for a, b in TOP_PAIRS})
    # коэффициенты LR-AGREE по группам пар (описательно, «из пилота», знак не предсказывался)
    co = Z.lr_coefs(ag, corr, allh, idi)

    def grp(i, o):
        if fam[i] == CLONE and fam[o] == CLONE:
            return 'клон–клон'
        if (names[i] == DEDUP and fam[o] == CLONE) or (names[o] == DEDUP and fam[i] == CLONE):
            return 'deduped–клон'
        return 'прочие'
    groups = {}
    for (i, o), w in co.items():
        groups.setdefault(grp(i, o), []).append(w)
    res['lr_coef_groups_descr'] = dict(mean={k: float(np.mean(v)) for k, v in groups.items()}, n={k: len(v) for k, v in groups.items()},
                                       main_dedup={f'{names[i]}←{names[o]}': w for (i, o), w in co.items() if {names[i], names[o]} == {CLONE, DEDUP}})
    # задачи OOD, где все головы неверны и согласны (совет 54, интуит)
    A_ = np.array([[-1 if x is None else x for x in a] for a in ans])
    wrong_all = (~corr[:, ood]).all(0)
    same_all = (A_[:, ood] == A_[0, ood][None, :]).all(0) & (A_[0, ood] >= 0)
    res['all_wrong_ood_descr'] = dict(all_wrong=float(wrong_all.mean()), all_wrong_same=float((wrong_all & same_all).mean()))
    # ПОДПИСЬ
    swi, swo = Z.same_wrong_rates(ans, corr, idi, allh), Z.same_wrong_rates(ans, corr, ood, allh)
    pp = [p for p in swi if swi[p][0] is not None and swo[p][0] is not None]
    ncp = [p for p in pp if not (fam[p[0]] == CLONE and fam[p[1]] == CLONE)]
    res['signature_descr'] = dict(all=float(spearmanr([swi[p][0] for p in pp], [swo[p][0] for p in pp]).correlation),
                                  without_clone_pairs=float(spearmanr([swi[p][0] for p in ncp], [swo[p][0] for p in ncp]).correlation),
                                  pairs={f'{names[a]}|{names[b]}': [swi[(a, b)][0], swo[(a, b)][0]] for a, b in pp})
    res['verdicts'] = {k: res[k]['verdict'] for k in ('R1', 'R2', 'R3', 'R4')}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    print('ИОИ:', {e: round(v['ioi'], 4) for e, v in full.items()})
    for k in ('R1', 'R2', 'R3', 'R4'):
        print(f"{k}: Δ {res[k]['delta']:.4f} ДИ [{res[k]['ci'][0]:.4f}, {res[k]['ci'][1]:.4f}] {res[k]['monte_carlo_note']}")
    print('LR, один класс в выборке ID:', res['lr_one_class'])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 4000
    BD = int(a[a.index('--boot-dose') + 1]) if '--boot-dose' in a else 4000
    W = int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 1)
    main(a[0], a[1], B, BD, workers=W)
