#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03: выборка полей вывода для ledger.py audit (как audit_view_d2.json в DISTILL-02) — только поля, которые печатает отчёт,
чтобы совпадения не были случайными из-за плотности чисел в полном test.json. Ссылки на номера записей ERRORS — отдельным полем
(это номера, а не данные). Пишет audit_view_d3.json.
  python3 audit_view_d3.py"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
T = os.path.join(ROOT, 'gha_out/distill03_test')
KINDS = ('prog', 'shape')
t = json.load(open(os.path.join(T, 'test.json'), encoding='utf-8'))
v = {'verdicts': t['verdicts'], 'seconds': t['seconds'], 'families': {}}


def kind_view(r, k):
    return dict(D=r['D'], p=r['p'], k=r['k'], n_perm=r['n_perm'], rank=r['rank'], n_distinct=r['n_distinct'], n_pos=r['n_pos'],
                own_first=r['own_first'], diag=[r['s'][i][i] for i in range(k)],
                nearest=dict(per_head=r['nearest_other']['per_head'], mean=r['nearest_other']['mean'], best=r['nearest_other']['heads_own_best']),
                without=r.get('without', {}))


for fam, fr in t['families'].items():
    k = fr['k']
    fv = dict(k=k, n_envs=len(fr['envs_kept']), input_gain=dict(per_head=fr['input_gain']['per_head'], mean=fr['input_gain']['mean'], n_pos=fr['input_gain']['n_pos']),
              decomposition=fr['decomposition'], kinship={kind: fr['kinship'][kind]['per_head'] for kind in KINDS},
              **{kind: kind_view(fr[kind], k) for kind in KINDS})
    d = fr['descriptive']['new5']
    fv['new5'] = dict(k=d['k'], n_envs=len(d['envs_kept']), **{kind: dict(D=d[kind]['D'], p=d[kind]['p'], rank=d[kind]['rank'], n_perm=d[kind]['n_perm']) for kind in KINDS})
    v['families'][fam] = fv
hl = open(os.path.join(T, 'hashes.log'), encoding='utf-8').read()
v['hashes_files'] = int(re.search(r'\((\d+) файлов\)', hl).group(1))
pil = json.load(open(os.path.join(ROOT, 'gha_out/distill03_pilot/pilot.json'), encoding='utf-8'))['families']['thousands']
v['pilot'] = dict(prog_D=pil['prog']['D'], shape_D=pil['shape']['D'])
v['expect'] = json.load(open(os.path.join(HERE, 'expect_d3.json'), encoding='utf-8'))['rules']
v['derived'] = json.load(open(os.path.join(HERE, 'notes_derived_d3.json'), encoding='utf-8'))
sb = json.load(open(os.path.join(ROOT, 'journal/support_bits.json'), encoding='utf-8'))['C-109']
line = open(os.path.join(HERE, 'support_bits_d3.log'), encoding='utf-8').read()          # вывод tools/support_bits.py, строка C-109
nums = [float(x) for x in re.findall(r'[+-]\d+\.\d+', line)]
v['support_bits_C109'] = dict(total_bits=nums[0], base_bits=nums[1], group_bits=nums[2], power=sb['supports'][0]['power'],
                              false_level=sb['supports'][0]['false_level'])
v['errors_refs'] = [180, 224, 225, 226, 227]           # номера записей ERRORS и замков, не данные
v['familywise_bound'] = 4 * 12 / 5040                    # PREREG §7: четыре проверки × 12/5040 (ERRORS № 226, дополнение)
json.dump(v, open(os.path.join(HERE, 'audit_view_d3.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('записано audit_view_d3.json')
