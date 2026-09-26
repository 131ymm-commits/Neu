# DIV-02, редакция 3 (совет, docs/council; council_div02_v1.json). Классический шаг: n/2 или 3n+1.
# Руки: CHAIN (эстафета по 60 значений), SOLO_LONG (одна голова, весь путь), SEG1 (одна голова, отрезки по 60 в одном контексте),
# SC (m полных попыток, мода), EST (оценка). Все пошаговые руки выписывают каждое значение; шаги и правильность считает код.
#   build <pilot|run> | analyze <pilot|run> <out.json>
import json, sys, math, random, hashlib, statistics as st
from hive_core import score_q
TIERS = [(10**12, 10**13), (10**15, 10**16), (10**18, 10**19)]
CFG = dict(pilot=dict(seed=93000, per=3, m=3), run=dict(seed=92000, per=8, m=None))
NO = 'Не используй никакие инструменты и не открывай файлы: считай сам, в уме, опираясь только на текст ниже.'


def traj(n):
    t = []
    while n != 1: n = n // 2 if n % 2 == 0 else 3 * n + 1; t.append(n)
    return t


def build(mode, m=None):
    c = CFG[mode]; rng = random.Random(c['seed'])
    qs = [dict(id=f'{mode[0].upper()}{t}-{i}', tier=t, n=rng.randrange(*TIERS[t])) for t in range(3) for i in range(c['per'])]
    for q in qs: q['L'] = len(traj(q['n']))
    K = max(12, math.ceil(1.2 * max(q['L'] for q in qs) / 60))
    sec = f'/root/div_secret/div02b_{mode}.json'; json.dump(qs, open(sec, 'w'))
    order_rng = random.Random(c['seed'] + 1)
    pub = [dict(id=q['id'], n=str(q['n']), order=order_rng.sample(['CHAIN', 'SOLO_LONG', 'SEG1', 'SC', 'EST'], 5)) for q in qs]
    js = open('div02b_step.js').read().replace('const QS = null', 'const QS = ' + json.dumps(pub)).replace('const NO = null', 'const NO = ' + json.dumps(NO, ensure_ascii=False))
    js = js.replace('const K = null', f'const K = {K}').replace('const M = null', f'const M = {m or c["m"]}').replace("name: 'div02b'", f"name: 'div02b-{mode}'")
    open(f'{"pilot" if mode == "pilot" else "run"}/div02b_{mode}.js', 'w').write(js)
    print(mode, 'чисел', len(qs), 'L', [q['L'] for q in qs], 'K', K, 'sha правды', hashlib.sha256(json.dumps(qs).encode()).hexdigest()[:16])


def m1(values, truth):
    """M1 = (i−1)/L, i — первый шаг, где значение не совпало с правдой (или первый невыписанный)."""
    L = len(truth)
    for i, t in enumerate(truth):
        if i >= len(values) or str(values[i]).strip() != str(t): return i / L, i
    return 1.0, L


def chain_values(links):
    vals, broken_at = [], None
    for k, l in enumerate(links):
        if not l or not isinstance(l.get('values'), list): break
        v = [str(x).strip() for x in l['values']]
        vals += v
        if '1' in v: break
        if len(v) != 60: broken_at = len(vals) - len(v); break  # звено не из 60 значений — ошибка на его первом шаге
    return vals, broken_at


def analyze(mode, path):
    qs = json.load(open(f'/root/div_secret/div02b_{mode}.json')); r = json.load(open(path)); rows = []
    for q in qs:
        T = [str(x) for x in traj(q['n'])]; L = len(T); o = r[q['id']]; row = dict(id=q['id'], tier=q['tier'], L=L)
        for arm in ('SOLO_LONG', 'SEG1'):
            v = ((o.get(arm) or {}).get('values')) or []; row[arm] = m1(v, T)[0]
            row[arm + '_exact'] = (v.index('1') + 1 if '1' in v else None) == L and m1(v, T)[0] == 1.0
        cv, bad = chain_values(o.get('CHAIN') or [])
        mm, i = m1(cv, T)
        if bad is not None: mm = min(mm, bad / L)
        row['CHAIN'] = mm; row['CHAIN_exact'] = mm == 1.0; row['CHAIN_links'] = len(o.get('CHAIN') or [])
        sc = [(x or {}).get('values') or [] for x in (o.get('SC') or [])]
        ans = [v.index('1') + 1 if '1' in v else None for v in sc]; cnt = {}
        for a in ans:
            if a is not None: cnt[a] = cnt.get(a, 0) + 1
        mode_ans = max(cnt, key=lambda a: (cnt[a], -ans.index(a))) if cnt else None
        row['SC_exact'] = mode_ans == L; row['SC_M1'] = [m1(v, T)[0] for v in sc]
        e = o.get('EST') or {}; row['EST'] = e.get('steps'); row['EST_exact'] = e.get('steps') == L
        rows.append(row)
    json.dump(rows, open(f'{"pilot" if mode == "pilot" else "run"}/div02b_rows.json', 'w'), indent=1)
    for x in rows: print(x['id'], 'L', x['L'], '| M1 CHAIN %.2f SOLO_LONG %.2f SEG1 %.2f SC %s | точно C/S/G/SC/E' % (x['CHAIN'], x['SOLO_LONG'], x['SEG1'], [round(v, 2) for v in x['SC_M1']]),
                         int(x['CHAIN_exact']), int(x['SOLO_LONG_exact']), int(x['SEG1_exact']), int(x['SC_exact']), int(x['EST_exact']))


if __name__ == '__main__':
    build(sys.argv[2]) if sys.argv[1] == 'build' else analyze(sys.argv[2], sys.argv[3])
