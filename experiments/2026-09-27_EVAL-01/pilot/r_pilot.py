# Проверка достижимости P4 на пилоте (PREREG §7): R по клеткам пилота (8 элементов, 4+4) для BLIND / NOTE / RECOMPUTE(+NOTE),
# отношение R_ветви / R_BLIND с бутстреп-ИД95 по элементам; ширина ИД говорит, разрешима ли граница ≤ 0,5 при n = 154 (4 клетки × 32).
import json, os, sys, random, statistics as st
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
from eval01_main import rstat, clip
from eval01_pilot import target_of, label
key = json.load(open(f'{HERE}/pilot/sample_key.json')); truth = json.load(open('/root/eval_secret/truth.json'))
items = {json.loads(l)['id']: json.loads(l) for l in open(f'{HERE}/data/items_public.jsonl')}
out = json.load(open(f'{HERE}/pilot/out_full.json'))['out']
cells = {}
for i in key['ids']:
    it = items[i]; cells.setdefault(f"{it['source']}/{it['family']}", []).append((key['aliases'][i], bool(truth[i].get(target_of(it)))))
two = {c: v for c, v in cells.items() if 0 < sum(y for _, y in v) < len(v)}
def R_mean(arm, sample):
    rs = [rstat([(clip(out[arm][a]['p_correct']), y) for a, y in lst]) for lst in sample.values()]
    rs = [r['R'] for r in rs if r and r['R'] is not None]; return st.mean(rs) if rs else None
res = {}
for arm in ('BLIND', 'NOTE', 'RECOMPUTE'):
    res[arm] = dict(R=R_mean(arm, two), by_cell={c: (rstat([(clip(out[arm][a]['p_correct']), y) for a, y in v]) or {}).get('R') for c, v in two.items()})
rng = random.Random(0); ratios = {'NOTE': [], 'RECOMPUTE': []}
for _ in range(2000):
    s = {c: [rng.choice(v) for _ in v] for c, v in two.items()}
    rb = R_mean('BLIND', s)
    for arm in ratios:
        ra = R_mean(arm, s)
        if rb and ra is not None: ratios[arm].append(ra / rb)
for arm, v in ratios.items():
    v.sort(); res[arm]['ratio_vs_BLIND'] = dict(point=res[arm]['R'] / res['BLIND']['R'], ci95=[v[50], v[1949]], n_boot=len(v), ci_width=v[1949] - v[50])
res['note'] = 'клетки пилота по 8 элементов (13 двухклассных); ширина ИД при n = 32 на клетку ожидаемо ≈ вдвое уже (√4)'
json.dump(res, open(f'{HERE}/pilot/r_pilot.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k == 'note' else {kk: vv for kk, vv in v.items() if kk != 'by_cell'}) for k, v in res.items()}, ensure_ascii=False, indent=1))
