#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01R: факты отчёта из run/results_platon01r.json, replication_r.json и журналов → facts_r.json."""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
r3 = lambda x: None if x is None else round(float(x), 3)
p2 = lambda x: None if x is None else float(f'{x:.2g}')
ci = lambda v: None if v is None else [r3(v[0]), r3(v[1])]
d = json.load(open(os.path.join(HERE, 'run', 'results_platon01r.json'), encoding='utf-8'))
S, t, f, rc, cr = d['summary'], d['tests'], d['tests_forced'], d['regime_cmp'], d['conf_rule_forced']
cells = {c: {'K': x['K'], 'FC': x['FC'], 'FC_ci95': ci(x['FC_ci95']), 'TC': x['TC'], 'TC_ci95': ci(x['TC_ci95']),
             'none_share': r3(x['none_share_mean']), 'kinds': x['head_kinds'], 'hold': r3(x['claim_hold_rate']),
             'canon': r3(x['claim_canonical_rate']), 'conf': r3(x['conf_mean_claims']), 'FC_conf': x['FC_conf'],
             'TC_conf': x['TC_conf'], 'FC_conf005': x['FC_conf005'], 'rep_canon_K': x['rep_canonical_among_K'],
             'out_mean': round(x['out_tokens_mean']), 'cost': round(x['cost_usd_total'], 4)} for c, x in S.items()}
tests = {'holm_p': {k: p2(v) for k, v in d['holm_family']['p_values'].items()}, 'holm': d['holm_family']['rejected'],
         'free': {'verdict': t['verdict'], 'upper_ZS': r3(t['equivalence_upper95_ZS']), 'upper_ZN': r3(t['equivalence_upper95_ZN']),
                  'P3': {'b': t['P3']['b_TS_only'], 'c': t['P3']['c_TN_only'], 'p': p2(t['P3']['p_one_sided']),
                         'TC_TS': r3(t['P3']['TC_TS']), 'TC_TN': r3(t['P3']['TC_TN']), 'diff': r3(t['P3']['diff_TC_TS_minus_TN']),
                         'ci': ci(t['P3']['diff_ci95_boot']), 'ci_law': ci(t['P3']['diff_ci95_boot_by_law'])},
                  'refusal': {k: {'mean': r3(v['mean_Z_minus_T']), 'ci': ci(v['ci95_boot']), 'ci_law': ci(v['ci95_boot_by_law']),
                                  'disc': v['discriminating_lower_ge_0.5']} for k, v in t['refusal_Z_minus_T'].items()}},
         'forced': {'verdict': f['verdict'], 'P1F': {'k': f['P1']['k'], 'rate': r3(f['P1']['FC_ZS']), 'ci': ci(f['P1']['ci95']),
                                                     'p': p2(f['P1']['p_one_sided'])},
                    'P2F': {'b': f['P2']['b_ZS_only'], 'c': f['P2']['c_ZN_only'], 'p': p2(f['P2']['p_one_sided']),
                            'FC_ZN': r3(f['P2']['FC_ZN']), 'diff': r3(f['P2']['diff_FC_ZS_minus_ZN']), 'ci': ci(f['P2']['diff_ci95_boot']),
                            'ci_law': ci(f['P2']['diff_ci95_boot_by_law'])},
                    'IOI_TN': {k: r3(v) for k, v in f['IOI_TN'].items()}, 'deception_Z': {k: r3(v) for k, v in f['deception_Z'].items()}},
         'P4': {'b': rc['b_forced_only'], 'c': rc['c_free_only'], 'p': p2(rc['p_one_sided_mcnemar']),
                'diff': r3(rc['FC_ZS_forced'] - rc['FC_ZS_free']), 'ci': ci(rc['diff_ci95_boot'])},
         'rule_C': {'FC_conf': cr['FC_conf_ZS'], 'upper': r3(cr['upper95_one_sided']), 'TC_conf_TS': r3(cr['TC_conf_TS']),
                    'verdict': cr['verdict'], 'g005_FC': cr['sensitivity_gate_0.05']['FC_conf_ZS'],
                    'g005_upper': r3(cr['sensitivity_gate_0.05']['upper95_one_sided']), 'g005_verdict': cr['sensitivity_gate_0.05']['verdict']}}
T = d['tables']
by_law_ZSF = {l: sum(1 for x in T if x['law'] == l and x['cell'] == 'ZS' and x['regime'] == 'forced' and x['FC'])
              for l in sorted({x['law'] for x in T})}
parse = [{'table': x['table'], 'raw': h.get('raw')} for x in T for h in x['heads'] if h.get('kind') in ('PARSE_ERR', 'TRIVIAL', 'INVALID')]
sens = {}
for tau in ('tau005', 'tau02'):
    e = json.load(open(os.path.join(HERE, 'run', f'results_platon01r_{tau}.json'), encoding='utf-8'))
    sens[tau] = {'FC_ZSF': e['summary']['ZSF']['FC'], 'FC_ZNF': e['summary']['ZNF']['FC'], 'TC_TN': e['summary']['TN']['TC'],
                 'holm': e['holm_family']['rejected'], 'free': e['tests']['verdict'][:21], 'forced': e['tests_forced']['verdict'][:22],
                 'rule_C': e['conf_rule_forced']['verdict']}
st, fi = [], []
for p in glob.glob(os.path.join(HERE, 'run', 'journal', 'I*.jsonl')):
    for line in open(p, encoding='utf-8'):
        rr = json.loads(line); st.append(rr['started']); fi.append(rr['finished'])
rep = json.load(open(os.path.join(HERE, 'replication_r.json'), encoding='utf-8'))
out = {'cells': cells, 'tests': tests, 'by_law_ZSF_FC': by_law_ZSF, 'parse_errors': parse, 'sensitivity': sens,
       'totals': {'calls': d['heads_total'], 'lost': d['heads_lost'], 'started': min(st), 'finished': max(fi),
                  'out_total': sum(S[c]['out_tokens_total'] for c in S), 'cost_usd': round(sum(S[c]['cost_usd_total'] for c in S), 2),
                  'out_per_call': round(sum(S[c]['out_tokens_total'] for c in S) / d['heads_total'])},
       'replication': rep, 'audit': json.load(open(os.path.join(HERE, 'audit_heads_sealed.json'), encoding='utf-8'))}
json.dump(out, open(os.path.join(HERE, 'facts_r.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ('cells', 'tests', 'by_law_ZSF_FC', 'parse_errors', 'sensitivity', 'totals')}, ensure_ascii=False))
