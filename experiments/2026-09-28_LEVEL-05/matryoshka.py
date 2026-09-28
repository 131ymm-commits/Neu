# LEVEL-05 матрёшка: сборка сценария и анализ. python3 matryoshka.py build <tag> | analyze <tag> <out.json>
# Уровни (вложены): L1 = решатель S0; L2 = интегратор a (решатели S0–S3, 5 голов); L3 = интегратор a уровня 3 (L2 a, b — 10 голов + 1); L4 (20 голов + 3).
import json, os, sys, statistics as st, random, math
HERE = os.path.dirname(os.path.abspath(__file__)); SECRET = '/root/level5_secret'
def within(a, t):
    try: a = int(str(a).replace(' ', '').replace(',', '')); t = int(t)
    except Exception: return False
    return abs(a - t) <= 0.01 * abs(t)
def clip(c):
    try: return min(1.0, max(0.0, float(c)))
    except Exception: return 0.5
def build(tag):
    tasks = json.load(open(f'{HERE}/tasks/{tag}.json'))
    src = open(f'{HERE}/matryoshka_step.js').read().replace('const TASKS = null', 'const TASKS = ' + json.dumps([dict(id=t['id'], text=t['text']) for t in tasks], ensure_ascii=False))
    os.makedirs(f'{HERE}/run', exist_ok=True); open(f'{HERE}/run/{tag}.js', 'w').write(src); print('задач', len(tasks), 'вызовов', 23 * len(tasks))
def metrics(rows):
    if not rows: return None
    T = st.mean(r[1] for r in rows); C = st.mean(r[0] for r in rows)
    return dict(n=len(rows), T=round(T, 3), C=round(C, 3), ioi=round((1 - T) + max(0, C - T), 3), brier=round(st.mean((c - y) ** 2 for c, y in rows), 3), missing=0)
def analyze(tag, path):
    truth = json.load(open(f'{SECRET}/{tag}.json')); tasks = {t['id']: t for t in json.load(open(f'{HERE}/tasks/{tag}.json'))}
    out = json.load(open(path)); out = out.get('out', out)
    lv = {1: [], 2: [], 3: [], 4: []}; fam = {}; allS = []; miss = {1: 0, 2: 0, 3: 0, 4: 0}
    for tid, o in out.items():
        t = truth[tid]; f = tasks[tid]['fam']
        units = {1: [o['S'][0]], 2: [o['L2'][0]], 3: [o['L3'][0]], 4: [o['L4']]}
        for L, us in units.items():
            u = us[0]
            if not u: miss[L] += 1; continue
            row = (clip(u.get('confidence')), float(within(u.get('answer'), t)))
            lv[L].append(row); fam.setdefault(f, {}).setdefault(L, []).append(row)
        for s in o['S']:
            if s: allS.append((clip(s.get('confidence')), float(within(s.get('answer'), t))))
    res = dict(levels={L: metrics(r) for L, r in lv.items()}, missing=miss, all_solvers=metrics(allS),
               by_family={f: {L: metrics(r) for L, r in d.items()} for f, d in fam.items()})
    # ренормировка: предсказание T уровня k+1 при независимости частей = P(большинство верных) по T уровня k
    def maj(p, n):
        return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n // 2 + 1, n + 1)) + (0.5 * math.comb(n, n // 2) * p ** (n // 2) * (1 - p) ** (n // 2) if n % 2 == 0 else 0)
    ren = {}
    Ts = {L: (res['levels'][L] or {}).get('T') for L in lv}
    if Ts[1] is not None: ren['L2_pred_from_solvers_indep'] = round(maj(res['all_solvers']['T'], 4), 3)
    if Ts[2] is not None: ren['L3_pred_from_L2_indep'] = round(maj(Ts[2], 2), 3)
    if Ts[3] is not None: ren['L4_pred_from_L3_indep'] = round(maj(Ts[3], 2), 3)
    # корреляция решателей: доля задач, где все 16 дали одинаковый ответ
    same = [len({(s or {}).get('answer') for s in o['S']}) == 1 for o in out.values()]
    ren['share_tasks_all16_same_answer'] = round(st.mean(same), 3) if same else None
    res['renorm'] = ren
    json.dump(res, open(f'{HERE}/run/{tag}_analysis.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res['levels'], ensure_ascii=False)); print('решатели все:', res['all_solvers']); print('ренормировка:', ren)
    for f, d in res['by_family'].items(): print(f, {L: (m['T'], m['C'], m['ioi']) for L, m in d.items() if m})
if __name__ == '__main__':
    build(sys.argv[2]) if sys.argv[1] == 'build' else analyze(sys.argv[2], sys.argv[3])
