#!/usr/bin/env python3
"""TRUST-01, пост-хок (описательно, вердикты не меняет; записан после прогона 28.10.2026) → posthoc_trust_01.json:
1) средние по 10 зёрнам итоговые веса каждой руки рядом с точными и наивными;
2) средние точные метрики рук в диапазоне и после сдвига (лог-потеря, Брайер, ECE);
3) траектории по поколениям (одиночные снимки генотипа, точный перебор): самообман и отношение масштабов —
   растёт ли уверенность ACC или подходит к точной снизу; меняется ли масштаб KELLY между 750 и 1499
   (неспецифичность T6b).
Запуск из папки опыта: python3 posthoc_trust_01.py"""
import json
import os

import numpy as np

import exp_trust_01 as E

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'results_trust_01.json')))
names = d['names']; arms = d['params']['ARMS']
w_exact = np.array(d['theory']['w_exact'])


def scale(w):
    """Масштаб как в PREREG §4: √(Σ w² четырёх весов вне пары + (сумма пары)²), без w0."""
    w = np.asarray(w)
    return float(np.sqrt(w[1] ** 2 + w[2] ** 2 + w[4] ** 2 + w[5] ** 2 + (w[3] + w[6]) ** 2))


S_EX = scale(w_exact)
out = dict(names=names, exact=np.round(w_exact, 3).tolist(), naive=np.round(d['theory']['w_naive'], 3).tolist(),
           ml=np.round(d['theory']['w_ml'], 3).tolist(), mean_w={}, sd_w={}, metrics={}, traj={})
GS = (100, 250, 500, 750, 1000, 1250, 1499)
for a in arms:
    runs = [r for r in d['runs'] if r['arm'] == a]
    W = np.array([r['w_final'] for r in runs])
    out['mean_w'][a] = np.round(W.mean(0), 3).tolist()
    out['sd_w'][a] = np.round(W.std(0, ddof=1), 3).tolist()
    m = {}
    for key in ('exact', 'exact_shifted'):
        for f in ('self_dec', 'ignorance', 'logloss', 'brier', 'ece', 'acc'):
            m[f'{key}.{f}'] = round(float(np.mean([r[key][f] for r in runs])), 4)
    out['metrics'][a] = m
    tr = {}
    for g in GS:
        sd, sc = [], []
        for r in runs:
            t = [t for t in r['traj'] if t['g'] == g]
            assert len(t) == 1, (a, g)
            sd.append(E.exact_metrics(t[0]['w'])['self_dec']); sc.append(scale(t[0]['w']) / S_EX)
        tr[g] = dict(self_dec=round(float(np.mean(sd)), 4), scale_ratio=round(float(np.mean(sc)), 3),
                     n_scale_up_vs_750=None)
    s750 = {r['seed']: scale([t for t in r['traj'] if t['g'] == 750][0]['w']) for r in runs}
    s1499 = {r['seed']: scale([t for t in r['traj'] if t['g'] == 1499][0]['w']) for r in runs}
    tr[1499]['n_scale_up_vs_750'] = int(sum(s1499[s] > s750[s] for s in s750))
    out['traj'][a] = tr
out['bits_exact'] = np.round(w_exact / np.log(2), 2).tolist()            # веса в битах: log2 отношения правдоподобия
out['bits_kelly'] = np.round(np.array(out['mean_w']['KELLY']) / np.log(2), 2).tolist()
out['pair_bits'] = dict(exact=round(float((w_exact[3] + w_exact[6]) / np.log(2)), 2),
                        naive=round(float(2 * d['theory']['w_naive'][3] / np.log(2)), 2))
a_pairs = [r['w_final'][3] + r['w_final'][6] for r in d['runs'] if r['arm'] == 'KELLY']
naive_pair = 2 * d['theory']['w_naive'][3]; exact_pair = w_exact[3] + w_exact[6]
out['discount_learned_kelly'] = round(float((naive_pair - np.mean(a_pairs)) / (naive_pair - exact_pair)), 3)   # доля скидки пересказу
for k in ('exact_exact', 'exact_naive', 'exact_shifted_exact'):
    out[k] = {f: round(float(v), 4) for f, v in d['theory'][k].items()}
json.dump(out, open(os.path.join(HERE, 'posthoc_trust_01.json'), 'w'), ensure_ascii=False, indent=1)
print('веса:', names)
print('точные', out['exact']); print('наивные', out['naive'])
for a in arms:
    print(f'{a:8s}', out['mean_w'][a], '±', out['sd_w'][a])
print('\nметрики (среднее по зёрнам; точный перебор):')
for a in arms:
    print(f'{a:8s}', out['metrics'][a])
print('биты: точные', out['bits_exact'], 'KELLY', out['bits_kelly'], 'пара', out['pair_bits'])
print('доля скидки пересказу, выученная KELLY:', out['discount_learned_kelly'])
print('точная формула', out['exact_exact']); print('наивная формула', out['exact_naive'])
print('\nтраектории (поколение: самообман / отношение масштабов):')
for a in arms:
    print(f'{a:8s}', ' '.join(f"{g}:{out['traj'][a][g]['self_dec']:+.4f}/{out['traj'][a][g]['scale_ratio']:.2f}" for g in GS),
          '| масштаб 1499 > 750 в', out['traj'][a][1499]['n_scale_up_vs_750'], 'из 10')
