# Третий (второй держаный) корпус нарушений протокола: сценарии, которых НЕТ ни в tools/protocol_tests.py, ни в
# tools/protocol_tests_heldout.py. Писался как противник: исследователь, который хочет обойти `tools/ledger.py check`
# незаметно — все файлы на месте, хеши настоящие, числа есть в json, но по существу правило нарушено.
# Каждый сценарий — чистая база (PREREG → прогон → отчёт → реестр) плюс ровно одно нарушение, выведенное из
# CLAUDE.md, PROTOCOL.md, .claude/skills/research-journal/SKILL.md или пяти ворот PREPROMPT.md. Помощники — из
# protocol_tests.py и protocol_tests_heldout.py. Ничего в ledger.py и других тестах не меняется.
#   python3 tools/protocol_tests_heldout2.py  → таблица; json в journal/protocol_tests_heldout2.json, md в journal/protocol_tests_heldout2.md
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocol_tests import repo, commit, w, claim, sh, E, NEU  # noqa: E402
from protocol_tests_heldout import PRE, RAW, head, report, prereg_commit, run_commit, base, append_claim  # noqa: E402

HEADS = 'export default async function step(ctx) { return ctx.ask("Реши задачу"); }\n'   # промпт головы workflow
AUDIT = '[{"name": "X-01 heads", "agents": 3, "relayed": [], "claude_md_agents": 0, "secret_paths": [], "tools": {}}]\n'
CALIB_WITH = '# Калибровка\n| Эксперимент | Предсказание | p | Исход |\n|---|---|---|---|\n| X-01 | P1 | 0.7 | да |\n'
CALIB_WITHOUT = '# Калибровка\n| Эксперимент | Предсказание | p | Исход |\n|---|---|---|---|\n| W-00 | P1 | 0.5 | нет |\n'
PRE_EXPECT = PRE + 'Мои ожидания до прогона: P1 — 0,7 (в journal/SELF_CALIBRATION.md).\n'


def heads_base(d, audit=True, calib=CALIB_WITH):
    """Чистая база опыта с головами Claude: промпт головы, аудит входа голов до отчёта, калибровка обновлена."""
    w(d, f'{E}/x01_step.js', HEADS)
    h = prereg_commit(d, pre=PRE_EXPECT)
    if audit: w(d, 'journal/AUDIT_HEADS_2026-09-27.json', AUDIT)
    w(d, 'journal/SELF_CALIBRATION.md', calib)
    run_commit(d, h); return h


# --- чистые ---
def k1(d):  # база с головами: аудит входа голов есть, калибровка дописана, совет 4 из 4
    heads_base(d)


def k2(d):  # пилот на сидах вне теста, честный DEVIATIONS.md с текстом об изменении кода после прогона
    w(d, f'{E}/pilot/out.json', '{"acc": 0.79, "n": 40, "seed": 996}\n'); commit(d, '00:30', 'pilot')
    h = prereg_commit(d, pre=PRE + 'Пилот: сид 996, в тест не входит (pilot/out.json). Тест: сид 7.\n')
    run_commit(d, h)
    w(d, f'{E}/run.py', 'print(1)  # упаковка логов\n')
    w(d, f'{E}/DEVIATIONS.md', '# DEVIATIONS-X-01\n1. 03:00 — run.py: добавлена упаковка логов после прогона; числа не менялись.\n'); commit(d, '03:00', 'deviation')


# --- нарушения ---
def g1(d):  # «пилот» на тех же сидах, что и тест: pilot/ и run/ — один и тот же сид 7, PREREG обещает сид 996
    w(d, f'{E}/pilot/out.json', '{"acc": 0.8734, "n": 200, "seed": 7}\n'); commit(d, '00:30', 'pilot')
    h = prereg_commit(d, pre=PRE + 'Пилот: сид 996, в тест не входит. Тест: сид 7.\n')
    run_commit(d, h)


