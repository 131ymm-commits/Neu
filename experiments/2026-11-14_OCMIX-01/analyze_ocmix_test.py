#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: анализ теста по PREREG. python3 analyze_ocmix_test.py OUT_DIR RESULT.json [--boot B] [--workers W]
OUT_DIR — вывод ocmix_extract_test.py (SPLIT = 'test'). Головы — список HEADS_TEST ниже (закреплён в PREREG по проверке
метода на пилоте). Оценщики — analyze_ocmix (AGREE, LR-AGREE, CONF — код OCCOR-01; VETO, MIX-LR — по HYPOTHESIS).
Калибровка — изотоническая по ID; выбор головы на задаче OOD — наибольшая откалиброванная вероятность, ничья «поровну»;
верхушка — 10 % выбранных ответов (top10_sel, граничный блок ничьих дробно).
Бутстреп — вложенный: в каждом повторе выборка задач ID с возвращением (переподгонка LR-AGREE, MIX-LR и калибровки), затем
выборка задач OOD; B повторов (по умолчанию 4000), зерно 1301. Выборки делаются заранее в главном процессе; счёт — в
нескольких процессах (один поток BLAS на процесс), результат от их числа не зависит.
Интервал — бутстреп с поправкой на смещение (BC, analyze_occor.bc_ci; процентильный — описательно).
Правила (уровень — LEVEL на сторону; ложное «подтверждено» по серии из трёх правил — не выше 3 · LEVEL):
  R1 (главное): D1 = самообман верхушки (top10_sel.deception) VETO − LR-AGREE. Подтверждено — верхняя граница ДИ < 0;
     опровергнуто — нижняя > 0; иначе «не решено».
  R2: D2 = ИОИ(VETO) − ИОИ(CONF) — так же.
  R3: D3 = ИОИ(LR-AGREE) − ИОИ(AGREE) — повтор C-086 на свежем сдвиге — так же.
