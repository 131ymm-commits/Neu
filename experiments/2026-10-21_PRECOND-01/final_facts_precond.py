# PRECOND-01: производные числа итогового отчёта — для ledger.py audit и check_final_precond.py (по образцу final_facts_think.py).
# Только арифметика над open_an.json, val_an.json, *_push_activity.json, опубликованными солями и журналами драйвера.
#   python3 final_facts_precond.py  →  final_facts.json
import collections, datetime, glob, hashlib, json, os, subprocess
o, v = json.load(open('open_an.json')), json.load(open('val_an.json'))
me, w, ce = o['main_effects'], o['winners'], o['ceiling']
SALT = dict(open='664859e371541d83f19badb107231c4d71219a32070e4a8cf8be79c77fb673d3',            # PREREG §2
            val='be1fb959e8f4af03fe6ca8e567aa6f7c49f11206f46e81bc0a0ec5f8dfebf13e')
# Т1: этап «не определён», если выпало больше 20 % задач (открытие — меньше 8 из 9, проверка — меньше 40 из 50)
defined = dict(open=o['n_tasks'] >= 8, val=v['n_tasks'] >= 40)
# PREREG §5: решения — по неокруглённым (К2). Где в json только округлённое, знак должен быть однозначен: |x| ≥ 0,001
def sure(x, edge=0.0): assert abs(x - edge) >= 0.001, f'решение по округлённому {x} у границы {edge}: нужен пересчёт без округления'; return x
lo = min(me, key=lambda f: me[f]['effect_raw']); ties = [f for f in me if me[f]['effect_raw'] == me[lo]['effect_raw']]
def E(hit, ok=True, why=None): return dict(outcome=bool(hit) if ok else None, undefined=None if ok else why)
same_om, same_oa = w['coincide']['model_eq_obs'], w['coincide']['obs_eq_anchor']
pr, sh, va = v['primary'], v['shrinkage'], v['vs_anchor']
expect = dict(
    E1=E(o['Q1']['p'] < 0.05, defined['open'], 'открытие не определено (Т1)'),
    E2=E(lo == 'REFUSE', defined['open'] and len(ties) == 1, 'равенство неокруглённых оценок'),
    E3=E(me['CLAIMS']['effect_raw'] > 0, defined['open'], 'открытие не определено (Т1)'),
    E4=E(sure(o['REFUSE_x_CLAIMS']['effect']) < 0, defined['open'], 'открытие не определено (Т1)'),
    E5=E(isinstance(sh['OBS'], float) and sure(sh['OBS'], 0.5) > 0.5, defined['val'] and w['gain_open_raw']['OBS'] > 0 and not same_oa,
         'выигрыш на открытии ≤ 0, победители совпали или проверка не определена'),
    E6=E(not same_om and sure(pr['diff_obs_minus_model']['mean']) > 0, defined['val'] and not same_om, 'победители совпали или проверка не определена'),
    E7=E(ce['H1_mean'] < 0.1, defined['open'] and ce['D_m']['mean'] > 0, 'среднее D_m ≤ 0 (Т2)'),
    E8=E(sure(va['OBS']['ci95'][0]) > 0, defined['val'], 'проверка не определена (Т1)'))
# журналы драйвера: итоги, попытки, модели, версии, effort, инструменты голов, выход
GROUPS = ('open_exec', 'val_exec', 'open_eval_medium', 'open_eval_high', 'val_eval_medium')
calls = {}
for g in GROUPS:
    fin, att, na, models, cli, binsha, eff, tools, mcp, out_all, out_fin = (collections.Counter(), 0, 0, set(), set(), set(), set(), set(), set(), 0, 0)
    for p in glob.glob(f'run/{g}_journal/WH_*.jsonl'):
        for line in open(p, encoding='utf-8'):
            x = json.loads(line); att += 1; na += x['outcome'] == 'нет ответа'; u = (x.get('usage') or {}).get('out') or 0; out_all += u
            if x.get('final'): fin[x['final']] += 1; out_fin += u
            models.update(x.get('model_usage_keys') or []); cli.add(x.get('cli_init_version')); binsha.add(x.get('binary_sha256')); eff.add(x.get('effort'))
            for ev in (x.get('stream') or {}).get('events_no_deltas') or []:
                if ev.get('subtype') == 'init': tools.add(tuple(ev.get('tools') or [])); mcp.add(tuple(ev.get('mcp_servers') or []))
    ev = [json.loads(l) for l in open(f'run/{g}_journal/run_log.jsonl', encoding='utf-8') if l.strip()]
    started = collections.Counter((e['job'], e['attempt']) for e in ev if e['event'] == 'вызов')
    rec = {(json.loads(l)['job'], json.loads(l)['attempt']) for p in glob.glob(f'run/{g}_journal/WH_*.jsonl') for l in open(p, encoding='utf-8')}
    unrec = sum(1 for k in started if k not in rec)              # начатый вызов без записи в журнале — оборван и потерян
    seg, s = [], None                                     # сегменты драйвера: старт → пауза или готово; без записи о конце — оборван
    for e in ev:
        if e['event'] == 'старт':
            if s: seg.append([s[:16], '—', 'оборван'])
            s = e['at']
        elif e['event'] in ('пауза', 'готово') and s: seg.append([s[:16], e['at'][:16], e['event']]); s = None
    if s: seg.append([s[:16], '—', 'оборван'])
    calls[g] = dict(finals=dict(fin), attempts=att, no_answer_attempts=na, models=sorted(models), cli=sorted(c for c in cli if c),
                    binary_sha256=sorted(b[:16] for b in binsha if b), effort=sorted(e for e in eff if e), init_tools=sorted(map(list, tools)),
                    mcp_servers=sorted(map(list, mcp)), out_all=out_all, out_final=out_fin, started=sum(started.values()), started_unrecorded=unrec, segments=seg)
