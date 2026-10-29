#!/usr/bin/env python3
"""SCORE-01: что голова получила на входе первого запроса — сумма input + cache_creation + cache_read из первого message_start
(LENSES-1, L1-1: при рабочей папке внутри репозитория CLI добавлял снимок git, и вход одного промпта рос по ходу прогона).

Два режима.
  python3 ctx_check.py <папка потоков> [<папка потоков> …]
      по потоку: папка, id, вход первого запроса; затем разброс входа у одинаковых промптов (как в пилотах; run/pilot_ctxcheck.log).
  python3 ctx_check.py --journal <журнал этапа> --jobs <задания этапа> [--streams <папка потоков>] [--out <json>]
      проверка этапа теста (правило — PREREG §2 и §4; LENSES-1b N5, LENSES-1c П1–П2). Всё — из журнала (git):
      - вход первого запроса итоговой записи каждого задания — из stream.events_no_deltas журнала (с LENSES-1c П2; поток .cache —
        только запасной путь, если в записи нет message_start); записи без входа считаются;
      - (а) изменение входа внутри задачи: остатки аддитивной модели «вход = задача + рука» (МНК); |остаток| > R_MAX у доли
        вызовов больше FRAC_MAX — флаг (так ловится снимок git, который меняется от вызова к вызову, как в пилоте 2);
      - (б) абсолютный уровень: остаток против линии «вход = a + b·байты промпта» чистого пилота 3 (run/pilot_ctx_line.json,
        ctx_line_calib.py); |среднее| > M_ABS или доля |остаток| > R_ABS больше FRAC_MAX — флаг (ступенька, дрейф, постоянная
        добавка: снимок пилота 1 лежал выше линии на 705–1278 токенов);
      - (в) записей без входа больше FRAC_MAX — флаг;
      - (г) конфигурация (config_check): HOME и рабочая папка голов из run_config.json вне git-дерева,
        CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1, у всех итоговых записей config_sha256 = sha256 канонического run_config.json
        (конфигурация не менялась между продолжениями), один init (среда головы не менялась посреди этапа).
      Наклон остатков (а) по времени — только описательно: эффекты задач поглощают всё, что медленнее одной задачи (LENSES-1c П1)."""
import collections
import glob
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
R_MAX, FRAC_MAX = 25.0, 0.05                        # (а) токенов; доля вызовов (она же — для (б) и (в))
R_ABS, M_ABS = 100.0, 50.0                          # (б) токенов: большой остаток против линии; средний остаток этапа
LINE_PATH = os.path.join(HERE, 'run', 'pilot_ctx_line.json')


def _usage_sum(u):
    return u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)


def first_usage(events):
    """Первый message_start в последовательности событий → usage (или None)."""
    for o in events:
        e = o.get('event') or {}
        if o.get('type') == 'stream_event' and e.get('type') == 'message_start':
            return e['message'].get('usage') or {}
    return None


def first_input(path):
    """Вход первого запроса из файла потока (.jsonl.gz) или None."""
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            ev = []
            for line in fh:
                try:
                    ev.append(json.loads(line))
                except ValueError:
                    continue
                u = first_usage(ev[-1:])
                if u is not None:
                    return _usage_sum(u)
    except (OSError, EOFError):
        return None
    return None


def prompt_bytes(jobs_path):
    return {j['id']: len(j['prompt'].encode('utf-8')) for j in map(json.loads, open(jobs_path, encoding='utf-8'))}


def stage_rows(journal, streams=None):
    """Итоговые записи журнала → строки (id, задача, рука, повтор, время в часах, вход), пропущенные id и сведения о записях."""
    rows, skipped = [], []
    meta = dict(config_sha=collections.Counter(), init=collections.Counter(), cache_read=collections.Counter(), from_stream=0)
    for fn in sorted(glob.glob(os.path.join(journal, 'WH_*.jsonl'))):
        for line in open(fn, encoding='utf-8'):
            r = json.loads(line)
            if not r.get('final'):
                continue
            meta['config_sha'][r.get('config_sha256')] += 1
            meta['init'][r.get('init_sha256')] += 1
            st = r.get('stream') if isinstance(r.get('stream'), dict) else {}
            u = first_usage(st.get('events_no_deltas') or [])
            inp = _usage_sum(u) if u is not None else None
            if u is not None:
                meta['cache_read'][u.get('cache_read_input_tokens', 0)] += 1
            if inp is None and streams and st.get('file'):          # запасной путь: файл потока (вне git)
                p = os.path.join(streams, r['task'], st['file'])
                inp = first_input(p) if os.path.exists(p) else None
                meta['from_stream'] += inp is not None
            if inp is None:
                skipped.append(r['job'])
                continue
            task, arm, rep = r['job'].split('|')
            rows.append((r['job'], task, arm, rep, datetime.fromisoformat(r['started']).timestamp() / 3600, inp))
    return rows, skipped, meta


