# Расчёты, которых требовал совет 11 до регистрации EVAL-01 (Левое, Скептик): МДЭ Брайера для клеточного оценщика,
# бутстреп разности ИОИ, сетка перекалибровки BLIND. Данные — пилот 1 (140 × 3). Выход: pilot/mde_pilot.json
import json, statistics as st, random, math, os, sys
D = os.path.dirname(os.path.abspath(__file__)); HERE = os.path.dirname(D); sys.path.insert(0, HERE)
from eval01_main import ci, half_T   # единый ИД-helper (индексы [50], [1949] при 2000) и полвердикт при p = 0,5
key = json.load(open(f'{D}/sample_key.json')); truth = json.load(open('/root/eval_secret/truth.json'))
items = {json.loads(l)['id']: json.loads(l) for l in open(f'{HERE}/data/items_public.jsonl')}
out = json.load(open(f'{D}/out_full.json'))['out']
def tgt(it): return 'within_1pct' if it['kind'] == 'estimate' else 'exact'
rows = []
for i in key['ids']:
    it = items[i]; y = bool(truth[i].get(tgt(it))); al = key['aliases'][i]
    rows.append(dict(cell=f"{it['source']}/{it['family']}", y=y, **{a: min(1, max(0, out[a][al]['p_correct'])) for a in out}))
cells = sorted({r['cell'] for r in rows})
two = [c for c in cells if 0 < sum(r['y'] for r in rows if r['cell'] == c) < sum(1 for r in rows if r['cell'] == c)]
def brier(p, y): return (p - y) ** 2
def recal(p, lam, c): p = 0.5 + lam * (p - 0.5); return 0.5 if abs(p - 0.5) < c else p
def ioi(rs, a, lam=1.0, c=0.0):
    ps = [(recal(r[a], lam, c), r['y']) for r in rs]
    T = st.mean((0.5 if p == 0.5 else float((p > 0.5) == y)) for p, y in ps); C = st.mean(max(p, 1 - p) for p, _ in ps)  # p = 0,5 — полвердикта
    return (1 - T) + max(0, C - T)
def cellmean(rs, a, **kw): return st.mean(ioi([r for r in rs if r['cell'] == c], a, **kw) for c in two)
res = {}
ss = 0; n = 0
for c in two:
    d = [brier(r['BLIND'], r['y']) - brier(r['RECOMPUTE'], r['y']) for r in rows if r['cell'] == c]
    ss += (len(d) - 1) * st.variance(d); n += len(d) - 1
s = math.sqrt(ss / n); res['sd_pooled_brier_diff'] = round(s, 4); res['n_two_class_cells'] = len(two)
res['mde_brier'] = {f'z={z}': dict(cells4x32=round(z * s / math.sqrt(128), 4), items154=round(z * s / math.sqrt(154), 4)) for z in (1.96, 2.24)}
random.seed(0); base = cellmean(rows, 'BLIND'); rec = cellmean(rows, 'RECOMPUTE'); diffs = []
for _ in range(2000):
    bs = []
    for c in two:
        rs = [r for r in rows if r['cell'] == c]; bs += [random.choice(rs) for _ in rs]
    diffs.append(cellmean(bs, 'BLIND') - cellmean(bs, 'RECOMPUTE'))
res['ioi_cellmean'] = dict(BLIND=round(base, 4), RECOMPUTE_NOTE=round(rec, 4), diff=round(base - rec, 4), ci95=[round(x, 4) for x in ci(diffs)])
grid = {}
for lam in (0.3, 0.5, 0.7, 1.0):
    for c in (0, 0.05, 0.1, 0.15, 0.2):
        b = st.mean(st.mean(brier(recal(r['BLIND'], lam, c), r['y']) for r in rows if r['cell'] == cc) for cc in two)
        abst = st.mean(recal(r['BLIND'], lam, c) == 0.5 for r in rows)
        grid[f'lam={lam},c={c}'] = dict(brier=round(b, 4), ioi=round(cellmean(rows, 'BLIND', lam=lam, c=c), 4), abstain=round(abst, 3))
res['recal_grid'] = grid
ok = {k: v for k, v in grid.items() if v['abstain'] <= 0.3}
res['recal_best_brier'] = min(ok.items(), key=lambda kv: kv[1]['brier'])
# Блок по требованию Левого / рецензии 3.4: 4 семейства основного дизайна (n = 32, по 8 в пилоте), s_pooled с бутстреп-ИД, откат по верхней границе,
# МДЭ_T из SD парной разности T (полвердикт при p = 0,5). z: 1,96 (0,05), 2,24 (0,025), 2,39 (0,05/3 — первый шаг Холма при трёх первичных).
FOUR = ['HIVE-01/TWIN', 'HIVE-01/COLLATZ', 'HIVE-01/SUB5', 'LEVEL-04/MODSQ-link']; FALLBACK = 0.075; ZS = {'1.96': 1.96, '2.24': 2.24, '2.39': 2.394}
def s_pooled(rs, cs, f):
    ss = n = 0
    for c in cs:
        d = [f(r) for r in rs if r['cell'] == c]
        if len(d) < 2: continue
        ss += (len(d) - 1) * st.variance(d); n += len(d) - 1
    return math.sqrt(ss / n)
bd = lambda r: brier(r['BLIND'], r['y']) - brier(r['RECOMPUTE'], r['y'])
td = lambda r: half_T(r['RECOMPUTE'], r['y']) - half_T(r['BLIND'], r['y'])
s4, sT4, sT13 = s_pooled(rows, FOUR, bd), s_pooled(rows, FOUR, td), s_pooled(rows, two, td)
rng = random.Random(1); bs4, bT4 = [], []
for _ in range(2000):
    bs = []
    for c in FOUR:
        rs = [r for r in rows if r['cell'] == c]; bs += [rng.choice(rs) for _ in rs]
    bs4.append(s_pooled(bs, FOUR, bd)); bT4.append(s_pooled(bs, FOUR, td))
c4, cT4 = ci(bs4), ci(bT4)
res['four_families'] = dict(cells=FOUR, n_items=sum(r['cell'] in FOUR for r in rows), sd_pooled_brier_diff=round(s4, 4), sd_ci95=[round(x, 4) for x in c4],
    mde_brier_cells4x32={z: dict(point=round(v * s4 / math.sqrt(128), 4), upper_ci=round(v * c4[1] / math.sqrt(128), 4), fallback_per_item=(v * c4[1] / math.sqrt(128) > FALLBACK)) for z, v in ZS.items()},
    fallback_rule=f'если верхняя граница ИД МДЭ_Брайер > {FALLBACK} — главный разрез откатывается на разрез по элементам (154)',
    sd_pooled_T_diff=round(sT4, 4), sd_T_ci95=[round(x, 4) for x in cT4], mde_T_cells4x32={z: round(v * sT4 / math.sqrt(128), 4) for z, v in ZS.items()},
    sd_pooled_T_diff_13cells=round(sT13, 4), mde_T_13cells={z: round(v * sT13 / math.sqrt(128), 4) for z, v in ZS.items()})
res['mde_brier']['z=2.39'] = dict(cells4x32=round(2.394 * s / math.sqrt(128), 4), items154=round(2.394 * s / math.sqrt(154), 4))
json.dump(res, open(f'{D}/mde_pilot.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'recal_grid'}, ensure_ascii=False, indent=1))
