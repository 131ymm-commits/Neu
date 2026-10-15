# SELECT-01: объясняет ли длина размышлений выигрыш D_N? Пост-хок после итогового отчёта (советы 32 и 33, «что проверить
# потом»: длина размышлений, сравнение D_N и C_N при одинаковой длине). Описательно, вердикт не меняет.
# Единица — отдельный голос (регрет его выбора по правде от кода), длина — выходные токены вызова (out).
# 1) Внутри задачи и руки: длиннее думавшие голоса ошибаются меньше? Среднее по задачам (регрет длинной половины −
#    короткой) и Спирмен внутри задачи.
# 2) D_N против C_N при равной длине: МНК на отклонениях от средних задачи, регрет ~ [голос D_N] + ln(out);
#    ДИ — бутстреп по задачам.
#   python3 thinking_posthoc.py > thinking_posthoc.json      (правда: /root/select_secret*/truth или SEC_MAIN, SEC_REP)
import collections, json, math, os, statistics as st, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import spearman  # noqa: E402
SEC = {'main': os.environ.get('SEC_MAIN', '/root/select_secret'), 'rep': os.environ.get('SEC_REP', '/root/select_secret_rep')}
r3 = lambda x: round(float(x), 3)
out = {'note': 'пост-хок после итогового отчёта и совета 33; описательно, вердикт не меняет'}
for S in ('main', 'rep'):
    tasks = sorted(json.load(open(f'{S}_an_wh.json'))['per_task'])
    V = collections.defaultdict(list)   # (задача, рука) → [(регрет, out)]
    for line in open(f'evals/{S}_eval.complete.jsonl', encoding='utf-8'):
        e = json.loads(line)
        if e['task'] in tasks and isinstance(e.get('choice'), int) and e['choice'] >= 0 and e.get('out'):
            V[(e['task'], e['arm'])].append((e['choice'], e['out']))
    res = {}
    for arm in ('B_blind', 'B_zayavka', 'C_N', 'D_N'):
        halves, rhos = [], []
        for t in tasks:
            tr = json.load(open(f'{SEC[S]}/truth/{t}.json')); orc, mean = max(tr), st.mean(tr)
            v = [((orc - tr[c]) / (orc - mean), o) for c, o in V[(t, arm)]]
            if len(v) < 3:
                continue
            med = st.median(o for _, o in v)
            lo = [r for r, o in v if o < med]; hi = [r for r, o in v if o > med]
            if lo and hi:
                halves.append(st.mean(hi) - st.mean(lo))
            if len({r for r, _ in v}) > 1 and len({o for _, o in v}) > 1:
                rhos.append(spearman([o for _, o in v], [r for r, _ in v]))
        res[arm] = dict(tasks=len(halves), long_minus_short_regret=r3(st.mean(halves)), within_task_spearman_out_regret=r3(st.mean(rhos)),
                        mean_out=round(st.mean(o for t in tasks for _, o in V[(t, arm)])))
    rows = []   # D_N и C_N, отклонения от средних задачи
    for t in tasks:
        tr = json.load(open(f'{SEC[S]}/truth/{t}.json')); orc, mean = max(tr), st.mean(tr)
        v = [((orc - tr[c]) / (orc - mean), math.log(o), 1.0 if a == 'D_N' else 0.0) for a in ('C_N', 'D_N') for c, o in V[(t, a)]]
        if len({d for *_, d in v}) < 2:
            continue
        m = np.array(v); m -= m.mean(axis=0); rows.append(m)
    def fit(blocks):
        X = np.vstack(blocks); b, *_ = np.linalg.lstsq(X[:, 1:], X[:, 0], rcond=None); return b   # [ln(out), голос D_N]
    b = fit(rows); rng = np.random.default_rng(15102026)
    bs = np.array([fit([rows[i] for i in rng.integers(0, len(rows), len(rows))]) for _ in range(2000)])
    ci = lambda j: [r3(np.percentile(bs[:, j], 2.5)), r3(np.percentile(bs[:, j], 97.5))]
    res['D_N_vs_C_N_at_equal_length'] = dict(tasks=len(rows), coef_D_N=r3(b[1]), ci95_D_N=ci(1), coef_ln_out=r3(b[0]), ci95_ln_out=ci(0),
        note='регрет ~ голос D_N + ln(out), отклонения от средних задачи; отрицательное — меньше регрет')
    out[S] = res
print(json.dumps(out, ensure_ascii=False, indent=1))
