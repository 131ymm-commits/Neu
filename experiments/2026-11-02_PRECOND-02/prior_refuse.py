# PRECOND-02, подготовка (пост-хок по старым данным, не в зачёт; до пилота и до PREREG):
# контраст REFUSE — опора D_N против той же опоры без REFUSE — мерой PRECOND-01, на выборках, где обе руки уже есть.
# По коду (02.11): клетка PRECOND {ROLE, PROCEDURE} байт в байт равна промпту C_N SELECT-01 / THINK-01, клетка C44 — D_N.
# Мера PRECOND-01 (PREREG §4, §4.6): регрет голоса нормированный; отказ (−1) → регрет A0 задачи; сбой и мусор → 1;
# мера руки на задаче — средний регрет её пяти голосов; задача исключается, если лучший − средний ≤ EPS (150).
# В SELECT-01 и THINK-01 первичная мера была другой (большинство голосов, у D_N — среди неотказавшихся), поэтому числа здесь новые.
# Правда — sim.truth из опубликованных солей (sha256 сверяются с PREREG этих опытов). Экспозиция «снимка git» — журнал аудита 29.10.
#   python3 prior_refuse.py  →  prior_refuse.json
import hashlib, json, math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(HERE, '..'); SEL = os.path.join(EXP, '2026-10-07_SELECT-01')
sys.path.insert(0, SEL)
import sim  # noqa: E402
from analyze import EPS, a0  # noqa: E402
SAMPLES = [   # (имя, папка, файл выборов, сиды, соль, sha256 соли по PREREG/DEVIATIONS)
    ('SELECT-01 main', '2026-10-07_SELECT-01', 'evals/main_eval.jsonl', range(8001, 8101), 'salts/main_salt.txt', 'c2ec553d51a5158c26b69609c4226fd6168e49de51e0c23176f041d651420d32'),
    ('SELECT-01 rep', '2026-10-07_SELECT-01', 'evals/rep_eval.jsonl', range(8101, 8201), 'salts/main_salt.txt', 'c2ec553d51a5158c26b69609c4226fd6168e49de51e0c23176f041d651420d32'),
    ('THINK-01 rep', '2026-10-15_THINK-01', 'evals/rep_eval.jsonl', range(8251, 8301), 'salts/rep_salt.txt', '9ccf6c2435be4246da3d10778a08bac087704ef43c385a96b013df49974fbb10'),
]
AUD = json.load(open(os.path.join(EXP, '..', 'journal', 'AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.json'), encoding='utf-8'))
EXPOSED = {'SELECT-01 rep': set().union(*(set(v['tasks']) for v in AUD['experiments/2026-10-07_SELECT-01/run/rep_eval_journal']['exposed'].values()))}

def tq(q, df):   # квантиль t бисекцией по неполной бете (как analyze_precond.t_ppf), чтобы не тянуть scipy
    sys.path.insert(0, os.path.join(EXP, '2026-10-21_PRECOND-01')); import analyze_precond as AP; return AP.t_ppf(q, df)

def ci(v):
    n = len(v); m = st.mean(v); s = st.stdev(v); h = tq(0.975, n - 1) * s / math.sqrt(n); return dict(n=n, mean=round(m, 4), sd=round(s, 4), ci95=[round(m - h, 4), round(m + h, 4)])

out = {}
for name, folder, evf, seeds, saltf, sha in SAMPLES:
    D = os.path.join(EXP, folder); salt = open(os.path.join(D, saltf)).read().strip()
    assert hashlib.sha256(salt.encode()).hexdigest() == sha, f'{name}: sha256 соли не совпал'
    votes = {}
    for e in map(json.loads, open(os.path.join(D, evf), encoding='utf-8')):
        if e['arm'] in ('C_N', 'D_N'): votes.setdefault((e['task'], e['arm']), {})[int(e['i'])] = e
    per, a0r, refs, outs, excl = {}, [], {'C_N': [0, 0], 'D_N': [0, 0]}, {'C_N': [], 'D_N': []}, []
    for s in seeds:
        t = f'WH_{s}'; pp = os.path.join(D, 'pools', f'{t}.json')
        if not os.path.exists(pp) or (t, 'C_N') not in votes: continue
        pool = json.load(open(pp)); tk = json.load(open(os.path.join(D, 'tasks', f'{t}.json')))
        tr = [sim.truth(tk, c['plan'], salt) for c in pool]; orc, mu = max(tr), st.mean(tr)
        if orc - mu <= EPS['WH']: excl.append(t); continue
        reg = lambda i: (orc - tr[i]) / (orc - mu); ra0 = reg(a0(pool, t)); a0r.append(ra0)
        m = {}
        for arm in ('C_N', 'D_N'):
            rs = []
            for i in range(5):
                e = votes[(t, arm)].get(i); c = None if e is None or e.get('error') else e.get('choice')
                rs.append(reg(c) if isinstance(c, int) and 0 <= c < len(tr) else (ra0 if c == -1 else 1.0))
                refs[arm][0] += c == -1; refs[arm][1] += 1; outs[arm].append((e or {}).get('out') or 0)
            m[arm] = st.mean(rs)
        per[t] = m
    T = sorted(per); d = [per[t]['D_N'] - per[t]['C_N'] for t in T]
    r = dict(tasks=len(T), excluded_eps=excl, A0_mean=round(st.mean(a0r), 4), C_N=round(st.mean(per[t]['C_N'] for t in T), 4),
             D_N=round(st.mean(per[t]['D_N'] for t in T), 4), D_minus_C=ci(d),
             refusal_share={a: round(v[0] / v[1], 4) for a, v in refs.items()}, out_mean={a: round(st.mean(v)) for a, v in outs.items()})
    if name in EXPOSED:
        dd = [per[t]['D_N'] - per[t]['C_N'] for t in T if t not in EXPOSED[name]]; r['D_minus_C_unexposed'] = ci(dd)
    out[name] = r
json.dump(out, open(os.path.join(HERE, 'prior_refuse.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
