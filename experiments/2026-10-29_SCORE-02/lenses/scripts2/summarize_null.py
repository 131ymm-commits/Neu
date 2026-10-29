#!/usr/bin/env python3
"""LENSES-2: сводка прогона нуля X1oc (null/*.jsonl) → печать и null/summary.json.
Для каждого файла: средний Δc и Δ по повторам (оценка «правды» заглушки), SD точечных оценок и средний SD бутстрепа, доли исходов X1oc
и X1o по букве, для подвыборки с --refit — то же при пересчёте карты на каждом пересэмпле (B = 2000) против фиксированной карты (B = 2000).
Ложный уровень при истинном Δc = 0 — линейная интерполяция доли «подтверждено» по трём s около нуля."""
import glob
import json
import math
import os

import numpy as np

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'null')
out = {}
for p in sorted(glob.glob(os.path.join(D, 'opus_s*_n*.jsonl')) + glob.glob(os.path.join(D, 'hi_s*_n*.jsonl'))):
    rs = [json.loads(l) for l in open(p)]
    if not rs:
        continue
    k = os.path.basename(p)[:-6]
    dc = np.array([r['dc'] for r in rs]); d1 = np.array([r['d1'] for r in rs])
    R = len(rs)
    rate = lambda key, val: sum(r[key] == val for r in rs) / R
    se = lambda q: math.sqrt(q * (1 - q) / R)
    o = dict(R=R, dc_mean=float(dc.mean()), dc_se=float(dc.std(ddof=1) / math.sqrt(R)), dc_sd=float(dc.std(ddof=1)),
             boot_sdc_mean=float(np.mean([r['sdc'] for r in rs])), d1_mean=float(d1.mean()), d1_sd=float(d1.std(ddof=1)),
             boot_sd1_mean=float(np.mean([r['sd1'] for r in rs])),
             x1oc_conf=rate('x1oc', 'подтверждено'), x1oc_ref=rate('x1oc', 'опровергнуто'),
             x1o_conf=rate('x1o', 'подтверждено'), x1o_ref=rate('x1o', 'опровергнуто'),
             auc=dict((s, float(np.mean([r['auc'][s] for r in rs]))) for s in ('agree', 'single', 'single_c')),
             nlev=float(np.mean([r['nlev'] for r in rs])),
             share_zero_levels=float(np.mean([sum(1 for x in r['shares'] if x == 0) for r in rs])))
    o['x1oc_conf_se'] = se(o['x1oc_conf'])
    o['both_conf'] = sum(r['x1o'] == 'подтверждено' and r['x1oc'] == 'подтверждено' for r in rs) / R
    # покрытие: доля интервалов, накрывающих средний Δc (оценка правды заглушки)
    o['x1oc_cover'] = float(np.mean([r['cic'][0] <= o['dc_mean'] <= r['cic'][1] for r in rs]))
    rr = [r for r in rs if 'cic_refit' in r]
    if rr:
        o['refit'] = dict(R=len(rr), conf_fixedB=sum(r['x1oc_fixedB'] == 'подтверждено' for r in rr) / len(rr),
                          conf_refit=sum(r['x1oc_refit'] == 'подтверждено' for r in rr) / len(rr),
                          ref_fixedB=sum(r['x1oc_fixedB'] == 'опровергнуто' for r in rr) / len(rr),
                          ref_refit=sum(r['x1oc_refit'] == 'опровергнуто' for r in rr) / len(rr),
                          sd_fixedB=float(np.mean([r['sdc_fixedB'] for r in rr])), sd_refit=float(np.mean([r['sdc_refit'] for r in rr])),
                          cover_fixedB=float(np.mean([r['cic_fixedB'][0] <= o['dc_mean'] <= r['cic_fixedB'][1] for r in rr])),
                          cover_refit=float(np.mean([r['cic_refit'][0] <= o['dc_mean'] <= r['cic_refit'][1] for r in rr])))
    out[k] = o
    print(f"{k}: R {R}; Δc {o['dc_mean']:+.4f} ± {o['dc_se']:.4f} (SD оценок {o['dc_sd']:.4f}, SD бутстрепа {o['boot_sdc_mean']:.4f}); "
          f"X1oc подтверждено {o['x1oc_conf']:.4f} ± {o['x1oc_conf_se']:.4f}, опровергнуто {o['x1oc_ref']:.4f}, покрытие {o['x1oc_cover']:.3f}; "
          f"Δ {o['d1_mean']:+.4f} (SD {o['d1_sd']:.4f}), X1o подтверждено {o['x1o_conf']:.3f}; AUC agree/single/single_c "
          f"{o['auc']['agree']:.3f}/{o['auc']['single']:.3f}/{o['auc']['single_c']:.3f}; уровней {o['nlev']:.2f}, пустых уровней single_c {o['share_zero_levels']:.2f}")
    if rr:
        f = o['refit']
        print(f"   карта фиксирована / пересчитывается (B = 2000, R {f['R']}): подтверждено {f['conf_fixedB']:.4f} / {f['conf_refit']:.4f}; "
              f"опровергнуто {f['ref_fixedB']:.4f} / {f['ref_refit']:.4f}; SD бутстрепа {f['sd_fixedB']:.4f} / {f['sd_refit']:.4f}; "
              f"покрытие {f['cover_fixedB']:.3f} / {f['cover_refit']:.3f}")
# интерполяция ложного уровня при Δc = 0 по трём s
for n in (100, 59):
    pts = sorted((out[k]['dc_mean'], out[k]['x1oc_conf'], out[k]['x1oc_ref']) for k in out if k.endswith(f'_n{n}') and k.startswith('opus_s0'))
    if len(pts) >= 2:
        x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts]); z = np.array([p[2] for p in pts])
        A = np.vstack([x, np.ones_like(x)]).T
        bc = np.linalg.lstsq(A, y, rcond=None)[0]; bz = np.linalg.lstsq(A, z, rcond=None)[0]
        out[f'interp_n{n}'] = dict(points=pts, conf_at0=float(bc[1]), ref_at0=float(bz[1]), slope_conf=float(bc[0]))
        print(f"n = {n}: доля «подтверждено» X1oc при Δc = 0 (линейно по {len(pts)} точкам) {bc[1]:.4f}; «опровергнуто» {bz[1]:.4f}; точки {[(round(a, 4), round(b, 4)) for a, b, _ in pts]}")
# «установлено» для SA_opus: в каждой выборке X1o и X1oc подтверждены (выборки независимы → произведение долей)
for pre in sorted({k.rsplit('_n', 1)[0] for k in out if '_n' in k and not k.startswith('interp')}):
    a, b = out.get(f'{pre}_n100'), out.get(f'{pre}_n59')
    if a and b:
        out[f'{pre}_status'] = dict(sa_both=a['x1o_conf'] * b['x1o_conf'], sac_both=a['x1oc_conf'] * b['x1oc_conf'], established=a['both_conf'] * b['both_conf'])
        print(f"{pre}: X1o «в обеих» {a['x1o_conf'] * b['x1o_conf']:.4f}; X1oc «в обеих» {a['x1oc_conf'] * b['x1oc_conf']:.5f}; "
              f"«установлено» (X1o и X1oc в обеих) {a['both_conf'] * b['both_conf']:.5f}")
json.dump(out, open(os.path.join(D, 'summary.json'), 'w'), ensure_ascii=False, indent=1)
