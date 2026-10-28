#!/usr/bin/env python3
"""SCORE-01: сборка DRAFT-PREREG-SCORE-01.md из prereg_template.md, текста §3 ниже, предсказаний analyze_score01.PRED
и таблиц, которые печатают скрипты пилотов (числа — командой). Весь текст живёт в шаблоне и здесь: черновик руками не правится
(урок TRUST-04, третья проверка, находка 1).
  python3 assemble_prereg_score01.py [--status "регистрация …"]"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_score01 as A  # noqa: E402

STATUS = sys.argv[sys.argv.index('--status') + 1] if '--status' in sys.argv else 'черновик; не регистрация'
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
run = lambda *c: subprocess.run([sys.executable, *c], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()

T1 = run('pilot_tables.py', 'pilot1_opus', 'pilot1_haiku')
T2 = run('pilot2_tables.py', 'opus', 'haiku')
PW = run('power_score01.py', '--md')
POW = json.load(open(os.path.join(HERE, 'pilot_power.json')))
H = json.loads(run('prompts_score.py', 'hash'))
CHK = {s: json.load(open(os.path.join(HERE, 'truth', f'check_{s}.json')))['summary'] for s in ('pilot', 'main', 'rep')}


def corr_aa():
    out = []
    for line in T2.splitlines():
        c = line.split('|')
        if len(c) > 4 and 'повтор 0 и' in c[2] and c[2].split(',')[0].strip() == c[2].split(' и ')[1].split(',')[0].strip():
            out.append((c[1].strip(), c[2].strip(), c[3].strip()))
    return out


AA = corr_aa()
AA_TXT = '; '.join(f'{m}: {pair.split(",")[0]} — {r}' for m, pair, r in AA)

PILOTS = f"""- **Микропилот 0** (`PILOT0.md`; формат «фактически лучший из 8», 20 задач × 2 руки × 2 модели). Навыка нет: точность 1–2 из 20 при случайных 2,5. Самообман почти равен уверенности. Решение: формат с ненулевым навыком.
- **Микропилот 1** (`PILOT1.md`; формат «в лучшей половине», те же 20 задач, руки LOG и WIN, повтор 0). Метки — по `sim.truth` (R = 1000):

{T1}

- **Микропилот 2** (`PILOT2.md`; те же 20 задач): рука NONE (повтор 0) и повторы LOG и WIN тем же промптом (повтор 1), один прогон, руки вперемешку по задачам. Таблицы — по меткам R = 4000 (метки 24 пилотных задач по R = 1000 и R = 4000 расходятся в одной: WH_7011):

{T2}

- **Что показали пилоты.**
  - Opus различает половины слабо, но выше случайного: AUC около 0,6 в руках с правилом. У Haiku навык неустойчив: ответы одного промпта в двух вызовах коррелируют по p слабо.
  - Направление WIN − LOG пилота 1 (у обеих моделей WIN лучше) повтор не воспроизвёл. Разности повторов одного промпта (A/A) того же порядка, что разности рук. Значит, различие рук пилота 1 укладывается в шум одного вызова.
  - Самообман есть во всех клетках.
  - NONE у Opus — короче рассуждение и ниже точность, чем в руках с правилом того же прогона.
- **Правило выбора устройства** записано до конца микропилота 2 (коммит 6dc721f): пересказы правил LOG2 и WIN2 входят, если у какой-либо модели |самообман WIN − LOG| по среднему двух повторов больше двух стандартных ошибок, а разности A/A — меньше двух. Условие не выполнено ни у одной модели (строка «среднее двух повторов» и строки A/A таблицы выше). Пересказы не входят. NONE входит, как и было записано.
- **Метки по 4000 реализациям** (`truth_check.py`, после микропилота 2; решение — до основного прогона):
  - пилот — пересчёт первых 1000 совпал с `sim.truth` в {CHK['pilot']['same_truth']} из {CHK['pilot']['n']}, четвёрка по 4000 совпала с четвёркой по 1000 в {CHK['pilot']['top4_same']} из {CHK['pilot']['n']};
  - основная — {CHK['main']['same_truth']} из {CHK['main']['n']} и {CHK['main']['top4_same']} из {CHK['main']['n']};
  - повтор — {CHK['rep']['same_truth']} из {CHK['rep']['n']} и {CHK['rep']['top4_same']} из {CHK['rep']['n']};
  - разрыв 4-го и 5-го кандидатов меньше двух стандартных ошибок парной разности при R = 1000 — в {CHK['pilot']['z45_lt2']}, {CHK['main']['z45_lt2']} и {CHK['rep']['z45_lt2']} задачах соответственно; меньше одной — в {CHK['pilot']['z45_lt1']}, {CHK['main']['z45_lt1']} и {CHK['rep']['z45_lt1']}.
  - Метки теста — по 4000 (точнее при той же правде; где четвёрки совпадают, метки те же).
