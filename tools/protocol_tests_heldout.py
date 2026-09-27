# Держаный (held-out) корпус нарушений протокола: сценарии, которых НЕТ в tools/protocol_tests.py.
# Цель — проверить, не подогнан ли `tools/ledger.py check` под собственный корпус (8/8). Каждый сценарий строится
# на чистой базе (PREREG → прогон → отчёт → реестр, check проходит) и добавляет ровно одно новое нарушение,
# выведенное из CLAUDE.md, PROTOCOL.md или .claude/skills/research-journal/SKILL.md. Помощники берутся из protocol_tests.py.
#   python3 tools/protocol_tests_heldout.py   → таблица; json в journal/protocol_tests_heldout.json, md в journal/protocol_tests_heldout.md
import os, sys, json, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol_tests import repo, commit, w, claim, sh, E, PREREG, NEU  # noqa: E402

PRE = PREREG + 'Предсказания: P1 — точность ≥ 0.80 на 200 задачах; провал — < 0.70; третий исход — между.\n'
RAW = '{"acc": 0.8734, "n": 200, "seed": 7}\n'


def head(d):
    return sh(d, 'git', 'rev-parse', '--short', 'HEAD').stdout.strip()


def report(h, verdict='✓', acc='0.8734'):
    return f'# REPORT-X-01\nПредрегистрация: {h}.\nP1 {verdict}: acc {acc} (run/raw_0.json:1).\n'


def prereg_commit(d, pre=PRE, t='01:00'):
    w(d, f'{E}/PREREG-X-01.md', pre); w(d, f'{E}/run.py', 'print(1)\n')
    w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'); w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за')
    commit(d, t, 'prereg'); return head(d)


def run_commit(d, h, verdict='✓', acc='0.8734', status='подтверждено', t='02:00'):
    w(d, f'{E}/run/raw_0.json', RAW); w(d, f'{E}/REPORT-X-01.md', report(h, verdict, acc))
    claim(d, status, f'{E}/REPORT-X-01.md'); commit(d, t, 'run')


def base(d):
    h = prereg_commit(d); run_commit(d, h); return h


def append_claim(d, status, why, support):
    with open(f'{d}/claims.jsonl', 'a') as f:
        f.write(json.dumps(dict(op='set', id='C-001', status=status, why=why, support=support, ts='2026-09-27T03:00'), ensure_ascii=False) + '\n')


# --- сценарии: (нарушение?, правило-источник, построение) ---
def h1(d):  # отчёт ссылается на хеш, которого нет в истории: коммит PREREG переписан amend'ом (история переписана)
    h0 = prereg_commit(d)
    sh(d, 'git', 'commit', '-q', '--amend', '-m', 'prereg (поправил сообщение)', t='01:30')
    run_commit(d, h0)


def h2(d):  # число в REPORT, которого нет ни в одном json
    h = prereg_commit(d); run_commit(d, h, acc='0.91')


def h3(d):  # PREREG без предсказаний с порогами
    h = prereg_commit(d, pre='# PREREG-X-01\nВопрос: даёт ли диалог голов прирост? Постановка: 200 задач EVO. Совет: принято (заседание 1).\n')
    run_commit(d, h)


def h4(d):  # код прогона изменён после первого прогона, DEVIATIONS.md нет
    h = base(d)
    w(d, f'{E}/run.py', 'print(2)  # изменил отбор после прогона\n'); w(d, f'{E}/run/raw_1.json', RAW); commit(d, '03:00', 'fix run')


def h5(d):  # чекпойнт *.pkl в git
    h = base(d); w(d, f'{E}/run/model_final.pkl', 'PKL' * 1000); commit(d, '03:00', 'ckpt')


def h6(d):  # правда от кода лежит рядом с промптами голов (головы могут её прочитать)
    h = prereg_commit(d)
    w(d, f'{E}/prompts/task_01.md', 'Реши задачу'); w(d, f'{E}/prompts/truth.json', '{"task_01": 42}')
    run_commit(d, h)


def h7(d):  # запись в ERRORS.md удалена
    w(d, 'journal/ERRORS.md', '# ERRORS\n1. Ошибся в пороге.\n2. Предположил без проверки.\n'); commit(d, '00:30', 'errors')
    h = base(d)
    w(d, 'journal/ERRORS.md', '# ERRORS\n2. Предположил без проверки.\n'); commit(d, '03:00', 'cleanup errors')


def h8(d):  # отчёт без ссылки на хеш PREREG
    h = prereg_commit(d)
    w(d, f'{E}/run/raw_0.json', RAW); w(d, f'{E}/REPORT-X-01.md', '# REPORT-X-01\nP1 ✓: acc 0.8734 (run/raw_0.json:1).\n')
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def h9(d):  # повтор прогона после отрицательного отчёта, вердикт перевёрнут без новой PREREG
    h = prereg_commit(d); run_commit(d, h, verdict='✗', acc='0.61', status='опровергнуто')
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.61, "n": 200, "seed": 7}\n'); commit(d, '02:30', 'fix json')
    w(d, f'{E}/run/raw_1.json', '{"acc": 0.85, "n": 200, "seed": 8}\n'); w(d, f'{E}/REPORT-X-01.md', report(h, '✓', '0.85'))
    append_claim(d, 'подтверждено', 'перепрогон на сиде 8', f'{E}/REPORT-X-01.md'); commit(d, '03:00', 'rerun')


