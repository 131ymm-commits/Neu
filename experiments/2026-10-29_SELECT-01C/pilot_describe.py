#!/usr/bin/env python3
"""SELECT-01C: описание пилота чистого контекста (6 задач пилота 2 SELECT-01 — WH 7307–7312; руки B_blind × 12 и D_N × 5; Opus 5.5,
medium, конфигурация jobs/cfg_clean.json). Полный прогон SELECT-01C не регистрируется (ERRORS № 124); пилот — запись для промптов
SELECT-01 в чистой конфигурации. Вход первого запроса — из журнала (stream.events_no_deltas), как ctx_check.py SCORE-01.
Выборы — тем же кодом SELECT-01: harness.py collect_eval (номера обратно через perm), analyze.py (регрет; правда — из опубликованной
соли основной выборки, она же соль пилотов). Описательно, без проверок гипотез: пилот мал.
  python3 pilot_describe.py   → pilot_describe.json и печать (журнал — run/pilot_describe.log)"""
import json
import os
import statistics as st
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SEL = os.path.join(ROOT, 'experiments', '2026-10-07_SELECT-01')
SC = os.path.join(ROOT, 'experiments', '2026-10-28_SCORE-01')
SEC = os.path.join(ROOT, '.cache', 'select01c_secret', 'main')
f = lambda x, d=1: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def main():
    sys.path.insert(0, SC)
    import ctx_check as C
    env = dict(os.environ, SELECT_ROOT=HERE, SELECT_SECRET=SEC)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'run_sealed2.py'), 'export', '--journal', os.path.join(HERE, 'run', 'pilot'),
                    '--out', os.path.join(HERE, 'run', 'pilot_out.jsonl')], check=True, cwd=ROOT, capture_output=True)
    subprocess.run([sys.executable, os.path.join(SEL, 'harness.py'), 'collect_eval', 'pilot'], check=True, env=env, capture_output=True)
    an = subprocess.run([sys.executable, os.path.join(SEL, 'analyze.py'), 'WH', os.path.join(HERE, 'evals', 'pilot.jsonl'),
                         '--out', os.path.join(HERE, 'pilot_an_wh.json')], check=True, env=env, capture_output=True, text=True)
    A = json.load(open(os.path.join(HERE, 'pilot_an_wh.json'), encoding='utf-8'))
    out = dict(analyze={k: A[k] for k in ('n_tasks', 'excluded', 'invalid_votes', 'mean_regret', 'tokens', 'budget', 'tests', 'secondary')})
    log = []
    # вход первого запроса против байтов промпта
    nb = C.prompt_bytes(os.path.join(HERE, 'jobs', 'pilot_jobs.jsonl'))
    rows, skipped, meta = C.stage_rows(os.path.join(HERE, 'run', 'pilot'), None)
    x = np.array([nb[r[0]] for r in rows], float)
    y = np.array([r[5] for r in rows], float)
    X = np.c_[np.ones(len(x)), x]
    a, b = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - (a + b * x)
    L = json.load(open(os.path.join(SC, 'run', 'pilot_ctx_line.json'), encoding='utf-8'))['line']['claude-opus-5-5']
    r_sc = y - (L['a'] + L['b'] * x)
    chk = C.stage_check(rows, skipped, line=None, nbytes=None)
    cfg = C.config_check(os.path.join(HERE, 'run', 'pilot'), meta)
    out['ctx'] = dict(n=len(rows), skipped=len(skipped), line=dict(a=float(a), b=float(b), resid_sd=float(res.std(ddof=2)), resid_max=float(np.abs(res).max()),
                                                                  bytes_range=[int(x.min()), int(x.max())]),
                      vs_score01_line=dict(mean=float(r_sc.mean()), max_abs=float(np.abs(r_sc).max())),
                      within_task=dict(max_abs=chk.get('max_abs_resid'), frac_gt=chk.get('frac_resid_gt')), config=cfg)
    log.append(f"вход первого запроса: вызовов {len(rows)}, без входа {len(skipped)}; линия пилота a {f(a)}, b {f(b, 4)} токена на байт, "
               f"остаток SD {f(res.std(ddof=2))}, наибольший {f(np.abs(res).max())}; байты промпта {int(x.min())}–{int(x.max())}")
    log.append(f"против линии Opus из SCORE-01 (a {f(L['a'])}, b {f(L['b'], 4)}): средний остаток {f(r_sc.mean())}, наибольший |остаток| {f(np.abs(r_sc).max())}")
    log.append(f"внутри задачи (вход = задача + рука): наибольший |остаток| {f(chk.get('max_abs_resid') or 0)}, доля > 25 — {f(chk.get('frac_resid_gt') or 0, 3)}; "
               f"конфигурация: {cfg}")
    # вызовы, токены, время, цена
    recs = [json.loads(l) for l in open(os.path.join(HERE, 'run', 'pilot_out.jsonl'), encoding='utf-8')]
    J = {}
    import glob
    for p in glob.glob(os.path.join(HERE, 'run', 'pilot', 'WH_*.jsonl')):
        for l in open(p, encoding='utf-8'):
            r = json.loads(l)
            if r.get('final'):
                J[r['job']] = r
    import datetime as dt
    for arm in ('B_blind', 'D_N'):
        rr = [r for k, r in J.items() if k.split('|')[1] == arm]
        dur = [(dt.datetime.fromisoformat(r['finished']) - dt.datetime.fromisoformat(r['started'])).total_seconds() for r in rr]
        cost = sum(r['usage']['cost_usd'] for r in rr)
        outt = [r['usage']['out'] for r in rr]
        ok = sum(1 for r in rr if r['final'] == 'годный')
        ref = sum(1 for e in map(json.loads, open(os.path.join(HERE, 'evals', 'pilot.jsonl'), encoding='utf-8')) if e['arm'] == arm and e['choice'] == -1)
        out[arm] = dict(calls=len(rr), valid=ok, refusals=ref, out_mean=st.mean(outt), dur_median=st.median(dur), dur_max=max(dur), cost=cost)
        log.append(f"{arm}: вызовов {len(rr)}, годных {ok}, отказов {ref}; выход в среднем {st.mean(outt):.0f} токенов; длительность медиана {st.median(dur):.0f} с, "
                   f"наибольшая {max(dur):.0f} с; цена {f(cost, 2)} $")
    tot = sum(r['usage']['cost_usd'] for r in J.values())
    out['cost_total'] = tot
    log.append(f"всего: вызовов {len(J)}, цена {f(tot, 2)} $; выгрузка — {len(recs)} записей")
    mr = A['mean_regret']
    log.append('регрет (описательно, 6 задач): ' + ', '.join(f"{k} {f(v['mean'], 3)}" for k, v in mr.items()))
    t = A['tests'].get('D_N', {})
    if t:
        log.append(f"D_N − B_blind {f(t['vs_B_blind']['mean_diff'], 3)}, D_N − A0 {f(t['vs_A0']['mean_diff'], 3)} (6 задач; полный перебор знаков: p {f(t['vs_B_blind']['p'], 3)} и {f(t['vs_A0']['p'], 3)}); "
                   f"бюджет: {A['budget']}")
    json.dump(out, open(os.path.join(HERE, 'pilot_describe.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, 'run', 'pilot_describe.log'), 'w', encoding='utf-8').write('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