out_total = sum(c['out_all'] for c in calls.values())
# сырые потоки (вне git, в контейнере): sha256 распакованного потока против записанного драйвером (как rep_checks THINK-01)
import gzip
streams = collections.Counter()
for g in GROUPS:
    for p in glob.glob(f'run/{g}_journal/WH_*.jsonl'):
        for line in open(p, encoding='utf-8'):
            x = json.loads(line); s_ = x.get('stream') or {}; f_ = f'../../.cache/precond01_streams/{g}/{x["task"]}/{s_.get("file")}'
            if not s_.get('file') or not os.path.exists(f_): streams['нет файла'] += 1; continue
            streams['совпал' if hashlib.sha256(gzip.open(f_).read()).hexdigest() == s_.get('sha256') else 'не совпал'] += 1
# порядок этапов: коммит выборов → серверное событие пуша → правда; соль опубликована и совпала с PREREG
git = lambda *a: subprocess.run(['git', *a], capture_output=True, text=True, check=True).stdout.strip()
order = {}
for st_ in ('open', 'val'):
    pa = json.load(open(f'{st_}_push_activity.json'))
    tm = min(os.path.getmtime(p) for p in glob.glob(f'/root/precond_secret_{st_}/truth/WH_*.json'))      # первая запись правды (mtime)
    order[st_] = dict(commit=pa['commit'], commit_at=git('show', '-s', '--format=%cI', pa['commit']), push_time=pa['event']['timestamp'],
                      truth_first_mtime=datetime.datetime.fromtimestamp(tm, datetime.timezone.utc).isoformat()[:19],
                      evals_sha256=pa['evals_sha256'], evals_sha_on_disk=hashlib.sha256(open(f'evals/{st_}.jsonl', 'rb').read()).hexdigest(),
                      salt_sha_published=hashlib.sha256(open(f'salts/{st_}_salt.txt', 'rb').read()).hexdigest(), salt_sha_prereg=SALT[st_])
# коммиты, где файлы появились впервые (порядок: пулы проверки до правды открытия, победители до заданий проверки, соль после события)
first = lambda f: git('log', '--diff-filter=A', '--format=%h %cI', '--', f).splitlines()[-1].split()
commits = {f: dict(zip(('commit', 'at'), first(f))) for f in ('pools/WH_8359.json', 'open_an.json', 'winners.json', 'run/val_eval_medium_jobs.jsonl',
                                                              'val_an.json', 'salts/open_salt.txt', 'salts/val_salt.txt', 'final_facts_precond.py')}
assert commits['pools/WH_8359.json']['at'] < order['open']['truth_first_mtime'] and commits['winners.json']['at'] < commits['run/val_eval_medium_jobs.jsonl']['at']
assert order['open']['push_time'][:19] < commits['salts/open_salt.txt']['at'][:19] and order['val']['push_time'][:19] < commits['salts/val_salt.txt']['at'][:19]
assert commits['final_facts_precond.py']['at'][:19] < order['val']['truth_first_mtime']                     # правила исходов — до правды проверки
# код на диске против sha256 регистрации (prereg_hashes.json, PREREG §10)
PH = json.load(open('prereg_hashes.json'))['files']
code_mismatch = sorted(f for f, h in PH.items() if hashlib.sha256(open(f, 'rb').read()).hexdigest() != h)
facts = dict(defined=defined, expectations=expect, commits=commits, code_files=len(PH), code_mismatch=code_mismatch, strongest=lo, calls=calls, out_total=out_total, streams=dict(streams), order=order,
             selection_null_p=w['selection_null_p'], gain_open_raw=w['gain_open_raw'],
             out_ratio_high_medium=round(o['out_per_call']['high'] / o['out_per_call']['medium64'], 2))     # цена high против medium (совет 39)
json.dump(facts, open('final_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(facts, ensure_ascii=False)[:3000])