Проверки метода (провал любой → R1–R3 «не определено (проверка метода)»): загружены все головы HEADS_TEST; у каждой на ID
и на OOD не меньше 20 верных и 20 неверных; ответов без числа не больше 5 %; голов не меньше 6.
Защита LR: если повторов, где у какой-то головы в выборке ID один класс, больше 1 %, правила с LR-AGREE (R1, R3) — «не решено».
Хвосты BC: для каждого правила — число повторов за каждой границей и интервалы по двум половинам повторов; если половины
дают разный вердикт — пометка «граница по Монте-Карло неустойчива» (вердикт не меняет).
Описательно (вес 0, без вердикта, в серию не входит; интервалы — BC 99 %): MIX-LR против VETO (ИОИ и верхушка), MIX-LR
против LR-AGREE (верхушка), VETO против CONF (верхушка), VETO против LR-AGREE и AGREE (ИОИ); разложение R2 на ΔT и ΔC;
доля поддержанных выбранных ответов VETO; кросс-подгонка LR-AGREE и MIX-LR (только точка); AUROC; верхушка по всем парам."""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocmix as M  # noqa: E402

HEADS_TEST = ['pythia-1.4b', 'pythia-1.4b-deduped', 'pythia-2.8b', 'pythia-2.8b@step133000', 'pythia-2.8b@step123000',
              'pythia-2.8b@step113000', 'pythia-2.8b-deduped', 'pythia-6.9b', 'pythia-6.9b-deduped']
# ↑ закреплено в PREREG-OCMIX-01 §2: все девять голов прошли проверку метода на пилоте
LEVEL = 0.0025
DESCR_LEVEL = 0.005
MIN_EACH, MAX_NONE, MIN_HEADS = 20, 0.05, 6
SEED_B = 1301
LR_FAIL_MAX = 0.01
RULES = {'R1': ('top', 'VETO', 'LR-AGREE'), 'R2': ('ioi', 'VETO', 'CONF'), 'R3': ('ioi', 'LR-AGREE', 'AGREE')}
LR_RULES = ('R1', 'R3')
DESCR = {'MIX−VETO': ('ioi', 'MIX-LR', 'VETO'), 'MIXtop−VETOtop': ('top', 'MIX-LR', 'VETO'), 'MIXtop−LRtop': ('top', 'MIX-LR', 'LR-AGREE'),
         'VETOtop−CONFtop': ('top', 'VETO', 'CONF'), 'VETO−LR': ('ioi', 'VETO', 'LR-AGREE'), 'VETO−AGREE': ('ioi', 'VETO', 'AGREE'),
         'R2_dT': ('T', 'VETO', 'CONF'), 'R2_dC': ('C', 'VETO', 'CONF')}
U = 'не определено (проверка метода)'
UL = 'не решено (LR: один класс в выборке ID больше чем в 1 % повторов)'


def val(r, kind, e):
    return r[e]['top10_sel']['deception'] if kind == 'top' else r[e][{'ioi': 'ioi', 'T': 'T', 'C': 'C'}[kind]]


def verdict(lo, hi):
    return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')


def ci_entry(boot, point, level):
    b = np.asarray(boot, float)
    (lo, hi), z0 = M.bc_ci(b, point, level)
    return dict(delta=float(point), ci=[lo, hi], ci_percentile=[float(x) for x in np.quantile(b, (level, 1 - level))], z0=z0,
                boot_median=float(np.median(b)), share_below_0=float(np.mean(b < 0)), level=level)


def tails(boot, point, level):
    b = np.asarray(boot, float)
    (lo, hi), _ = M.bc_ci(b, point, level)
    h = len(b) // 2
    halves = [M.bc_ci(b[:h], point, level)[0], M.bc_ci(b[h:], point, level)[0]]
    vh = [verdict(*x) for x in halves]
    return dict(n_below_lo=int((b < lo).sum()), n_above_hi=int((b > hi).sum()), halves=halves, verdict_halves=vh, unstable=bool(vh[0] != vh[1]))


_ST = {}


def _init(st):
    _ST.clear()
    _ST.update(st)


def _init_worker(st):
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)
    _init(st)


def _pmap(fn, items, st, workers):
    if workers <= 1:
        _init(st)
        return [fn(x) for x in items]
    with mp.get_context('fork').Pool(workers, initializer=_init_worker, initargs=(st,)) as pool:
        return pool.map(fn, items, chunksize=max(1, len(items) // (8 * workers)))


def _rep(fc):
    s = _ST
    r = M.crowd(s['ag'], s['corr'], s['logp'], s['allh'], fc[0], fc[1])
    out = {k: val(r, kind, a) - val(r, kind, b) for k, (kind, a, b) in {**RULES, **DESCR}.items()}
    out['lr_one_class'] = r['LR-AGREE']['lr_one_class']
    return out


def main(out_dir, dst, B=4000, heads_test=None, workers=1):
    d, heads_all = M.load(out_dir)
    want = heads_test or HEADS_TEST or [M.label(h) for h in heads_all]
    by = {M.label(h): h for h in heads_all}
    missing = [w for w in want if w not in by]
    heads = [by[w] for w in want if w in by]
    ans, corr, rid, logp = M.arrays(d, heads)
    names = [M.label(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    allh = list(range(len(heads)))
    res = dict(split=d.get('split'), n_id=int(len(idi)), n_ood=int(len(ood)), heads=names, missing=missing, level=LEVEL,
               descr_level=DESCR_LEVEL, B=B, top10_main='top10_sel',
               errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h])
    counts = {}
    for k in allh:
        counts[names[k]] = dict(id_correct=int(corr[k][rid].sum()), id_wrong=int((~corr[k][rid]).sum()),
                                ood_correct=int(corr[k][~rid].sum()), ood_wrong=int((~corr[k][~rid]).sum()),
                                none_frac=float(np.mean([a is None for a in ans[k]])))
    method_ok = (not missing and len(heads) >= MIN_HEADS and all(min(v['id_correct'], v['id_wrong'], v['ood_correct'], v['ood_wrong']) >= MIN_EACH
                                                                and v['none_frac'] <= MAX_NONE for v in counts.values()))
    res['method'] = dict(ok=bool(method_ok), counts=counts, n_heads=len(heads))
    res['accuracy'] = {names[k]: dict(id=float(corr[k][rid].mean()), ood=float(corr[k][~rid].mean())) for k in allh}
    ag = M.agree_matrix(ans)
    full = M.crowd(ag, corr, logp, allh, idi, ood, auroc=True)
    res['evaluators'] = full
    g = np.random.default_rng(SEED_B)
    draws = [(g.choice(idi, len(idi)), g.choice(ood, len(ood))) for _ in range(B)]
    reps = _pmap(_rep, draws, dict(ag=ag, corr=corr, logp=logp, allh=allh), workers)
    n_fail = sum(1 for r in reps if r['lr_one_class'] > 0)
    res['lr_one_class'] = dict(reps=n_fail, share=n_fail / B)
    lr_bad = n_fail > LR_FAIL_MAX * B
    for k, (kind, a, b) in {**RULES, **DESCR}.items():
        bk = [r[k] for r in reps]
        e = ci_entry(bk, val(full, kind, a) - val(full, kind, b), LEVEL if k in RULES else DESCR_LEVEL)
        if k in RULES:
            e['tails'] = tails(bk, e['delta'], LEVEL)
            e['monte_carlo_note'] = 'граница по Монте-Карло неустойчива' if e['tails']['unstable'] else ''
            e['verdict'] = U if not method_ok else (UL if (k in LR_RULES and lr_bad) else verdict(*e['ci']))
        res[k if k in RULES else f'descr_{k}'] = e
    cf = M.crowd(ag, corr, logp, allh, idi, ood, S=M.crossfit_scores(ag, corr, logp, allh, idi, ood))
    res['crossfit_descr'] = dict(k=M.CF_K, seed=M.CF_SEED, evaluators=cf,
                                 rules={k: val(cf, kind, a) - val(cf, kind, b) for k, (kind, a, b) in RULES.items()})
    res['verdicts'] = {k: res[k]['verdict'] for k in RULES}
    res['verdict'] = '; '.join(f'{k}: {v}' for k, v in res['verdicts'].items())
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    print('ИОИ:', {e: round(v['ioi'], 4) for e, v in full.items()})
    print('верхушка:', {e: round(v['top10_sel']['deception'], 4) for e, v in full.items()})
    for k in RULES:
        print(f"{k}: Δ {res[k]['delta']:.4f} ДИ [{res[k]['ci'][0]:.4f}, {res[k]['ci'][1]:.4f}] {res[k]['monte_carlo_note']}")
    print('LR, один класс в выборке ID:', res['lr_one_class'])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 4000
    W = int(a[a.index('--workers') + 1]) if '--workers' in a else (os.cpu_count() or 1)
    main(a[0], a[1], B, workers=W)
