# CLAUDE-01: генератор задач с вычисляемой правдой (см. docs/council/2026-09-26_CLAUDE-01_session2.md).
# Тип I — индукция функции по 12 примерам; скрытые тесты — все x из −100…100 и 500 случайных из ±10000.
# Тип C — счёт чисел 1..N (N ~ 1e15) с условиями на цифры и остатки; правда — динамика по цифрам (сверена с перебором).
# Секреты (эталон, скрытые входы, ответ) пишутся ВНЕ репозитория; в PREREG идёт только их SHA-256.
import json, random, hashlib, os, sys
from functools import lru_cache


def dsum(x): return sum(map(int, str(abs(x))))
def rev(x): s = str(abs(x))[::-1].lstrip('0') or '0'; return int(s) * (1 if x >= 0 else -1)

PRIMS = {  # имя -> (фабрика параметров, формат выражения на Python)
    'lin':   (lambda r: dict(a=r.choice([-3, -2, 2, 3, 5]), b=r.randint(-9, 9)), '{a}*x+({b})'),
    'mod':   (lambda r: dict(m=r.choice([5, 6, 7, 9, 11])), 'x%{m}'),
    'div':   (lambda r: dict(k=r.choice([2, 3, 4, 5])), 'x//{k}'),
    'dsum':  (lambda r: dict(), 'dsum(x)'),
    'rev':   (lambda r: dict(), 'rev(x)'),
    'sqm':   (lambda r: dict(p=r.choice([13, 17, 19, 23])), '(x*x)%{p}'),
    'abs':   (lambda r: dict(c=r.randint(-20, 20)), 'abs(x-({c}))'),
    'xor':   (lambda r: dict(k=r.choice([3, 5, 6, 9, 12])), '(x^{k})'),
}


def prim(r):
    n = r.choice(list(PRIMS)); f, fmt = PRIMS[n]; return fmt.format(**f(r))


def make_I(level, seed):
    r = random.Random(seed)
    if level == 1:
        expr = prim(r)
    elif level == 2:
        m, t = r.choice([2, 3, 4]), None
        t = r.randrange(m)
        expr = f'({prim(r)}) if x%{m}=={t} else ({prim(r)})'
    else:
        c1 = r.randint(-30, 30); m = r.choice([2, 3]); t = r.randrange(m)
        expr = f'({prim(r)}) if x<{c1} else (({prim(r)}) if x%{m}=={t} else ({prim(r)}))'
    src = f'def f(x):\n    return {expr}\n'
    env = dict(dsum=dsum, rev=rev); exec(src, env); f = env['f']
    xs = r.sample(range(-60, 61), 12)
    hidden = list(range(-100, 101)) + [r.randint(-10000, 10000) for _ in range(500)]   # сплошной отрезок ловит сдвиги границ
    return dict(kind='I', level=level, seed=seed,
                public=dict(examples=[[x, f(x)] for x in xs]),
                secret=dict(src=src, hidden=[[x, f(x)] for x in hidden]))


def count_dp(N, m_sum, r_sum, q, r_mod, bad_digit):
    """Число x в [1, N]: сумма цифр ≡ r_sum (mod m_sum), x ≡ r_mod (mod q), цифра bad_digit не встречается."""
    D = list(map(int, str(N)))

    @lru_cache(None)
    def go(i, tight, s, v, started):
        if i == len(D):
            return int(started and s == r_sum and v == r_mod)
        tot = 0
        for d in range(0, (D[i] if tight else 9) + 1):
            st = started or d > 0
            if st and d == bad_digit:
                continue
            tot += go(i + 1, tight and d == D[i], (s + d) % m_sum if st else 0, (v * 10 + d) % q if st else 0, st)
        return tot
    return go(0, True, 0, 0, False)


def brute(N, m_sum, r_sum, q, r_mod, bad_digit):
    return sum(1 for x in range(1, N + 1) if dsum(x) % m_sum == r_sum and x % q == r_mod and (bad_digit > 9 or str(bad_digit) not in str(x)))


def make_C(level, seed):
    r = random.Random(seed)
    N = r.randint(10 ** 14, 10 ** 16)
    m_sum, q = r.choice([7, 9, 11, 13]), r.choice([3, 7, 11, 13, 17])
    p = dict(m_sum=m_sum, r_sum=r.randrange(m_sum), q=q if level >= 2 else 1, r_mod=0, bad_digit=r.randrange(10) if level >= 3 else 10)
    if level >= 2: p['r_mod'] = r.randrange(q)
    conds = [f'сумма цифр числа при делении на {p["m_sum"]} даёт остаток {p["r_sum"]}']
    if level >= 2: conds.append(f'само число при делении на {p["q"]} даёт остаток {p["r_mod"]}')
    if level >= 3: conds.append(f'в десятичной записи числа нет цифры {p["bad_digit"]}')
    text = f'Сколько целых чисел x, 1 ≤ x ≤ {N}, удовлетворяют всем условиям: ' + '; '.join(conds) + '?'
    return dict(kind='C', level=level, seed=seed, public=dict(N=N, text=text),
                secret=dict(params=p, answer=count_dp(N, **p)))


def selftest():
    r = random.Random(1)
    for _ in range(40):
        p = dict(m_sum=r.choice([7, 9, 11]), r_sum=0, q=r.choice([1, 3, 7]), r_mod=0, bad_digit=r.choice([10, r.randrange(10)]))
        p['r_sum'] = r.randrange(p['m_sum']); p['r_mod'] = r.randrange(p['q'])
        N = r.randint(1, 30000)
        assert count_dp(N, **p) == brute(N, **p), (N, p)
    for s in range(30):
        for lv in (1, 2, 3):
            t = make_I(lv, s); env = dict(dsum=dsum, rev=rev); exec(t['secret']['src'], env)
            assert all(env['f'](x) == y for x, y in t['secret']['hidden'])
    print('самопроверка: динамика = перебор на 40 случаях; эталоны I сходятся со своими тестами')


if __name__ == '__main__':
    selftest()
