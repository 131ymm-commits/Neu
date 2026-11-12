#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01: факты для отчёта из run/results_platon01.json (и файлов чувствительности, журналов) → facts_platon01.json.

Числа отчёта берутся только отсюда (правило CLAUDE.md: каждое число — из json, сверка ledger.py audit). Округление —
как в тексте отчёта: доли и границы — 3 знака, p — 2 значащие цифры, токены — целые.
  python3 facts_platon01.py
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def r3(x):
    return None if x is None else round(float(x), 3)


def p2(x):
    return None if x is None else float(f'{x:.2g}')


def ci(v):
    return None if v is None else [r3(v[0]), r3(v[1])]


def main():
    d = json.load(open(os.path.join(HERE, 'run', 'results_platon01.json'), encoding='utf-8'))
    S = d['summary']
    cells = {}
    for c, x in S.items():
        cells[c] = {
            'n': x['n_tables'], 'K': x['K'], 'FC': x['FC'], 'TC': x['TC'], 'FC_ci95': ci(x['FC_ci95']),
            'TC_ci95': ci(x['TC_ci95']), 'FC_rate': r3(x['FC_rate']), 'TC_rate': r3(x['TC_rate']),
            'none_consensus': x['none_consensus'], 'none_share_mean': r3(x['none_share_mean']), 'kinds': x['head_kinds'],
            'claims': x['claims'], 'claim_hold_rate': r3(x['claim_hold_rate']), 'claim_canonical_rate': r3(x['claim_canonical_rate']),
            'conf_mean_claims': r3(x['conf_mean_claims']), 'conf_mean_holding': r3(x['conf_mean_holding']),
            'conf_mean_failing': r3(x['conf_mean_failing']), 'overconfidence': r3(x['overconfidence_claims']),
            'pair_agree_rate': r3(x['pair_agree_rate']), 'pairs': x['pairs'], 'ties': x['clique_ties'], 'ties_K': x['clique_ties_K'],
            'K_all_members_hold': x['K_all_members_hold'], 'FC_conf': x['FC_conf'], 'TC_conf': x['TC_conf'],
            'FC_conf005': x['FC_conf005'], 'TC_conf005': x['TC_conf005'], 'rep_canonical_among_K': x['rep_canonical_among_K'],
            'mixed_cliques': x['mixed_cliques'], 'conf_missing': x['conf_missing_claims'], 'z_flagged': x['z_flagged_tables'],
            'lost': x['lost_heads'], 'out_mean': round(x['out_tokens_mean']), 'out_total': x['out_tokens_total'],
            'inp_mean': round(x['inp_tokens_mean']), 'cost_usd': round(x['cost_usd_total'], 4),
        }
    t, f = d['tests'], d['tests_forced']
    rc, cr = d['regime_cmp'], d['conf_rule_forced']
    tests = {
        'holm': {'p': {k: p2(v) for k, v in d['holm_family']['p_values'].items()}, 'rejected': d['holm_family']['rejected']},
        'free': {
            'verdict': t['verdict'], 'valid': t['valid'], 'TC_TS': r3(t['positive_control_TC_TS']),
            'FC_ZS': t['P1']['k'], 'FC_ZS_ci95': ci(t['P1']['ci95']), 'FC_ZN_ci95': ci(t['P2']['ci95_ZN']),
            'upper95_ZS': r3(t['equivalence_upper95_ZS']), 'upper95_ZN': r3(t['equivalence_upper95_ZN']),
            'P3': {'b': t['P3']['b_TS_only'], 'c': t['P3']['c_TN_only'], 'p': p2(t['P3']['p_one_sided']),
                   'p_worst': p2(t['P3']['p_worst_losses']), 'TC_TS': r3(t['P3']['TC_TS']), 'TC_TN': r3(t['P3']['TC_TN']),
                   'diff': r3(t['P3']['diff_TC_TS_minus_TN']), 'diff_ci95': ci(t['P3']['diff_ci95_boot']),
                   'diff_ci95_by_law': ci(t['P3']['diff_ci95_boot_by_law']), 'verdict': t['P3']['verdict']},
            'refusal': {nm: {'mean': r3(v['mean_Z_minus_T']), 'ci95': ci(v['ci95_boot']), 'ci95_by_law': ci(v['ci95_boot_by_law']),
                             'NONE_Z': r3(v['NONE_Z']), 'NONE_T': r3(v['NONE_T']), 'discriminating': v['discriminating_lower_ge_0.5']}
                        for nm, v in t['refusal_Z_minus_T'].items()},
            'K_T_minus_K_Z_S': r3(t['K_T_minus_K_Z_S']), 'K_T_minus_K_Z_S_ci95': ci(t['K_T_minus_K_Z_S_ci95_boot']),
            'K_T_minus_K_Z_N': r3(t['K_T_minus_K_Z_N']), 'K_T_minus_K_Z_N_ci95': ci(t['K_T_minus_K_Z_N_ci95_boot']),
            'IOI_TS': {k: r3(v) for k, v in t['IOI_TS'].items()}, 'IOI_TN': {k: r3(v) for k, v in t['IOI_TN'].items()},
            'lost_fisher': t['lost_fisher_two_sided'],
        },
        'forced': {
            'verdict': f['verdict'], 'valid': f['valid'], 'TC_TS': r3(f['positive_control_TC_TS']),
            'P1F': {'k': f['P1']['k'], 'n': f['P1']['n'], 'rate': r3(f['P1']['FC_ZS']), 'ci95': ci(f['P1']['ci95']),
                    'p': p2(f['P1']['p_one_sided']), 'p_worst': p2(f['P1']['p_worst_losses'])},
            'P2F': {'b': f['P2']['b_ZS_only'], 'c': f['P2']['c_ZN_only'], 'p': p2(f['P2']['p_one_sided']),
                    'p_worst': p2(f['P2']['p_worst_losses']), 'FC_ZN': r3(f['P2']['FC_ZN']), 'FC_ZN_ci95': ci(f['P2']['ci95_ZN']),
                    'diff': r3(f['P2']['diff_FC_ZS_minus_ZN']), 'diff_ci95': ci(f['P2']['diff_ci95_boot']),
                    'diff_ci95_by_law': ci(f['P2']['diff_ci95_boot_by_law'])},
            'P3_descr': {'b': f['P3']['b_TS_only'], 'c': f['P3']['c_TN_only'], 'p': p2(f['P3']['p_one_sided']),
                         'TC_TS': r3(f['P3']['TC_TS']), 'TC_TN': r3(f['P3']['TC_TN'])},
            'upper95_ZS': r3(f['equivalence_upper95_ZS']), 'upper95_ZN': r3(f['equivalence_upper95_ZN']),
            'LR_S': r3(f['LR_S']), 'LR_N': r3(f['LR_N']),
            'K_T_minus_K_Z_S': r3(f['K_T_minus_K_Z_S']), 'K_T_minus_K_Z_S_ci95': ci(f['K_T_minus_K_Z_S_ci95_boot']),
            'K_T_minus_K_Z_N': r3(f['K_T_minus_K_Z_N']), 'K_T_minus_K_Z_N_ci95': ci(f['K_T_minus_K_Z_N_ci95_boot']),
            'IOI_TS': {k: r3(v) for k, v in f['IOI_TS'].items()}, 'IOI_TN': {k: r3(v) for k, v in f['IOI_TN'].items()},
            'deception_Z': {k: r3(v) for k, v in f['deception_Z'].items()},
        },
        'P4': {'b': rc['b_forced_only'], 'c': rc['c_free_only'], 'p': p2(rc['p_one_sided_mcnemar']),
               'diff': r3(rc['FC_ZS_forced'] - rc['FC_ZS_free']), 'diff_ci95': ci(rc['diff_ci95_boot'])},
        'rule_C': {'FC_conf_ZS': cr['FC_conf_ZS'], 'upper95': r3(cr['upper95_one_sided']), 'TC_conf_TS': r3(cr['TC_conf_TS']),
                   'verdict': cr['verdict'], 'gate005_FC': cr['sensitivity_gate_0.05']['FC_conf_ZS'],
                   'gate005_upper95': r3(cr['sensitivity_gate_0.05']['upper95_one_sided']),
                   'gate005_TC_conf_TS': r3(cr['sensitivity_gate_0.05']['TC_conf_TS']),
                   'gate005_verdict': cr['sensitivity_gate_0.05']['verdict']},
    }
    # по законам: ложное согласие в ZS режима F; канонические формы среди ложных согласий без имён
    T = d['tables']
    laws = sorted({x['law'] for x in T})
    by_law = {l: {c: {'FC': sum(1 for x in T if x['law'] == l and x['cell'] == c[:2] and x['regime'] == ('forced' if c.endswith('F') else 'free') and x['FC']),
                      'TC': sum(1 for x in T if x['law'] == l and x['cell'] == c[:2] and x['regime'] == ('forced' if c.endswith('F') else 'free') and x['TC'])}
                  for c in ('TS', 'TN', 'TSF', 'TNF', 'ZSF', 'ZNF')} for l in laws}
    znf_fc = [{'table': x['table'], 'law': x['law'], 'answers': [h.get('raw') for h in x['heads']]}
              for x in T if x['cell'] == 'ZN' and x['regime'] == 'forced' and x['FC']]
    tnf_fc = [{'table': x['table'], 'law': x['law'], 'answers': [h.get('raw') for h in x['heads']],
               'rep_canonical': x['rep_is_canonical']} for x in T if x['cell'] == 'TN' and x['regime'] == 'forced' and x['FC']]
    parse = [{'table': x['table'], 'head': h['head'], 'raw': h.get('raw'), 'err': h.get('err')}
             for x in T for h in x['heads'] if h.get('kind') in ('PARSE_ERR', 'TRIVIAL', 'INVALID')]
    # чувствительность к порогам
    sens = {}
    for tau in ('tau005', 'tau02'):
        e = json.load(open(os.path.join(HERE, 'run', f'results_platon01_{tau}.json'), encoding='utf-8'))
        sens[tau] = {'cells': {c: {'FC': e['summary'][c]['FC'], 'TC': e['summary'][c]['TC']} for c in e['summary']},
                     'holm': e['holm_family']['rejected'], 'free': e['tests']['verdict'], 'forced': e['tests_forced']['verdict'],
                     'rule_C': e['conf_rule_forced']['verdict'],
                     'P1F_p': p2(e['tests_forced']['P1']['p_one_sided']), 'P2F_p': p2(e['tests_forced']['P2']['p_one_sided']),
                     'P3_p': p2(e['tests']['P3']['p_one_sided'])}
    # время прогона и вызовы
    st, fi, n, outc = [], [], 0, {}
    for p in glob.glob(os.path.join(HERE, 'run', 'journal', 'I*.jsonl')):
        for line in open(p, encoding='utf-8'):
            rr = json.loads(line); n += 1
            st.append(rr['started']); fi.append(rr['finished'])
            k = (rr.get('outcome'), rr.get('final'), rr.get('attempt'))
            outc[str(k)] = outc.get(str(k), 0) + 1
    totals = {'calls': n, 'outcomes': outc, 'started': min(st), 'finished': max(fi),
              'out_total': sum(c['out_total'] for c in cells.values()),
              'cost_usd_total': round(sum(S[c]['cost_usd_total'] for c in S), 2),
              'heads_lost': d['heads_lost']}
    audit = json.load(open(os.path.join(HERE, 'audit_heads_sealed.json'), encoding='utf-8'))
    # ожидания E1–E7 по букве PREREG §6 — исход считает код
    fr, fo = d['tests'], d['tests_forced']
    zsf = [x for x in T if x['cell'] == 'ZS' and x['regime'] == 'forced']
    fc_zsf = [x for x in zsf if x['FC']]
    E = {
        'E1': (0.85, bool(fr['third_outcome_rare_false_consensus'] and fr['refusal_Z_minus_T']['S']['NONE_Z'] >= 0.5
                         and fr['refusal_Z_minus_T']['N']['NONE_Z'] >= 0.5 and fr['valid'])),
        'E2': (0.85, bool(fr['P3']['rejected_holm'])),
        'E3': (0.75, bool(fo['P1']['rejected_holm'] and fo['P2']['rejected_holm'])),
        'E4': (0.8, bool(rc['FC_ZS_forced'] - rc['FC_ZS_free'] >= 0.15)),
        'E5': (0.7, (bool(sum(x['rep_is_canonical'] for x in fc_zsf) >= len(fc_zsf) / 2) if fc_zsf else None)),
        'E6': (0.6, cr['verdict'] == 'порог уверенности снимает ложное согласие'),
        'E7': (0.95, bool(fr['positive_control_TC_TS'] >= 0.3 and fo['positive_control_TC_TS'] >= 0.3)),
    }
    scored = [(pv, o) for pv, o in E.values() if o is not None]
    expectations = {'items': {k: {'p': pv, 'outcome': o} for k, (pv, o) in E.items()},
                    'n_scored': len(scored), 'hits': sum(o for _, o in scored),
                    'mean_p': r3(sum(pv for pv, _ in scored) / len(scored)),
                    'brier': r3(sum((pv - o) ** 2 for pv, o in scored) / len(scored)),
                    'self_deception': r3(sum(pv for pv, _ in scored) / len(scored) - sum(o for _, o in scored) / len(scored))}
    # вес опоры: log2(мощность / ложный уровень); мощность — наименьшая из сценариев PREREG §9 («вдвое слабее»)
    pw = json.load(open(os.path.join(HERE, 'power_platon.json'), encoding='utf-8'))
    half = [x for x in pw['family'] if x['family'] == ['P3', 'P1F', 'P2F'] and 'вдвое' in x['scenario']][0]['power']
    reach = pw['third_outcome']['40']['P_reach_if_p_0.05_both']
    bits = {'C-070 (P1F и P2F; по P2F)': {'power': r3(half['P2F']), 'bits': round(math.log2(half['P2F'] / 0.05), 2)},
            'C-071 (P3)': {'power': r3(half['P3']), 'bits': round(math.log2(half['P3'] / 0.05), 2)},
            'C-072 (контроль свободного режима)': {'power': r3(reach), 'bits': round(math.log2(reach / 0.05), 2)},
            'C-073 (правило C; мощность без числа — 0,8, по совету 43 ограничено сверху наименьшим в серии)':
                {'power_rule_default': 0.8, 'bits_uncapped': round(math.log2(0.8 / 0.05), 2),
                 'power': r3(half['P2F']), 'bits': round(math.log2(half['P2F'] / 0.05), 2)},
            'сценарий «доли пилотов» (для DEVIATIONS)': {'power': 1.0, 'bits': round(math.log2(1.0 / 0.05), 2)}}
    out = {'cells': cells, 'tests': tests, 'by_law': by_law, 'ZNF_false_consensus': znf_fc, 'TNF_false_consensus': tnf_fc,
           'parse_errors': parse, 'sensitivity': sens, 'totals': totals, 'audit_heads': audit,
           'expectations': expectations, 'support_bits': bits,
           'by_ncols_ZSF': {g: d['by_ncols'][g]['ZSF'] for g in d['by_ncols']},
           'free_Z_heads_none_total': S['ZS']['head_kinds'].get('NONE', 0) + S['ZN']['head_kinds'].get('NONE', 0),
           'free_Z_heads_total': S['ZS']['heads_total'] + S['ZN']['heads_total'],
           'inp_mean_range': [min(round(S[c]['inp_tokens_mean']) for c in S), max(round(S[c]['inp_tokens_mean']) for c in S)]}
    json.dump(out, open(os.path.join(HERE, 'facts_platon01.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({'totals': totals, 'holm': tests['holm'], 'free': tests['free']['verdict'], 'forced': tests['forced']['verdict'],
                      'rule_C': tests['rule_C']['verdict']}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
