#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01R: исходы повтора по PREREG §4 и веса опоры по §5 (написано до данных) → replication_r.json.
  python3 replication_r.py run/results_platon01r.json"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ALPHA = 0.05


def bits_hit(power):
    return round(math.log2(power / ALPHA), 2)


def bits_miss(power):
    return round(min(0.0, math.log2((1 - power) / (1 - ALPHA))), 2)


def main():
    d = json.load(open(sys.argv[1], encoding='utf-8'))
    pw = json.load(open(os.path.join(HERE, 'power_r.json'), encoding='utf-8'))
    half, son = pw['family']['вдвое слабее'], pw['family']['по пилоту Sonnet']
    S, tf, tF, cr = d['summary'], d['tests'], d['tests_forced'], d['conf_rule_forced']
    rej = d['holm_family']['rejected']
    fc_zsf = S['ZSF']['FC']
    floor = fc_zsf <= 2
    ceil = S['TN']['TC'] > 0.9 * S['TN']['n_tables']
    undefined_lost = 'не определено' in (tf['verdict'] or '')[:14] or 'не определено' in (tF['verdict'] or '')[:14]
    out = {}

    def put(cid, cond_undef, hit, p_hit, p_miss, why):
        if cond_undef:
            out[cid] = {'outcome': 'не определено: потолок или пол', 'bits': 0.0, 'why': why}
        elif hit:
            out[cid] = {'outcome': 'повторилось', 'bits': bits_hit(p_hit)}
        else:
            out[cid] = {'outcome': 'не повторилось', 'bits': bits_miss(p_miss)}
    put('C-070', floor, bool(rej.get('P1F') and rej.get('P2F') and tF['P1']['rejected_holm'] and tF['P2']['rejected_holm']),
        half['P2F'], son['P2F'], f'FC в ZS режима F = {fc_zsf} ≤ 2 из 40')
    put('C-071', ceil, bool(rej.get('P3') and tf['P3']['rejected_holm']), half['P3'], son['P3'],
        f"TC в TN свободного режима = {S['TN']['TC']} > 36 из 40")
    free_ok = tf['verdict'].startswith('головы воздерживаются')
    put('C-072', False, free_ok, pw['bounds']['0.05']['free_both_cells_frechet_lower'], 0.0, '')
    put('C-073', floor, cr['verdict'] == 'порог уверенности снимает ложное согласие', pw['bounds']['0.05']['rule_C'], 0.0,
        f'FC в ZS режима F = {fc_zsf} ≤ 2 из 40')
    if undefined_lost:
        for k in out:
            out[k] = {'outcome': 'не определено (потери или условие осмысленности)', 'bits': 0.0}
    res = {'outcomes': out, 'FC_ZSF': fc_zsf, 'TC_TN_free': S['TN']['TC'], 'floor': floor, 'ceiling': ceil,
           'free_verdict': tf['verdict'], 'forced_verdict': tF['verdict'], 'rule_C': cr['verdict'], 'holm': rej}
    json.dump(res, open(os.path.join(HERE, 'replication_r.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
