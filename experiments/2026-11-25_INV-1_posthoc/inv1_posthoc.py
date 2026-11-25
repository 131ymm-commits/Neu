#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ИНВ-1, пост-хок на готовых данных PLATON-01 (Haiku 5.5) и PLATON-01R (Sonnet 5.5). Новых вызовов голов нет.

Вопрос: какая доля ошибок голов видна без скрытой правды.
- Ошибка: голова выдала выражение (kind == EXPR), и оно не держится на скрытых строках (holds == False). Это правда от кода
  из зарегистрированных анализов; здесь не пересчитывается.
- Проверка без правды: R_shown >= TAU, то есть выражение не держится уже на 13 строках, которые видела сама голова.
  TAU = 0,1 — зарегистрированный порог PLATON-01; 0,05 и 0,2 — чувствительность. Нечисловое R_shown считается флагом.
Числа берутся только из run/results_*.json.
"""
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = {'haiku': ROOT / '2026-11-12_PLATON-01/run/results_platon01.json',
       'sonnet': ROOT / '2026-11-13_PLATON-01R/run/results_platon01r.json'}

def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return [round(max(0, c-h), 4), round(min(1, c+h), 4)]

def flag(h, tau):
    r = h.get('R_shown')
    return (r is None) or (not math.isfinite(r)) or (r >= tau)

def tally(heads, tau):
    ex = [h for h in heads if h.get('kind') == 'EXPR']
    err = [h for h in ex if not h.get('holds')]
    ok = [h for h in ex if h.get('holds')]
    caught = sum(flag(h, tau) for h in err)
    fa = sum(flag(h, tau) for h in ok)
    return {'heads': len(heads), 'expr': len(ex), 'errors': len(err), 'caught': caught,
            'caught_share': round(caught/len(err), 4) if err else None, 'caught_ci95': wilson(caught, len(err)),
            'correct': len(ok), 'false_alarms': fa,
            'false_alarm_share': round(fa/len(ok), 4) if ok else None, 'false_alarm_ci95': wilson(fa, len(ok)),
            'uncaught_conf_mean': (round(sum(h['confidence'] for h in err if not flag(h, tau)) /
                                         max(1, len(err)-caught), 4) if len(err) > caught else None)}

out = {'note': 'пост-хок, разведка, без предрегистрации; вердикты PLATON-01 и PLATON-01R не меняет', 'models': {}}
for name, path in SRC.items():
    r = json.load(open(path))
    regimes = {}
    for t in r['tables']:
        reg = t.get('regime')
        regimes.setdefault(reg, {}).setdefault(t['cell'], []).extend(t['heads'])
    m = {}
    for tau in (0.1, 0.05, 0.2):
        m[f'tau_{tau}'] = {}
        for reg, cells in regimes.items():
            allh = [h for hs in cells.values() for h in hs]
            T = [h for c, hs in cells.items() if c.startswith('T') for h in hs]
            Z = [h for c, hs in cells.items() if c.startswith('Z') for h in hs]
            m[f'tau_{tau}'][str(reg)] = {'all': tally(allh, tau), 'T_law_present': tally(T, tau), 'Z_no_law': tally(Z, tau),
                                         **{c: tally(hs, tau) for c, hs in sorted(cells.items())}}
    out['models'][name] = m
json.dump(out, open(Path(__file__).with_name('inv1_posthoc.json'), 'w'), ensure_ascii=False, indent=1)
for name, m in out['models'].items():
    for reg, d in m['tau_0.1'].items():
        for k in ('T_law_present', 'Z_no_law', 'all'):
            x = d[k]
            print(name, reg, k, 'expr', x['expr'], 'err', x['errors'], 'caught', x['caught'], x['caught_share'], x['caught_ci95'],
                  '| ok', x['correct'], 'fa', x['false_alarms'], x['false_alarm_share'], '| conf(uncaught)', x['uncaught_conf_mean'])
