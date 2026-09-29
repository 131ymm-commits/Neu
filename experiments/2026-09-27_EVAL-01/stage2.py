# EVAL-01, стадия 2 (PREREG §9, правило Скептика): ≈ 300 новых элементов из остатка пула по тем же четырём большим клеткам, сколько есть;
# только COUNCIL (RC1, C2, C3) + BLIND; анализ отдельно от стадии 1; семейство Холма {Брайер, ИОИ} при α = 0,025.
#   python3 stage2.py build   → stage2/sample_key.json, stage2/jobs.json, stage2/eval01_stage2_part{1,2}.js (делит build_parts, см. DEVIATIONS №3)
#   python3 stage2.py analyze stage2/out.json → stage2/analysis.json
import json, os, sys, random, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'stage2'); os.makedirs(D, exist_ok=True); sys.path.insert(0, HERE)
from eval01_pilot import label, render, criterion
from eval01_main import BIG, full_chain, cell_of, clip, num, recal, metrics, agg, ci, pboot, holm, NO, TRUTH
SEED = 2811; PER_CELL = 75; ARMS = ['BLIND', 'RC1', 'C2', 'C3']; ALPHA2 = 0.025
def build():
    items = [json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl'))]; truth = json.load(open(TRUTH))
    used = set(json.load(open(os.path.join(HERE, 'pilot', 'sample_key.json')))['ids'])
    k1 = json.load(open(os.path.join(HERE, 'main', 'sample_key.json'))); used |= set(k1['ids']) | set(k1['dry_ids'])
    rng = random.Random(SEED); sample = []; plan = {}
    for key in BIG:
        pool = [x for x in items if (x['source'], x['family']) == key and not x['leak_note'] and x['id'] not in used]
        if key == ('LEVEL-04', 'MODSQ-link'): pool = [x for x in pool if label(x, truth) or full_chain(x)]   # правило 1.2: неверные — только полные цепочки
        rng.shuffle(pool); good = [x for x in pool if label(x, truth)]; bad = [x for x in pool if not label(x, truth)]
        nb = min(len(bad), PER_CELL // 2); ng = min(len(good), PER_CELL - nb); nb = min(len(bad), PER_CELL - ng)   # поровну, где есть; остаток — другим классом
        take = good[:ng] + bad[:nb]; sample += take; plan[cell_of(take[0])] = dict(good=ng, bad=nb)
    rng.shuffle(sample); aliases = {it['id']: f's{i:03d}' for i, it in enumerate(sample)}
    json.dump(dict(seed=SEED, ids=[it['id'] for it in sample], aliases=aliases, cells={aliases[it['id']]: cell_of(it) for it in sample}, plan=plan), open(os.path.join(D, 'sample_key.json'), 'w'), ensure_ascii=False, indent=1)
    jobs = [dict(alias=aliases[it['id']], arm=a, task=it['task'], answer=render(it, with_note=False), criterion=criterion(it)) for it in sample for a in ARMS]
    json.dump(jobs, open(os.path.join(D, 'jobs.json'), 'w'), ensure_ascii=False)
    src = open(os.path.join(HERE, 'eval01_main_step.js')).read().replace("name: 'eval01-main'", "name: 'eval01-stage2'")
    src = src.replace('const JOBS = null', 'const JOBS = ' + json.dumps(jobs, ensure_ascii=False)).replace('const PAIRS = null', 'const PAIRS = []').replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    open(os.path.join(D, 'eval01_stage2.js'), 'w').write(src)
    print('элементов', len(sample), plan, 'вызовов', len(jobs), 'байт', len(src.encode()))
def analyze(path):
    key = json.load(open(os.path.join(D, 'sample_key.json'))); truth = json.load(open(TRUTH))
    items = {it['id']: it for it in (json.loads(l) for l in open(os.path.join(HERE, 'data', 'items_public.jsonl')))}
    out = json.load(open(path)); out = out.get('out', out); al = key['aliases']; cells = key['cells']
    y = {al[i]: label(items[i], truth) for i in key['ids']}; imputed = {a: 0 for a in ARMS}
    def get(arm, a):
        r = (out.get(arm) or {}).get(a); p = num(r.get('p_correct')) if r else None
        if p is None: imputed[arm] += 1; return 0.5
        return clip(p)
    P = {}
    for a in y:
        b = get('BLIND', a); P[a] = dict(BLIND=b, BLIND_RECAL=recal(b), COUNCIL=st.mean([get('RC1', a), get('C2', a), get('C3', a)]))
    by = {}
    for a in y: by.setdefault(cells[a], []).append(a)
    def main_cut(arm, s): return agg([metrics([(P[a][arm], y[a]) for a in lst]) for lst in s.values()])
    res = dict(n=len(y), plan=key['plan'], imputed=imputed, main_cut={arm: main_cut(arm, by) for arm in ('BLIND', 'BLIND_RECAL', 'COUNCIL')})
    rng = random.Random(0); boots = []
    for _ in range(2000):
        s = {c: [rng.choice(l) for _ in l] for c, l in by.items()}; boots.append({arm: main_cut(arm, s) for arm in ('BLIND_RECAL', 'COUNCIL')})
    diffs = {}
    for k in ('brier', 'ioi'):
        v = [b['COUNCIL'][k] - b['BLIND_RECAL'][k] for b in boots]
        pt = res['main_cut']['COUNCIL'][k] - res['main_cut']['BLIND_RECAL'][k]
        p = pboot(v) if pt < 0 else 1.0   # предсказание: совет лучше (разность < 0)
        diffs[k] = dict(point=pt, ci95=ci(v), p_boot=p)
    res['diff_council_minus_recal'] = diffs
    res['holm'] = holm({k: d['p_boot'] for k, d in diffs.items()}, alpha=ALPHA2)
    rej = res['holm']['table']
    res['verdict'] = 'совет подтверждён' if all(rej[k]['reject'] for k in ('brier', 'ioi')) else ('совет подтверждён частично (' + ', '.join(k for k in ('brier', 'ioi') if rej[k]['reject']) + ')' if any(rej[k]['reject'] for k in ('brier', 'ioi')) else 'совет не подтверждён')
    json.dump(res, open(os.path.join(D, 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ('n', 'plan', 'imputed', 'main_cut', 'diff_council_minus_recal', 'verdict')}, ensure_ascii=False, indent=1))
if __name__ == '__main__':
    build() if sys.argv[1] == 'build' else analyze(sys.argv[2])
