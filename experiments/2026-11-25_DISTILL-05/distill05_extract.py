#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05: извлечение свежих ответов голов (фаза test7) — 8 новых сред «тысяч» с пятизначными суммами, X = 119, 129, 149, 159, 179,
189, 199, 209 (a от 100·X до 100·X + 99, b от 10 до 99, переход через тысячу). Ни одного X из прежних фаз; пулы свежие, места с 0, 1100
задач на среду. Среды строит код OCDIV-02 (`ocdiv2_extract.env_of`), прогон — `ocdiv2_extract.run`, сборка — `distill04_extract.merge_d4`;
зарегистрированный код DISTILL-04 не меняется (фаза добавляется в его таблицы при импорте). main всегда возвращает код выхода (ERRORS № 233).
  python3 distill05_extract.py --phase test7 --model REPO [--revision REV] --envs NAME,... --out DIR [--bs 16] [--limit N]
  python3 distill05_extract.py merge ВЫХОД test7 thousands ПАПКА..."""
import argparse
import glob
import json
import os
import sys
import time

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-19_DISTILL-04'))
import distill04_extract as X4  # noqa: E402

X2 = X4.X2
TEST7_X = (119, 129, 149, 159, 179, 189, 199, 209)
USED_X = tuple(X4.USED_THOUSANDS_X) + tuple(X4.FAMILIES6['test6']['thousands'])
X4.FAMILIES6['test7'] = {'thousands': TEST7_X}
X4.PHASES6['test7'] = dict(p=3, n=1100, start=0, prompt='id')


def envs_d5():
    return X4.envs_d4('test7')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'merge':
        out, phase, fam = sys.argv[2:5]
        X4.merge_d4(out, phase, fam, sorted(set(d for pat in sys.argv[5:] for d in glob.glob(pat))))
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=('test7',), required=True)
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
    envs = X4.env_by_name(a.phase, a.envs.split(','))
    if a.limit:
        envs = [dict(e, problems=e['problems'][:a.limit], idx=e['idx'][:a.limit]) for e in envs]
    log('фаза', a.phase, '| сред', len(envs), '| задач', sum(len(e['problems']) for e in envs))
    dst = os.path.join(a.out, f"answers_{a.model.split('/')[-1]}.json")
    res = dict(experiment='DISTILL-05', phase=a.phase, model=a.model, limit=a.limit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=X2.DX.prompt_sha(e['prompt_head'])) for e in envs])
    try:
        res.update(X2.run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим (как в DISTILL-02/04)
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)
    return 0


if __name__ == '__main__':
    sys.exit(main())
