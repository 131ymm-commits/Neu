#!/usr/bin/env python3
"""SCORE-01: сборка DRAFT-PREREG-SCORE-01.md из prereg_template.md, текста §3 ниже, предсказаний analyze_score01.PRED
и таблиц, которые печатают скрипты пилотов (числа — командой). Весь текст живёт в шаблоне и здесь: черновик руками не правится
(урок TRUST-04, третья проверка, находка 1).
  python3 assemble_prereg_score01.py [--status "регистрация …"] [--out PREREG-SCORE-01.md]"""
import glob
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_score01 as A  # noqa: E402

STATUS = sys.argv[sys.argv.index('--status') + 1] if '--status' in sys.argv else 'черновик; не регистрация'
OUT = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'DRAFT-PREREG-SCORE-01.md'
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
run = lambda *c: subprocess.run([sys.executable, *c], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()

T1 = run('pilot_tables.py', 'pilot1_opus', 'pilot1_haiku')
T2 = run('pilot2_tables.py', 'opus', 'haiku')
T3 = run('pilot3_tables.py', 'opus', 'haiku')
PW = run('power_score01.py', '--md')
POW = json.load(open(os.path.join(HERE, 'pilot_power.json')))
POW12 = json.load(open(os.path.join(HERE, 'pilot12_power.json')))
POW12S = json.load(open(os.path.join(HERE, 'pilot12_power_single.json')))
H = json.loads(run('prompts_score.py', 'hash'))
CHK = {s: json.load(open(os.path.join(HERE, 'truth', f'check_{s}.json')))['summary'] for s in ('pilot', 'main', 'rep')}
CTX = open(os.path.join(HERE, 'run', 'ctxcheck.log'), encoding='utf-8').read()


def journal_calls(prefix):
    n = 0
    for d in glob.glob(os.path.join(HERE, 'run', f'{prefix}_*')):
        if os.path.isdir(d):
            for fn in glob.glob(os.path.join(d, 'WH_*.jsonl')):
                n += sum(1 for l in open(fn, encoding='utf-8') if json.loads(l).get('final'))
    return n


CALLS = {k: journal_calls(k) for k in ('pilot0', 'pilot1', 'pilot2', 'ctxcheck', 'pilot3')}


def corr_aa():
    out = []
    for line in T3.splitlines():
        c = [x.strip() for x in line.split('|')]
        if len(c) > 4 and ' и ' in c[2] and 'повтор 0 и' in c[2]:
            a, b = c[2].split(' и ')
            if a.split(',')[0] == b.split(',')[0] and b.endswith('повтор 1'):
                out.append((c[1], a.split(',')[0], c[3]))
    return out


AA_TXT = '; '.join(f'{"Opus" if m == "opus" else "Haiku"} {arm} — {r}' for m, arm, r in corr_aa())


def rule_check_12():
    """Правило выбора устройства (коммит 6dc721f) по пилотам 1–2: статистика как записана (объединённые пары, n = 40)
    и как считалась в первом черновике (среднее двух повторов, n = 20)."""
    from pilot2_describe import pairs, val
    out = []
    for model in ('opus', 'haiku'):
        E = json.load(open(os.path.join(HERE, 'evals', f'pilot12_{model}.json')))
        rows = {'|'.join(k.split('|')[:2]) + ('' if k.endswith('|0') else '_' + k.split('|')[2]): v for k, v in E['rows'].items()}
        tasks = sorted({v['task'] for v in E['rows'].values()})
        z = lambda x: abs(sum(x) / len(x)) / (math.sqrt(sum((v - sum(x) / len(x)) ** 2 for v in x) / (len(x) - 1)) / math.sqrt(len(x)))
        pooled = pairs(rows, tasks, 'WIN', 'LOG', 'self_dec') + pairs(rows, tasks, 'WIN_1', 'LOG_1', 'self_dec')
        two = []
        for t in tasks:
            ks = [f'{t}|{c}' for c in ('LOG', 'LOG_1', 'WIN', 'WIN_1')]
            if all(rows.get(k) and rows[k]['valid'] for k in ks):
                two.append((val(rows[ks[2]], 'self_dec') + val(rows[ks[3]], 'self_dec')) / 2 - (val(rows[ks[0]], 'self_dec') + val(rows[ks[1]], 'self_dec')) / 2)
        aa = [z(pairs(rows, tasks, f'{a}_1', a, 'self_dec')) for a in ('LOG', 'WIN')]
        out.append(f'{model}: |среднее| / SE по объединённым парам (n = {len(pooled)}) {f(z(pooled), 2)}, по среднему двух повторов (n = {len(two)}) {f(z(two), 2)}; A/A — {f(aa[0], 2)} (LOG) и {f(aa[1], 2)} (WIN)')
    return '; '.join(out)


def direction_check():
    """Правило направлений NONE-контрастов (DESIGN_after_lenses1.md): знак среднего пилота 3 в форме теста; |среднее| < 1 SE — в разведку.
    SE — по средним задач (единица — задача, n = 20)."""
    import power_score01 as PS
    out, keep = [], {}
    for model in ('opus', 'haiku'):
        ps, per_task = PS.variants(model)
        for j, p in enumerate(ps):
            if p['id'] not in ('O7', 'O8', 'H7', 'H8'):
                continue
            tv = [float(np.nanmean(v[:, j])) for v in per_task]
            m = sum(tv) / len(tv)
            se = math.sqrt(sum((x - m) ** 2 for x in tv) / (len(tv) - 1)) / math.sqrt(len(tv))
            keep[p['id']] = dict(mean=m, se=se, sign=1 if m > 0 else -1, keep=abs(m) >= se)
            d = 0 if p['measure'] == 'out' else 3
            out.append(f"{p['id']} ({model}, {p['measure']}): среднее {f(m, d)}, SE {f(se, d)} → " +
                       (f"направление {'> 0' if m > 0 else '< 0'}" if abs(m) >= se else 'в разведку'))
    return out, keep


DIR_LINES, DIR_KEEP = direction_check()

PILOTS = f"""- **Микропилот 0** (`PILOT0.md`; формат «фактически лучший из 8», 20 задач × 2 руки × 2 модели). Навыка нет: точность 1–2 из 20 при случайных 2,5. Самообман почти равен уверенности. Решение: формат с ненулевым навыком.
- **Микропилоты 1 и 2** (`PILOT1.md`, `PILOT2.md`; формат «в лучшей половине», те же 20 задач; пилот 2 — рука NONE и повторы LOG и WIN).
  - **Шли со снимком git в контексте голов** (ERRORS № 118, LENSES-1 L1-1): среди пяти последних коммитов, видимых головам, во время пилота 1 был a768438 («…WIN поднимает уверенность на 0,03–0,04…»), во время пилота 2 — 63e9e44 («…WIN лучше LOG по самообману и Брайеру у обеих моделей…»). Это другое условие, чем в тесте, и канал ожиданий. Их числа — запись истории устройства; основа §4–§6 — пилот 3.
  - Пилот 1 (метки по R = 1000):

{T1}

  - Пилот 2 (метки по R = 4000):

{T2}

  - Что они дали устройству: формат «в лучшей половине» (у Opus AUC около 0,6); направление WIN − LOG пилота 1 повтор не воспроизвёл; разности A/A того же порядка, что разности рук; рука NONE и два вызова на клетку у Haiku.
- **Правило выбора устройства** записано до конца микропилота 2 (коммит 6dc721f), когда я уже видел частичный срез Opus по 8 задачам: пересказы правил LOG2 и WIN2 входят, если у какой-либо модели |самообман WIN − LOG| по объединённым парам двух повторов больше двух стандартных ошибок, а разности A/A — меньше двух. Первый черновик считал статистику по среднему двух повторов, а не по объединённым парам (LENSES-1 L3-3); вот обе: {rule_check_12()}. Первое условие не выполнено ни у одной модели ни в одной форме; пересказов в опыте нет.
- **Проверка чистоты контекста** (`ctx_check.py`, `run/ctxcheck.log`; при 66 неотслеживаемых файлах в репозитории) — вход первого запроса одного промпта (WH_7001, LOG) в чистой конфигурации, в старой и в пилоте 1:

```
{CTX.strip()}
```

  В чистой конфигурации вход одного промпта совпадает с точностью до 12 токенов; в старой тот же вызов несёт снимок git.
- **Микропилот 3** (`PILOT3.md`; чистый контекст; те же 20 задач; руки LOG, WIN, NONE, по два вызова на клетку, один прогон на модель, вызовы задачи вперемешку; метки по R = 4000) — **основа направлений, допусков и мощности**:

{T3}

- **Правило направлений NONE-контрастов** (записано до результатов пилота 3, `DESIGN_after_lenses1.md`, коммит 9962627): знак среднего пилота 3 в форме теста; при |среднее| меньше одной стандартной ошибки пилота — часть уходит в разведку. Итог: {'; '.join(DIR_LINES)}.
- **Метки по 4000 реализациям** (`truth_check.py`):
  - пилот — пересчёт первых 1000 совпал с `sim.truth` в {CHK['pilot']['same_truth']} из {CHK['pilot']['n']}, четвёрка по 4000 совпала с четвёркой по 1000 в {CHK['pilot']['top4_same']} из {CHK['pilot']['n']};
  - основная — {CHK['main']['same_truth']} из {CHK['main']['n']} и {CHK['main']['top4_same']} из {CHK['main']['n']};
  - повтор — {CHK['rep']['same_truth']} из {CHK['rep']['n']} и {CHK['rep']['top4_same']} из {CHK['rep']['n']};
  - разрыв 4-го и 5-го кандидатов меньше двух стандартных ошибок парной разности при R = 1000 — в {CHK['pilot']['z45_lt2']}, {CHK['main']['z45_lt2']} и {CHK['rep']['z45_lt2']} задачах; меньше одной — в {CHK['pilot']['z45_lt1']}, {CHK['main']['z45_lt1']} и {CHK['rep']['z45_lt1']};
  - метки теста — по 4000; проверяльщик пересчитал все 223 четвёрки своим кодом — совпали (LENSES-1, L2-6).
- **Изменения после DESIGN** (до регистрации): формат «лучший из 8» → «в лучшей половине»; рука NONE; два вызова на клетку у Haiku; предсказание «лог-потеря LOG < WIN» снято, эквивалентность по Брайеру добавлена; ECE не предсказывается; негодный ответ не повторяется (правило `run_sealed2`, а не «один повтор» DESIGN); направление WIN − LOG заменено эквивалентностью (после пилота 2); допуски ±0,1 и ±0,05 выбраны после пилота 2; метки по 4000 реализациям; чистый контекст голов и пилот 3 как основа (после LENSES-1).
- **Изменения после микропилота 3** (записаны до основного прогона): направления SD у обеих моделей — по пилоту 3 (у Haiku знак сменился против загрязнённого пилота 2); H7 ушёл в разведку (|среднее| < 1 SE); новые предсказания из пилотов — длина рассуждения WIN − LOG (O9, H9; сводные SE_opus, SE_haiku) и точность WIN − LOG у Haiku (HE3, разведка); направления разведки — по знаку пилота 3; ожидания §5 — по мощности пилота 3.
- **Правки по LENSES-1:**
  - L1-1 — чистый контекст (§2), проверка вызовами (выше), пилот 3;
  - L2-1 — знаменатель потерь — задачи выборки;
  - L2-2 — сухой прогон всех четырёх этапов с потерями и выпавшими задачами, сверка хешей и покрытия в копии опыта (`dry/dry_run.sh`, `dry/dry_analysis.log`, `dry/dry_check.log`);
  - L2-3 — блок paired из evals в анализ не идёт (у Haiku он только по повтору 0);
  - L2-4 — список хешей полон (задачи и пулы — сводно); строка документации исправлена;
  - L2-5 — точные команды — §7;
  - L3-1 — мощность с неопределённостью пилота, вес по ней (§6); пилот 3 — порождающая выборка для направлений SC, SD и разведки, это сказано в §6;
  - L3-2 — SA сформулирован для двух конкретных строк; оговорки о допуске и об одном измерении — §8;
  - L3-3 — этот раздел;
  - L3-4 — запас кромок — в §6 (столбец мощности с неопределённостью пилота);
  - L3-5 — «установлено» для SA и SB записано как изъятие из правила CLAUDE.md с причиной (§4); оговорки о SB и о Haiku — §8;
  - L3-6 — описательные фразы пилотов не говорят «ниже» или «выше», где интервал накрывает 0;
  - L3-7 — встроенный A/A у Haiku (§2).
- **Вызовов в пилотах** (итоговые записи журналов): пилот 0 — {CALLS['pilot0']}, пилот 1 — {CALLS['pilot1']}, пилот 2 — {CALLS['pilot2']}, проверка контекста — {CALLS['ctxcheck']}, пилот 3 — {CALLS['pilot3']}.
- **Хеши текстов** (`python3 prompts_score.py hash`): ROLE_H {H['ROLE_H'][:8]}…, ROLE_H_NONE {H['ROLE_H_NONE'][:8]}…, LOG_H {H['LOG_H'][:8]}…, WIN_H {H['WIN_H'][:8]}…, schema_H {H['schema_H'][:8]}…."""


def pred_lines():
    out = []
    for model in ('opus', 'haiku'):
        ps = [p for p in A.PRED if p['model'] == model]
        if not ps:
            continue
        out.append(f'### {"Opus 5.5" if model == "opus" else "Haiku 5.5"}')
        for c in sorted({p['comp'] for p in ps if p['comp']}):
            parts = [p for p in ps if p['comp'] == c]
            out.append(f'- **{c}** — «{A.COMP_TEXT[c]}»; части: ' + '; '.join(f"**{p['id']}** {p['text']}" for p in parts) + '.')
        ex = [p for p in ps if not p['comp']]
        if ex:
            out.append('- **Разведка (вне семьи, в реестр — только как гипотеза):** ' + '; '.join(f"**{p['id']}** {p['text'].replace('разведка: ', '')}" for p in ex) + '.')
    out += ['### Исходы',
            '- **Направленное** — по 95 % t-интервалу среднего: «подтверждено» — интервал целиком на предсказанной стороне; «опровергнуто» — целиком на другой; иначе «не показано».',
            '- **Эквивалентность** — по 90 % t-интервалу (TOST, уровень 0,05 с каждой стороны): «подтверждено» — интервал внутри ±δ; «опровергнуто» — целиком вне ±δ; иначе «не показано».',
            f'- **Потери:** если годных задач у цели меньше {int(A.MIN_VALID_SHARE * 100)} % задач выборки — «не показано (потери)».',
            '- **Сводный исход** (в каждой выборке отдельно): «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута; иначе «не подтверждено».',
            '- **Статус** (ключ status анализа):',
            '  - SA и SB, подтверждённые и в основной выборке, и в повторе, — «установлено». Это **изъятие** из правила CLAUDE.md («установлено» — после повтора с контролем на неспецифичность), с причиной: SA — утверждение об отсутствии разницы больше допуска между двумя руками, которые обе добавляют одну строку правила (неспецифичный эффект «есть строка» у них общий); SB — о наличии самообмана, без причинного утверждения. Неспецифичного пути через снимок git нет, пока контекст голов чист (§2).',
            '  - SC, SD и SE — не выше «подтверждено (повторено; причина не проверялась)»: контроля на неспецифичность (нейтральной строки или пересказа правила) для них нет (§8).',
            '  - Иначе — исход основной выборки и повтора как есть.',
            '- **Чтение по шуму:** вердикты по букве не меняются; если интервал эквивалентности вышел за ±δ при среднем внутри — пишется «не показано: интервал шире допуска», а не «разница есть».']
    return '\n'.join(out)


def expect_lines():
    rows = ['| | Модель | Предсказание | Вероятность |', '|---|---|---|---|']
    for p in A.PRED:
        rows.append(f"| {p['id']} | {p['model']} | {p['text']} | {f(p['expect'], 2)} |")
    rows += ['', '- Все ожидания — после пилота (класс калибровки «после пилота»); одинаковы для основной выборки и повтора. Ставил их по мощности с неопределённостью пилота (§6), с поправкой вниз там, где направление выбрано по тому же пилоту.']
    return '\n'.join(rows)


def power_lines():
    out = [f'- **Метод** (`power_score01.py`): цель оценивается по пилоту 3 в том виде, в каком её даст тест. Opus (один вызов на клетку) — значение задачи по одному повтору (два варианта на задачу); Haiku (два вызова) — по среднему двух повторов. «В точке» — нормальное приближение с t-квантилем при n = 100 и истинном эффекте, равном пилотному среднему (верхняя оценка); «с неопределённостью пилота» — двухуровневый бутстреп ({POW["B"]} повторений): пилотные задачи пересэмплируются, затем тест из 100 задач по букве анализа. Ложный уровень — на границе: 0,025 у направленного, 0,05 у эквивалентности. Вес — log₂(мощность с неопределённостью / ложный уровень), пол ложного уровня 0,001.',
           '- **Пилот 3 — порождающая выборка** для направлений SC и SD и для разведки (ворота 4, ревизия 3.2 (а)): по нему выбраны знаки. Поэтому даже мощность с неопределённостью пилота не учитывает «проклятие победителя»; ожидания §5 ниже мощности.',
           '', PW, '']
    conf_ids = [p['id'] for p in A.PRED if p['comp']]
    s_alpha = sum(POW['preds'][i]['alpha'] for i in conf_ids)
    s_comp = sum(v['alpha'] for v in POW['comps'].values())
    out.append(f'- **Ложный уровень серии** (Бонферрони, одна выборка): по {len(conf_ids)} частям семьи — {f(s_alpha, 3)}; по {len(POW["comps"])} сводным — {f(s_comp, 3)}. Повтор — та же сумма на второй выборке; «установлено» требует обеих.')
    out.append('- Ложный уровень сводного — наибольший у частей; мощность сводного с неопределённостью пилота — совместная (все части в одном бутстрепе). Основная выборка и повтор — одна группа опор: один код, одни промпты и модели.')
    out.append(f"- Для записи: по загрязнённым пилотам 1–2 (`pilot12_power.json`, `pilot12_power_single.json`) мощность SA_haiku в точке была {f(math.prod(POW12[i]['power'] for i in ('H1', 'H2', 'H3')), 2)} при двух вызовах и {f(math.prod(POW12S[i]['power'] for i in ('H1', 'H2', 'H3')), 2)} при одном — отсюда два вызова на клетку у Haiku.")
    return '\n'.join(out)


def resources():
    J = {k: sum(1 for _ in open(os.path.join(HERE, 'run', f'{k}_jobs.jsonl'))) for k in ('main_opus', 'rep_opus', 'main_haiku', 'rep_haiku')}
    cmd = lambda st, m, seed, par: (f"python3 tools/run_sealed2.py run --jobs experiments/2026-10-28_SCORE-01/run/{st}_jobs.jsonl --seed {seed} "
                                    f"--journal experiments/2026-10-28_SCORE-01/run/{st} --streams .cache/score01_streams/{st} "
                                    f"--config experiments/2026-10-28_SCORE-01/run/cfg_{m}_clean.json --parallel {par}")
    return '\n'.join([
        f"- **Задания** (`run/<этап>_jobs.jsonl`, хеши — `prereg_hashes.json`): Opus — {J['main_opus']} (основная) и {J['rep_opus']} (повтор), один вызов на клетку; Haiku — {J['main_haiku']} и {J['rep_haiku']}, два вызова на клетку. Всего {sum(J.values())}.",
        f"- **Цена** вызова в пилоте 1 (поле cost_usd CLI, в пересчёте на API): Opus около 0,11 $, Haiku около 0,01 $ (`evals/pilot1_*.json`). Итого около {0.11 * (J['main_opus'] + J['rep_opus']):.0f} $ (Opus) и {0.01 * (J['main_haiku'] + J['rep_haiku']):.0f} $ (Haiku).",
        "- **Время:** в пилотах у Opus около 0,8 мин на вызов на поток, у Haiku — около 1,7 мин. Четыре прогона идут одновременно; лимиты аккаунта `run_sealed2` ждёт сам. После перезапуска контейнера прогон продолжается с места той же командой.",
        "- **Команды** (из корня репозитория; зёрна задают только порядок вызовов внутри задачи). Фоновая задача живёт до 2 ч, поэтому каждый прогон идёт с `--stop-after 6600` (мягкая пауза: начатые вызовы дописываются) и продолжается той же командой; набор и порядок вызовов от этого не меняются:",
        f"  - `{cmd('main_opus', 'opus', 101, 2)}`",
        f"  - `{cmd('rep_opus', 'opus', 102, 2)}`",
        f"  - `{cmd('main_haiku', 'haiku', 103, 4)}`",
        f"  - `{cmd('rep_haiku', 'haiku', 104, 4)}`",
        "  - выгрузка: `python3 tools/run_sealed2.py export --journal experiments/2026-10-28_SCORE-01/run/<этап> --out experiments/2026-10-28_SCORE-01/run/<этап>_out.jsonl`;",
        "  - меры (из папки опыта): `python3 score01.py metrics <этап> <main|rep> run/<этап>_out.jsonl half4`;",
        "  - анализ: `python3 analyze_score01.py` (все четыре этапа; хеши и покрытие сверяются);",
        "  - чистота контекста: `python3 experiments/2026-10-28_SCORE-01/ctx_check.py .cache/score01_streams/<этап> …` (из корня репозитория).",
        "- **Порядок:** все четыре прогона — после регистрации; анализ — когда закончены все четыре."])


tpl = open(os.path.join(HERE, 'prereg_template.md'), encoding='utf-8').read()
out = (tpl.replace('{{STATUS}}', STATUS).replace('{{PILOTS}}', PILOTS).replace('{{PREDICTIONS}}', pred_lines())
       .replace('{{EXPECT}}', expect_lines()).replace('{{POWER}}', power_lines()).replace('{{RESOURCES}}', resources())
       .replace('{{AA_CORR}}', AA_TXT))
assert '{{' not in out, 'не все метки заменены'
open(os.path.join(HERE, OUT), 'w', encoding='utf-8').write(out)
print('собрано:', OUT, len(out), 'знаков; направления:', {k: (v['sign'], v['keep']) for k, v in DIR_KEEP.items()})
