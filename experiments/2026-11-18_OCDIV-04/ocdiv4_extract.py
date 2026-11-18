#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04: извлечение ответов голов на новых местах перестановки пар (HYPOTHESIS §3, 7aed3606). Код OCDIV-02 не меняется:
среды строит `ocdiv2_extract.env_of` (подсказка только из ID, p = 3, те же зёрна сред), прогон — `ocdiv2_extract.run`.
  pilot3 — 600 задач на среду с места 6000;  test3 — 2200 задач на среду с места 3400 (прежние фазы — места 0–3200).
  «тысячи» X = 19…89 (8 сред), «длина» X = 9, 99, 999 (3 среды).
  python3 ocdiv4_extract.py --phase pilot3|test3 --model REPO [--revision REV] --envs NAME,NAME... --out DIR [--bs 16] [--limit N]"""
import argparse
import json
import os
import sys
import time

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-17_OCDIV-02'))
import ocdiv2_extract as X2  # noqa: E402   OCDIV-02 (prereg_hashes2.json): env_of, run, shots_id

FAMILIES4 = {'thousands': (19, 29, 39, 49, 59, 69, 79, 89), 'length': (9, 99, 999)}
PHASES4 = {'pilot3': dict(p=3, n=600, start=6000, prompt='id'), 'test3': dict(p=3, n=2200, start=3400, prompt='id')}


def envs_ocdiv4(phase, fams=tuple(FAMILIES4)):
    ph = PHASES4[phase]
    fams = tuple(FAMILIES4) if fams is None else fams
    return [X2.env_of(fam, X, ph['p'], ph['n'], ph['start'], ph['prompt']) for fam in fams for X in FAMILIES4[fam]]


def env_by_name(phase, names):
    allv = {e['name']: e for e in envs_ocdiv4(phase)}
    miss = [n for n in names if n not in allv]
    if miss:
        raise SystemExit(f'нет таких сред фазы {phase}: {miss}')
    return [allv[n] for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=tuple(PHASES4), required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--revision', default='main')
    ap.add_argument('--envs', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--bs', type=int, default=16)
    ap.add_argument('--limit', type=int, default=0, help='только для сухого прогона: первые N задач каждой среды')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    def log(*x):
        print(f'[{time.time() - t0:7.1f} с]', *x, flush=True)
    envs = env_by_name(a.phase, a.envs.split(','))
    if a.limit:
        envs = [dict(e, problems=e['problems'][:a.limit], idx=e['idx'][:a.limit]) for e in envs]
    log('фаза', a.phase, '| сред', len(envs), '| задач', sum(len(e['problems']) for e in envs))
    dst = os.path.join(a.out, f"answers_{a.model.split('/')[-1]}.json")
    res = dict(experiment='OCDIV-04', phase=a.phase, model=a.model, limit=a.limit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=X2.DX.prompt_sha(e['prompt_head'])) for e in envs])
    try:
        res.update(X2.run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим (как в OCDIV-02)
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)


if __name__ == '__main__':
    main()