def h10(d):  # реестр «подтверждено», отчёт по букве говорит «опровергнуто»
    h = prereg_commit(d); run_commit(d, h, verdict='✗ опровергнуто', acc='0.61', status='подтверждено')
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.61, "n": 200}\n'); commit(d, '02:30', 'json')


def h11(d):  # PREREG закоммичен, но не запушен до прогона (origin есть, push был только init)
    remote = tempfile.mkdtemp(prefix='neu_remote_'); sh(remote, 'git', 'init', '-q', '--bare')
    sh(d, 'git', 'remote', 'add', 'origin', remote); sh(d, 'git', 'push', '-q', '-u', 'origin', 'HEAD')
    base(d)


def h12(d):  # статус в реестре сменён записью без «почему» (в обход ledger.py set)
    base(d); append_claim(d, 'опровергнуто', '', f'{E}/REPORT-X-01.md'); commit(d, '03:00', 'set')


SCENARIOS = {
    'K0 чисто: база PREREG → прогон → отчёт → реестр': (False, '—', base),
    'H1 отчёт ссылается на хеш PREREG, которого нет в истории (amend)': (True, 'PROTOCOL §3.3/§3.5, §6.2; CLAUDE.md п.3–4', h1),
    'H2 число в REPORT, которого нет ни в одном json': (True, 'CLAUDE.md «каждое число из json»; PROTOCOL §4.4, §5.1', h2),
    'H3 PREREG без предсказаний с порогами': (True, 'PROTOCOL §3.3; SKILL «Перед любым экспериментом» п.1', h3),
    'H4 код прогона изменён после прогона, DEVIATIONS.md нет': (True, 'PROTOCOL §3.3 «отклонения — в DEVIATIONS.md»', h4),
    'H5 чекпойнт *.pkl в git': (True, 'CLAUDE.md п.5; PROTOCOL §6.3', h5),
    'H6 правда от кода рядом с промптами голов': (True, 'CLAUDE.md «правду не класть туда, где её могут прочитать головы»', h6),
    'H7 запись в journal/ERRORS.md удалена': (True, 'CLAUDE.md п.2; PROTOCOL §4.2', h7),
    'H8 REPORT без ссылки на хеш PREREG': (True, 'PROTOCOL §3.5; SKILL «После эксперимента» п.1', h8),
    'H9 перепрогон после отчёта, вердикт перевёрнут без новой PREREG': (True, 'PROTOCOL §3.5–3.6 «вердикт по букве, пост-хок не меняет»', h9),
    'H10 реестр «подтверждено», отчёт говорит «опровергнуто»': (True, 'PROTOCOL §3.5; CLAUDE.md «выводы меняются с опорой»', h10),
    'H11 PREREG закоммичен, но не запушен до прогона': (True, 'PROTOCOL §3.3 «коммит и push до первого прогона»; SKILL п.2', h11),
    'H12 смена статуса в реестре без «почему» (в обход ledger.py set)': (True, 'CLAUDE.md «выводы меняются только через ledger.py»', h12),
}


def main():
    rows = []
    for name, (is_violation, rule, build) in SCENARIOS.items():
        d = repo(); build(d)
        r = sh(d, 'python3', 'tools/ledger.py', 'check'); caught = r.returncode != 0
        rows.append(dict(scenario=name, rule=rule, violation=is_violation, flagged=caught, ok=(caught == is_violation),
                         tail=(r.stdout + r.stderr).strip().splitlines()[-3:]))
        shutil.rmtree(d, ignore_errors=True)
    v = [x for x in rows if x['violation']]; k = [x for x in rows if not x['violation']]
    score = sum(x['flagged'] for x in v) / len(v); fa = sum(x['flagged'] for x in k)
    for x in rows:
        print(f"{'✓' if x['ok'] else '✗'} {x['scenario']:70s} {'нарушение' if x['violation'] else 'чисто':9s} → {'поймано' if x['flagged'] else 'пропущено'}")
    print(f'доля пойманных новых нарушений: {sum(x["flagged"] for x in v)}/{len(v)} = {score:.2f}; ложных тревог на чистых: {fa}/{len(k)}')
    json.dump(dict(rows=rows, caught=score, false_alarms=fa, n_violations=len(v)),
              open(f'{NEU}/journal/protocol_tests_heldout.json', 'w'), ensure_ascii=False, indent=1)
    L = ['# Держаный корпус нарушений протокола (tools/protocol_tests_heldout.py)', '',
         f'Сценарии, которых нет в tools/protocol_tests.py. Поймано {sum(x["flagged"] for x in v)}/{len(v)} новых нарушений, '
         f'ложных тревог на чистых: {fa}/{len(k)}. Подробности — journal/protocol_tests_heldout.json.', '',
         '| Сценарий | Правило-источник | Результат |', '|---|---|---|']
    for x in rows:
        L.append(f"| {x['scenario']} | {x['rule']} | {'поймано' if x['flagged'] else ('чисто' if not x['violation'] else 'пропущено')} |")
    open(f'{NEU}/journal/protocol_tests_heldout.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return 0 if score == 1.0 and fa == 0 else 1


if __name__ == '__main__': sys.exit(main())
