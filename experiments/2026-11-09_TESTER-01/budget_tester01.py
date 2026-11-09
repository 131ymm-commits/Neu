#!/usr/bin/env python3
# TESTER-01: расход по журналу драйвера (все попытки); код 2 — если бюджет исчерпан.
#   python3 budget_tester01.py <журнал> [--cap 500000] [--cap-usd 60]
# Выход — не мера цены: в многоходовой сессии почти весь расход — вход, то есть повторное чтение контекста (ERRORS № 136).
# Поэтому печатается и вход, и cost_usd из CLI (цена по прейскуранту API, а не по лимиту подписки).
import glob, json, os, sys
a = sys.argv; j = a[1]
cap = int(a[a.index('--cap') + 1]) if '--cap' in a else 500000
cap_usd = float(a[a.index('--cap-usd') + 1]) if '--cap-usd' in a else None
out = inp = usd = n = fin = 0
for p in glob.glob(os.path.join(j, '*.jsonl')):
    if p.endswith('run_log.jsonl'): continue
    for line in open(p, encoding='utf-8'):
        r = json.loads(line); u = r.get('usage') or {}; n += 1; fin += bool(r.get('final'))
        out += u.get('out') or 0; inp += u.get('inp') or 0; usd += u.get('cost_usd') or 0
over = out >= cap or (cap_usd is not None and usd >= cap_usd)
print(f'вызовов {n}, итогов {fin}, выход {out} из {cap}, вход {inp / 1e6:.1f} млн, по прейскуранту API ${usd:.2f}' + (f' из ${cap_usd:.0f}' if cap_usd is not None else ''))
sys.exit(2 if over else 0)
