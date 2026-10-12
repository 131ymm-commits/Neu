# SELECT-01: объединённая оценка по основной выборке и повтору (совет 31: Левое, Инженер) — описательно, без p.
#   python3 pool.py main_an_wh.json rep_an_wh.json [--out pooled_wh.json]
# Каждая выборка считается своим analyze.py со своей солью (свой SELECT_SECRET). Здесь берутся per_task обеих выборок:
# разности регрета C_N − B_blind, D_N − B_blind, C_N − A0, D_N − A0 по задачам, среднее по объединению задач и
# 95 % ДИ бутстрепом по задачам (analyze.boot_ci: 20 000 повторов, зерно 0).
import argparse, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import boot_ci  # noqa: E402
PAIRS = (('C_N', 'B_blind'), ('D_N', 'B_blind'), ('C_N', 'A0'), ('D_N', 'A0'))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('files', nargs=2); ap.add_argument('--out'); a = ap.parse_args()
    per = [json.load(open(f))['per_task'] for f in a.files]
    both = set(per[0]) & set(per[1])
    if both:
        sys.exit(f'задачи повторяются в двух выборках: {sorted(both)[:5]}')
    out = dict(files=a.files, n_tasks=[len(p) for p in per], pooled={})
    for x, y in PAIRS:
        d = [p[t][x] - p[t][y] for p in per for t in sorted(p) if x in p[t] and y in p[t]]
        if d:
            lo, hi = boot_ci(d)
            out['pooled'][f'{x} − {y}'] = dict(n=len(d), mean=round(st.mean(d), 3), ci95=[round(lo, 3), round(hi, 3)])
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.out:
        json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