def stage_check(rows, skipped, line=None, nbytes=None):
    """Мера этапа и флаг. line — {'a', 'b'} линии пилота 3 для модели этапа; nbytes — байты промпта по строкам rows."""
    import numpy as np
    why = []
    n_all = len(rows) + len(skipped)
    base = dict(n=len(rows), skipped=len(skipped), skipped_jobs=skipped[:20],
                thresholds=dict(r_max=R_MAX, frac_max=FRAC_MAX, r_abs=R_ABS, m_abs=M_ABS))
    if len(rows) < 10:
        return dict(base, flag=True, why=['меньше 10 вызовов с входом'], frac_resid_gt=float('nan'), slope_per_hour=float('nan'))
    if len(skipped) / n_all > FRAC_MAX:
        why.append(f'записей без входа {len(skipped)} из {n_all}')
    tasks = sorted({r[1] for r in rows}); arms = sorted({r[2] for r in rows})
    ti = {t: i for i, t in enumerate(tasks)}; ai = {a: i for i, a in enumerate(arms)}
    X = np.zeros((len(rows), len(tasks) + len(arms) - 1)); y = np.array([r[5] for r in rows], float)
    for k, r in enumerate(rows):
        X[k, ti[r[1]]] = 1
        if ai[r[2]] > 0:
            X[k, len(tasks) + ai[r[2]] - 1] = 1
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    res = y - X @ beta
    t = np.array([r[4] for r in rows]); tc = t - t.mean()
    slope = float((tc * res).sum() / (tc * tc).sum()) if (tc * tc).sum() > 0 else 0.0
    big = int(np.sum(np.abs(res) > R_MAX))
    if big / len(rows) > FRAC_MAX:
        why.append(f'вход меняется внутри задачи: |остаток| > {R_MAX:.0f} у {big} из {len(rows)}')
    out = dict(base, tasks=len(tasks), arms=arms, max_abs_resid=float(np.abs(res).max()), sd_resid=float(res.std(ddof=1)),
               n_resid_gt=big, frac_resid_gt=big / len(rows), slope_per_hour=slope, span_hours=float(t.max() - t.min()),
               arm_effect_vs_first={arms[0]: 0.0, **{a: float(beta[len(tasks) + ai[a] - 1]) for a in arms[1:]}})
    if line is not None:
        ab = y - (line['a'] + line['b'] * np.array(nbytes, float))
        nb = int(np.sum(np.abs(ab) > R_ABS))
        out.update(abs_mean=float(ab.mean()), abs_sd=float(ab.std(ddof=1)), abs_max=float(np.abs(ab).max()), n_abs_gt=nb,
                   frac_abs_gt=nb / len(rows))
        if abs(ab.mean()) > M_ABS:
            why.append(f'средний вход выше линии пилота 3 на {ab.mean():.0f} токенов')
        if nb / len(rows) > FRAC_MAX:
            why.append(f'|остаток против линии пилота 3| > {R_ABS:.0f} у {nb} из {len(rows)}')
    else:
        why.append('нет линии пилота 3 для этой модели')
    out.update(flag=bool(why), why=why)
    return out


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


def config_check(journal, meta=None):
    c = json.load(open(os.path.join(journal, 'run_config.json'), encoding='utf-8'))
    env = (c.get('env_explicit') or {}).get('CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS')
    sha = hashlib.sha256(json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    r = dict(home=c.get('home'), work_dir=c.get('work_dir'), home_in_git=in_git(c.get('home') or '/'),
             work_dir_in_git=in_git(c.get('work_dir') or '/'), git_instructions_off=env == '1',
             n_init_files=len(glob.glob(os.path.join(journal, 'init_*.json'))), model=c.get('model'))
    if meta is not None:
        r.update(config_sha_records={k[:12] if k else None: v for k, v in meta['config_sha'].items()}, config_sha_file=sha[:12],
                 config_same=set(meta['config_sha']) == {sha}, n_init=len(meta['init']), cache_read=dict(meta['cache_read']),
                 from_stream=meta['from_stream'])
    r['ok'] = bool(c.get('home') and c.get('work_dir') and not r['home_in_git'] and not r['work_dir_in_git'] and r['git_instructions_off']
                   and (meta is None or (r['config_same'] and r['n_init'] == 1)))
    return r


def stage(journal, jobs, streams=None):
    """Полная проверка этапа: строки из журнала, линия пилота 3 модели этапа, байты промптов, конфигурация; флаг — по всему."""
    rows, skipped, meta = stage_rows(journal, streams)
    cfg = config_check(journal, meta)
    L = json.load(open(LINE_PATH, encoding='utf-8'))['line'].get(cfg['model']) if os.path.exists(LINE_PATH) else None
    nb = prompt_bytes(jobs)
    res = stage_check(rows, skipped, line=L, nbytes=[nb[r[0]] for r in rows])
    res.update(journal=os.path.relpath(journal, HERE), jobs=os.path.relpath(jobs, HERE), config=cfg)
    if not cfg['ok']:
        res['why'] = res['why'] + ['конфигурация голов не та']
    res['flag'] = bool(res['why'])
    return res


def main():
    a = sys.argv[1:]
    if '--journal' in a:
        j, jb = a[a.index('--journal') + 1], a[a.index('--jobs') + 1]
        s = a[a.index('--streams') + 1] if '--streams' in a else None
        res = stage(j, jb, s)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        if '--out' in a:
            json.dump(res, open(a[a.index('--out') + 1], 'w'), ensure_ascii=False, indent=1)
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
