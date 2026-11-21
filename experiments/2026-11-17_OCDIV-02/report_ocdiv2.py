#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка REPORT-OCDIV-02.md: текст — мой, числа — из json счёта на GitHub Actions тем же форматированием, каким их сверяет
ledger.py audit. Производные числа (число задач среды, разрыв ID − OOD у голов, знаки Т4 по средам, вес опоры по PREREG §10, ложный
уровень серии по PREREG §7) считаются здесь и пишутся в report_derived.json рядом — его читает ledger.py audit. Вердиктов скрипт не меняет.
  python3 report_ocdiv2.py [ANALYSIS.json PILOT2V2.json OUT.md]
По умолчанию: gha_out/ocdiv2_sum_test/analysis.json, gha_out/ocdiv2_sum_pilot2v2/pilot.json (мощность Т4 для веса опоры — PREREG §6, §10).
Каркас написан до вывода анализа (17.11.2026) и проверен на заглушечном analysis.json; разделы «Коротко», «Для главного вопроса»
и «Что дальше» — после данных (report_notes.json, notes_ocdiv2.py)."""
import json
import os
import re
import sys
from math import log2

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
a = sys.argv[1:]
P_ = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)   # noqa: E731
J = lambda p: json.load(open(P_(p), encoding='utf-8'))             # noqa: E731
an_path = a[0] if a else 'gha_out/ocdiv2_sum_test/analysis.json'
an = J(an_path)
pil = J(a[1] if len(a) > 1 else 'gha_out/ocdiv2_sum_pilot2v2/pilot.json')
ex = J(os.path.join(X, 'expect_ocdiv2.json'))
OUT = a[2] if len(a) > 2 else os.path.join(X, 'REPORT-OCDIV-02.md')
DER_PATH = os.path.join(os.path.dirname(os.path.abspath(OUT)), 'report_derived.json')
TLOG = os.path.join(os.path.dirname(P_(an_path)), 'tests.log')
REGHASH, RUNHASH, ANHASH = '55e7a62b', 'c78b50d2', 'c1b8bb20'
LEVEL, DESCR_LEVEL = 0.0025, 0.005
NOTES = {}
if os.path.exists(os.path.join(X, 'report_notes.json')):
    NOTES = json.load(open(os.path.join(X, 'report_notes.json'), encoding='utf-8'))
CNC = os.path.join(ROOT, 'docs/council/2026-11-17_OCDIV-02-report_session69.json')
CN = json.load(open(CNC, encoding='utf-8')) if os.path.exists(CNC) else None


def n(x, d=4, sign=True):
    if x is None or x != x:
        return '—'
    s = f'{abs(x):.{d}f}'.replace('.', ',')
    if x < 0 and float(s.replace(',', '.')) != 0:
        return '−' + s
    return ('+' if sign and x > 0 and float(s.replace(',', '.')) != 0 else '') + s


def iv(ci, d=4):
    return f'[{n(ci[0], d)}; {n(ci[1], d)}]' if ci else '—'


def g(d, *keys):
    for k in keys:
        d = (d or {}).get(k)
    return d


meth = an.get('method', {})
valid = meth.get('valid', [])
envs = an['envs']
V = an.get('verdicts', {})

# ───────────── производные числа (report_derived.json)
pw = pil['families']['length']['power']['T4']
v4 = V.get('T4', '')
if v4 == 'подтверждено':
    w4 = dict(bits=log2(pw['power_confirm'] / LEVEL), power=pw['power_confirm'], note='log₂(мощность «подтверждено» / 0,0025); верхняя оценка, не для реестра')
elif v4 == 'опровергнуто':
    w4 = dict(bits=(-log2(pw['power_refute'] / LEVEL) if pw['power_refute'] > LEVEL else None), power=pw['power_refute'],
              note='−log₂(мощность «опровергнуто» / 0,0025); верхняя оценка, не для реестра')
else:
    w4 = dict(bits=0.0, power=None, note='вердикта нет — вес 0')
w4['verdict'] = v4
heads = {}
for nm, h in (an.get('acc_by_head_mean') or {}).items():
    heads[nm] = dict(id=h['id'], ood=h['ood'], drop=h['id'] - h['ood'], ct_ood=g(an, 'ct_ood_by_head_mean', nm),
                     n_envs=int(sum(nm in envs[e]['acc'] for e in valid)),
                     method_ok_envs=int(sum(bool(g(envs[e], 'method', nm, 'ok')) for e in envs)))
t4env = {e: g(an, 'T4', 'by_env', e) for e in valid}
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import raw_status as RS  # noqa: E402   время заданий — только поля белого списка (замок № 180)
secs = {}
for f in sorted(__import__('glob').glob(os.path.join(ROOT, 'gha_out/ocdiv2_test_*/answers_*.json'))):
    d = RS.filtered(json.load(open(f, encoding='utf-8')))
    for env_, s_ in (d.get('seconds_env') or {}).items():
        nt_ = envs[env_]['n_id'] + envs[env_]['n_ood'] if env_ in envs else 2200
        secs[os.path.basename(os.path.dirname(f))] = dict(seconds=s_, sec_per_task=s_ / nt_)
time_ = dict(n_jobs=len(secs), max_min=(max(v['seconds'] for v in secs.values()) / 60 if secs else None),
             min_min=(min(v['seconds'] for v in secs.values()) / 60 if secs else None),
             max_sec_per_task=(max(v['sec_per_task'] for v in secs.values()) if secs else None),
             slowest=(max(secs, key=lambda k: secs[k]['seconds']) if secs else None), limit_sec_per_task=4.6, step_limit_min=340)
DER = dict(source=f'PREREG-OCDIV-02 §5–§10 (регистрация {REGHASH}); числа — из {os.path.relpath(P_(an_path), ROOT)}',
           n_tasks={e: envs[e]['n_id'] + envs[e]['n_ood'] for e in envs},
           heads=heads, drop_mean=(sum(h['drop'] for h in heads.values()) / len(heads) if heads else None),
           t4_sign=dict(pos=int(sum(v > 0 for v in t4env.values() if v is not None)), neg=int(sum(v < 0 for v in t4env.values() if v is not None)),
                        zero=int(sum(v == 0 for v in t4env.values() if v is not None)), n=len(t4env)),
           weight_T4=w4, series_false=dict(confirm=LEVEL, any=2 * LEVEL), job_time=time_,
           n_crowd=len(an.get('crowd_effective', [])), n_crowd_reg=len(an.get('crowd', {})),
           council69=(dict(seconds=CN['timer']['end'] - CN['timer']['start'], over_s=CN['timer'].get('over_s')) if CN else None))
json.dump(DER, open(DER_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ───────────── отчёт
L = []
add = L.append
ROLE = {'T4': 'правило с вердиктом', 'T1': 'проверка построения', 'T3': 'проверка построения', 'T2': 'описательно'}
TEXT = {'T4': 'F − F₀ вне диапазона: ложное большинство сверх перестановочного нуля',
        'T1': 'C − T вне диапазона у POST-CV (полоса ±0,02)',
        'T3': 'r = Σ(C − T вне диапазона) / Σ(T на ID − T вне диапазона), семь голов',
        'T2': 'ИОИ(AGREE) − ИОИ(POST-CV) вне диапазона'}

add('# OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ» — отчёт (17.11.2026)')
add('')
add('Главный вопрос Neu — оценщик, который не обманывается под давлением отбора. В OCDIV-01 сдвиг был лёгким: вне диапазона калибровки '
    'семь открытых голов пяти производителей ошибались не чаще, чем на нём. Здесь сдвиг трудный: длина слагаемого растёт от 3 до 7 цифр, '
    'а подсказка — только из примеров диапазона калибровки (ID). Проверяется, складываются ли ошибки разных голов вне диапазона в ложное '
    'большинство чаще, чем при независимых ошибках с теми же частотами (Т4). Ещё проверяется, сколько разрыва точности ID − OOD остаётся '
    'не замеченным в заявке головы (Т3, r).')
add(f'- **Предрегистрация — коммит {REGHASH}** (`PREREG-OCDIV-02.md`; совет 68 — три линзы, принято 3 из 4). Запуск теста — коммит {RUNHASH}, '
    f'анализа — {ANHASH}.')
nt = sorted(set(DER['n_tasks'].values()))
add('- **Данные** — GitHub Actions, процессор раннера: 35 заданий (7 голов × 5 сред «длины», X = 9, 99, 999, 9999, 99999; подсказка только '
    f"из ID, p = 3), задач в среде — {', '.join(str(x) for x in nt)}. Ещё одно задание повторено под другим именем на другом раннере.")
add(f"- **Счёт** — GitHub Actions: `gha_out/ocdiv2_sum_test/analysis.json`, B = {an['B']}, M4 — точка ± z·ст. откл. повторов, "
    f"z = {n(an['z'], 3, False)}. Производные числа — `report_derived.json` (этот же скрипт).")
add('')
add('## Итог')
add('')
add('| Статистика | Роль (PREREG §5) | Что | Точка | M4 при 0,0025 | Δ/s | z\\* | Исход | Вес опоры |')
add('|---|---|---|---|---|---|---|---|---|')
for k in ('T4', 'T1', 'T3', 'T2'):
    e = an.get(k)
    if not e:
        add(f"| {k} | {ROLE[k]} | {TEXT[k]} | — | — | — | — | {V.get(k, '—')} | — |")
        continue
    if k == 'T4':
        out_ = e['verdict'] + (' — чувствителен к уровню' if e.get('sensitive_to_level') else '')
        ws = 'не определён' if w4['bits'] is None else ('0 бит' if w4['bits'] == 0 else n(w4['bits'], 2) + ' бит')
    elif k in ('T1', 'T3'):
        out_ = f"{e.get('check_result', e['verdict'])} (вердикта нет)"
        ws = '0 бит'
    else:
        out_ = f"описательно; по правилу было бы «{e.get('verdict_rule_descr', '—')}»"
        ws = '0 бит'
    add(f"| {k} | {ROLE[k]} | {TEXT[k]} | {n(e['delta'])} | {iv(e['ci'])} | {n(e['z_point'], 1)} | {n(e['z_star'], 1, False)} | {out_} | {ws} |")
add('')
t4 = an.get('T4') or {}
gd = t4.get('leave_one_range_out')
ZC = [e for e in valid if envs[e]['T4']['F'] == 1.0]          # совет 69, Н3: F = 1 — Т4 ноль по построению
NZC = [e for e in valid if e not in ZC]
if gd:
    mw = '; '.join(f'без X = {k} — {n(v)}' for k, v in gd.get('mean_without', {}).items())
    add(f"- **Предохранитель «без одной среды» у Т4:** знак среднего сохраняется — {'да' if gd.get('holds') else 'нет'}. Предохранитель проверяет знак, "
        f"а не величину (совет 69). Невырожденных по знаку сред — {len(NZC)}: > 0 — {sum(t4env[e] > 0 for e in NZC)}, < 0 — "
        f"{sum(t4env[e] < 0 for e in NZC)}; в {' и '.join(ZC)} F = 1, Т4 — ноль по построению. Среднее без одной среды: {mw}; интервалы для них не считались.")
add(f"- Вердикт Т4 — по среднему пяти сред; из них {an['nondeg']['k_degenerate_by_pilot']} вырождены по пилоту 2 (PREREG §3). В тесте Т4 — ноль "
    f"по построению в {len(ZC)} из них (F = 1: вне диапазона почти никто не верен); L_X999_p3 в тесте — переходная зона (ниже, «Т4 по средам»).")
add('- Вес опоры — верхняя оценка, не для реестра (PREREG §10): перенос M4 на уровень 0,0025 для среднего пяти сред не проверен. '
    'z\\* — z, при котором меняется исход; пометка «чувствителен к уровню» — при z\\* < 2,807 × 1,5.')
add(f"- Знаки: Т4 > 0 — ложное большинство чаще, чем при перестановочном нуле. Т2 < 0 значило бы, что у согласия (AGREE) ИОИ вне диапазона "
    f"меньше, чем у POST-CV; здесь — «{g(an, 'T2', 'verdict_rule_descr')}» (PREREG §5: Т2 описательно).")
add('- **Нуль** (совет 69): основной F₀ (Т4) и H₀ (гомоплазия) — один перестановочный нуль без страт (`ocdiv2.py`, стр. 156–172 и 314): '
    'ответы каждой головы переставляются между задачами среды. Точность головы он сохраняет, трудность задачи — нет. Поэтому F − F₀ > 0 смешивает '
    'общую трудность задач и совпадение самих неверных ответов; вклад общей трудности не исключён. По коду (`false_major`, стр. 147–153) F '
    'засчитывает и задачу, где верных голосов нет вовсе. '
    f"У Т4 есть описательный вариант со стратами по числу переносов ({n(g(an, 'descr_T4 (другой нуль)', 'delta'))}), у H₀ — нет.")
add(f"- Общий ложный уровень серии (PREREG §7): правило одно, ложное «подтверждено» — не больше {n(LEVEL, 4, False)}, с ложным «опровергнуто» — "
    f"не больше {n(2 * LEVEL, 3, False)}. Уровень номинальный.")
for k in ('T1', 'T3'):
    e = an.get(k) or {}
    if e.get('n_boot_dropped'):
        add(f"- {k}: исключено повторов бутстрепа с неопределённым значением хоть в одной среде — {e['n_boot_dropped']} "
            f"(доля {n(e['share_boot_dropped'], 4, False)}).")
add('')
if NOTES.get('short'):
    add('**Коротко.**')
    for s_ in NOTES['short']:
        add(s_ if s_.startswith('  - ') else f'- {s_}')
    add('')
add('**Метод опыта.**')
add(f"- Годных сред {meth.get('n_valid')} из {meth.get('n_envs')}; опыт определён — {'да' if meth.get('ok') else 'нет'}. "
    f"FIXED-нов (Qwen2.5-0.5B) в толпе всех годных сред — {'да' if meth.get('fixed_in_all_valid') else 'нет'}.")
drop = an.get('crowd_dropped') or {}
out_m = []                                                     # совет 69, Н4: кто не прошёл проверку метода и почему — из json
for e in sorted(envs, key=len):
    for h, m_ in envs[e]['method'].items():
        if not m_['ok']:
            why = []
            if m_.get('none_frac_id', 0) > 0.05:
                why.append(f"доля ответов без числа на ID {n(m_['none_frac_id'], 4, False)} > 0,05")
            if m_.get('id_wrong', 99) < 20:
                why.append(f"неверных на ID {m_['id_wrong']} < 20")
            if m_.get('id_correct', 99) < 20:
                why.append(f"верных на ID {m_['id_correct']} < 20")
            out_m.append(f"{h} в {e} — {', '.join(why) or 'см. json'}")
add(f"- Толпа: по ревизии и версиям — {DER['n_crowd']} из {DER['n_crowd_reg']}, "
    + ('выбывших нет.' if not drop else 'выбыли: ' + '; '.join(f'{k} — {v}' for k, v in drop.items()) + '.')
    + ' В толпе среды — головы, прошедшие проверку метода (PREREG §4): '
    + '; '.join(f"{len(envs[e]['crowd'])} в {e}" for e in sorted(envs, key=len) if len(envs[e]['crowd']) < DER['n_crowd'])
    + f", в остальных средах — {DER['n_crowd']}." + (' Не прошли: ' + '; '.join(out_m) + '.' if out_m else ''))
add(f"- Сборка: ключи задач и подсказки сверены с источником — {'да' if an.get('keys_checked') else 'нет'}; "
    f"ошибок загрузки голов — {len(an.get('head_errors') or [])}.")
if os.path.exists(TLOG):
    tl = open(TLOG, encoding='utf-8').read()
    ok_, bad_ = len(re.findall(r'^✓', tl, re.M)), len(re.findall(r'^✗', tl, re.M))
    add(f'- Тесты кода в задании анализа: пройдено {ok_}, провалено {bad_} (`gha_out/ocdiv2_sum_test/tests.log`).')
cpu = sorted({c for v in (an.get('cpu_models') or {}).values() for c in (v or [])})
if cpu:
    add(f"- Процессоры раннеров: {'; '.join(cpu)}.")
if time_['n_jobs']:
    add(f"- Время заданий извлечения ({time_['n_jobs']} заданий теста, без повтора): от {n(time_['min_min'], 1, False)} до "
        f"{n(time_['max_min'], 1, False)} мин; самое долгое — `{time_['slowest']}`, {n(time_['max_sec_per_task'], 3, False)} с на задачу при пороге "
        f"{n(time_['limit_sec_per_task'], 1, False)} с (половина лимита шага {time_['step_limit_min']} мин). Время при p = 3 до теста не мерилось (PREREG §2).")
add(f"- Время анализа — {n(an.get('seconds'), 0, False)} с.")
add('')
add('| Среда | задач ID | задач OOD | голов в толпе | годна | оракул вне диапазона | невырождена по пилоту 2 |')
add('|---|---|---|---|---|---|---|')
for nm in sorted(envs, key=lambda s: len(s)):
    e = envs[nm]
    add(f"| {nm} | {e['n_id']} | {e['n_ood']} | {len(e['crowd'])} | {'да' if e['valid'] else 'нет'} | {n(e.get('oracle_ood'), 4, False)} | "
        f"{'да' if nm in an['nondeg']['list_by_pilot'] else 'нет'} |")
add('')
mm = an['nondeg'].get('mismatch') or []
add(f"- Оракул — доля задач вне диапазона, где верна хоть одна голова толпы. Порог невырожденности — {n(an['nondeg']['oracle_threshold'], 1, False)}; "
    + ('по тесту он разделяет среды так же, как по пилоту 2.' if not mm else
       f"расхождение с пилотом 2: {', '.join(mm)}. По PREREG §3 это записывается, вердикт не меняется."))
add('')
add('## Т4 по средам (точки; в скобках — ст. откл. повторов)')
add('')
add('| Среда | F | F₀ | F − F₀ | F − F₀ со стратами по переносам | гомоплазия H | H₀ |')
add('|---|---|---|---|---|---|---|')
for nm in sorted(valid, key=lambda s: len(s)):
    e = envs[nm]
    t, h = e['T4'], e['homoplasy']
    add(f"| {nm} | {n(t['F'], 4, False)} | {n(t['F0'], 4, False)} | {n(t['point'])} ({n(t['sd'], 4, False)}) | "
        f"{n(t['point_strata'])} ({n(t['sd_strata'], 4, False)}) | {n(h['H'], 4, False)} | {n(h['H0'], 4, False)} |")
add('')
add(f"- Знак F − F₀ по средам (совет 69, Н3): невырожденных по знаку сред — {len(NZC)}: > 0 — {sum(t4env[e] > 0 for e in NZC)}, "
    f"< 0 — {sum(t4env[e] < 0 for e in NZC)}. В {' и '.join(ZC)} F = 1: Т4 — ноль по построению "
    f"(в L_X9999_p3 F − F₀ = {n(t4env.get('L_X9999_p3'), 7)} — F₀ чуть меньше 1).")
nd_t = [e for e in sorted(valid, key=len) if envs[e]['oracle_ood'] >= an['nondeg']['oracle_threshold']]
if set(nd_t) != set(an['nondeg']['list_by_pilot']):
    DER['t4_mean_nondeg_by_test_posthoc'] = sum(t4env[e] for e in nd_t) / len(nd_t)
    add(f"- **Пост-хок, по правде теста (вердикт не меняет; совет 69):** по оракулу теста невырождены {len(nd_t)} среды — {', '.join(nd_t)}; "
        f"среднее Т4 по ним — {n(DER['t4_mean_nondeg_by_test_posthoc'])} (точка; интервал не считался). Основная разбивка — по пилоту 2. "
        f"L_X999_p3 — переходная зона: оракул {n(envs['L_X999_p3']['oracle_ood'], 4, False)}, Т4 {n(t4env['L_X999_p3'])}.")
for k, lab in (('descr_T4 невырожденные среды', 'Т4 по двум невырожденным средам'), ('descr_T4 (другой нуль)', 'Т4 со стратами по числу переносов')):
    e = an.get(k)
    if e:
        add(f"- {lab} (описательно): {n(e['delta'])}, M4 при 0,005 — {iv(e['ci'])}.")
add('')
add('## Проверки построения Т1 и Т3 по средам (точки; в скобках — ст. откл. повторов)')
add('')
add('| Среда | Т1 = C − T у POST-CV | Т3 = r | Σ(C − T вне диапазона) | Σ(T на ID − T вне диапазона) |')
add('|---|---|---|---|---|')
for nm in sorted(valid, key=lambda s: len(s)):
    p, s = envs[nm]['point'], envs[nm]['sd']
    add(f"| {nm} | {n(p['T1'])} ({n(s['T1'], 4, False)}) | {n(p['T3'])} ({n(s['T3'], 4, False)}) | {n(p['T3 num'])} | {n(p['T3 den'])} |")
add('')
for k, lab in (('descr_T3 невырожденные среды', 'r по невырожденным средам'), ('descr_T3 вырожденные среды', 'r по вырожденным средам')):
    e = an.get(k)
    if e:
        add(f"- {lab} (описательно): {n(e['delta'])}, M4 при 0,005 — {iv(e['ci'])}.")
add('- Т1 и Т3 — проверки построения (совет 68): их исход находкой об оценщике не называется. Сведения даёт величина r — какая доля '
    'разрыва точности ID − OOD осталась в заявке головы, откалиброванной на ID.')
add('')
add('## Головы толпы (среднее по годным средам; описательно)')
add('')
add('| Голова | точность ID | точность OOD | разрыв ID − OOD | C − T вне диапазона | проверка метода пройдена, сред |')
add('|---|---|---|---|---|---|')
for nm, h in heads.items():
    add(f"| {nm} | {n(h['id'], 4, False)} | {n(h['ood'], 4, False)} | {n(h['drop'])} | {n(h['ct_ood'])} | {h['method_ok_envs']} из {len(envs)} |")
add('')
add(f"- Средний по головам разрыв ID − OOD — {n(DER['drop_mean'])}.")
add('')
add('## Незнание и самообман отдельно (вне диапазона; среднее точек по годным средам)')
add('')
add('| Оценщик | T (доля верных) | C (средняя заявка) | незнание | самообман | ИОИ | Брайер |')
add('|---|---|---|---|---|---|---|')
pm = an.get('parts_mean') or {}
for e_ in ('CONF', 'CONF (core)', 'POST-CV', 'POST-IN', 'ONE-BEST', 'FIXED', 'SHIFT', 'AGREE'):
    if f'T {e_}' not in pm:
        continue
    add(f"| {e_} | {n(pm[f'T {e_}'], 4, False)} | {n(pm.get(f'C {e_}'), 4, False)} | {n(pm.get(f'ign {e_}'), 4, False)} | "
        f"{n(pm.get(f'dec {e_}'), 4, False)} | {n(pm.get(f'ioi {e_}'), 4, False)} | {n(pm.get(f'brier {e_}'), 4, False)} |")
add('')
add(f"- Оракул вне диапазона, среднее по годным средам, — {n(an.get('oracle_ood_mean'), 4, False)}.")
add('')
hm_ = an.get('homoplasy_mean') or {}
add('## Гомоплазия и AGREE (описательно, вес 0)')
add('')
add(f"- Гомоплазия — доля задач вне диапазона, где самый частый неверный числовой ответ набрал не меньше 3 голосов: H = {n(hm_.get('H'), 4, False)}, "
    f"при перестановочном нуле H₀ = {n(hm_.get('H0'), 4, False)}, разность {n(hm_.get('diff'))} (среднее по годным средам).")
add(f"- AGREE на задачах с гомоплазией: заявка {n(hm_.get('agree_claim'), 4, False)}, доля верных {n(hm_.get('agree_T'), 4, False)}; "
    f"на остальных задачах вне диапазона: заявка {n(hm_.get('agree_claim_rest'), 4, False)}, доля верных {n(hm_.get('agree_T_rest'), 4, False)}. "
    f"В эти средние входят и {' и '.join(ZC)}, где доля верных — 0 по построению; по средам — в json (`envs.*.homoplasy`), для L_X9_p3 и L_X99_p3 — "
    "в «Коротко».")
add('')
add('## Совпадение ошибок пар (вне диапазона; описательно, вес 0)')
add('')
add('| Пары | обе ошиблись одним ответом | — ошибкой «перенос» | — «прочее» | обе ошиблись |')
add('|---|---|---|---|---|')
for k, lab in (('uncond_same', 'одного производителя'), ('uncond_cross', 'разных производителей')):
    u = an.get(k) or {}
    add(f"| {lab} | {n(u.get('u'), 4, False)} | {n(u.get('u перенос'), 4, False)} | {n(u.get('u прочее'), 4, False)} | {n(u.get('both_wrong'), 4, False)} |")
add('')
add('- «Перенос» — |d| записывается только нулями и единицами и кончается нулём; «прочее» — иначе (HYPOTHESIS). Доли — от всех задач вне диапазона.')
add('')
add('## Повтор на другом раннере (описательно)')
add('')
for r in an.get('repeat_check') or []:
    add(f"- {r['model']}, {r['env']}: задач {r['n']}; ответы совпали в доле {n(r['answers_equal'], 4, False)}; наибольшее |Δ logp| — "
        f"{n(r['max_abs_dlogp'], 6, False)}; процессор основного задания — {r['cpu_main']}, повтора — {r['cpu_rep']}. Это одно задание "
        f"({r['model'].split('/')[-1]} × {r['env']}) на двух процессорах; для остальных заданий детерминизм не проверялся (совет 69, Н5).")
if not an.get('repeat_check'):
    add('- Вывода повтора в анализе нет.')
add('')
add('## Описательно (вес 0; M4 при 0,005)')
add('')
add('| Разность | Точка | M4 при 0,005 |')
add('|---|---|---|')
for k, e in an.items():
    if k.startswith('descr_'):
        add(f"| {k[6:]} | {n(e['delta'])} | {iv(e['ci'])} |")
add('')
OUTCOME = {'E1': lambda: g(an, 'T1', 'check_result') == 'подтверждено', 'E2': lambda: g(an, 'T3', 'check_result') == 'подтверждено',
           'E3': lambda: V.get('T4') == 'подтверждено', 'E4': lambda: V.get('T4') == 'опровергнуто',
           'E5': lambda: bool(an.get('T2') and an['T2']['ci'][0] > 0), 'E6': lambda: bool(meth.get('ok'))}
add('## Ожидания (PREREG §6; исход — по json анализа)')
add('')
add('| № | Исход | Вероятность до прогона | Сбылось |')
add('|---|---|---|---|')
DER['expect_hits'] = {}
for e in ex['expect']:
    hit = OUTCOME[e['id']]()
    DER['expect_hits'][e['id']] = hit
    add(f"| {e['id']} | {e['text']}{' (тривиальное — вне сводной калибровки)' if e.get('trivial') else ''} | {n(e['p'], 3, False)} | {'да' if hit else 'нет'} |")
add('')
json.dump(DER, open(DER_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for sec, title in (('main_question', 'Для главного вопроса'), ('next', 'Что дальше')):
    if NOTES.get(sec):
        add(f'## {title}')
        add('')
        for s_ in NOTES[sec]:
            add(s_ if s_.startswith('  - ') else f'- {s_}')
        add('')
add('## Вес опоры (PREREG §10; верхняя оценка, не для реестра)')
add('')
add(f"- Т4: {w4['verdict']}; вес {('не определён' if w4['bits'] is None else ('0 бит' if w4['bits'] == 0 else n(w4['bits'], 2) + ' бит'))}"
    + (f"; мощность {n(w4['power'], 3, False)}" if w4.get('power') is not None else '') + f"; {w4['note']}. "
    'В `journal/support_bits.json` не вносится (PREREG §10; совет 69 — голоса формалиста и интуита). Вес относится только к знаку среднего пяти сред.')
add('- Т1, Т3 (проверки построения), Т2 и всё описательное — 0 бит. Данные пилотов опорой не считаются.')
add('')
if CN:
    add('## Совет 69 — оценка отчёта')
    add('')
    tm = CN.get('timer', {})
    add(f"- Стенограмма — `docs/council/2026-11-17_OCDIV-02-report_session69.md`. Итог — {CN.get('status')}: "
        + ', '.join(f"{v['name']} — {v['vote']}" for v in CN.get('votes', [])) + f"; заседание {DER['council69']['seconds']} с, перебор {tm.get('over_s')} с.")
    for s_ in NOTES.get('council', []):
        add(s_ if s_.startswith('  - ') else f'- {s_}')
    add('')
add('## Отклонения')
add('')
add('См. `DEVIATIONS.md`.' if os.path.exists(os.path.join(X, 'DEVIATIONS.md')) else
    'Нет. Расхождение оракула L_X999_p3 с пилотом 2 записано по PREREG §3 (раздел «Метод опыта»); вердикт оно не меняет.')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('записано', OUT, len(L), 'строк; производные —', DER_PATH)
