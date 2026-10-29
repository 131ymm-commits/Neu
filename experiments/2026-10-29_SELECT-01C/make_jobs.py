#!/usr/bin/env python3
"""SELECT-01C: задания оценщиков. Тексты — тем же кодом, что в SELECT-01 (harness.py eval_jobs: prompts.eval_prompt, perm по
sha256(сид|perm), пулы и задачи SELECT-01). Сначала восстанавливается полный файл заданий повтора SELECT-01 (все четыре руки, тот же
порядок и сериализация) и сверяется его sha256 с run_config.json журнала rep_eval (272a6120…): так доказывается, что промпты те же.
Затем из него берутся только руки B_blind (12) и D_N (5) — тест; и те же руки на задачах пилота 2 SELECT-01 — пилот.
  python3 make_jobs.py   → jobs/test_jobs.jsonl, jobs/pilot_jobs.jsonl и печать сверки"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEL = os.path.abspath(os.path.join(HERE, '..', '2026-10-07_SELECT-01'))
REP_SHA = '272a6120e63cb3ef21e23dbfb1c4a911ab298b6ce2e8a9369b526a9c73a6b529'   # run/rep_eval_journal/run_config.json SELECT-01
SPEC_FULL = 'B_zayavka:5,B_blind:12,C_N:5,D_N:5'                                 # PREREG SELECT-01 §11, порядок как в run_select01.sh
ARMS = ('B_blind', 'D_N')
PILOT_TASKS = ['WH_7307', 'WH_7308', 'WH_7309', 'WH_7310', 'WH_7311', 'WH_7312']   # пулы пилота 2 SELECT-01; в тест не входят


def jobs_for(tids, spec):
    os.environ['SELECT_ROOT'] = SEL
    sys.path.insert(0, SEL)
    import harness
    import prompts
    import sim
    out = []
    for t in tids:
        if not os.path.exists(os.path.join(SEL, 'pools', f'{t}.json')):
            continue
        tk = harness.task(t)
        pool = json.load(open(os.path.join(SEL, 'pools', f'{t}.json')))
        pm = harness.perm(t)
        shown = [pool[j] for j in pm]
        rules = sim.RULES[tk['type']](tk)
        for a, n in spec.items():
            for i in range(int(n)):
                out.append(dict(id=f'{t}|{a}|{i}', prompt=prompts.eval_prompt(a, rules, shown), schema=prompts.EVAL_SCHEMA))
    return out


def dump(jobs):
    return ''.join(json.dumps(j, ensure_ascii=False) + '\n' for j in jobs)


def main():
    spec = dict(x.split(':') for x in SPEC_FULL.split(','))
    rep = [f'WH_{s}' for s in json.load(open(os.path.join(SEL, 'seeds_rep.json')))['WH']]
    full = jobs_for(rep, spec)
    sha = hashlib.sha256(dump(full).encode()).hexdigest()
    print(f'полный файл заданий повтора SELECT-01: {len(full)} заданий, sha256 {sha} — {"совпал" if sha == REP_SHA else "НЕ СОВПАЛ"} с run_config.json')
    assert sha == REP_SHA, 'промпты не те же, что в повторе SELECT-01'
    test = [j for j in full if j['id'].split('|')[1] in ARMS]
    pilot = jobs_for(PILOT_TASKS, {a: spec[a] for a in ARMS})
    for name, jj in (('test', test), ('pilot', pilot)):
        p = os.path.join(HERE, 'jobs', f'{name}_jobs.jsonl')
        open(p, 'w', encoding='utf-8').write(dump(jj))
        tasks = sorted({j['id'].split('|')[0] for j in jj})
        print(f'{name}: заданий {len(jj)}, задач {len(tasks)}, sha256 {hashlib.sha256(dump(jj).encode()).hexdigest()}')


if __name__ == '__main__':
    main()
