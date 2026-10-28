#!/usr/bin/env python3
"""TRUST-03: адресная сверка чисел отчёта — строит из facts_trust_03.json и support_bits_trust_03.json строки так, как
они записаны в REPORT-TRUST-03.md (десятичная запятая, знак «−»), и ищет каждую в тексте дословно. ledger.py audit по
папке даёт «неинформативно» (в json слишком много чисел), поэтому нужна эта проверка. Запуск из папки опыта."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
f = json.load(open(os.path.join(HERE, 'facts_trust_03.json')))
sb = json.load(open(os.path.join(HERE, 'support_bits_trust_03.json')))
rep = open(os.path.join(HERE, 'REPORT-TRUST-03.md'), encoding='utf-8').read()
fmt = lambda x: (f'{float(x):.5f}'.rstrip('0').rstrip('.').replace('.', ',').replace('-', '−')) if float(x) != 0 else '0'
want = []
for k, v in f['verdicts'].items():
    want.append((f'{k} счёт', f"{v['n']}/10"))
    key = 'value' if 'value' in v else 'diff'
    m, lo, hi = v[key]
    want.append((f'{k} оценка', f'{fmt(m)} [{fmt(lo)}; {fmt(hi)}]'))
for arm, v in f['arms'].items():
    for k in ('wG', 'u', 'logloss', 'b'):
        want.append((f'{arm} {k}', fmt(v[k][0])))
for arm in ('DEMES', 'DEMES_10x40', 'DEMES_IND', 'DEMES_POOLED'):
    p = f['price'][arm]
    want += [(f'{arm} Прайс внутри', ('+' if p['within'] > 0 else '') + fmt(p['within'])), (f'{arm} Прайс между', fmt(p['between']))]
want += [('К1 разность', fmt(round(f['K1']['logloss_gap'][0], 4))), ('К1 SD', fmt(round(f['K1']['wG_sd_groups'][0], 4))),
         ('Д2 срывы', f"{f['D2']['n_breakdown']} из 10"), ('Д2 мин u без срыва', fmt(min(x for x in f['D2']['u'] if x > -1))),
         ('Д2 макс u без срыва', fmt(max(f['D2']['u'])))]
for cid in ('C-048', 'C-049', 'C-050', 'C-051', 'C-052'):
    want.append((f'{cid} бит', f"+{sb[cid]['bits_1']}".replace('.', ',')))
miss = [(lab, s) for lab, s in want if s not in rep]
print(f'строк {len(want)}, не найдено {len(miss)}')
for lab, s in miss:
    print('  НЕТ', lab, s)