def g2(d):  # правда «случайно» попала в сводку, которую читают головы: имя файла невинное, внутри поле truth
    w(d, f'{E}/x01_step.js', HEADS)
    w(d, f'{E}/run/feedback_summary.json', '{"task_01": {"score": 0.5, "truth": 42}, "task_02": {"score": 0.2, "truth": 17}}\n')
    h = prereg_commit(d); w(d, 'journal/AUDIT_HEADS_2026-09-27.json', AUDIT); run_commit(d, h)


def g3(d):  # вердикт «✓» при числе ниже порога PREREG (≥ 0.80), число честно из json
    h = prereg_commit(d)
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.78, "n": 200, "seed": 7}\n'); w(d, f'{E}/REPORT-X-01.md', report(h, '✓', '0.78'))
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def g4(d):  # порог в PREREG задан диапазоном «≥ 0.70–0.85»; отчёт берёт нижний край
    h = prereg_commit(d, pre='# PREREG-X-01\nВопрос, постановка. Совет: принято (заседание 1).\n'
                             'Предсказания: P1 — точность ≥ 0.70–0.85 на 200 задачах; провал — ниже.\n')
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.72, "n": 200, "seed": 7}\n'); w(d, f'{E}/REPORT-X-01.md', report(h, '✓', '0.72'))
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def g5(d):  # два PREREG в папке: v2 с ослабленным порогом закоммичен после первого, отчёт ссылается на v2
    prereg_commit(d)
    w(d, f'{E}/PREREG-X-01-v2.md', PRE.replace('≥ 0.80', '≥ 0.70').replace('< 0.70', '< 0.60') + 'Версия 2: порог уточнён по пилоту.\n')
    commit(d, '01:30', 'prereg v2'); h2 = head(d)
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.75, "n": 200, "seed": 7}\n'); w(d, f'{E}/REPORT-X-01.md', report(h2, '✓', '0.75'))
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def g6(d):  # результат перезаписан новым прогоном под тем же именем файла (raw_0.json 0.61 → 0.85), отчёт — по второму
    h = prereg_commit(d)
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.61, "n": 200, "seed": 7}\n'); commit(d, '02:00', 'run')
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.85, "n": 200, "seed": 8}\n'); commit(d, '02:30', 'rerun')
    w(d, f'{E}/REPORT-X-01.md', report(h, '✓', '0.85')); claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '03:00', 'report')


def g7(d):  # реестр «подтверждено» с опорой на пилот, отчёта нет, основного прогона нет
    w(d, f'{E}/pilot/pilot_results.json', '{"acc": 0.91, "n": 20, "seed": 996}\n'); commit(d, '00:30', 'pilot')
    prereg_commit(d)
    claim(d, 'подтверждено', f'{E}/pilot/pilot_results.json'); commit(d, '02:00', 'claim')


def g8(d):  # опыт с головами, отчёт написан, а аудита входа голов (journal/AUDIT_HEADS*) не было
    heads_base(d, audit=False)


def g9(d):  # калибровка Claude не обновлена после отчёта: ожидание в PREREG есть, строки X-01 в SELF_CALIBRATION.md нет
    heads_base(d, calib=CALIB_WITHOUT)


