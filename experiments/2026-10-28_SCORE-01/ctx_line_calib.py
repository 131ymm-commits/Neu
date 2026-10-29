#!/usr/bin/env python3
"""SCORE-01: калибровка абсолютной меры проверки контекста (LENSES-1c, П1) — вход первого запроса ≈ a + b·байты промпта.
Линия строится по чистому пилоту 3 отдельно для каждой модели и пишется в run/pilot_ctx_line.json (её читает ctx_check.py).
Здесь же — проверка линии: остатки на пилоте 3 (в выборке и с исключением задачи), остатки пилотов 1–2 (снимок git), диапазон
байтов промптов теста и внесённые в пилот 3 сдвиги (ступенька, дрейф). Вход берётся из журнала (поле stream.events_no_deltas).
Головы не вызываются. Импорт ничего не пишет: всё — в main().
  python3 ctx_line_calib.py   → run/pilot_ctx_line.json и печать (журнал — run/pilot_ctx_line.log)"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctx_check as C  # noqa: E402

PILOT_JOBS = {'pilot1': 'run/pilot1_jobs.jsonl', 'pilot2': 'run/pilot2_jobs.jsonl', 'pilot3': 'run/pilot3_jobs.jsonl'}
f = lambda x, d=1: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def rows(stage):
    jobs = C.prompt_bytes(os.path.join(HERE, PILOT_JOBS[stage.split('_')[0]]))
    rs, skipped, _ = C.stage_rows(os.path.join(HERE, 'run', stage), None)
    return [r + (jobs[r[0]],) for r in rs], skipped


def fit(x, y):
    X = np.c_[np.ones(len(x)), x]
    return np.linalg.lstsq(X, y, rcond=None)[0]


def main():
    out = dict(note='линия «вход первого запроса = a + b·байты промпта» по чистому пилоту 3; LENSES-1c П1', line={}, check={})
    for model, st in (('claude-opus-5-5', 'pilot3_opus'), ('claude-haiku-5-5', 'pilot3_haiku')):
        R, sk = rows(st)
        x = np.array([r[-1] for r in R], float); y = np.array([r[5] for r in R], float); task = [r[1] for r in R]
        a, b = fit(x, y); res = y - (a + b * x)
        loto = np.empty(len(R))                                  # остатки с исключением задачи: линия без этой задачи
        for t in sorted(set(task)):
            m = np.array([q == t for q in task])
            a_, b_ = fit(x[~m], y[~m]); loto[m] = y[m] - (a_ + b_ * x[m])
        out['line'][model] = dict(a=float(a), b=float(b), n=len(R), skipped=len(sk), bytes_range=[int(x.min()), int(x.max())],
                                  resid_sd=float(res.std(ddof=2)), resid_max=float(np.abs(res).max()),
                                  loto_sd=float(loto.std(ddof=1)), loto_max=float(np.abs(loto).max()))
        print(f"{model}: a {f(a)}, b {f(b, 4)}; вызовов {len(R)}, байты промпта {int(x.min())}–{int(x.max())}; остаток SD {f(res.std(ddof=2))}, "
              f"наибольший {f(np.abs(res).max())}; с исключением задачи SD {f(loto.std(ddof=1))}, наибольший {f(np.abs(loto).max())}")

    # байты промптов теста против пилотного диапазона
    for st in ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku'):
        xb = list(C.prompt_bytes(os.path.join(HERE, 'jobs', f'{st}_jobs.jsonl')).values())
        out['check'][f'bytes_{st}'] = [min(xb), max(xb)]
        print(f'{st}: байты промптов {min(xb)}–{max(xb)}')
    # пилоты 1–2 (снимок git) против линии пилота 3
    for st in ('pilot1_opus', 'pilot1_haiku', 'pilot2_opus', 'pilot2_haiku'):
        R, _ = rows(st)
        model = 'claude-opus-5-5' if st.endswith('opus') else 'claude-haiku-5-5'
        L = out['line'][model]
        r = np.array([q[5] - (L['a'] + L['b'] * q[-1]) for q in R])
        out['check'][st] = dict(mean=float(r.mean()), min=float(r.min()), max=float(r.max()), frac_gt=float(np.mean(np.abs(r) > C.R_ABS)))
        print(f'{st}: остаток против линии пилота 3 — среднее {f(r.mean())}, наименьший {f(r.min())}, наибольший {f(r.max())}, '
              f'доля |остаток| > {f(C.R_ABS, 0)}: {f(np.mean(np.abs(r) > C.R_ABS), 3)}')
    # внесённые сдвиги на пилоте 3 (в выборке): ступенька с середины этапа и дрейф по времени
    for model, st in (('claude-opus-5-5', 'pilot3_opus'), ('claude-haiku-5-5', 'pilot3_haiku')):
        R, sk = rows(st)
        t = np.array([q[4] for q in R]); mid = np.median(t)
        for name, add in (('без сдвига', np.zeros(len(R))), ('ступенька +1400 с середины', 1400.0 * (t >= mid)),
                          ('ступенька +100 с середины', 100.0 * (t >= mid)), ('постоянная +700', np.full(len(R), 700.0)),
                          ('дрейф 1000 ток./ч', 1000.0 * (t - t.min()))):
            R2 = [q[:5] + (q[5] + d,) for q, d in zip(R, add)]
            chk = C.stage_check(R2, sk, line=out['line'][model], nbytes=[q[-1] for q in R])
            out['check'].setdefault(f'inject_{st}', {})[name] = dict(flag=chk['flag'], why=chk['why'])
            print(f"  {st}, {name}: флаг {'да' if chk['flag'] else 'нет'} ({'; '.join(chk['why']) or '—'})")
    json.dump(out, open(os.path.join(HERE, 'run', 'pilot_ctx_line.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
