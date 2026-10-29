#!/usr/bin/env python3
"""Своя проверка контекста этапов SCORE-01 по PREREG §2 (а)–(г) и §4: вход первого запроса — первый message_start
в stream.events_no_deltas итоговой записи журнала; (а) остатки аддитивной модели «задача + рука» (МНК);
(б) остаток против линии пилота 3 (run/pilot_ctx_line.json, хеширован при регистрации); (в) записи без входа; (г) конфигурация."""
import glob, hashlib, json, os
from datetime import datetime
import numpy as np

EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
line = json.load(open(f'{EXP}/run/pilot_ctx_line.json'))['line']
A = json.load(open(f'{EXP}/analysis_score01.json'))
out = []
for st in ['main_opus', 'rep_opus', 'main_haiku', 'rep_haiku']:
    J = f'{EXP}/run/{st}'
    cfg = json.load(open(f'{J}/run_config.json'))
    csha = hashlib.sha256(json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    jobs = {j['id']: j for j in map(json.loads, open(f'{EXP}/jobs/{st}_jobs.jsonl', encoding='utf-8'))}
    recs, nofinal, skipped = [], 0, []
    shas, inits, models, finals_per_job = set(), set(), set(), {}
    for fn in sorted(glob.glob(f'{J}/WH_*.jsonl')):
        for l in open(fn, encoding='utf-8'):
            r = json.loads(l)
            if not r.get('final'):
                nofinal += 1
                continue
            finals_per_job[r['job']] = finals_per_job.get(r['job'], 0) + 1
            shas.add(r.get('config_sha256')); inits.add(r.get('init_sha256')); models.add(r.get('model_target'))
            ev = (r.get('stream') or {}).get('events_no_deltas') or []
            u = None
            for o in ev:
                e = o.get('event') or {}
                if o.get('type') == 'stream_event' and e.get('type') == 'message_start':
                    u = e['message'].get('usage') or {}
                    break
            if u is None:
                skipped.append(r['job']); continue
            inp = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
            t, arm, rep = r['job'].split('|')
            recs.append((r['job'], t, arm, datetime.fromisoformat(r['started']).timestamp() / 3600, inp,
                         len(jobs[r['job']]['prompt'].encode('utf-8'))))
    dup = [k for k, v in finals_per_job.items() if v > 1]
    tasks = sorted({x[1] for x in recs}); arms = sorted({x[2] for x in recs})
    X = np.zeros((len(recs), len(tasks) + len(arms) - 1)); y = np.array([x[4] for x in recs], float)
    for k, x in enumerate(recs):
        X[k, tasks.index(x[1])] = 1
        if arms.index(x[2]) > 0:
            X[k, len(tasks) + arms.index(x[2]) - 1] = 1
    res = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
    L = line[cfg['model']]
    ab = y - (L['a'] + L['b'] * np.array([x[5] for x in recs], float))
    tt = np.array([x[3] for x in recs])
    def in_git(p):
        p = os.path.abspath(p)
        while True:
            if os.path.exists(os.path.join(p, '.git')):
                return True
            q = os.path.dirname(p)
            if q == p:
                return False
            p = q
    cfg_ok = (not in_git(cfg['home'])) and (not in_git(cfg['work_dir'])) and cfg['env_explicit'].get('CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS') == '1' \
        and shas == {csha} and len({i for i in inits if i}) == 1
    fa = np.mean(np.abs(res) > 25); fb = np.mean(np.abs(ab) > 100)
    flag = fa > 0.05 or abs(ab.mean()) > 50 or fb > 0.05 or len(skipped) / (len(recs) + len(skipped)) > 0.05 or not cfg_ok
    an = A['ctx'][st]
    out.append(f'{st}: записей с входом {len(recs)}, без входа {len(skipped)}, неитоговых {nofinal}, дублей итоговых {len(dup)}, '
               f'моделей {models}; (а) max|ост| {np.abs(res).max():.1f}, доля>25 {fa:.3f}; (б) среднее {ab.mean():+.2f}, '
               f'max|ост| {np.abs(ab).max():.1f}, доля>100 {fb:.3f}; длительность {tt.max() - tt.min():.2f} ч; '
               f'(г) home {cfg["home"]} work {cfg["work_dir"]} git_off {cfg["env_explicit"].get("CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS")} '
               f'sha записей = sha файла: {shas == {csha}}, init {len({i for i in inits if i})}; флаг {flag} | '
               f'анализ: max {an["max_abs_resid"]:.1f}, среднее {an["abs_mean"]:+.2f}, max {an["abs_max"]:.1f}, ч {an["span_hours"]:.2f}, флаг {an["flag"]}')
    # разность с ctx_<этап>.json в run/
    cj = json.load(open(f'{EXP}/run/ctx_{st}.json'))
    out.append(f'   run/ctx_{st}.json: abs_mean {cj["abs_mean"]:+.2f}, abs_max {cj["abs_max"]:.1f}, max_abs_resid {cj["max_abs_resid"]:.1f}, flag {cj["flag"]}')
print('\n'.join(out))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rc_ctx.log'), 'w').write('\n'.join(out) + '\n')