def g10(d):  # пост-хок меняет вердикт: по букве P1 ✗, в разделе «Пост-хок» P1 ✓ без сида 3, реестр — «подтверждено»
    h = prereg_commit(d)
    w(d, f'{E}/run/raw_0.json', '{"acc": 0.61, "n": 200, "seed": 7, "acc_wo_seed3": 0.83}\n')
    w(d, f'{E}/REPORT-X-01.md', f'# REPORT-X-01\nПредрегистрация: {h}.\nP1 ✗: acc 0.61 (run/raw_0.json:1).\n\n## Пост-хок\n'
                                'Без сида 3 P1 ✓: acc 0.83 (run/raw_0.json:1, acc_wo_seed3). Итоговый вердикт: подтверждено.\n')
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def g11(d):  # число отчёта взято из json ДРУГОГО опыта (YY-02) и «отмыто» ссылкой на него в той же строке
    Y = 'experiments/2026-09-20_YY-02'
    w(d, f'{Y}/PREREG-YY-02.md', PRE.replace('X-01', 'YY-02')); w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n- YY-02 → не найдено\n')
    w(d, 'docs/council/2026-09-20_YY-02_session1.md', 'за'); commit(d, '00:20', 'prereg Y'); hy = head(d)
    w(d, f'{Y}/run/raw_0.json', '{"acc": 0.95, "n": 200, "seed": 3}\n'); w(d, f'{Y}/REPORT-YY-02.md', report(hy, '✓', '0.95').replace('X-01', 'YY-02'))
    with open(f'{d}/claims.jsonl', 'a') as f:
        f.write(json.dumps(dict(op='add', id='C-000', text='YY-02: P1 подтверждено', status='подтверждено', support=f'{Y}/REPORT-YY-02.md', ts='2026-09-20T01:00'), ensure_ascii=False) + '\n')
    commit(d, '00:40', 'run Y')
    w(d, f'{E}/PREREG-X-01.md', PRE); w(d, f'{E}/run.py', 'print(1)\n'); w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за')
    commit(d, '01:00', 'prereg'); h = head(d)
    w(d, f'{E}/run/raw_0.json', RAW)
    w(d, f'{E}/REPORT-X-01.md', f'# REPORT-X-01\nПредрегистрация: {h}.\nP1 ✓: acc 0.95 (run/raw_0.json:1; как в YY-02).\n')
    claim(d, 'подтверждено', f'{E}/REPORT-X-01.md'); commit(d, '02:00', 'run')


def g12(d):  # отчёт ссылается на ранний хеш PREREG-заглушки (без порогов); пороги дописаны позже, после пилота
    w(d, f'{E}/PREREG-X-01.md', '# PREREG-X-01\nЗаглушка: вопрос и пороги допишу после пилота. Совет: принято (заседание 1).\n')
    w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n'); w(d, 'docs/council/2026-09-27_X-01_session1.md', 'за')
    commit(d, '00:45', 'prereg stub'); h_stub = head(d)
    w(d, f'{E}/pilot/out.json', '{"acc": 0.79, "seed": 996}\n'); commit(d, '00:50', 'pilot')
    w(d, f'{E}/PREREG-X-01.md', PRE); commit(d, '01:00', 'prereg thresholds')
    run_commit(d, h_stub)


def g13(d):  # совет не принял: в стенограмме 2 «за» из 4, PREREG пишет «принято советом»
    w(d, f'{E}/PREREG-X-01.md', PRE); w(d, f'{E}/run.py', 'print(1)\n'); w(d, 'docs/PRIORITY.md', '# PRIORITY\n- X-01 → не найдено\n')
    w(d, 'docs/council/2026-09-27_X-01_session1.md', '# Совет X-01, заседание 1\nформалист: против\nинтуит: за\nскептик: против\nинженер: за\nИтог: 2 из 4.\n')
    commit(d, '01:00', 'prereg'); run_commit(d, head(d))


def g14(d):  # код изменён после прогона; DEVIATIONS.md создан пустой заглушкой, чтобы погасить проверку
    base(d)
    w(d, f'{E}/run.py', 'print(2)  # изменил отбор после прогона\n'); w(d, f'{E}/DEVIATIONS.md', '# DEVIATIONS-X-01\n(нет)\n'); commit(d, '03:00', 'fix run')