- **Изменения после пилотов** (всё — до регистрации):
  - формат «лучший из 8» → «в лучшей половине» (после микропилота 0);
  - рука NONE и повторы (после микропилота 1);
  - предсказание о разнице LOG и WIN — эквивалентность вместо направления: направление пилота 1 не повторилось (после микропилота 2);
  - метки по 4000 реализациям (после проверки меток);
  - предсказания о NONE — по микропилоту 2 (§4).
- **Хеши текстов** (`python3 prompts_score.py hash`): ROLE_H {H['ROLE_H'][:8]}…, ROLE_H_NONE {H['ROLE_H_NONE'][:8]}…, LOG_H {H['LOG_H'][:8]}…, WIN_H {H['WIN_H'][:8]}…, schema_H {H['schema_H'][:8]}….
- **Сухой прогон** (`dry/`): заглушка выгрузки с заданным навыком рук и 3–5 % потерь → `score01.py metrics … half4` → `analyze_score01.py --evals dry/evals` → вердикты и сводные; анализ видит заложенный эффект и пропускает задачи с потерями. Вызов голов `run_sealed2` проверен самими пилотами (180 + 120 вызовов)."""


def pred_lines():
    out = []
    for model in ('opus', 'haiku'):
        ps = [p for p in A.PRED if p['model'] == model]
        if not ps:
            continue
        out.append(f'### {"Opus 5.5" if model == "opus" else "Haiku 5.5"}')
        comps = sorted({p['comp'] for p in ps if p['comp']})
        for c in comps:
            key = c.split('_')[0]
            parts = [p for p in ps if p['comp'] == c]
            out.append(f'- **{c}** — «{A.COMP_TEXT[key]}»; части: ' + '; '.join(f"**{p['id']}** {p['text']}" for p in parts) + '.')
        ex = [p for p in ps if not p['comp']]
        if ex:
            out.append('- **Разведка (вне семьи, в реестр — только как гипотеза):** ' + '; '.join(f"**{p['id']}** {p['text']}" for p in ex) + '.')
    out.append('### Исходы')
    out.append('- **Направленное** — по 95 % t-интервалу среднего: «подтверждено» — интервал целиком на предсказанной стороне; «опровергнуто» — целиком на другой; иначе «не показано».')
    out.append('- **Эквивалентность** — по 90 % t-интервалу (TOST, уровень 0,05 с каждой стороны): «подтверждено» — интервал внутри ±δ; «опровергнуто» — целиком вне ±δ; иначе «не показано».')
    out.append(f'- **Потери:** если годных задач у цели меньше {int(A.MIN_VALID_SHARE * 100)} % выборки — «не показано (потери)».')
    out.append('- **Сводный исход** (в каждой выборке отдельно): «подтверждено» — все части подтверждены; «опровергнуто» — хоть одна опровергнута; иначе «не подтверждено».')
    out.append('- **Статус** (ключ status анализа):')
    out.append('  - SA и SB, подтверждённые и в основной выборке, и в повторе, — «установлено». SA — утверждение об отсутствии разницы больше допуска, SB — о наличии самообмана; неспецифичной причины в них нет.')
    out.append('  - SC и SD — не выше «подтверждено (повторено; причина не проверялась)»: контроля на неспецифичность для них нет (§8).')
    out.append('  - Иначе — исход основной выборки и повтора как есть.')
    out.append('- **Чтение по шуму:** вердикты по букве не меняются; если интервал эквивалентности вышел за ±δ при среднем внутри — пишется «не показано: интервал шире допуска», а не «разница есть».')
    return '\n'.join(out)


def expect_lines():
    rows = ['| | Модель | Предсказание | Вероятность |', '|---|---|---|---|']
    for p in A.PRED:
        rows.append(f"| {p['id']} | {p['model']} | {p['text']} | {f(p['expect'], 2)} |")
    rows.append('')
    rows.append('- Все ожидания — после пилота (класс калибровки «после пилота»); одинаковы для основной выборки и повтора.')
    return '\n'.join(rows)


def power_lines():
    out = ['- **Метод** (`power_score01.py`): разность одного вызова на задачу оценивается по парам пилота — повторы 0 (пилот 1) и 1 (пилот 2) для LOG и WIN; NONE — с повтором 1 других рук (тот же прогон). Мощность — нормальное приближение с t-квантилем при n = 100 задач (у повтора n = 99 — почти та же); при SD × 1,5 — запас на недооценку разброса по 20 пилотным задачам. Ложный уровень — на границе: 0,025 у направленного, 0,05 у эквивалентности. Вес — log₂(мощность / ложный уровень), пол ложного уровня 0,001.', '', PW, '']
    comps = {}
    for p in A.PRED:
        if p['comp']:
            comps.setdefault(p['comp'], []).append(p['id'])
    out.append('| Сводный | Части | Ложный уровень | Мощность | При SD × 1,5 | Вес |')
    out.append('|---|---|---|---|---|---|')
    for c, ids in comps.items():
        a_ = max(POW[i]['alpha'] for i in ids)
        pw = math.prod(POW[i]['power'] for i in ids)
        pw15 = math.prod(POW[i]['power_sd15'] for i in ids)
        out.append(f"| {c} | {', '.join(ids)} | {f(a_, 3)} | {f(pw, 3)} | {f(pw15, 3)} | {f(math.log2(pw / max(a_, 0.001)), 1)} бита |")
    n_conf = sum(1 for p in A.PRED if p['comp'])
    s_alpha = sum(POW[p['id']]['alpha'] for p in A.PRED if p['comp'])
    s_comp = sum(max(POW[i]['alpha'] for i in ids) for ids in comps.values())
    out.append('')
    out.append(f'- **Ложный уровень серии** (Бонферрони, одна выборка): по {n_conf} частям семьи — {f(s_alpha, 3)}; по {len(comps)} сводным — {f(s_comp, 3)}. Повтор — та же сумма на второй выборке; «установлено» требует обеих.')
    out.append('- Ложный уровень сводного — наибольший у частей, мощность — произведение (как в TRUST-04). Основная выборка и повтор — одна группа опор: один код, одни промпты и модели.')
    return '\n'.join(out)


def resources():
    n_main, n_rep = 100, 99
    arms = 3
    return (f"- Вызовов: основная выборка {n_main} × {arms} руки × 2 модели = {n_main * arms * 2}; повтор {n_rep} × {arms} × 2 = {n_rep * arms * 2}.\n"
            f"- Цена вызова в пилоте 1 (поле cost_usd CLI, в пересчёте на API): Opus около 0,11 $, Haiku около 0,01 $ (`evals/pilot1_*.json`). Итого около {0.11 * (n_main + n_rep) * arms:.0f} $ (Opus) и {0.01 * (n_main + n_rep) * arms:.0f} $ (Haiku).\n"
            "- Время: у Opus в пилотах около 0,8 мин на вызов на поток, у Haiku — 1,5–3 мин; по два потока на прогон, лимиты аккаунта `run_sealed2` ждёт сам. Прогон продолжается с места после перезапуска (`run_sealed2 run` той же командой).\n"
            "- Порядок: основная выборка и повтор обеих моделей запускаются после регистрации; анализ — когда закончены все четыре прогона.")


tpl = open(os.path.join(HERE, 'prereg_template.md'), encoding='utf-8').read()
out = (tpl.replace('{{STATUS}}', STATUS).replace('{{PILOTS}}', PILOTS).replace('{{PREDICTIONS}}', pred_lines())
       .replace('{{EXPECT}}', expect_lines()).replace('{{POWER}}', power_lines()).replace('{{RESOURCES}}', resources())
       .replace('{{AA_CORR}}', AA_TXT))
assert '{{' not in out, 'не все метки заменены'
open(os.path.join(HERE, 'DRAFT-PREREG-SCORE-01.md'), 'w', encoding='utf-8').write(out)
print('собрано: DRAFT-PREREG-SCORE-01.md,', len(out), 'знаков')
