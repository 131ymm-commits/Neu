#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PLATON-01 (ветвь П9): мир с правдой от кода.

Экземпляр — знакомый закон физики со случайными постоянными и диапазонами. Из экземпляра строятся четыре таблицы:
  данные T — строки подчиняются закону; Z — каждый столбец таблицы T перемешан отдельно (те же значения столбцов, связи нет);
  имена S — физические имена с описанием и единицами; N — нейтральные a, b, c, d (тот же порядок столбцов).
Для проверки утверждений голов — новые строки того же процесса: в показанном диапазоне (in) и вне его (out).
Для Z новые строки — новые строки T, перемешанные по столбцам (произведение распределений столбцов).

Всё детерминировано от зерна экземпляра: random.Random(f'platon01|{seed}|<поток>'), отдельные потоки на параметры, строки,
перестановки и имена. Значения показанных строк округлены до трёх значащих цифр; новые строки не округляются.
Запуск: python3 platon_world.py show <зерно>  — печатает экземпляр (для глаз), ничего не пишет.
"""
import json
import math
import random
import sys

N_ROWS = 13          # нечётное: медиана — порядковая статистика, она переходит в медиану при монотонном преобразовании
N_HOLD = 400         # новых строк в каждом из наборов in / out
LETTERS = 'abcd'


def rng_for(seed, stream):
    return random.Random(f'platon01|{seed}|{stream}')


def fmt3(x):
    """Три значащие цифры, десятичная запись без экспоненты."""
    if x == 0 or not math.isfinite(x):
        raise ValueError(f'недопустимое значение {x}')
    e = math.floor(math.log10(abs(x)))
    d = 2 - e
    v = round(x, d)
    if v != 0 and math.floor(math.log10(abs(v))) != e:      # округление перешло в следующий порядок (9.996 → 10.0)
        e += 1
        d = 2 - e
        v = round(x, d)
    return f'{v:.{d}f}' if d > 0 else f'{int(round(v))}'


def loguni(r, lo, hi):
    return math.exp(r.uniform(math.log(lo), math.log(hi)))


# ---------- законы ----------
# Каждый закон: столбцы (имя, описание для S), свободные переменные, зависимая переменная, параметры, диапазоны,
# решение для зависимой и каноническое выражение инварианта (в именах столбцов S).

def _p_fall(r):
    g = r.uniform(3, 20); lo = r.uniform(0.3, 1.0)
    return {'g': g, 'rng': {'t': (lo, lo * r.uniform(2.5, 4.0))}}


def _p_pendulum(r):
    g = r.uniform(3, 20); lo = r.uniform(0.1, 0.5)
    return {'g': g, 'rng': {'L': (lo, lo * r.uniform(3.0, 6.0))}}


def _p_kepler(r):
    M = r.uniform(0.4, 2.5); lo = r.uniform(0.3, 1.0)
    return {'M': M, 'rng': {'a': (lo, lo * r.uniform(3.0, 6.0))}}


def _p_gas(r):
    nR = r.uniform(2, 20); plo = r.uniform(50, 120); tlo = r.uniform(200, 300)
    return {'nR': nR, 'rng': {'P': (plo, plo * r.uniform(2.0, 3.0)), 'T': (tlo, tlo * r.uniform(1.5, 2.0))}}


def _p_lens(r):
    f = r.uniform(5, 30)
    return {'f': f, 'rng': {'d1': (f * r.uniform(1.3, 1.8), f * r.uniform(3.5, 6.0))}}


def _p_spring(r):
    A = r.uniform(0.1, 0.5); w = r.uniform(1.5, 8.0)
    return {'A': A, 'w': w, 'rng': {'x': (0.15 * A, 0.75 * A)}}


def _p_energy(r):
    H = r.uniform(5, 40)
    return {'g': 9.81, 'H': H, 'rng': {'h': (0.15 * H, 0.75 * H)}}


def _p_coulomb(r):
    eps = r.uniform(1, 10); qlo = r.uniform(0.5, 2.0); rlo = r.uniform(0.02, 0.1)
    return {'eps': eps, 'rng': {'q1': (qlo, qlo * r.uniform(4, 8)), 'q2': (qlo, qlo * r.uniform(4, 8)),
                                'r': (rlo, rlo * r.uniform(3, 6))}}


def _p_ohm(r):
    ilo = r.uniform(0.05, 0.5); rlo = r.uniform(2, 20)
    return {'rng': {'I': (ilo, ilo * r.uniform(4, 8)), 'R': (rlo, rlo * r.uniform(4, 8))}}


def _p_kinetic(r):
    mlo = r.uniform(0.2, 2.0); vlo = r.uniform(0.5, 3.0)
    return {'rng': {'m': (mlo, mlo * r.uniform(4, 8)), 'v': (vlo, vlo * r.uniform(3, 6))}}


def _out_unbounded(lo, hi):
    """Вне показанного диапазона для неограниченной переменной: [lo/3, lo) и (hi, 3hi]."""
    return [(lo / 3, lo), (hi, 3 * hi)]


LAWS = {
    'fall': {
        'cols': [('t', 'время свободного падения от начала, с'), ('h', 'пройденный путь, м')],
        'free': ['t'], 'dep': 'h', 'params': _p_fall,
        'solve': lambda p, x: p['g'] / 2 * x['t'] ** 2,
        'inv': lambda p: 'h/t**2',
        'out': lambda p: {'t': _out_unbounded(*p['rng']['t'])},
    },
    'pendulum': {
        'cols': [('L', 'длина маятника, м'), ('T', 'период колебаний маятника, с')],
        'free': ['L'], 'dep': 'T', 'params': _p_pendulum,
        'solve': lambda p, x: 2 * math.pi * math.sqrt(x['L'] / p['g']),
        'inv': lambda p: 'T**2/L',
        'out': lambda p: {'L': _out_unbounded(*p['rng']['L'])},
    },
    'kepler': {
        'cols': [('a', 'большая полуось орбиты планеты, а. е.'), ('T', 'период обращения планеты, лет')],
        'free': ['a'], 'dep': 'T', 'params': _p_kepler,
        'solve': lambda p, x: math.sqrt(x['a'] ** 3 / p['M']),
        'inv': lambda p: 'T**2/a**3',
        'out': lambda p: {'a': _out_unbounded(*p['rng']['a'])},
    },
    'gas': {
        'cols': [('P', 'давление газа в сосуде, кПа'), ('V', 'объём газа, л'), ('T', 'температура газа, К')],
        'free': ['P', 'T'], 'dep': 'V', 'params': _p_gas,
        'solve': lambda p, x: p['nR'] * x['T'] / x['P'],
        'inv': lambda p: 'P*V/T',
        'out': lambda p: {'P': _out_unbounded(*p['rng']['P']), 'T': _out_unbounded(*p['rng']['T'])},
    },
    'lens': {
        'cols': [('d1', 'расстояние от собирающей линзы до предмета, см'),
                 ('d2', 'расстояние от линзы до изображения предмета, см')],
        'free': ['d1'], 'dep': 'd2', 'params': _p_lens,
        'solve': lambda p, x: 1 / (1 / p['f'] - 1 / x['d1']),
        'inv': lambda p: '1/d1 + 1/d2',
        'out': lambda p: {'d1': [(max(1.05 * p['f'], p['rng']['d1'][0] / 3), p['rng']['d1'][0]),
                                 (p['rng']['d1'][1], 3 * p['rng']['d1'][1])]},
    },
    'spring': {
        'cols': [('x', 'смещение груза на пружине от положения равновесия, м'), ('v', 'скорость груза, м/с')],
        'free': ['x'], 'dep': 'v', 'params': _p_spring,
        'solve': lambda p, x: p['w'] * math.sqrt(p['A'] ** 2 - x['x'] ** 2),
        'inv': lambda p: f"x**2 + v**2/{p['w'] ** 2!r}",
        'out': lambda p: {'x': [(0.01 * p['A'], 0.15 * p['A']), (0.75 * p['A'], 0.99 * p['A'])]},
    },
    'energy': {
        'cols': [('h', 'высота мяча, брошенного вертикально вверх, м'), ('v', 'скорость мяча, м/с')],
        'free': ['h'], 'dep': 'v', 'params': _p_energy,
        'solve': lambda p, x: math.sqrt(2 * (p['g'] * p['H'] - p['g'] * x['h'])),
        'inv': lambda p: 'v**2/2 + 9.81*h',
        'out': lambda p: {'h': [(0.01 * p['H'], 0.15 * p['H']), (0.75 * p['H'], 0.99 * p['H'])]},
    },
    'coulomb': {
        'cols': [('q1', 'заряд первого шарика, мкКл'), ('q2', 'заряд второго шарика, мкКл'),
                 ('r', 'расстояние между шариками, м'), ('F', 'сила взаимодействия шариков, Н')],
        'free': ['q1', 'q2', 'r'], 'dep': 'F', 'params': _p_coulomb,
        'solve': lambda p, x: 8.99e-3 / p['eps'] * x['q1'] * x['q2'] / x['r'] ** 2,
        'inv': lambda p: 'F*r**2/(q1*q2)',
        'out': lambda p: {k: _out_unbounded(*p['rng'][k]) for k in ('q1', 'q2', 'r')},
    },
    'ohm': {
        'cols': [('I', 'сила тока через резистор, А'), ('R', 'сопротивление резистора, Ом'),
                 ('U', 'напряжение на резисторе, В')],
        'free': ['I', 'R'], 'dep': 'U', 'params': _p_ohm,
        'solve': lambda p, x: x['I'] * x['R'],
        'inv': lambda p: 'U/(I*R)',
        'out': lambda p: {k: _out_unbounded(*p['rng'][k]) for k in ('I', 'R')},
    },
    'kinetic': {
        'cols': [('m', 'масса тела, кг'), ('v', 'скорость тела, м/с'), ('E', 'кинетическая энергия тела, Дж')],
        'free': ['m', 'v'], 'dep': 'E', 'params': _p_kinetic,
        'solve': lambda p, x: x['m'] * x['v'] ** 2 / 2,
        'inv': lambda p: 'E/(m*v**2)',
        'out': lambda p: {k: _out_unbounded(*p['rng'][k]) for k in ('m', 'v')},
    },
}
LAW_ORDER = ['fall', 'pendulum', 'kepler', 'gas', 'lens', 'spring', 'energy', 'coulomb', 'ohm', 'kinetic']


def _row(law, p, r, ranges):
    """Одна строка: свободные переменные лог-равномерно из диапазона (или из одного из отрезков), зависимая — по закону."""
    x = {}
    for k in law['free']:
        seg = ranges[k]
        if isinstance(seg, list):                     # объединение отрезков: отрезок по длине в логарифмах
            ws = [math.log(b) - math.log(a) for a, b in seg]
            u = r.uniform(0, sum(ws)); i = 0
            while i < len(seg) - 1 and u > ws[i]:
                u -= ws[i]; i += 1
            a, b = seg[i]
        else:
            a, b = seg
        x[k] = loguni(r, a, b)
    x[law['dep']] = law['solve'](p, x)
    return x


def make_instance(seed, law_key):
    """Экземпляр: параметры, показанная таблица T (округлённая), таблица Z, новые строки in/out для T и для Z, имена."""
    law = LAWS[law_key]
    p = law['params'](rng_for(seed, 'params'))
    cols = [c for c, _ in law['cols']]
    order = cols[:]
    rng_for(seed, 'order').shuffle(order)            # порядок столбцов: один для S и N
    # показанные строки T: свободные округляются, зависимая считается по округлённым и тоже округляется
    rr = rng_for(seed, 'rows')
    shown_T = []
    for _ in range(N_ROWS):
        x = _row(law, p, rr, p['rng'])
        for k in law['free']:
            x[k] = float(fmt3(x[k]))
        x[law['dep']] = float(fmt3(law['solve'](p, x)))
        shown_T.append(x)
    # Z: каждый столбец T перемешан отдельно; перемешивание повторяется, пока истинный закон не перестанет держаться
    rp = rng_for(seed, 'perm')
    from platon_check import R_measure, compile_expr      # без кругового импорта на уровне модуля
    inv = law['inv'](p)
    f_inv = compile_expr(inv, cols)
    tries = 0
    while True:
        tries += 1
        cols_vals = {c: [row[c] for row in shown_T] for c in cols}
        for c in cols:
            rp.shuffle(cols_vals[c])
        shown_Z = [{c: cols_vals[c][i] for c in cols} for i in range(N_ROWS)]
        if R_measure(f_inv, shown_Z, cols, seed=f'{seed}|z|{tries}') >= 0.3 or tries >= 50:
            break
    # новые строки T: в показанном диапазоне и вне его (без округления)
    rh = rng_for(seed, 'hold')
    hold_in_T = [_row(law, p, rh, p['rng']) for _ in range(N_HOLD)]
    hold_out_T = [_row(law, p, rh, law['out'](p)) for _ in range(N_HOLD)]
    # новые строки Z: новые строки T, перемешанные по столбцам
    rz = rng_for(seed, 'holdz')

    def scramble(rows):
        cv = {c: [row[c] for row in rows] for c in cols}
        for c in cols:
            rz.shuffle(cv[c])
        return [{c: cv[c][i] for c in cols} for i in range(len(rows))]
    hold_in_Z = scramble([_row(law, p, rh, p['rng']) for _ in range(N_HOLD)])
    hold_out_Z = scramble([_row(law, p, rh, law['out'](p)) for _ in range(N_HOLD)])
    letters = {c: LETTERS[i] for i, c in enumerate(order)}   # N: буквы по порядку столбцов в таблице
    return {
        'seed': seed, 'law': law_key, 'params': p, 'cols': cols, 'order': order, 'letters': letters,
        'desc': dict(law['cols']), 'inv_S': inv, 'z_tries': tries,
        'shown': {'T': shown_T, 'Z': shown_Z},
        'hold': {'T': {'in': hold_in_T, 'out': hold_out_T}, 'Z': {'in': hold_in_Z, 'out': hold_out_Z}},
    }


def rename_rows(rows, mapping):
    return [{mapping[k]: v for k, v in row.items()} for row in rows]


def table_view(inst, data, names):
    """Таблица в именах ячейки: (имена столбцов по порядку, описания или None, строки с ключами-именами)."""
    order = inst['order']
    if names == 'S':
        mp = {c: c for c in order}
        desc = [inst['desc'][c] for c in order]
    else:
        mp = inst['letters']
        desc = None
    idents = [mp[c] for c in order]
    return idents, desc, rename_rows(inst['shown'][data], mp), mp


def inv_in_names(inst, names):
    """Каноническое выражение инварианта в именах ячейки (для N — буквы)."""
    import re
    if names == 'S':
        return inst['inv_S']
    mp = inst['letters']
    return re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b', lambda m: mp.get(m.group(0), m.group(0)), inst['inv_S'])


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'show':
        sd = int(sys.argv[2])
        lk = sys.argv[3] if len(sys.argv) > 3 else LAW_ORDER[sd % len(LAW_ORDER)]
        inst = make_instance(sd, lk)
        print(json.dumps({k: inst[k] for k in ('seed', 'law', 'params', 'order', 'letters', 'inv_S', 'z_tries')},
                         ensure_ascii=False, indent=1))
        for d in ('T', 'Z'):
            idents, desc, rows, _ = table_view(inst, d, 'S')
            print(d, idents)
            for row in rows:
                print('  ', [fmt3(row[c]) for c in idents])
    else:
        print(__doc__)
