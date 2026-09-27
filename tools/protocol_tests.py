# Корпус синтетических нарушений протокола: сколько из них ловит `tools/ledger.py check` (критерий 2 «протокол под кодом», DECISIONS 27.09.2026).
# Каждый сценарий — временный git-репозиторий с копией tools/ledger.py; коммиты с явными датами. Нарушение считается пойманным, если check завершился с кодом 1.
#   python3 tools/protocol_tests.py            → таблица и доля пойманных; json в journal/protocol_tests.json
import os, sys, json, subprocess, tempfile, shutil
NEU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREREG = '# PREREG-X-01\nВопрос, постановка, предсказания P1 с порогом. Совет: принято (заседание 1).\n'


def sh(cwd, *cmd, t=None):
    env = dict(os.environ); env.pop('GIT_DIR', None)
    if t: env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = f'2026-09-27T{t}:00'
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def repo():
    d = tempfile.mkdtemp(prefix='neu_proto_'); os.makedirs(f'{d}/tools'); os.makedirs(f'{d}/docs/council'); os.makedirs(f'{d}/journal')
    shutil.copy(f'{NEU}/tools/ledger.py', f'{d}/tools/ledger.py')
    sh(d, 'git', 'init', '-q'); sh(d, 'git', 'config', 'user.email', 'x@x'); sh(d, 'git', 'config', 'user.name', 'x'); sh(d, 'git', 'config', 'core.hooksPath', '/dev/null')
    open(f'{d}/claims.jsonl', 'w').close(); open(f'{d}/docs/PRIORITY.md', 'w').write('# PRIORITY\n'); open(f'{d}/journal/ERRORS.md', 'w').write('# ERRORS\n')
    commit(d, '00:00', 'init'); return d


def commit(d, t, msg): sh(d, 'git', 'add', '-A'); sh(d, 'git', 'commit', '-q', '-m', msg, t=t)


def w(d, path, text): os.makedirs(os.path.dirname(f'{d}/{path}'), exist_ok=True); open(f'{d}/{path}', 'w').write(text)


def claim(d, status, support, text='X-01: P1 подтверждено'):
    with open(f'{d}/claims.jsonl', 'a') as f: f.write(json.dumps(dict(op='add', id='C-001', text=text, status=status, support=support or '', ts='2026-09-27T01:00'), ensure_ascii=False) + '\n')


E = 'experiments/2026-09-27_X-01'
SCENARIOS = {
    # чистые: нарушений нет, check должен пройти
    'K1 чисто: PREREG → прогон → отчёт': (False, lambda d: (w(d, f'{E}/PREREG-X-01.md', PREREG), w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'), w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за'), commit(d, '01:00', 'prereg'),
                                                            w(d, f'{E}/run/raw_0.json', '{}'), w(d, f'{E}/REPORT-X-01.md', 'P1 ✓'), claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'), commit(d, '02:00', 'run'))),
    'K2 чисто: пилот и сухой прогон до PREREG': (False, lambda d: (w(d, f'{E}/pilot/out.json', '{}'), w(d, f'{E}/dry/mock.mjs', ''), commit(d, '00:30', 'pilot'), w(d, f'{E}/PREREG-X-01.md', PREREG), w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'),
                                                                   w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за'), commit(d, '01:00', 'prereg'), w(d, f'{E}/run/raw_0.json', '{}'), commit(d, '02:00', 'run'))),
    # нарушения
    'V1 PREREG изменён после прогона': (True, lambda d: (w(d, f'{E}/PREREG-X-01.md', PREREG), commit(d, '01:00', 'prereg'), w(d, f'{E}/run/raw_0.json', '{}'), commit(d, '02:00', 'run'), w(d, f'{E}/PREREG-X-01.md', PREREG + 'порог смягчён\n'), commit(d, '03:00', 'edit'))),
    'V2 прогон раньше PREREG': (True, lambda d: (w(d, f'{E}/run/raw_0.json', '{}'), commit(d, '01:00', 'run'), w(d, f'{E}/PREREG-X-01.md', PREREG), commit(d, '02:00', 'prereg'))),
    'V3 статус «подтверждено» без опоры': (True, lambda d: (claim(d, 'подтверждено', None), commit(d, '01:00', 'claim'))),
    'V4 опора указывает на несуществующий файл': (True, lambda d: (claim(d, 'подтверждено', f'{E}/REPORT-НЕТ.md'), commit(d, '01:00', 'claim'))),
    'V5 PREREG без строки «кто раньше» в PRIORITY': (True, lambda d: (w(d, f'{E}/PREREG-X-01.md', PREREG), w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за'), commit(d, '01:00', 'prereg'))),
    'V6 прогон без предрегистрации': (True, lambda d: (w(d, f'{E}/run/raw_0.json', '{}'), w(d, f'{E}/REPORT-X-01.md', 'P1 ✓'), commit(d, '01:00', 'run'))),
    'V7 отчёт есть, в реестре ничего': (True, lambda d: (w(d, f'{E}/PREREG-X-01.md', PREREG), w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'), w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за'), commit(d, '01:00', 'prereg'),
                                                        w(d, f'{E}/run/raw_0.json', '{}'), w(d, f'{E}/REPORT-X-01.md', 'P1 ✓'), commit(d, '02:00', 'run'))),
    'V8 PREREG ссылается на совет, стенограммы нет': (True, lambda d: (w(d, f'{E}/PREREG-X-01.md', PREREG), w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'), commit(d, '01:00', 'prereg'))),
}


def main():
    rows = []
    for name, (is_violation, build) in SCENARIOS.items():
        d = repo(); build(d)
        r = sh(d, 'python3', 'tools/ledger.py', 'check'); caught = r.returncode != 0
        rows.append(dict(scenario=name, violation=is_violation, flagged=caught, ok=(caught == is_violation), tail=(r.stdout + r.stderr).strip().splitlines()[-3:]))
        shutil.rmtree(d, ignore_errors=True)
    v = [x for x in rows if x['violation']]; k = [x for x in rows if not x['violation']]
    score = sum(x['flagged'] for x in v) / len(v); fa = sum(x['flagged'] for x in k)
    for x in rows: print(f"{'✓' if x['ok'] else '✗'} {x['scenario']:48s} {'нарушение' if x['violation'] else 'чисто':9s} → {'поймано' if x['flagged'] else 'пропущено'}")
    print(f'доля пойманных нарушений: {sum(x["flagged"] for x in v)}/{len(v)} = {score:.2f}; ложных тревог на чистых: {fa}/{len(k)}')
    json.dump(dict(rows=rows, caught=score, false_alarms=fa, n_violations=len(v)), open(f'{NEU}/journal/protocol_tests.json', 'w'), ensure_ascii=False, indent=1)
    return 0 if score == 1.0 and fa == 0 else 1


if __name__ == '__main__': sys.exit(main())
