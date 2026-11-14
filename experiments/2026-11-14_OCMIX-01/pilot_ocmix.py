#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCMIX-01: разбор пилота → analysis_pilot.json. python3 pilot_ocmix.py [OUT_DIR] [--boot B]
Пилот даёт две вещи (HYPOTHESIS, «Закреплено до данных пилота»): головы теста (проверка метода) и мощность.
  1. Головы: точность ID / OOD, верные и неверные на каждом участке, доля ответов без числа, проверка метода
     (не меньше 20 верных и 20 неверных на ID и на OOD, ответов без числа не больше 5 %); толпа годна, если прошло не меньше 6.
  2. Полный набор прошедших голов: ИОИ, верхушка (top10_sel и top10_all), AUROC пяти оценщиков (analyze_ocmix.crowd).
  3. Вложенный бутстреп (B повторов, зерно 1316): выборка ID с возвращением (переподгонка LR-AGREE, MIX-LR и калибровки),
     затем выборка OOD. Разности: H1 — самообман верхушки VETO − LR-AGREE; H2 — ИОИ VETO − CONF; H3 — ИОИ LR-AGREE − AGREE;
     описательно — MIX-LR против VETO, верхушка VETO против CONF и MIX-LR против LR-AGREE, ИОИ VETO против LR-AGREE и AGREE.
     Интервалы 99 %: процентильный и BC."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_ocmix as M  # noqa: E402

MIN_EACH, MAX_NONE, MIN_HEADS = 20, 0.05, 6
SEED_BOOT = 1316
DELTAS = {'H1': ('top', 'VETO', 'LR-AGREE'), 'H2': ('ioi', 'VETO', 'CONF'), 'H3': ('ioi', 'LR-AGREE', 'AGREE'),
          'MIX−VETO': ('ioi', 'MIX-LR', 'VETO'), 'MIXtop−VETOtop': ('top', 'MIX-LR', 'VETO'), 'VETOtop−CONFtop': ('top', 'VETO', 'CONF'),
          'MIXtop−LRtop': ('top', 'MIX-LR', 'LR-AGREE'), 'VETO−LR': ('ioi', 'VETO', 'LR-AGREE'), 'VETO−AGREE': ('ioi', 'VETO', 'AGREE')}


def val(r, kind, e):
    return r[e]['top10_sel']['deception'] if kind == 'top' else r[e]['ioi']


def main(out_dir, B=1000):
    d, heads = M.load(out_dir)
    ans, corr, rid, logp = M.arrays(d, heads)
    names = [M.label(h) for h in heads]
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
    ag = M.agree_matrix(ans)
    full = M.crowd(ag, corr, logp, keep, idi, ood, auroc=True)
    res['full'] = full
    g = np.random.default_rng(SEED_BOOT)
    bs = {k: [] for k in DELTAS}
    for _ in range(B):
        fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
        r = M.crowd(ag, corr, logp, keep, fit, cols)
        for k, (kind, a, b) in DELTAS.items():
            bs[k].append(val(r, kind, a) - val(r, kind, b))
    res['deltas'] = {}
    for k, (kind, a, b) in DELTAS.items():
        pt = val(full, kind, a) - val(full, kind, b)
        v = np.array(bs[k])
        (lo, hi), z0 = M.bc_ci(v, pt, 0.005)
        res['deltas'][k] = dict(point=float(pt), ci99=[float(x) for x in np.quantile(v, (0.005, 0.995))], ci99_bc=[lo, hi], z0=z0,
                                boot_median=float(np.median(v)), share_below_0=float(np.mean(v < 0)), B=B)
    json.dump(res, open(os.path.join(HERE, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('kept', 'design_ok', 'deltas')}, ensure_ascii=False, indent=1)[:3000])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0] if a and not a[0].startswith('--') else os.path.join(HERE, 'pilot', 'out')
    main(out, int(a[a.index('--boot') + 1]) if '--boot' in a else 1000)
