# PRECOND-01, пилот на effort high (27.10.2026; слово автора «Делай» — пилот до заморозки PREREG, совет 36).
# Только разброс голоса на high для мощности контраста взаимодействия effort × ингредиент; выводов о действиях нет, в тест не идёт.
# Клетки заданы правилом до вызовов: предусловия P00, P05, P10, P15 (каждое пятое из 16; две пары дополнений, каждый ингредиент
# включён ровно в двух) × задачи WH_8001–8005 (первые пять пилота) × 1 голос = 20 вызовов. Промпты — байт в байт из pilot_jobs.jsonl.
#   python3 pilot_high.py jobs | collect | analyze
import json, math, os, statistics as st, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault('PRECOND_TAG', 'pilot_high')
import pilot_precond as PL  # noqa: E402
PRES = ['P00', 'P05', 'P10', 'P15']; TASKS = [f'WH_{s}' for s in range(8001, 8006)]

def jobs():
    js = [j for j in map(json.loads, open(f'{HERE}/run/pilot_jobs.jsonl')) if j['id'].split('|')[0] in TASKS and j['id'].split('|')[1] in PRES]
    assert len(js) == len(PRES) * len(TASKS)
    with open(f'{HERE}/run/pilot_high_jobs.jsonl', 'w') as fh:
        for j in js: fh.write(json.dumps(j, ensure_ascii=False) + '\n')
    print(len(js), 'заданий')

def rows(evals):
    out = []
    for e in map(json.loads, open(evals)):
        if e['task'] not in TASKS or e['pre'] not in PRES: continue
        tr = json.load(open(f'{PL.SEC}/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr); reg = lambda i: (orc - tr[i]) / (orc - mean)
        c = e['choice']; refused = c == -1; valid = isinstance(c, int) and 0 <= c < len(tr)
        r = reg(c) if valid else (reg(PL.a0(PL.pool_of(e['task']), e['task'])) if refused else 1.0)   # как в пилоте medium
        out.append(dict(task=e['task'], pre=e['pre'], regret=r, refused=refused, lost=not valid and not refused, out=e['out'] or 0,
                        p_best=e['p_best'], hit=valid and tr[c] == orc))
    return out

def stats(R):
    """Разброс в двухфакторной раскладке «задача × предусловие» без повторов: остаток после средних задачи и предусловия."""
    g = st.mean(x['regret'] for x in R)
    tm = {t: st.mean(x['regret'] for x in R if x['task'] == t) for t in TASKS}
    pm = {p: st.mean(x['regret'] for x in R if x['pre'] == p) for p in PRES}
    res = [x['regret'] - tm[x['task']] - pm[x['pre']] + g for x in R]
    df = (len(TASKS) - 1) * (len(PRES) - 1)
    conf = [(x['p_best'], x['hit']) for x in R if x['p_best'] is not None and not x['refused']]
    return dict(n=len(R), lost=sum(x['lost'] for x in R), refused=sum(x['refused'] for x in R), mean_regret=round(g, 3),
                sd_vote=round(st.pstdev([x['regret'] - tm[x['task']] for x in R]), 3),            # та же мера, что sd_vote пилота medium
                sd_resid_df=round(math.sqrt(sum(v * v for v in res) / df), 3), df=df,           # остаток с поправкой на степени свободы
                out_per_call=round(st.mean(x['out'] for x in R)), zero=sum(x['regret'] == 0 for x in R),
                per_pre={p: round(pm[p], 3) for p in PRES},
                conf=dict(n=len(conf), mean_p=round(st.mean(p for p, h in conf), 3) if conf else None,
                          hit=round(sum(h for p, h in conf) / len(conf), 3) if conf else None))

def analyze():
    hi, me = rows(f'{HERE}/evals/pilot_high.jsonl'), rows(f'{HERE}/evals/pilot.jsonl')
    assert len(hi) == len(me) == len(PRES) * len(TASKS)
    s = dict(high=stats(hi), medium_same_cells=stats(me))
    sm, sh = s['medium_same_cells']['sd_resid_df'], s['high']['sd_resid_df']
    # мощность контраста взаимодействия effort × ингредиент: SE = √(SE_m² + SE_h²), SE_уровня = 2·sd/√N (совет 36, голос «против»)
    s['n_per_level_for_se_interaction'] = {str(t): math.ceil(4 * (sm ** 2 + sh ** 2) / t ** 2) for t in (0.05, 0.071)}
    s['ratio_sd_high_to_medium'] = round(sh / sm, 2) if sm else None
    json.dump(s, open(f'{HERE}/pilot_high_analysis.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(s, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    if sys.argv[1] == 'collect': PL.collect()
    else: dict(jobs=jobs, analyze=analyze)[sys.argv[1]]()
