#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ИНВ-2, пост-хок на готовых данных PLATON-01 (Haiku 5.5) и PLATON-01R (Sonnet 5.5). Новых вызовов голов нет.

Вопрос: сколько точек правды ВНЕ показанного диапазона нужно, чтобы поймать ошибки, которые сходятся на своих строках.
Правило записано до расчёта:
- утверждение головы: выражение E постоянно; c — медиана E на 13 показанных строках (Claim.c);
- масштаб s — IQR(E) на показанных строках с независимо перемешанными столбцами (знаменатель зарегистрированной меры R);
- точка x «нарушает», если |E(x) − c| / s > TAU или E(x) не число; TAU = 0,1 (зарегистрированный), 0,05 и 0,2 — чувствительность;
- проверка k точками: флаг, если нарушает хотя бы одна; k = 1, 2, 4, 8; 200 случайных наборов точек на утверждение, зерно фиксировано;
- контроль: те же k точек, но ВНУТРИ показанного диапазона (новые строки in).
Группы: «невидимые ошибки» (R_shown < 0,1 и не держится), «верные» (держится) — для ложных тревог.
Самопроверка: пересчитанный R_shown должен совпасть с записанным в results.
"""
import json, math, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '2026-11-12_PLATON-01'))
import platon_check as C
import platon_world as W

SRC = {'haiku': ROOT / '2026-11-12_PLATON-01/run', 'sonnet': ROOT / '2026-11-13_PLATON-01R/run'}
RES = {'haiku': 'results_platon01.json', 'sonnet': 'results_platon01r.json'}
TAU0, KS, DRAWS = 0.1, (1, 2, 4, 8), 200

def scale(f, shown, idents, jid):
    pts = C.rows_to_points(shown, idents)
    g = C.gen(f'R|shown|{jid}')
    perm = {k: np.concatenate([g.permutation(pts[k]) for _ in range(C.N_PERM_SHOWN)]) for k in idents}
    return C.iqr(f(pts)), C.iqr(f(perm))

out = {'rule': 'нарушение: |E(x)-c|/s > TAU или не число; флаг при хотя бы одном нарушении из k', 'draws': DRAWS, 'models': {}}
for name, rd in SRC.items():
    res = json.load(open(rd / RES[name]))
    insts, recs, maxdiff = {}, [], 0.0
    for t in res['tables']:
        key = (t['seed'], t['law'])
        if key not in insts:
            insts[key] = W.make_instance(t['seed'], t['law'], heads=len(t['heads']))
        inst = insts[key]
        idents, _, _, mp = W.table_view(inst, t['data'], t['names'])
        hin = C.rows_to_points(W.rename_rows(inst['hold'][t['data']]['in'], mp), idents)
        hout = C.rows_to_points(W.rename_rows(inst['hold'][t['data']]['out'], mp), idents)
        for k, h in enumerate(t['heads']):
            if h.get('kind') != 'EXPR':
                continue
            shown = W.table_view(inst, t['data'], t['names'], k)[2]
            cl = C.Claim(h['raw'], idents, shown, f"claim|{h['job']}")
            num, den = scale(cl.f, shown, idents, h['job'])
            if h.get('R_shown') is not None and den > 0:
                maxdiff = max(maxdiff, abs(num / den - h['R_shown']))
            err_hidden = not h.get('holds')
            seen = (h.get('R_shown') is None) or (h['R_shown'] >= TAU0)
            group = 'correct' if not err_hidden else ('error_seen' if seen else 'error_unseen')
            if group == 'error_seen' or not (den > 0 and math.isfinite(den)):
                continue
            dev = {}
            for lab, pts in (('out', hout), ('in', hin)):
                with np.errstate(all='ignore'):
                    v = cl.f(pts)
                d = np.abs(v - cl.c) / den
                dev[lab] = np.where(np.isfinite(d), d, np.inf)
            recs.append({'group': group, 'regime': t.get('regime'), 'cell': t['cell'], 'law': t['law'], 'table': t['table'], 'dev': dev})
    g = np.random.default_rng(20261125)
    idx = {k: np.array([g.choice(W.N_HOLD, size=k, replace=False) for _ in range(DRAWS)]) for k in KS}
    m = {'selfcheck_max_abs_diff_R_shown': maxdiff, 'n': {gr: sum(1 for r in recs if r['group'] == gr) for gr in ('error_unseen', 'correct')}}
    for tau in (0.1, 0.05, 0.2):
        tt = {}
        for gr in ('error_unseen', 'correct'):
            rs = [r for r in recs if r['group'] == gr]
            tt[gr] = {}
            for lab in ('out', 'in'):
                tt[gr][lab] = {}
                for k in KS:
                    p = [float(np.mean(np.any(r['dev'][lab][idx[k]] > tau, axis=1))) for r in rs]
                    tt[gr][lab][f'k{k}'] = {'mean_flag_prob': round(float(np.mean(p)), 4) if p else None,
                                             'claims_flag_prob_ge_0.95': sum(1 for x in p if x >= 0.95),
                                             'claims_flag_prob_le_0.05': sum(1 for x in p if x <= 0.05), 'n': len(p)}
                tt[gr][lab]['single_point_share'] = round(float(np.mean([np.mean(r['dev'][lab] > tau) for r in rs])), 4) if rs else None
        m[f'tau_{tau}'] = tt
    out['models'][name] = m
json.dump(out, open(Path(__file__).with_name('inv2_shift.json'), 'w'), ensure_ascii=False, indent=1)
for name, m in out['models'].items():
    print(name, 'selfcheck', m['selfcheck_max_abs_diff_R_shown'], m['n'])
    for tau in ('tau_0.1', 'tau_0.05', 'tau_0.2'):
        for gr in ('error_unseen', 'correct'):
            for lab in ('out', 'in'):
                d = m[tau][gr][lab]
                print(' ', tau, gr, lab, [d[f'k{k}']['mean_flag_prob'] for k in KS], '| ≥0.95:', [d[f'k{k}']['claims_flag_prob_ge_0.95'] for k in KS])
