#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: просмотр пилота — ответы голов по таблицам и сводка (после platon_analyze.py).

  python3 pilot/pilot_view.py pilot/pilot_a_an.json
"""
import json
import sys

d = json.load(open(sys.argv[1], encoding='utf-8'))
for t in d['tables']:
    hs = []
    for h in t['heads']:
        k = h.get('kind')
        if k == 'EXPR':
            hs.append(f"{h.get('raw')!s:<28.28} c{h.get('confidence')} R{h.get('R_shown', 0) or 0:.2f}"
                      f"{' ✓' if h.get('holds') else ' ✗'}{' канон' if h.get('is_canonical') else ''}")
        else:
            hs.append(f"{k}{(' ' + str(h.get('raw'))[:20]) if k not in ('NONE', 'LOST', 'NO_RECORD') else ''}"
                      f"{(' c' + str(h.get('confidence'))) if h.get('confidence') is not None else ''}")
    flag = 'FC' if t['FC'] else ('TC' if t['TC'] else ('НЕТ×' + str(t['n_none']) if t['none_consensus'] else '—'))
    print(f"{t['table']:<16} {t['law']:<9} клика {t['clique_size']} {flag:<6} | " + ' | '.join(hs))
print()
for c, s in d['summary'].items():
    print(f"{c}: таблиц {s['n_tables']}, K {s['K']}, FC {s['FC']}, TC {s['TC']}, НЕТ-согласие {s['none_consensus']}, "
          f"виды {s['head_kinds']}, держится {s['claim_hold_rate']}, канон {s['claim_canonical_rate']}, "
          f"пары {s['pair_agree_rate']}, увер. {s['conf_mean_claims']}, вых {s['out_tokens_mean']}, $ {s['cost_usd_total']:.3f}")
t = d.get('tests')
if t:
    print('\nP1', t['P1'], '\nP2', t['P2'], '\nконтроль TS', t['positive_control_TC_TS'], 'TN', t['positive_control_TC_TN'],
          '\nLR_S', t['LR_S'], 'LR_N', t['LR_N'], '\nвердикт (на пилоте — ориентир):', t['verdict'])
