#!/usr/bin/env python3
"""TESTER-01, пилот: итоги по рукам из оценок score.js и журнала драйвера → pilot_an.json (в git — без описаний багов).

  python3 pilot_an_tester01.py --scores /root/tester01_secret/pilot_scores --journal /root/tester01_secret/pilot_journal --out pilot_an.json
"""
import argparse, glob, json, os

ap = argparse.ArgumentParser()
ap.add_argument('--scores', required=True); ap.add_argument('--journal', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()

cost = {}
for p in glob.glob(os.path.join(a.journal, '*.jsonl')):
    if p.endswith('run_log.jsonl'): continue
    for line in open(p, encoding='utf-8'):
        r = json.loads(line); u = r.get('usage') or {}
        task, arm, _ = r['job'].split('|')
        cost[(task.split('_')[0], arm)] = {'usd_cli': round(u.get('cost_usd') or 0, 2), 'inp': u.get('inp'), 'out': u.get('out'),
                                           'turns': (r.get('flags') or {}).get('message_start'), 'thinking': r.get('thinking_tokens'),
                                           'minutes': None, 'final': r.get('final')}

rows = []
for p in sorted(glob.glob(os.path.join(a.scores, '*_[SAW].json'))):
    d = json.load(open(p, encoding='utf-8')); game = os.path.basename(p).split('_')[0]
    c = cost.get((game, d['arm']), {})
    rows.append({'game': game, 'arm': d['arm'], 'copy': d['copy'], 'acts': d['acts'], 'restarts': d['restarts'],
                 'reports': d['nReports'], 'credited': sum(1 for r in d['reports'] if r['match']),
                 'bugs': len(d['bugs']), 'found': sum(b['found'] for b in d['bugs']), 'exposed': sum(b['exposed'] for b in d['bugs']),
                 'clean_fires': sum(b['cleanFire'] for b in d['bugs']),
                 'mean_conf': round(sum(r['confidence'] or 0 for r in d['reports']) / max(1, d['nReports']), 3),
                 'per_bug': {b['id']: ('found' if b['found'] else 'exposed' if b['exposed'] else 'none') for b in d['bugs']}, **c})

tot = {k: sum(r.get(k) or 0 for r in rows) for k in ('usd_cli', 'inp', 'out', 'reports', 'credited', 'found', 'exposed', 'bugs')}
by_arm = {}
for arm in 'SAW':
    rr = [r for r in rows if r['arm'] == arm]
    by_arm[arm] = {k: sum(r.get(k) or 0 for r in rr) for k in ('found', 'exposed', 'bugs', 'reports', 'credited', 'usd_cli', 'out', 'inp')}
    by_arm[arm]['usd_cli'] = round(by_arm[arm]['usd_cli'], 2)
res = {'sessions': rows, 'by_arm': by_arm, 'total': {**tot, 'usd_cli': round(tot['usd_cli'], 2)},
       'test_cost_estimate_usd': round(tot['usd_cli'] / max(1, len(rows)) * 18, 1),
       'note': 'цена — cost_usd CLI (прейскурант API), не лимит подписки; оценка теста = средняя сессия пилота × 18'}
open(a.out, 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({'by_arm': by_arm, 'total': res['total'], 'test_cost_estimate_usd': res['test_cost_estimate_usd']}, ensure_ascii=False))
