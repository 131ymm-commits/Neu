#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-02: факты отчёта из run/results_platon02.json, power02.json, журналов и аудита → facts02.json.
Ожидания E1–E6 (PREREG §8) и вес опоры (§7) ставит этот код. Запуск: python3 facts02.py [results.json] [out.json]"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'run', 'results_platon02.json')
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'facts02.json')
r3 = lambda x: None if x is None else round(float(x), 3)
p2 = lambda x: None if x is None else float(f'{x:.2g}')
ci = lambda v: None if v is None else [r3(v[0]), r3(v[1])]
d = json.load(open(src, encoding='utf-8'))
P = d['platon02']; S, T = P['summary'], P['tests']
pw = json.load(open(os.path.join(HERE, 'power02.json'), encoding='utf-8'))

cells = {k: {'n': v['n'], 'TC_Y': v['TC_Y'], 'TC_rate': r3(v['TC_Y'] / v['n']), 'TC_ci95': ci(v['TC_ci95']),
             'FC_any': v['FC_any'], 'FC_any_ci95': ci(v['FC_any_ci95']), 'FC_X': v['FC_X'], 'FC_X_ci95': ci(v['FC_X_ci95']),
             'FC_X_upper95': r3(v['FC_X_upper95']), 'rare': v['rare'], 'heads': v['heads'], 'categories': v['categories'],
             'X_share_heads': r3(v['X_share_heads']), 'X_share_ci95': ci(v['X_share_ci95_by_instance']),
             'none_consensus': v['none_consensus'], 'lost': v['lost']} for k, v in S.items()}
p3 = {k: {'b_MN_only': v['b_MN_only'], 'c_M_only': v['c_M_only'], 'p_one': p2(v['p_one_sided']), 'p_two': p2(v['p_two_sided']),
          'diff': r3(v['diff_MN_minus_M']), 'ci': ci(v['diff_ci95'])} for k, v in T['P3_descr'].items()}
tests = {'P1A': {'k': T['P1A']['k'], 'n': T['P1A']['n'], 'p': p2(T['P1A']['p']), 'rejected': T['P1A']['rejected']},
         'P2A': {'k': T['P2A']['k'], 'n': T['P2A']['n'], 'p': p2(T['P2A']['p']), 'rejected': T['P2A']['rejected']},
         'rare_A_both': T['rare_A_both'], 'valid_A': T['valid_A'], 'lost_bad_cells': T['lost_bad_cells'],
         'verdict': T['verdict'], 'verdict_P2A': T['verdict_P2A'], 'P3_descr': p3}

tabs = d['tables']
laws = sorted({t['law'] for t in tabs})
by_law = {}
for law in laws:
    row = {'layer': next(t['layer'] for t in tabs if t['law'] == law)}
    for rg in ('free', 'forced'):
        for c, nm in (('TS', 'M'), ('TN', 'MN')):
            tl = [t for t in tabs if t['law'] == law and t['regime'] == rg and t['cell'] == c]
            hs = [h for t in tl for h in t['heads']]
            row[f'{nm}_{rg}'] = {'n': len(tl), 'TC_Y': sum(t['TC'] for t in tl), 'FC_X': sum(t['FC_X'] for t in tl),
                                 'FC_any': sum(t['FC'] for t in tl), 'X_heads': sum(1 for h in hs if h.get('category') == 'X'),
                                 'NONE_heads': sum(1 for h in hs if h.get('category') == 'НЕТ')}
    by_law[law] = row

x_claims = [{'law': t['law'], 'layer': t['layer'], 'cell': t['cell'], 'regime': t['regime'], 'seed': t['seed'], 'raw': h.get('raw'),
             'confidence': h.get('confidence')} for t in tabs for h in t['heads'] if h.get('category') == 'X']
conf_by_cat = {}
for cat in ('Y', 'X', 'иное'):
    for rg in ('free', 'forced'):
        v = [h['confidence'] for t in tabs if t['regime'] == rg for h in t['heads']
             if h.get('category') == cat and h.get('confidence') is not None]
        conf_by_cat[f'{cat}_{rg}'] = {'n': len(v), 'mean': r3(sum(v) / len(v)) if v else None}
other = [{'law': t['law'], 'cell': t['cell'], 'regime': t['regime'], 'kind': h.get('kind'), 'raw': h.get('raw')}
         for t in tabs for h in t['heads'] if h.get('category') == 'иное']
