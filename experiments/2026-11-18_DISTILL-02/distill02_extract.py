#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-02: извлечение ответов голов на свежих задачах (тест). Код OCDIV-02 не меняется: среды строит `ocdiv2_extract.env_of`
(подсказка только из ID, p = 3, те же зёрна сред), прогон — `ocdiv2_extract.run`.
  test5 — те же 11 сред, что построение (OCDIV-04: «тысячи» X = 19…89, «длина» X = 9, 99, 999), 2200 задач с места START5
          (после пилота OCDIV-04, места 6000–6600; прежние фазы — 0–3200 и 3400–5603);
  new5  — новые среды для П4 (вне построения): «тысячи» с пятизначным a X = 109, 139, 169 и «длина» X = 9999, 2200 задач с места
          3400 (L_X9999 была в OCDIV-02 на местах 0–3200).
  python3 distill02_extract.py --phase test5|new5 --model REPO [--revision REV] --envs NAME,NAME... --out DIR [--bs 16] [--limit N]"""
import argparse
import json
import os
import sys
import time

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-17_OCDIV-02'))
import ocdiv2_extract as X2  # noqa: E402   OCDIV-02 (prereg_hashes2.json): env_of, run, shots_id

START5 = 6620                                                   # после конца пилота OCDIV-04 (6000 + 600 задач + пропуски примеров ≤ 4)
FAMILIES5 = {'test5': {'thousands': (19, 29, 39, 49, 59, 69, 79, 89), 'length': (9, 99, 999)},
             'new5': {'thousands': (109, 139, 169), 'length': (9999,)}}
START_NEW5 = 3400                                               # L_X9999 была в OCDIV-02 (места 0–3200): все новые среды — с 3400
PHASES5 = {'test5': dict(p=3, n=2200, start=START5, prompt='id'), 'new5': dict(p=3, n=2200, start=START_NEW5, prompt='id')}


def envs_d2(phase, fams=None):
    ph = PHASES5[phase]
    fam_x = FAMILIES5[phase]
    fams = tuple(fam_x) if fams is None else fams
    return [X2.env_of(fam, X, ph['p'], ph['n'], ph['start'], ph['prompt']) for fam in fams for X in fam_x[fam]]


def env_by_name(phase, names):
    allv = {e['name']: e for e in envs_d2(phase)}
    miss = [n for n in names if n not in allv]
    if miss:
        raise SystemExit(f'нет таких сред фазы {phase}: {miss}')
    return [allv[n] for n in names]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=tuple(PHASES5), required=True)
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
    res = dict(experiment='DISTILL-02', phase=a.phase, model=a.model, limit=a.limit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=X2.DX.prompt_sha(e['prompt_head'])) for e in envs])
    try:
        res.update(X2.run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим (как в OCDIV-02 и OCDIV-04)
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)


if __name__ == '__main__':
    main()
