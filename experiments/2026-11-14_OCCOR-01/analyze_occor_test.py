#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: анализ теста по PREREG. python3 analyze_occor_test.py OUT_DIR RESULT.json [--boot B] [--boot-dose BD]
OUT_DIR — вывод occor_extract.py (SPLIT = 'test'). Головы — список HEADS_TEST ниже (закреплён в PREREG по проверке метода
на пилоте), в этом порядке. Оценщики — analyze_occor (AGREE, NB-AGREE, LR-AGREE, NB-IND, FAM-AGREE, CONF).
Калибровка — изотоническая по ID; выбор головы на задаче OOD — наибольшая откалиброванная вероятность, ничья «поровну».
Бутстреп — вложенный: в каждом повторе выборка задач ID с возвращением (переподгонка NB-, LR- и NB-IND-параметров и
калибровки), затем выборка задач OOD; B повторов (по умолчанию 4000), зерно 1201. Доза — закреплённые составы толп
(до 12 на k = 1 и k = 4, зерно 1202), BD повторов (по умолчанию 1000), зерно 1203.
Интервал — бутстреп с поправкой на смещение (BC, analyze_occor.bc_ci; обычный процентильный — описательно).
Правила (уровень — LEVEL на сторону; серия из четырёх правил — не выше 4 · LEVEL):
  R1 (главное): Δ_LR = ИОИ(LR-AGREE) − ИОИ(AGREE) на полном наборе. Подтверждено — верхняя граница ДИ < 0; опровергнуто —
     нижняя > 0; иначе «не решено».
  R2: Δ_NB = ИОИ(NB-AGREE) − ИОИ(AGREE) — так же.
  R3 (специфичность): Δ_spec = ИОИ(LR-AGREE) − ИОИ(NB-IND) — так же.
  R4 (доза): Δ_LR(4) − Δ_LR(1) по толпам из 5 голов с k клонами — так же.
Проверки метода (провал любой → R1–R4 «не определено (проверка метода)»): загружены все головы HEADS_TEST; у каждой на ID
и на OOD не меньше 20 верных и 20 неверных; ответов без числа не больше 5 %; клонов не меньше 3, не-клонов не меньше 4.
Описательно (вес 0): FAM-AGREE против LR-AGREE и NB-AGREE (в обе стороны); CONF; самообман при жёстком отборе (верхние 10 %
пар); AUROC по головам; ничьи; доза для всех оценщиков; перенос долей одинаковых неверных ответов ID → OOD (ПОДПИСЬ)."""
import itertools
import json
import os
import sys

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_occor as Z  # noqa: E402

HEADS_TEST = None          # закрепляется в PREREG: список меток Z.label (модель или модель@ревизия)
LEVEL = 0.0025             # уровень на сторону (четыре правила → серия не выше 0,01); ДИ — (LEVEL, 1 − LEVEL)
CLONE, CROWD = 'pythia-2.8b', 5
MIN_EACH, MAX_NONE = 20, 0.05
SEED_B, SEED_CROWDS, SEED_BD = 1201, 1202, 1203
RULES = {'R1': ('LR-AGREE', 'AGREE'), 'R2': ('NB-AGREE', 'AGREE'), 'R3': ('LR-AGREE', 'NB-IND')}
DESCR = {'LR−FAM': ('LR-AGREE', 'FAM-AGREE'), 'NB−FAM': ('NB-AGREE', 'FAM-AGREE'), 'NB−NB-IND': ('NB-AGREE', 'NB-IND'),
         'LR−CONF': ('LR-AGREE', 'CONF'), 'AGREE−CONF': ('AGREE', 'CONF')}
U = 'не определено (проверка метода)'


def verdict(lo, hi):
    return 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не решено')


def main(out_dir, dst, B=4000, BD=1000, heads_test=None):
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
    res = dict(n_id=int(len(idi)), n_ood=int(len(ood)), heads=names, missing=missing, level=LEVEL, B=B, BD=BD,
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
    bs = {k: [] for k in pairs}
    for _ in range(B):
        fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
        r = Z.crowd_ioi(ag, corr, logp, fam, allh, fit, cols)
        for k, (a, b) in pairs.items():
            bs[k].append(r[a]['ioi'] - r[b]['ioi'])
    q = (LEVEL, 1 - LEVEL)
    for k, (a, b) in pairs.items():
        point = full[a]['ioi'] - full[b]['ioi']
        (lo, hi), z0 = Z.bc_ci(bs[k], point, LEVEL)
        e = dict(delta=point, ci=[lo, hi], ci_percentile=[float(x) for x in np.quantile(bs[k], q)], z0=z0,
                 boot_median=float(np.median(bs[k])), share_below_0=float(np.mean(np.array(bs[k]) < 0)))
        if k in RULES:
            e['verdict'] = verdict(lo, hi) if method_ok else U
        res[k if k in RULES else f'descr_{k}'] = e
    # доза
    gc = np.random.default_rng(SEED_CROWDS)
    crowds, dose = {}, {}
    for k in range(1, 5):
        allc = [tuple(sorted(c + n)) for c in itertools.combinations(clones, k) for n in itertools.combinations(nonc, CROWD - k)]
        if len(allc) > 60:
            allc = [allc[i] for i in sorted(gc.choice(len(allc), 60, replace=False))]
        crowds[k] = allc
        vals = [Z.crowd_ioi(ag, corr, logp, fam, list(c), idi, ood) for c in allc]
        dose[k] = dict(n_crowds=len(allc), **{e: float(np.mean([v[e]['ioi'] for v in vals])) for e in Z.EVALS})
    res['dose_descr'] = dose
    fixed = {k: (crowds[k] if len(crowds[k]) <= 12 else [crowds[k][i] for i in sorted(gc.choice(len(crowds[k]), 12, replace=False))]) for k in (1, 4)}

    def dlr(k, fit, cols):
        vv = [Z.crowd_ioi(ag, corr, logp, fam, list(c), fit, cols, evals=('AGREE', 'LR-AGREE')) for c in fixed[k]]
        return float(np.mean([v['LR-AGREE']['ioi'] - v['AGREE']['ioi'] for v in vv]))
    point4 = dlr(4, idi, ood) - dlr(1, idi, ood)
    g4 = np.random.default_rng(SEED_BD)
    b4 = []
    for _ in range(BD):
        fit, cols = g4.choice(idi, len(idi)), g4.choice(ood, len(ood))
        b4.append(dlr(4, fit, cols) - dlr(1, fit, cols))
    (lo, hi), z0 = Z.bc_ci(b4, point4, LEVEL)
    res['R4'] = dict(delta=point4, ci=[lo, hi], ci_percentile=[float(x) for x in np.quantile(b4, q)], z0=z0, boot_median=float(np.median(b4)),
                     share_below_0=float(np.mean(np.array(b4) < 0)), fixed_crowds={k: [[names[i] for i in c] for c in v] for k, v in fixed.items()},
                     verdict=verdict(lo, hi) if method_ok else U)
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
        print(f"{k}: Δ {res[k]['delta']:.4f} ДИ [{res[k]['ci'][0]:.4f}, {res[k]['ci'][1]:.4f}]")
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 4000
    BD = int(a[a.index('--boot-dose') + 1]) if '--boot-dose' in a else 1000
    main(a[0], a[1], B, BD)
