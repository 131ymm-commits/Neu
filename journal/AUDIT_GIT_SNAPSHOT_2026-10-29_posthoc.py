#!/usr/bin/env python3
"""Аудит канала «снимок git», дополнение 29.10.2026: пост-хок, не в зачёт — держатся ли выводы повторов без задач, чьи вызовы видели
в «Recent commits» коммит с исходом основной выборки (экспозиция — AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.json).
Тем же кодом анализа, что в опытах: SELECT-01 — analyze.py (perm_p, boot_ci) по per_task rep_an_wh.json; PRECOND-01 — analyze_precond.py
val_stage на выборах проверки без экспонированных задач (правда — из опубликованной соли в /root/precond_secret_val).
THINK-01: вызовы оценщиков повтора таких коммитов не видели (0 вызовов) — пересчитывать нечего.
  python3 journal/AUDIT_GIT_SNAPSHOT_2026-10-29_posthoc.py   → печать (журнал — AUDIT_GIT_SNAPSHOT_2026-10-29_posthoc.txt)"""
import json
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
EXP = json.load(open(os.path.join(ROOT, 'journal', 'AUDIT_GIT_SNAPSHOT_2026-10-29_exposure.json'), encoding='utf-8'))


def select01():
    sel = os.path.join(ROOT, 'experiments', '2026-10-07_SELECT-01')
    sys.path.insert(0, sel)
    argv, sys.argv = sys.argv, ['analyze']
    import analyze as A
    sys.argv = argv
    R = json.load(open(os.path.join(sel, 'rep_an_wh.json'), encoding='utf-8'))['per_task']
    e = EXP['experiments/2026-10-07_SELECT-01/run/rep_eval_journal']['exposed']
    print('SELECT-01, повтор (WH 8101–8200): D_N против B_blind и A0 (односторонний перестановочный p — оценка Монте-Карло, 200 000; ДИ — бутстреп 20 000)')
    for name, excl in (('все задачи', set()), ('без задач, где вызовы видели 35fc0e4', set(e['35fc0e4']['tasks'])),
                       ('без задач, где вызовы видели 24bc4ee', set(e['24bc4ee']['tasks']))):
        T = [t for t in R if t not in excl]
        dB = [R[t]['D_N'] - R[t]['B_blind'] for t in T]
        dA = [R[t]['D_N'] - R[t]['A0'] for t in T]
        pB, _ = A.perm_p(dB)
        pA, _ = A.perm_p(dA)
        cB, cA = A.boot_ci(dB), A.boot_ci(dA)
        mean = lambda x: sum(x) / len(x)
        print(f'  {name}: задач {len(T)}; D_N − B_blind {mean(dB):+.3f} [{cB[0]:+.3f}; {cB[1]:+.3f}], p {pB:.1e}; '
              f'D_N − A0 {mean(dA):+.3f} [{cA[0]:+.3f}; {cA[1]:+.3f}], p {pA:.4f}')


def precond01():
    pc = os.path.join(ROOT, 'experiments', '2026-10-21_PRECOND-01')
    sys.path.insert(0, pc)
    import analyze_precond as AN
    e = EXP['experiments/2026-10-21_PRECOND-01/run/val_eval_medium_journal']['exposed']['c98b937']['tasks']
    rows = [json.loads(l) for l in open(os.path.join(pc, 'evals', 'val.jsonl'), encoding='utf-8')]
    allt = sorted({r['task'] for r in rows})
    open_an = json.load(open(os.path.join(pc, 'open_an.json'), encoding='utf-8'))
    print('PRECOND-01, проверка победителя (WH 8310–8359): руки ANCHOR, MODEL, OBS (t-ДИ по задачам, как в analyze_precond.py)')
    for name, keep in (('все задачи', set(allt)), ('без задач, где вызовы видели c98b937', set(allt) - set(e)), ('только задачи, где видели c98b937', set(e))):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8') as fh:
            for r in rows:
                if r['task'] in keep:
                    fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        v = AN.val_stage(fh.name, open_an, 'val')
        os.unlink(fh.name)
        pr, va = v['primary']['diff_obs_minus_model'], v['vs_anchor']
        print(f"  {name}: задач {v['n_tasks']}; регрет ANCHOR {v['mean_regret']['ANCHOR']}, MODEL {v['mean_regret']['MODEL']}, OBS {v['mean_regret']['OBS']}; "
              f"OBS − MODEL {pr['mean']:+.3f} [{pr['ci95'][0]:+.3f}; {pr['ci95'][1]:+.3f}], односторонний p {pr['p_greater']:.3f}; "
              f"ANCHOR − OBS {va['OBS']['mean']:+.3f} [{va['OBS']['ci95'][0]:+.3f}; {va['OBS']['ci95'][1]:+.3f}]; "
              f"ANCHOR − MODEL {va['MODEL']['mean']:+.3f} [{va['MODEL']['ci95'][0]:+.3f}; {va['MODEL']['ci95'][1]:+.3f}]")


if __name__ == '__main__':
    select01()
    precond01()
