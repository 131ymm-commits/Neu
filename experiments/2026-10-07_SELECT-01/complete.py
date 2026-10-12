# SELECT-01: полнота выборки перед analyze (совет 31: Скептик, Инженер, Левое).
#   python3 complete.py <этап_eval> <seeds.json> <ключ> [--spec B_zayavka:5,B_blind:12,C_N:5,D_N:5] [--out json]
# Задачи с пулом берутся по pools/. У каждой в evals/<этап>.jsonl должно быть ровно по записи на каждую пару (рука, i) из spec.
# Пишет evals/<этап>.complete.jsonl — только полные задачи. Неполные исключаются вслепую к рукам (руки одной задачи идут
# вперемешку, неполной бывает задача, на которой прогон остановлен окончательно) и перечисляются.
# Отдельно по каждой руке — задачи без единого допустимого голоса: «потерян» (error), недопустимый номер, отказ −1.
import argparse, collections, json, os, sys
D = os.environ.get('SELECT_ROOT', os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('stage'); ap.add_argument('seeds'); ap.add_argument('key')
    ap.add_argument('--spec', default='B_zayavka:5,B_blind:12,C_N:5,D_N:5'); ap.add_argument('--out'); a = ap.parse_args()
    spec = {x.split(':')[0]: int(x.split(':')[1]) for x in a.spec.split(',')}
    want = {(arm, i) for arm, n in spec.items() for i in range(n)}
    tids = [f'{a.key}_{s}' for s in json.load(open(f'{D}/{a.seeds}'))[a.key]]
    with_pool = [t for t in tids if os.path.exists(f'{D}/pools/{t}.json')]
    rec = collections.defaultdict(dict)
    lines = collections.defaultdict(list)
    for line in open(f'{D}/evals/{a.stage}.jsonl', encoding='utf-8'):
        e = json.loads(line); rec[e['task']][(e['arm'], int(e['i']))] = e; lines[e['task']].append(line)
    stray = sorted(set(rec) - set(with_pool))
    complete = [t for t in with_pool if set(rec.get(t, {})) == want]
    incomplete = {t: len(rec.get(t, {})) for t in with_pool if t not in complete}
    no_valid = collections.defaultdict(list)
    for t in complete:
        k = len(json.load(open(f'{D}/pools/{t}.json')))
        for arm in spec:
            v = [rec[t][(arm, i)] for i in range(spec[arm])]
            ok = [e for e in v if isinstance(e.get('choice'), int) and 0 <= e['choice'] < k]
            if not ok:
                no_valid[arm].append(dict(task=t, lost=sum(1 for e in v if e.get('error')),
                                          refused=sum(1 for e in v if e.get('choice') == -1 and not e.get('error')),
                                          invalid=sum(1 for e in v if not e.get('error') and e.get('choice') != -1)))
    p = f'{D}/evals/{a.stage}.complete.jsonl'
    with open(p, 'w', encoding='utf-8') as fh:
        for t in complete:
            fh.writelines(lines[t])
    out = dict(stage=a.stage, tasks_in_seeds=len(tids), with_pool=len(with_pool), no_pool=[t for t in tids if t not in with_pool],
               complete=len(complete), incomplete=incomplete, stray_tasks_in_evals=stray, no_valid_votes=dict(no_valid),
               complete_evals=os.path.relpath(p, D))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.out:
        json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    if stray:
        sys.exit('в evals есть задачи без пула — остановка')
