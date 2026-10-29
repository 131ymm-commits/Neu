#!/usr/bin/env python3
"""SCORE-01: что голова получила на входе первого запроса — сумма input + cache_creation + cache_read из первого message_start
потока (LENSES-1, L1-1: при рабочей папке внутри репозитория CLI добавлял снимок git, и вход одного промпта рос по ходу прогона).
Одинаковые промпты в чистом контексте дают одинаковый вход (с точностью до нескольких токенов).

Два режима.
  python3 ctx_check.py <папка потоков> [<папка потоков> …]
      по потоку: папка, id, вход первого запроса; затем разброс входа у одинаковых промптов (как в пилотах; run/pilot_ctxcheck.log).
  python3 ctx_check.py --journal <журнал этапа> --streams <папка потоков этапа> [--out <json>]
      проверка этапа (LENSES-1b, N5; правило — PREREG §2 и §4). Берётся поток итоговой записи каждого задания (поле stream
      журнала), время — started. Потоки без message_start (прерванные вызовы) пропускаются и считаются. Мера, которая работает и
      при одном вызове на клетку: аддитивная модель «вход = задача + рука» по МНК (повторы — в одной клетке), её остатки и наклон
      остатков по времени. Флаг этапа — доля остатков с |остаток| > R_MAX больше FRAC_MAX или |наклон| > SLOPE_MAX токенов в час.
      Пороги выбраны по пилоту 3 (чистый контекст) и пилоту 2 (снимок git — положительный контроль); числа — PREREG §3.
      config_check — причина, а не след: HOME и рабочая папка голов из run_config.json журнала вне любого git-дерева,
      CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1 (ERRORS № 118); число файлов init — описательно."""
import glob
import gzip
import json
import os
import sys
from datetime import datetime

R_MAX, FRAC_MAX, SLOPE_MAX = 25.0, 0.05, 5.0          # токенов; доля вызовов; токенов в час


def first_input(path):
    try:
        fh = gzip.open(path, 'rt', encoding='utf-8')
        with fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                e = o.get('event') or {}
                if o.get('type') == 'stream_event' and e.get('type') == 'message_start':
                    u = e['message'].get('usage') or {}
                    return u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
    except (OSError, EOFError):
        return None
    return None


def stage_rows(journal, streams):
    """Итоговые записи журнала → [(id, задача, рука, повтор, время в часах от начала, вход)], число пропущенных."""
    rows, skipped = [], []
    for fn in sorted(glob.glob(os.path.join(journal, 'WH_*.jsonl'))):
        for line in open(fn, encoding='utf-8'):
            r = json.loads(line)
            if not r.get('final'):
                continue
            st = r.get('stream')
            st = st if isinstance(st, dict) else (json.loads(st.replace("'", '"')) if isinstance(st, str) and st.startswith('{') else {})
            p = os.path.join(streams, r['task'], st.get('file', '')) if st.get('file') else None
            inp = first_input(p) if p and os.path.exists(p) else None
            if inp is None:
                skipped.append(r['job'])
                continue
            task, arm, rep = r['job'].split('|')
            rows.append((r['job'], task, arm, rep, datetime.fromisoformat(r['started']).timestamp() / 3600, inp))
    return rows, skipped


def in_git(path):
    """Лежит ли путь внутри git-дерева (по наличию .git у него или у предков; путь может уже не существовать)."""
    p = os.path.abspath(path)
    while True:
        if os.path.exists(os.path.join(p, '.git')):
            return True
        q = os.path.dirname(p)
        if q == p:
            return False
        p = q


def config_check(journal):
    c = json.load(open(os.path.join(journal, 'run_config.json'), encoding='utf-8'))
    env = (c.get('env_explicit') or {}).get('CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS')
    r = dict(home=c.get('home'), work_dir=c.get('work_dir'), home_in_git=in_git(c.get('home') or '/'),
             work_dir_in_git=in_git(c.get('work_dir') or '/'), git_instructions_off=env == '1',
             n_init=len(glob.glob(os.path.join(journal, 'init_*.json'))))
    r['ok'] = bool(c.get('home') and c.get('work_dir') and not r['home_in_git'] and not r['work_dir_in_git'] and r['git_instructions_off'])
    return r


