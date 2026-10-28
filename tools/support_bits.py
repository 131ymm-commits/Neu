#!/usr/bin/env python3
"""Вес опоры в битах — правило Neu (решение автора 28.10.2026: «Вес опоры в битах.»).

Формула — docs/2026-10-28_trust_formula.md §2 и §5:
    log₂-шансы утверждения = база класса утверждения + Σ по независимым группам опор log₂ Λ.
- Пересказы одного источника и опоры с общей ошибкой — одна группа; в группе берётся наибольший вес (ω копии = 0).
- Вес опоры = вес класса × множитель чтения (что мы сами видели: полный текст, аннотацию, сниппет, по памяти).
- У опыта Neu с регистрацией до прогона вес — log₂(мощность / ложный уровень): байесов фактор подтверждения порогового
  теста (Иоаннидис 2005: PPV = (1 − β)R / ((1 − β)R + α)). Ложный уровень и мощность берутся из PREREG; мощность без
  числа — 0,8; ложный уровень меньше 0,001 не берётся. Опровержение даёт log₂((1 − мощность)/(1 − ложный уровень)) < 0.
- Начальные веса классов чтения — по суждению. Они пересчитываются по нашему послужному списку
  (journal/support_track.jsonl, строка {"class", "reading", "held": true/false}) как Λ̂ = (h + 1)/(m + 1) (Jøsang, α = β = 1),
  когда набирается не меньше 5 исходов класса.

  python3 tools/support_bits.py              веса утверждений из journal/support_bits.json → таблица
  python3 tools/support_bits.py --classes    таблица классов, множителей чтения и баз
"""
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CLASSES = {
    'наш_рег': dict(bits=None, why='опыт Neu, PREREG до прогона, вердикт по букве: log₂(мощность/ложный уровень)'),
    'наш_разведка': dict(bits=1.0, why='разведка, пост-хок или опыт без регистрации — по суждению, до послужного списка'),
    'журнал': dict(bits=1.0, why='рецензия сверх препринта: 0,5–1,5 бита (Schroter и др. 2008: 2,58 из 9 ошибок у рецензента)'),
    'препринт': dict(bits=0.0, why='без рецензии: сверх базы поля ничего'),
    'доклад': dict(bits=0.0, why='тезисы, постер, семинар: как препринт'),
    'повтор_чужой': dict(bits=4.0, why='успешный независимый повтор при мощности 0,8 и α 0,05: Λ = 16'),
    'пересказ': dict(bits=0.0, why='копия уже учтённого источника: ω = 0'),
}
READING = {'полный текст': 1.0, 'аннотация': 1.0, 'сниппет': 0.5, 'по памяти': 0.0, 'только название': 0.0}
BASES = {   # база класса утверждения: log₂-шансы доли верных (источник — docs/2026-10-28_trust_formula.md §3)
    'гипотеза_neu': (0.54, 'доля подтверждённых предсказаний Neu, journal/SELF_CALIBRATION.md (28.10.2026)'),
    'ml_статья': (0.635, 'Raff, NeurIPS 2019: 162 из 255 работ ML воспроизведены'),
    'психология': (0.36, 'Open Science Collaboration 2015: 36 % повторов значимы'),
    'соц_науки_NS': (0.62, 'Camerer и др. 2018: 13 из 21'),
    'нейтрально': (0.5, 'базы нет'),
}


def log2odds(p):
    return math.log2(p / (1 - p))


def support_bits(s):
    """Вес одной опоры в битах."""
    cls = CLASSES[s['class']]
    if s['class'] == 'наш_рег':
        a, pw = max(s['false_level'], 0.001), s.get('power', 0.8)   # меньше 0,001 не берём: хвосты модельные (PREREG-TRUST-02 §6)
        b = math.log2(pw / a) if s.get('held', True) else math.log2((1 - pw) / (1 - a))
    else:
        b = cls['bits']
    return b * READING[s.get('reading', 'полный текст')]


def claim_bits(c):
    """База + Σ по группам наибольшего веса в группе. Возвращает (биты, вероятность, разбивка)."""
    p0, _ = BASES[c['base']]
    total = log2odds(p0); parts = [('база ' + c['base'], round(log2odds(p0), 2))]
    groups = {}
    for s in c['supports']:
        groups.setdefault(s.get('group', s.get('note', '')), []).append(s)
    for g, ss in groups.items():
        best = max(ss, key=support_bits)
        b = support_bits(best); total += b; parts.append((g, round(b, 2)))
    return total, 1 / (1 + 2 ** (-total)), parts


def track_update():
    """Λ̂ по послужному списку классов чтения (если записей ≥ 5)."""
    p = os.path.join(ROOT, 'journal', 'support_track.jsonl')
    if not os.path.exists(p):
        return {}
    cnt = {}
    for line in open(p, encoding='utf-8'):
        if line.strip():
            r = json.loads(line); k = (r['class'], r['reading']); h, m = cnt.get(k, (0, 0))
            cnt[k] = (h + bool(r['held']), m + (not r['held']))
    return {k: dict(h=h, m=m, bits=round(math.log2((h + 1) / (m + 1)), 2)) for k, (h, m) in cnt.items() if h + m >= 5}


if __name__ == '__main__':
    if '--classes' in sys.argv:
        print('| Класс | Вес, бит | Основание |\n|---|---|---|')
        for k, v in CLASSES.items():
            print(f"| {k} | {'по формуле' if v['bits'] is None else v['bits']} | {v['why']} |")
        print('\n| Чтение | Множитель |\n|---|---|')
        for k, v in READING.items():
            print(f'| {k} | {v} |')
        print('\n| База | Доля | log₂-шансы | Источник |\n|---|---|---|---|')
        for k, (p, why) in BASES.items():
            print(f'| {k} | {p} | {log2odds(p):+.2f} | {why} |')
        tu = track_update()
        if tu:
            print('\nПослужной список (≥ 5 исходов):', tu)
        sys.exit(0)
    data = json.load(open(os.path.join(ROOT, 'journal', 'support_bits.json'), encoding='utf-8'))
    table = {}
    print('| Утверждение | Бит | P | Разбивка |\n|---|---|---|---|')
    for cid, c in data.items():
        if cid.startswith('_'):
            continue
        b, p, parts = claim_bits(c)
        table[cid] = dict(bits=round(b, 2), bits_1=round(b, 1), p=round(p, 4), parts=parts)
        print(f"| {cid} | {b:+.1f} | {p:.3f} | " + '; '.join(f'{g} {v:+.2f}' for g, v in parts) + ' |')
    if '--json' in sys.argv:                      # копия таблицы рядом с отчётом: числа отчёта — из json (ledger.py audit)
        json.dump(table, open(sys.argv[sys.argv.index('--json') + 1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
