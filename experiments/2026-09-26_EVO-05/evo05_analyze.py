# EVO-05: анализ строго по PREREG-EVO-05.md
import json, glob
import numpy as np
from scipy.stats import binom
R = {}
for f in glob.glob('runs/*.json'):
    d = json.load(open(f)); R[(d['task'], d['arm'], d['seed'])] = d
TASKS, S = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6'], range(60, 80)
v = lambda k: 'подтверждено' if k >= 74 else ('опровергнуто' if k <= 60 else 'разницы нет')
def wins(b, w, m):
    return sum(R[(t, b, s)][m] < R[(t, w, s)][m] for t in TASKS for s in S)
def cmp(b, w, m):
    k = wins(b, w, m); d = [R[(t, w, s)][m] - R[(t, b, s)][m] for t in TASKS for s in S]
    return dict(wins=k, reverse_wins=wins(w, b, m), verdict=v(k), median_gain=float(np.median(d)), sign_p=float(binom.sf(k - 1, 120, .5)))
out = {}
out['P1'] = cmp('HEAD', 'BASE', 'deception'); base_ign = wins('BASE', 'HEAD', 'ignorance')
out['P1']['gate_BASE_wins_ignorance'] = base_ign
out['P1']['reading'] = ('голова знает, что не знает' if base_ign <= 73 else 'самообман мал, потому что голова ничего не вырастила') if out['P1']['verdict'] == 'подтверждено' else '—'
out['P2'] = cmp('HEAD_LCB', 'HEAD', 'ioi'); out['P3'] = cmp('HEAD_LCB', 'R80', 'ioi')
out['P4'] = dict(HEAD_vs_BASE_ioi=cmp('HEAD', 'BASE', 'ioi'), HEAD_vs_BASE_ign=cmp('HEAD', 'BASE', 'ignorance'),
                 skill={a: dict(head=float(np.nanmedian([R[(t, a, s)]['head_mae_hidden'] or np.nan for t in TASKS for s in S])),
                                base=float(np.nanmedian([R[(t, a, s)]['base_mae_hidden'] or np.nan for t in TASKS for s in S])),
                                bias_top=float(np.nanmedian([R[(t, a, s)]['head_bias_hidden_top'] if R[(t, a, s)]['head_bias_hidden_top'] is not None else np.nan for t in TASKS for s in S])))
                        for a in ('HEAD', 'HEAD_LCB')},
                 table={f'{t}/{a}': {k: float(np.median([R[(t, a, s)][k] for s in S])) for k in ('ioi', 'ignorance', 'deception', 'final_true')}
                        for t in TASKS for a in ('BASE', 'R80', 'HEAD', 'HEAD_LCB')},
                 spread={a: float(np.mean([np.std([R[(t, a, s)]['final_true'] for s in S]) for t in TASKS])) for a in ('BASE', 'R80', 'HEAD', 'HEAD_LCB')})
json.dump(out, open('evo05_results.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('P1', 'P2', 'P3')}, ensure_ascii=False, indent=1))
print(json.dumps({k: out['P4'][k] for k in ('HEAD_vs_BASE_ioi', 'HEAD_vs_BASE_ign', 'skill', 'spread')}, ensure_ascii=False, indent=1))
for k, x in out['P4']['table'].items(): print(f"{k:12s} ИОИ {x['ioi']:.3f} незнание {x['ignorance']:.3f} самообман {x['deception']:.3f} итог {x['final_true']:.3f}")