other_kinds = {}
for o in other:
    other_kinds[o['kind']] = other_kinds.get(o['kind'], 0) + 1
fc_non_x = [{'law': t['law'], 'cell': t['cell'], 'regime': t['regime'], 'seed': t['seed'], 'rep_raw': t['heads'][int(t['rep'][1:]) - 1].get('raw')}
            for t in tabs if t['FC'] and not t['FC_X']]

# ожидания PREREG §8 (1 — сбылось, 0 — нет, None — не оценивается)
und = bool(T['lost_bad_cells'])
mA, mnA = S['M_free_A'], S['MN_free_A']
exp = {'E1': None if und or not T['valid_A'] else int(T['P1A']['rejected']),
       'E2': None if und or not T['valid_A'] else int(T['P2A']['rejected']),
       'E3A': None if und or not T['valid_A'] else int(T['rare_A_both']),
       'E3B': int(S['M_free_B']['FC_X'] == 0 and S['M_forced_B']['FC_X'] == 0) if 'M_free_B' in S else None,
       'E4': int(T['P3_descr']['free_A']['p_one_sided'] <= 0.05),
       'E5': int(T['valid_A']),
       'E6': int(mA['TC_Y'] >= mnA['TC_Y'])}

# вес опоры (PREREG §7)
wb = pw['weights_bits']
v = T['verdict']
if v.startswith('гипотеза подтверждена'):
    weight = {'hypothesis': r3(wb['confirm_P1A'])}
elif v.startswith('гипотеза опровергнута'):
    weight = {'hypothesis': r3(-wb['refute_narrow_A']), 'narrow_claim': r3(wb['refute_narrow_A'])}
else:
    weight = {'hypothesis': 0.0}
if T['P2A']['rejected'] and not und and T['valid_A']:
    weight['P2A_claim'] = r3(wb['confirm_P2A'])

st, fi = [], []
for p in glob.glob(os.path.join(os.path.dirname(src), 'journal', 'I*.jsonl')):
    for line in open(p, encoding='utf-8'):
        rr = json.loads(line); st.append(rr.get('started')); fi.append(rr.get('finished'))
st = [x for x in st if x]; fi = [x for x in fi if x]
Sm = d['summary']
totals = {'calls': d['heads_total'], 'lost': d['heads_lost'], 'started': min(st) if st else None, 'finished': max(fi) if fi else None,
          'out_total': sum(Sm[c]['out_tokens_total'] for c in Sm), 'cost_usd': round(sum(Sm[c]['cost_usd_total'] for c in Sm), 3),
          'out_per_call': round(sum(Sm[c]['out_tokens_total'] for c in Sm) / max(1, d['heads_total'])),
          'out_mean_by_cell': {c: round(Sm[c]['out_tokens_mean']) for c in Sm if Sm[c]['out_tokens_mean'] is not None}}
parse = [{'table': t['table'], 'raw': h.get('raw'), 'kind': h.get('kind')} for t in tabs for h in t['heads']
         if h.get('kind') in ('PARSE_ERR', 'TRIVIAL', 'INVALID')]
aud_p = os.path.join(HERE, 'audit_heads_sealed.json')
out = {'source': os.path.relpath(src, HERE), 'cells': cells, 'tests': tests, 'by_law': by_law, 'x_claims': x_claims,
       'conf_by_category': conf_by_cat, 'other_kinds': other_kinds, 'fc_not_x': fc_non_x, 'expectations': exp, 'weights_bits': weight,
       'power': {'P1A_half': pw['family']['вдвое слабее']['P1A'], 'frechet_5pct': pw['rare_reach_both_frechet']['0.05']},
       'totals': totals, 'parse_errors': parse, 'layers': P['layers'], 'lost_share': r3(P['lost_share']),
       'audit': json.load(open(aud_p, encoding='utf-8')) if os.path.exists(aud_p) and 'run' in src else None}
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('tests', 'expectations', 'weights_bits', 'totals', 'other_kinds')}, ensure_ascii=False))
for k in ('M_free_A', 'MN_free_A', 'M_forced_A', 'MN_forced_A', 'M_free_B', 'MN_free_B', 'M_forced_B', 'MN_forced_B'):
    if k in cells:
        c = cells[k]
        print(f"  {k}: TC_Y {c['TC_Y']}/{c['n']}, FC_X {c['FC_X']} (гр. {c['FC_X_upper95']}), FC {c['FC_any']}, виды {c['categories']}")
