#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: разбор пилота → analysis_pilot.json. python3 pilot_occor.py [OUT_DIR] [--boot B] [--boot-dose BD]
Пилот даёт две вещи (HYPOTHESIS, «Закреплено до данных пилота»): проверку метода (какие головы идут в тест) и мощность.
  1. Головы: точность ID / OOD, доля ответов без числа, число токенов ответа, проверка метода.
  2. Клоны: доля одинаковых ответов у пар чекпойнтов pythia-2.8b; доли одинаковых неверных ответов (ID, OOD) у всех пар,
     ранговая корреляция ID → OOD (все пары и без пар клон–клон).
  3. Полный набор прошедших голов: ИОИ пяти оценщиков; вложенный бутстреп (выборка ID с возвращением, переподгонка
     NB- и LR-параметров и калибровки, выборка OOD) для разностей NB-AGREE и LR-AGREE с AGREE, NB-IND и FAM-AGREE.
  4. Доза: толпы из 5 голов с k клонами (k = 1…4); Δ(k) = ИОИ(NB-AGREE или LR-AGREE) − ИОИ(AGREE), среднее по составам (все составы,
     если их не больше 60, иначе 60 случайных, зерно 1115); бутстреп Δ(4) − Δ(1) по закреплённым составам (до 12 на k)."""
import itertools
import json
import os
import sys

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_occor as Z  # noqa: E402

CLONE = 'pythia-2.8b'
MIN_EACH, MAX_NONE = 20, 0.05
CROWD, SEED_CROWDS, SEED_BOOT = 5, 1115, 1116


def ci(x, q=(0.005, 0.995)):
    return [float(v) for v in np.quantile(x, q)]


def main(out_dir, B=1000, BD=300):
    d, heads = Z.load(out_dir)
    ans, corr, rid, logp = Z.arrays(d, heads)
    names = [Z.label(h) for h in heads]
    fam_all = [Z.family(h) for h in heads]
    idi, ood = np.nonzero(rid)[0], np.nonzero(~rid)[0]
    res = dict(n_id=int(len(idi)), n_ood=int(len(ood)), errors=[f"{h['model']}@{h['revision']}: {h['error']}" for h in d['heads'] if 'error' in h])
    # 1. головы
    H = {}
    for k, h in enumerate(heads):
        none = float(np.mean([a is None for a in ans[k]]))
        cnt = {r: dict(correct=int(corr[k][m].sum()), wrong=int((~corr[k][m]).sum())) for r, m in (('ID', rid), ('OOD', ~rid))}
        ok = all(v['correct'] >= MIN_EACH and v['wrong'] >= MIN_EACH for v in cnt.values()) and none <= MAX_NONE
        H[names[k]] = dict(acc_id=float(corr[k][rid].mean()), acc_ood=float(corr[k][~rid].mean()), none_frac=none, counts=cnt,
                           n_tok=dict(zip(*[x.tolist() for x in np.unique([r['n_tok'] for r in heads[k]['rows']], return_counts=True)])),
                           method_ok=bool(ok), clone=fam_all[k] == CLONE, seconds=heads[k].get('seconds'))
    res['heads'] = H
    keep = [k for k in range(len(heads)) if H[names[k]]['method_ok']]
    clones = [k for k in keep if fam_all[k] == CLONE]
    nonc = [k for k in keep if fam_all[k] != CLONE]
    res['kept'] = [names[k] for k in keep]
    res['clones_kept'], res['nonclones_kept'] = [names[k] for k in clones], [names[k] for k in nonc]
    res['design_ok'] = len(clones) >= 3 and len(nonc) >= 4
    # 2. клоны и общие ошибки
    ag = Z.agree_matrix(ans)
    res['clone_answer_identity'] = {f'{names[a]}|{names[b]}': float(ag[a, b].mean()) for a, b in itertools.combinations(clones, 2)}
    swi, swo = Z.same_wrong_rates(ans, corr, idi, keep), Z.same_wrong_rates(ans, corr, ood, keep)
    pairs = [p for p in swi if swi[p][0] is not None and swo[p][0] is not None]
    res['same_wrong'] = {f'{names[a]}|{names[b]}': dict(id=swi[(a, b)][0], ood=swo[(a, b)][0], n_id=swi[(a, b)][1], n_ood=swo[(a, b)][1])
                         for a, b in pairs}
    nc_pairs = [p for p in pairs if not (fam_all[p[0]] == CLONE and fam_all[p[1]] == CLONE)]
    res['signature_spearman'] = dict(all=float(spearmanr([swi[p][0] for p in pairs], [swo[p][0] for p in pairs]).correlation),
                                     without_clone_pairs=float(spearmanr([swi[p][0] for p in nc_pairs], [swo[p][0] for p in nc_pairs]).correlation),
                                     n_pairs=len(pairs), n_pairs_without=len(nc_pairs))
    if not res['design_ok']:
        json.dump(res, open(os.path.join(HERE, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('ПРОВЕРКА ПОСТАНОВКИ НЕ ПРОЙДЕНА: клонов', len(clones), 'не-клонов', len(nonc)); return res
    fam = fam_all
    # 3. полный набор
    full = Z.crowd_ioi(ag, corr, logp, fam, keep, idi, ood, top10=True)
    res['full'] = {e: {k: v for k, v in r.items()} for e, r in full.items()}
    g = np.random.default_rng(SEED_BOOT)
    D = {'NB-AGREE−AGREE': [], 'LR-AGREE−AGREE': [], 'NB-AGREE−NB-IND': [], 'LR-AGREE−NB-IND': [], 'NB-AGREE−FAM-AGREE': [],
         'LR-AGREE−FAM-AGREE': []}
    for _ in range(B):
        fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
        r = Z.crowd_ioi(ag, corr, logp, fam, keep, fit, cols, evals=('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE'))
        for key in D:
            a, b = key.split('−')
            D[key].append(r[a]['ioi'] - r[b]['ioi'])
    res['full_delta'] = {k: dict(point=full[k.split('−')[0]]['ioi'] - full[k.split('−')[1]]['ioi'], ci99=ci(v), ci95=ci(v, (0.025, 0.975)),
                                 share_below_0=float(np.mean(np.array(v) < 0)), B=B) for k, v in D.items()}
    # 4. доза
    gc = np.random.default_rng(SEED_CROWDS)
    crowds = {}
    for k in range(1, 5):
        allc = [tuple(sorted(c + n)) for c in itertools.combinations(clones, k) for n in itertools.combinations(nonc, CROWD - k)]
        if len(allc) > 60:
            allc = [allc[i] for i in sorted(gc.choice(len(allc), 60, replace=False))]
        crowds[k] = allc
    dose = {}
    for k, cl in crowds.items():
        E5 = ('AGREE', 'NB-AGREE', 'LR-AGREE', 'NB-IND', 'FAM-AGREE')
        vals = [Z.crowd_ioi(ag, corr, logp, fam, list(c), idi, ood, evals=E5) for c in cl]
        dose[k] = dict(n_crowds=len(cl), **{f'{e}': float(np.mean([v[e]['ioi'] for v in vals])) for e in E5})
        dose[k]['delta_nb_agree'] = dose[k]['NB-AGREE'] - dose[k]['AGREE']
        dose[k]['delta_lr_agree'] = dose[k]['LR-AGREE'] - dose[k]['AGREE']
    res['dose'] = dose
    fixed = {k: (cl if len(cl) <= 12 else [cl[i] for i in sorted(gc.choice(len(cl), 12, replace=False))]) for k, cl in crowds.items() if k in (1, 4)}
    bs = []
    for _ in range(BD):
        fit, cols = g.choice(idi, len(idi)), g.choice(ood, len(ood))
        dk = {}
        for k in (1, 4):
            vv = [Z.crowd_ioi(ag, corr, logp, fam, list(c), fit, cols, evals=('AGREE', 'NB-AGREE', 'LR-AGREE')) for c in fixed[k]]
            dk[k] = (np.mean([v['NB-AGREE']['ioi'] - v['AGREE']['ioi'] for v in vv]), np.mean([v['LR-AGREE']['ioi'] - v['AGREE']['ioi'] for v in vv]))
        bs.append((dk[4][0] - dk[1][0], dk[4][1] - dk[1][1]))
    bs = np.array(bs)
    res['dose_contrast'] = {name: dict(point=dose[4][key] - dose[1][key], ci99=ci(bs[:, c]), ci95=ci(bs[:, c], (0.025, 0.975)),
                                       share_below_0=float(np.mean(bs[:, c] < 0)), B=BD, fixed_crowds={k: len(v) for k, v in fixed.items()})
                            for c, (name, key) in enumerate((('NB-AGREE', 'delta_nb_agree'), ('LR-AGREE', 'delta_lr_agree')))}
    json.dump(res, open(os.path.join(HERE, 'analysis_pilot.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('kept', 'design_ok', 'signature_spearman', 'full_delta', 'dose', 'dose_contrast')}, ensure_ascii=False, indent=1)[:4000])
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0] if a and not a[0].startswith('--') else os.path.join(HERE, 'pilot', 'out')
    B = int(a[a.index('--boot') + 1]) if '--boot' in a else 1000
    BD = int(a[a.index('--boot-dose') + 1]) if '--boot-dose' in a else 300
    main(out, B, BD)
