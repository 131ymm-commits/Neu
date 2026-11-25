#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ИНВ-1, пост-хок: разбор ошибок, НЕ видимых на своих строках (R_shown < TAU, holds == False), и сколько правды нужно на якорь.
Числа — из run/results_*.json; расчёт якоря — моделирование с фиксированным зерном."""
import json, math
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
SRC = {'haiku': ROOT / '2026-11-12_PLATON-01/run/results_platon01.json',
       'sonnet': ROOT / '2026-11-13_PLATON-01R/run/results_platon01r.json'}
TAU = 0.1
fin = lambda v: v is not None and math.isfinite(v)
out = {'tau': TAU, 'models': {}}
for name, p in SRC.items():
    r = json.load(open(p)); rows = []; ok_conf = []; err_tables = set(); all_err = 0; caught_tables = set()
    for t in r['tables']:
        for h in t['heads']:
            if h.get('kind') != 'EXPR':
                continue
            if h.get('holds'):
                ok_conf.append(h['confidence']); continue
            all_err += 1
            if fin(h.get('R_shown')) and h['R_shown'] < TAU:
                err_tables.add(t['table'])
                rows.append({'table': t['table'], 'regime': t.get('regime'), 'cell': t['cell'], 'law': t['law'], 'expr': h['expr'],
                             'conf': h['confidence'], 'R_shown': round(h['R_shown'], 4),
                             'R_in': round(h['R_in'], 4) if fin(h.get('R_in')) else None,
                             'R_out': round(h['R_out'], 4) if fin(h.get('R_out')) else None,
                             'canonical': h.get('is_canonical')})
    n = len(rows)
    in_fail = sum(1 for x in rows if not (fin(x['R_in']) and x['R_in'] < TAU))
    out_only = sum(1 for x in rows if fin(x['R_in']) and x['R_in'] < TAU)
    out['models'][name] = {
        'errors_total': all_err, 'uncaught': n, 'uncaught_tables': len(err_tables),
        'uncaught_fail_in_range': in_fail, 'uncaught_fail_only_out_of_range': out_only,
        'uncaught_conf_ge_0.5': sum(1 for x in rows if x['conf'] >= 0.5),
        'uncaught_conf_mean': round(float(np.mean([x['conf'] for x in rows])), 4) if rows else None,
        'correct_conf_mean': round(float(np.mean(ok_conf)), 4), 'correct_conf_lt_0.5': sum(1 for c in ok_conf if c < 0.5),
        'correct_total': len(ok_conf), 'by_law': {}, 'rows': rows}
    for x in rows:
        out['models'][name]['by_law'][x['law']] = out['models'][name]['by_law'].get(x['law'], 0) + 1

# Сколько правды нужно на якорь: оценка связи ошибок двух судей (фи) при доле ошибок e и истинной связи rho.
g = np.random.default_rng(20261125)
anchor = []
for e in (0.05, 0.1, 0.2):
    for rho in (0.0, 0.3, 0.6):
        p11 = e*e + rho*e*(1-e)
        probs = [p11, e-p11, e-p11, 1-2*e+p11]
        for n in (50, 100, 200, 500, 1000, 2000):
            est = []
            for _ in range(4000):
                c = g.multinomial(n, probs); a = (c[0]+c[1])/n; b = (c[0]+c[2])/n
                if a in (0, 1) or b in (0, 1):
                    continue
                est.append((c[0]/n - a*b) / math.sqrt(a*(1-a)*b*(1-b)))
            est = np.array(est)
            anchor.append({'e': e, 'rho': rho, 'n': n, 'sd_phi': round(float(est.std()), 3),
                           'undefined_share': round(1 - len(est)/4000, 3)})
out['anchor_sim'] = {'seed': 20261125, 'reps': 4000, 'grid': anchor}
json.dump(out, open(Path(__file__).with_name('inv1_uncaught.json'), 'w'), ensure_ascii=False, indent=1)
for k, m in out['models'].items():
    print(k, {a: b for a, b in m.items() if a != 'rows'})
    for x in m['rows'][:40]:
        print('  ', x['regime'], x['cell'], x['law'], x['expr'][:40], 'conf', x['conf'], 'Rs', x['R_shown'], 'Rin', x['R_in'], 'Rout', x['R_out'], x['canonical'])
print('anchor: n for sd_phi<=0.1')
for e in (0.05, 0.1, 0.2):
    for rho in (0.0, 0.3, 0.6):
        ns = [a['n'] for a in anchor if a['e'] == e and a['rho'] == rho and a['sd_phi'] <= 0.1 and a['undefined_share'] < 0.01]
        print(' e', e, 'rho', rho, 'min n', min(ns) if ns else '>2000', [(a['n'], a['sd_phi']) for a in anchor if a['e'] == e and a['rho'] == rho])
