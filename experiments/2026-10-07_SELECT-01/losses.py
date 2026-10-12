# SELECT-01: правило потерь (совет 29, условие Скептика) по журналу run_sealed2 одной выборки.
#   python3 losses.py <журнал_оценщиков> <evals/этап.jsonl> [--out json] [--bound 0.02]
# По каждой руке: вызовов с итогом, «потерян», попыток «нет ответа» до message_start (таймаут или гибель до начала
# ответа), ожиданий лимита, api_retry до и после начала, подмен модели, многоходовых ответов.
# Правило: для пары (рука семейства, B_blind) доля «потерян» или доля попыток «нет ответа» до начала ответа
# расходятся больше границы (0,02) → по этой руке исход «не измерено».
# Вторично: evals только по задачам, где ни у руки, ни у B_blind нет ни одного «потерян», и analyze.py по ним.
import argparse, collections, json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(here, '..', '..', 'tools'))
import run_sealed2 as rs  # noqa: E402
FAMILY = ('C_N', 'D_N')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('journal'); ap.add_argument('evals'); ap.add_argument('--out')
    ap.add_argument('--bound', type=float, default=0.02); ap.add_argument('--typ', default='WH')
    a = ap.parse_args()
    c = collections.defaultdict(collections.Counter); lost_tasks = collections.defaultdict(set)
    for r in rs.journal_records(a.journal):
        if r.get('role') != 'основной':
            continue
        arm, f = r.get('arm'), r.get('flags') or {}
        c[arm]['попыток'] += 1
        if r.get('final'):
            c[arm]['итогов'] += 1
        if r.get('final') == 'потерян':
            c[arm]['потерян'] += 1; lost_tasks[arm].add(r['task'])
        if r['outcome'] == rs.NA and 'wait_s' not in r and 'message_start' in r.get('reason', ''):
            c[arm]['нет_ответа_до_начала'] += 1
        if r['outcome'] == rs.NA and 'wait_s' in r:
            c[arm]['ожиданий_лимита'] += 1
        c[arm]['api_retry_до'] += f.get('api_retry_до_начала', 0); c[arm]['api_retry_после'] += f.get('api_retry_после_начала', 0)
        c[arm]['подмен'] += 'ответ не целевой модели' in r.get('reason', '')
        c[arm]['многоходовых'] += bool(r.get('final')) and (f.get('message_start') or 0) > 1
    share = lambda arm, k: c[arm][k] / c[arm]['итогов'] if c[arm]['итогов'] else float('nan')
    out = dict(bound=a.bound, by_arm={arm: dict(v) for arm, v in sorted(c.items())}, rule={}, secondary={})
    for arm in FAMILY:
        if arm not in c or 'B_blind' not in c:
            continue
        dl = abs(share(arm, 'потерян') - share('B_blind', 'потерян'))
        ds = abs(share(arm, 'нет_ответа_до_начала') - share('B_blind', 'нет_ответа_до_начала'))
        out['rule'][arm] = dict(lost_share=round(share(arm, 'потерян'), 4), lost_share_B_blind=round(share('B_blind', 'потерян'), 4),
                                start_share=round(share(arm, 'нет_ответа_до_начала'), 4),
                                start_share_B_blind=round(share('B_blind', 'нет_ответа_до_начала'), 4),
                                not_measured=bool(dl > a.bound or ds > a.bound))
        bad = lost_tasks[arm] | lost_tasks['B_blind']
        if bad:   # вторичный парный анализ на задачах без потерь в обеих руках
            p = os.path.splitext(a.evals)[0] + f'.clean_{arm}.jsonl'
            with open(p, 'w', encoding='utf-8') as fh:
                for line in open(a.evals, encoding='utf-8'):
                    if json.loads(line)['task'] not in bad:
                        fh.write(line)
            res = subprocess.run([sys.executable, os.path.join(here, 'analyze.py'), a.typ, p], capture_output=True, text=True, check=True)
            t = json.loads(res.stdout)['tests'].get(arm, {})
            out['secondary'][arm] = dict(excluded_tasks=sorted(bad), n_tasks=json.loads(res.stdout)['n_tasks'], vs_B_blind=t.get('vs_B_blind'))
        else:
            out['secondary'][arm] = dict(excluded_tasks=[], note='потерь нет: совпадает с первичным')
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.out:
        json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
