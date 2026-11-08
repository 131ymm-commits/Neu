# PRECOND-02: расход выхода по журналам драйвера против бюджета автора (08.11: «Можно использовать 50% недельных»).
# В хеши регистрации не входит: на задания, выборы, правду и анализ не влияет. Считает usage.out всех попыток (итоговых и нет)
# в живых журналах .cache/precond02_live, законченных не раньше --since (по умолчанию — сброс недельного лимита 09.11 01:00 UTC).
#   python3 budget_precond02.py [--since 2026-11-09T01:00:00+00:00] [--cap 16000000]   → печать; код 2, если бюджет исчерпан
import argparse, glob, json, os, sys
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__)); LIVE = os.path.join(HERE, '..', '..', '.cache', 'precond02_live')
ap = argparse.ArgumentParser(); ap.add_argument('--since', default='2026-11-09T01:00:00+00:00'); ap.add_argument('--cap', type=int, default=16_000_000)
a = ap.parse_args(); since = datetime.fromisoformat(a.since)
tot, by = 0, {}
for j in ('A_exec', 'B_exec', 'A_eval', 'B_eval'):
    for p in glob.glob(os.path.join(LIVE, f'{j}_journal', 'WH_*.jsonl')):
        for line in open(p, encoding='utf-8'):
            r = json.loads(line); fin = r.get('finished')
            if not fin or datetime.fromisoformat(fin) < since: continue
            u = (r.get('usage') or {}).get('out') or 0; tot += u; by[j] = by.get(j, 0) + u
left = a.cap - tot
print(f'выход с {a.since}: {tot:,} токенов'.replace(',', ' '), {k: v for k, v in by.items()}, f'| бюджет {a.cap:,}'.replace(',', ' '), f'| осталось {left:,}'.replace(',', ' '))
sys.exit(2 if left <= 0 else 0)
