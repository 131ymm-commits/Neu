#!/usr/bin/env python3
"""TRUST-04: записи в реестр (tools/ledger.py) и веса опор (journal/support_bits.json) по отчёту — после проверки отчёта.
Числа — из analysis_trust_04.json и pilot/v2/pilot_calib2.json (ложный уровень и мощность §6); тексты утверждений — здесь.
Запуск из папки опыта: python3 ledger_trust04.py [--dry]"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
DRY = '--dry' in sys.argv
an = json.load(open(os.path.join(HERE, 'analysis_trust_04.json')))
cal = json.load(open(os.path.join(HERE, 'pilot', 'v2', 'pilot_calib2.json')))['bits']['95']
f = lambda x, d=4: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
v = lambda k: an['verdicts'][k]
u = lambda k: v(k)['value'][0]
REP = 'experiments/2026-10-28_TRUST-04/REPORT-TRUST-04.md'
GROUP = 'TRUST-04 (9c37e56)'

assert all(s['outcome'] == 'подтверждено' for s in an['summary'].values()), 'не все сводные подтверждены — тексты ниже не годятся'
NEW = [
    ('SA', 'TRUST-04 SA: при одной архитектуре (40 × 10, гены у особей, мутация σ = 0,04 на ген, общий риск, основание групп целиком, '
           'без миграции; среднее по окну 2000 поколений и 20 зёрнам) сцепление w0 и w_G не создаёт остатка многоуровневого отбора: '
           f"средний вес группы приводит в шестую часть разрыва от дальновидной точки и при сцеплённом, и при раздельном наследовании (u {f(u('A1'))} и {f(u('A2'))}), "
           f"свой вес оставляет остаток при обоих ({f(u('A3'))} и {f(u('A4'))}); сцеплённое и раздельное эквивалентны (±0,1 разрыва)"),
    ('SA3', 'TRUST-04 SA3: при тех же условиях остаток создаёт отбор внутри группы по своему весу (E1): при E1 остаток около половины разрыва '
            f"и не зависит от того, свои веса или средний вес входят в F группы (DEMES_FREE {f(u('A4'))}, DEMES_GPOOL {f(u('A16'))}, эквивалентны ±0,1); "
            f"без E1 доверие приходит в шестую часть разрыва (POOLED_FREE {f(u('A2'))}, DEMES_NOWITHIN {f(u('A15'))}; у DEMES_NOWITHIN срывов "
            f"{v('A15')['breakdowns']} из 20 тестовых и 3 из 30 пилотных зёрен). Клетки «E1 нет» сняты разными способами; чистый контраст E2 — только при E1"),
    ('SA2', 'TRUST-04 SA2: общий ген группы приходит в треть разрыва от дальновидной точки и при шаге мутации втрое меньше эффективного шага '
            f"среднего группы (COUNCIL_SIGN u {f(u('A11'))}; эквивалентен шагу σ, ±0,1 разрыва)"),
    ('SB', 'TRUST-04 SB, SB2: знак разрыва «свой вес — средний вес группы» сохраняется в семи условиях (r_G 0,75 и 0,95, B_MAX 0,3 и 0,9, '
           'независимый риск, миграция 0,1, шаг мутации ×5; 20 из 20 зёрен в каждом); средний вес группы приходит в треть разрыва '
           f"в четырёх других мирах (u {f(min(u(k) for k in ('B8', 'B9', 'B10', 'B11')))}–{f(max(u(k) for k in ('B8', 'B9', 'B10', 'B11')))})"),
    ('SC', 'TRUST-04 SC: реализация модели, написанная агентом только по спецификации, на своих зёрнах воспроизводит основную по средним u '
           'четырёх рук (±0,1 разрыва) и по порядку «средний вес ниже своего» (20 из 20); спецификация — моя, общая ошибка спецификации прошла бы в обе'),
]
EXPL = [
    ('EB6', 'TRUST-04 (разведка): у рук с отбором внутри группы по своему весу доля пути u близка к 1 − R (R — доля межгрупповой дисперсии w_G): '
            f"в пределах 0,1 у {an['explore']['EB6']['n_within_01']} из 10 рук, ρ Спирмена {f(an['explore']['EB6']['spearman'], 3)}; "
            'исключение — независимый риск. Правило выбрано после пилота; R — статистика той же динамики, не независимая величина'),
    ('EB1-5', 'TRUST-04 (разведка): независимый риск расширяет разброс u у руки со средним весом группы '
              f"(SD {f(an['explore']['EB1']['sd_IND'])} против {f(an['explore']['EB1']['sd_base'])}); миграция 0,1 его не сдвигает (±0,1); "
              'миграция и шаг мутации ×5 ослабляют многоуровневый отбор; доля пути многоуровневого отбора не зависит от мира (±0,1, четыре мира)'),
]
SUP = dict(SA=('SA',), SA3=('SA3',), SA2=('SA2',), SB=('SB', 'SB2'), SC=('SC',))


def ledger(*args):
    cmd = [sys.executable, os.path.join(ROOT, 'tools', 'ledger.py'), *args]
    if DRY:
        print('СУХО:', ' '.join(a if ' ' not in a else repr(a[:80]) for a in args)); return 'C-XXX'
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    print(out); return out.split()[0]


sb_path = os.path.join(ROOT, 'journal', 'support_bits.json')
sb = json.load(open(sb_path))
for key, text in NEW:
    cid = ledger('add', text, '--status', 'подтверждено', '--support', f'{REP} ({key}; PREREG 9c37e56)')
    sb[cid] = dict(base='гипотеза_neu', text=text.split(':', 1)[0] + ': ' + text.split(':', 1)[1][:160].strip() + '…', supports=[
        dict(**{'class': 'наш_рег'}, group=GROUP, false_level=cal[c]['alpha'] if 'alpha' in cal[c] else cal[c]['false_level'],
             power=cal[c]['power'], held=True, note=f'сводный {c}, PREREG-TRUST-04 §6') for c in SUP[key]])
for key, text in EXPL:
    cid = ledger('add', text, '--status', 'гипотеза', '--support', f'{REP} ({key}, разведка)')
    sb[cid] = dict(base='гипотеза_neu', text=text[:200] + '…', supports=[dict(**{'class': 'наш_разведка'}, group=GROUP, note=f'разведка {key}, правило — после пилота')])
for cid, r in an['registry'].items():
    why = (f"Повтор TRUST-04 (PREREG 9c37e56; зёрна 600–619 и вторая реализация 700–719): держится — части {', '.join(r['parts'])} подтверждены, "
           f"вес повтора {f(r['bits'], 2)} бита. По правилу CLAUDE.md — «установлено» в пределах игрушки, с оговоркой: спецификация и бо́льшая часть кода "
           'общие с TRUST-03, вторая реализация — по моей спецификации')
    assert r['outcome'] == 'держится'
    ledger('set', cid, 'подтверждено', '--why', why, '--support', REP)
    sb[cid]['supports'].append(dict(**{'class': 'наш_рег'}, group=GROUP + ' — повтор', false_level=r['false_level'], power=r['power'], held=True,
                                    note='повтор утверждения TRUST-03: новые зёрна и вторая реализация; спецификация и большая часть кода общие с TRUST-03'))
if not DRY:
    json.dump(sb, open(sb_path, 'w'), ensure_ascii=False, indent=1)
    print('support_bits.json обновлён')