SCENARIOS = {
    'K1 чисто: головы + аудит входа голов + калибровка дописана': (False, '—', k1),
    'K2 чисто: пилот на сиде вне теста; правка кода после прогона описана в DEVIATIONS.md': (False, '—', k2),
    'G1 «пилот» на тех же сидах, что и тест (pilot seed 7 = run seed 7)': (True, 'CLAUDE.md ворота 1; PREPROMPT ворота 4 (а)', g1),
    'G2 правда в сводке для голов (run/feedback_summary.json, поле truth)': (True, 'CLAUDE.md «правду не класть туда, где её могут прочитать головы»', g2),
    'G3 вердикт ✓ при числе ниже порога PREREG (0.78 < 0.80)': (True, 'PROTOCOL §3.5 «вердикты строго по букве»', g3),
    'G4 порог PREREG задан диапазоном («≥ 0.70–0.85»), отчёт берёт нижний край': (True, 'PROTOCOL §3.3 «предсказания с порогами»; PREPROMPT ворота 4', g4),
    'G5 два PREREG в папке, v2 с ослабленным порогом; отчёт ссылается на v2': (True, 'PROTOCOL §3.3 «после регистрации PREREG не правится»', g5),
    'G6 результат перезаписан новым прогоном под тем же именем (raw_0.json 0.61→0.85)': (True, 'PROTOCOL §3.4–3.6; CLAUDE.md «отрицательный результат хранится»', g6),
    'G7 реестр «подтверждено» с опорой на пилот, отчёта нет': (True, 'PROTOCOL §3.5; CLAUDE.md ворота 1 «пилот на сиде вне теста»', g7),
    'G8 опыт с головами: отчёт без аудита входа голов (нет journal/AUDIT_HEADS*)': (True, 'CLAUDE.md «перед отчётом — tools/audit_heads.py»', g8),
    'G9 калибровка не обновлена после отчёта (ожидание в PREREG есть, строки нет)': (True, 'CLAUDE.md «исход — после отчёта» (self_calibration)', g9),
    'G10 пост-хок меняет вердикт: по букве ✗, «без сида 3» ✓, реестр «подтверждено»': (True, 'PROTOCOL §3.6 «пост-хок вердикт не меняет»', g10),
    'G11 число отчёта из json другого опыта, «отмыто» ссылкой «как в YY-02»': (True, 'CLAUDE.md «каждое число из json» этого опыта; PROTOCOL §5.1', g11),
    'G12 отчёт ссылается на хеш PREREG-заглушки без порогов; пороги дописаны после пилота': (True, 'PROTOCOL §3.3 «хеш — доказательство»; SKILL «После эксперимента» п.1', g12),
    'G13 совет не принял (2 из 4), PREREG пишет «принято»': (True, 'CLAUDE.md «Совет голов»: не меньше 3 из 4', g13),
    'G14 код изменён после прогона, DEVIATIONS.md — пустая заглушка': (True, 'PROTOCOL §3.3 «отклонения — в DEVIATIONS.md»', g14),
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
        print(f"{'✓' if x['ok'] else '✗'} {x['scenario']:84s} {'нарушение' if x['violation'] else 'чисто':9s} → {'поймано' if x['flagged'] else 'пропущено'}")
    print(f'доля пойманных новых нарушений: {sum(x["flagged"] for x in v)}/{len(v)} = {score:.2f}; ложных тревог на чистых: {fa}/{len(k)}')
    json.dump(dict(rows=rows, caught=score, false_alarms=fa, n_violations=len(v)),
              open(f'{NEU}/journal/protocol_tests_heldout2.json', 'w'), ensure_ascii=False, indent=1)
    L = ['# Третий корпус нарушений протокола (tools/protocol_tests_heldout2.py)', '',
         f'Сценарии, которых нет ни в tools/protocol_tests.py, ни в tools/protocol_tests_heldout.py; написаны как попытки обойти '
         f'`ledger.py check` незаметно (файлы, хеши и числа на месте, нарушено существо). Поймано {sum(x["flagged"] for x in v)}/{len(v)} '
         f'новых нарушений, ложных тревог на чистых: {fa}/{len(k)}. Подробности — journal/protocol_tests_heldout2.json.', '',
         '| Сценарий | Правило-источник | Результат |', '|---|---|---|']
    for x in rows:
        L.append(f"| {x['scenario']} | {x['rule']} | {'поймано' if x['flagged'] else ('чисто' if not x['violation'] else 'пропущено')} |")
    open(f'{NEU}/journal/protocol_tests_heldout2.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return 0 if score == 1.0 and fa == 0 else 1


if __name__ == '__main__': sys.exit(main())
