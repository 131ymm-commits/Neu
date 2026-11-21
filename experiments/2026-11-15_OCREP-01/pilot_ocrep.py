#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCREP-01: разбор пилота → analysis_pilot.json. python3 pilot_ocrep.py [OUT_DIR] [--boot B]
Пилот даёт три вещи (HYPOTHESIS, «Закреплено до данных пилота»): головы теста (проверка метода), мощность и решение по
условию включения R3 (самообман верхушки AGREE > 0,15 и мощность R3 ≥ 0,8 — считается в power_ocrep.py).
  1. Головы: точность, верные и неверные на ID и OOD, доля ответов без числа, проверка метода (≥ 20 и ≥ 20, ≤ 5 %; голов ≥ 6).
  2. Полный набор прошедших голов: ИОИ, верхушка (top10_sel, top10_all), AUROC восьми оценщиков (analyze_ocrep.crowd).
  3. Вложенный бутстреп (B повторов, зерно 1416): разности R1 — ИОИ LR-AGREE − AGREE, R2 — ИОИ LR-AGREE − NB-IND, R3 —
     самообман верхушки VETO − LR-AGREE; описательно — NB-AGREE − AGREE, FAM-AGREE − AGREE, MIX-LR − LR-AGREE, CONF − LR-AGREE.
     Интервалы 99 %: процентильный и BC."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocrep as Q  # noqa: E402

MIN_EACH, MAX_NONE, MIN_HEADS = 20, 0.05, 6
SEED_BOOT = 1416
BOOT_EVALS = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE', 'CONF', 'VETO', 'MIX-LR')
DELTAS = {'R1': ('ioi', 'LR-AGREE', 'AGREE'), 'R2': ('ioi', 'LR-AGREE', 'NB-IND'), 'R3': ('top', 'VETO', 'LR-AGREE'),
          'NB−AGREE': ('ioi', 'NB-AGREE', 'AGREE'), 'FAM−AGREE': ('ioi', 'FAM-AGREE', 'AGREE'), 'MIX−LR': ('ioi', 'MIX-LR', 'LR-AGREE'),
          'CONF−LR': ('ioi', 'CONF', 'LR-AGREE')}


def val(r, kind, e):
    return r[e]['top10_sel']['deception'] if kind == 'top' else r[e]['ioi']


def main(out_dir, B=1000):
    d, heads = Q.load(out_dir)
    ans, corr, rid, logp = Q.arrays(d, heads)
    names = [Q.label(h) for h in heads]
    fam_all = [Q.family(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    res = dict(n_id=int(len(idi)), n_ood=int(len(ood)), errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h])
    H = {}
    for k in range(len(heads)):
        none = float(np.mean([a is None for a in ans[k]]))
        cnt = {r: dict(correct=int(corr[k][m].sum()), wrong=int((~corr[k][m]).sum())) for r, m in (('ID', rid), ('OOD', ~rid))}
        ok = all(v['correct'] >= MIN_EACH and v['wrong'] >= MIN_EACH for v in cnt.values()) and none <= MAX_NONE
        H[names[k]] = dict(acc_id=float(corr[k][rid].mean()), acc_ood=float(corr[k][~rid].mean()), none_frac=none, counts=cnt, method_ok=bool(ok))
    res['heads'] = H
    keep = [k for k in range(len(heads)) if H[names[k]]['method_ok']]
    res['kept'] = [names[k] for k in keep]
    res['design_ok'] = len(keep) >= MIN_HEADS
    if not res['design_ok']:
        json.dump(res, open(os.path.join(HERE, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('ПРОВЕРКА ПОСТАНОВКИ НЕ ПРОЙДЕНА: голов', len(keep)); return res
    ag = Q.agree_matrix(ans)
    full = Q.crowd(ag, corr, logp, fam_all, keep, idi, ood, auroc=True)
    res['full'] = full
    g = np.random.default_rng(SEED_BOOT)
    bs = {k: [] for k in DELTAS}
    for _ in range(B):
        fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
        r = Q.crowd(ag, corr, logp, fam_all, keep, fit, cols, evals=BOOT_EVALS)
        for k, (kind, a, b) in DELTAS.items():
            bs[k].append(val(r, kind, a) - val(r, kind, b))
    res['deltas'] = {}
    for k, (kind, a, b) in DELTAS.items():
        pt = val(full, kind, a) - val(full, kind, b)
        v = np.array(bs[k])
        (lo, hi), z0 = Q.bc_ci(v, pt, 0.005)
        res['deltas'][k] = dict(point=float(pt), ci99=[float(x) for x in np.quantile(v, (0.005, 0.995))], ci99_bc=[lo, hi], z0=z0,
                                boot_median=float(np.median(v)), share_below_0=float(np.mean(v < 0)), B=B)
    res['agree_top10_sel_deception'] = full['AGREE']['top10_sel']['deception']
    json.dump(res, open(os.path.join(HERE, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('kept', 'design_ok', 'agree_top10_sel_deception', 'deltas')}, ensure_ascii=False, indent=1)[:3000])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0] if a and not a[0].startswith('--') else os.path.join(HERE, 'pilot', 'out')
    main(out, int(a[a.index('--boot') + 1]) if '--boot' in a else 1000)