def stage_check(rows, skipped):
    import numpy as np
    if len(rows) < 10:                                  # нечего проверять — флаг
        return dict(n=len(rows), skipped=len(skipped), skipped_jobs=skipped[:20], flag=True, why='меньше 10 вызовов с входом',
                    thresholds=dict(r_max=R_MAX, frac_max=FRAC_MAX, slope_max=SLOPE_MAX), frac_resid_gt=float('nan'),
                    slope_per_hour=float('nan'))
    tasks = sorted({r[1] for r in rows}); arms = sorted({r[2] for r in rows})
    ti = {t: i for i, t in enumerate(tasks)}; ai = {a: i for i, a in enumerate(arms)}
    X = np.zeros((len(rows), len(tasks) + len(arms) - 1)); y = np.array([r[5] for r in rows], float)
    for k, r in enumerate(rows):
        X[k, ti[r[1]]] = 1
        if ai[r[2]] > 0:
            X[k, len(tasks) + ai[r[2]] - 1] = 1
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ beta
    t = np.array([r[4] for r in rows]); t = t - t.mean()
    slope = float((t * res).sum() / (t * t).sum()) if (t * t).sum() > 0 else 0.0
    arm_eff = {arms[0]: 0.0, **{a: float(beta[len(tasks) + ai[a] - 1]) for a in arms[1:]}}
    big = int(np.sum(np.abs(res) > R_MAX))
    flag = bool(big / len(rows) > FRAC_MAX or abs(slope) > SLOPE_MAX)
    return dict(n=len(rows), skipped=len(skipped), skipped_jobs=skipped[:20], tasks=len(tasks), arms=arms,
                max_abs_resid=float(np.abs(res).max()), sd_resid=float(res.std(ddof=1)), n_resid_gt=big, frac_resid_gt=big / len(rows),
                slope_per_hour=slope, span_hours=float(t.max() - t.min()), arm_effect_vs_first=arm_eff,
                thresholds=dict(r_max=R_MAX, frac_max=FRAC_MAX, slope_max=SLOPE_MAX), flag=flag)


def main():
    a = sys.argv[1:]
    if '--journal' in a:
        j, s = a[a.index('--journal') + 1], a[a.index('--streams') + 1]
        out = a[a.index('--out') + 1] if '--out' in a else None
        rows, skipped = stage_rows(j, s)
        res = stage_check(rows, skipped)
        res.update(journal=j, streams=s, config=config_check(j))
        res['flag'] = bool(res['flag'] or not res['config']['ok'])
        print(json.dumps(res, ensure_ascii=False, indent=1))
        if out:
            json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
        return
    rows = []
    for d in a:
        for p in sorted(glob.glob(os.path.join(d, '*', '*.jsonl.gz'))):
            name = os.path.basename(p).split('-')[0]
            rows.append((os.path.getmtime(p), d, name, first_input(p)))
    rows.sort()
    by, none = {}, 0
    for t, d, name, inp in rows:
        if inp is None:                                  # прерванный вызов: потока без message_start нет входа
            none += 1
            continue
        key = name.rsplit('_', 1)[0]                     # задача_рука без номера повтора — один промпт
        by.setdefault((d, key), []).append(inp)
        print(f'{os.path.basename(d.rstrip("/"))}\t{name}\t{inp}')
    print(f'потоков без message_start: {none}')
    print('одинаковые промпты (задача и рука): разброс входа')
    for (d, key), v in sorted(by.items()):
        if len(v) > 1:
            print(f'  {os.path.basename(d.rstrip("/"))} {key}: {v} → размах {max(v) - min(v)}')


if __name__ == '__main__':
    main()
