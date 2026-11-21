#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04 «ПРОЧИЕ»: извлечение свежих ответов голов для теста. Код OCDIV-02 и DISTILL-02 не меняется: среды строит
`ocdiv2_extract.env_of` (подсказка только из ID, p = 3, те же правила пулов и зёрен), прогон — `ocdiv2_extract.run`.
  test6  — «тысячи», 8 новых сред X = 14, 24, …, 84 (a от 100·X до 100·X + 99): ни в одной прежней фазе этих X нет (OCDIV-02/03/04 и
           DISTILL-02 брали X = 19, 29, …, 89 и 109, 139, 169); пулы свежие, задачи — с места 0, 2200 на среду;
  test6L — «длина», L_X9999 (описательно): места с 5600 — после new5 DISTILL-02 (места 3400–5600; OCDIV-02 — 0–3200), 2200 задач.
  В средах построения (X = 19…89; 9, 99, 999) свежих мест почти нет: test5 занял места 6620–8822 из 8992 (проверено кодом).
  python3 distill04_extract.py --phase test6|test6L --model REPO [--revision REV] --envs NAME,... --out DIR [--bs 16] [--limit N]
  python3 distill04_extract.py merge ВЫХОД ФАЗА СЕМЕЙСТВО ПАПКА...   — сборка ответов (сверка задач, ключей, подсказки, ревизий; СТОП)"""
import argparse
import json
import os
import sys
import time

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-17_OCDIV-02'))
import ocdiv2_extract as X2  # noqa: E402   OCDIV-02 (prereg_hashes2.json): env_of, run, shots_id

FAMILIES6 = {'test6': {'thousands': (14, 24, 34, 44, 54, 64, 74, 84)}, 'test6L': {'length': (9999,)}}
PHASES6 = {'test6': dict(p=3, n=2200, start=0, prompt='id'), 'test6L': dict(p=3, n=2200, start=5600, prompt='id')}
USED_THOUSANDS_X = (19, 29, 39, 49, 59, 69, 79, 89, 109, 139, 169)       # прежние фазы — для замка свежести


def envs_d4(phase, fams=None):
    ph, fam_x = PHASES6[phase], FAMILIES6[phase]
    fams = tuple(fam_x) if fams is None else tuple(f for f in fams if f in fam_x)
    return [X2.env_of(fam, X, ph['p'], ph['n'], ph['start'], ph['prompt']) for fam in fams for X in fam_x[fam]]


def env_by_name(phase, names):
    allv = {e['name']: e for e in envs_d4(phase)}
    miss = [n for n in names if n not in allv]
    if miss:
        raise SystemExit(f'нет таких сред фазы {phase}: {miss}')
    return [allv[n] for n in names]


def merge_d4(out_dir, phase, family, job_dirs):
    """Сборка тем же кодом, что OCDIV-02 и DISTILL-02 (`ocdiv2.merge`): на время вызова `ocdiv2.D2.envs_ocdiv2` отдаёт среды envs_d4."""
    sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-18_OCDIV-04'))
    import ocdiv4 as C4
    W = C4.W
    assert phase in PHASES6, phase
    orig = W.D2.envs_ocdiv2
    W.D2.envs_ocdiv2 = lambda ph, fams=None: envs_d4(ph, fams)
    try:
        return W.merge(out_dir, phase, family, job_dirs)
    finally:
        W.D2.envs_ocdiv2 = orig


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'merge':
        import glob
        out, phase, fam = sys.argv[2:5]
        dirs = sorted(set(d for pat in sys.argv[5:] for d in glob.glob(pat)))
        return merge_d4(out, phase, fam, dirs)
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=tuple(PHASES6), required=True)
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
    res = dict(experiment='DISTILL-04', phase=a.phase, model=a.model, limit=a.limit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=X2.DX.prompt_sha(e['prompt_head'])) for e in envs])
    try:
        res.update(X2.run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим (как в OCDIV-02 и DISTILL-02)
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)


if __name__ == '__main__':
    sys.exit(main())
