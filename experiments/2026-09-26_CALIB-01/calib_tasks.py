# CALIB-01: счётные задачи с точным ответом (правда — count_dp, сверенный с перебором в c01_tasks.selftest).
# Трудность: уровень (число условий) и число цифр N. Головы решают без инструментов.
import random, json, sys, os
from functools import lru_cache
from c01_tasks import selftest


def count(N, m_sum, r_sum, q, r_mod, bad):
    """Число x в [1, N]: сумма цифр ≡ r_sum (mod m_sum), x ≡ r_mod (mod q), ни одной цифры из bad."""
    D = list(map(int, str(N)))
    @lru_cache(None)
    def go(i, tight, s, v, st):
        if i == len(D): return int(st and s == r_sum and v == r_mod)
        tot = 0
        for d in range((D[i] if tight else 9) + 1):
            s2 = st or d > 0
            if s2 and d in bad: continue
            tot += go(i + 1, tight and d == D[i], (s + d) % m_sum if s2 else 0, (v * 10 + d) % q if s2 else 0, s2)
        return tot
    return go(0, True, 0, 0, False)


def brute(N, m_sum, r_sum, q, r_mod, bad):
    return sum(1 for x in range(1, N + 1) if sum(map(int, str(x))) % m_sum == r_sum and x % q == r_mod and not (set(str(x)) & {str(b) for b in bad}))


def selftest2():
    r = random.Random(5)
    for _ in range(300):
        p = dict(m_sum=r.choice([3, 5, 7, 9, 11]), r_sum=0, q=r.choice([1, 3, 7, 11, 13]), r_mod=0, bad=tuple(r.sample(range(10), r.choice([0, 1, 2]))))
        p['r_sum'] = r.randrange(p['m_sum']); p['r_mod'] = r.randrange(p['q'])
        N = r.randint(1, 20000)
        assert count(N, **p) == brute(N, **p), (N, p)

NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: реши в уме, опираясь только на текст ниже.'


def make(level, digits, seed):
    for k in range(100):  # вырожденные задачи (ответ < 5) пропускаются детерминированно
        t = _make(level, digits, seed, k)
        if t['answer'] >= 5: return t
    raise RuntimeError('нет невырожденной задачи')


def _make(level, digits, seed, k):
    r = random.Random(f'{level}:{digits}:{seed}:{k}')
    N = r.randint(10 ** (digits - 1), 10 ** digits - 1)
    m_sum = r.choice([3, 4, 5, 7, 9]) if level < 4 else r.choice([7, 11, 13])
    q = r.choice([2, 3, 4, 5, 7]) if level < 4 else r.choice([7, 11, 13])
    nb = 0 if level < 3 else (1 if level == 3 else 2)
    p = dict(m_sum=m_sum, r_sum=r.randrange(m_sum), q=q if level >= 2 else 1, r_mod=0, bad=tuple(sorted(r.sample(range(10), nb))))
    if level >= 2: p['r_mod'] = r.randrange(q)
    conds = [f'сумма цифр числа при делении на {p["m_sum"]} даёт остаток {p["r_sum"]}']
    if level >= 2: conds.append(f'само число при делении на {p["q"]} даёт остаток {p["r_mod"]}')
    if nb == 1: conds.append(f'в десятичной записи числа нет цифры {p["bad"][0]}')
    if nb == 2: conds.append(f'в десятичной записи числа нет цифр {p["bad"][0]} и {p["bad"][1]}')
    text = f'Сколько целых чисел x, 1 ≤ x ≤ {N}, удовлетворяют всем условиям: ' + '; '.join(conds) + '?'
    return dict(id=f'L{level}D{digits}s{seed}', level=level, digits=digits, seed=seed, N=N, text=text, params=p, answer=count(N, **p))


def prompt(t):
    return (f'{NO_TOOLS}\n\nЗадача: {t["text"]}\n\nНужен точный ответ — одно целое число. '
            'Верни: answer — целое число (только цифры); confidence — твоя вероятность того, что ответ в точности верен (от 0 до 1); '
            'reasoning — кратко, как считал (до 5 фраз).')


if __name__ == '__main__':
    selftest2()
    tag = sys.argv[1]
    grid = [tuple(map(int, g.split('x'))) for g in sys.argv[2].split(',')]
    seed = int(sys.argv[3])
    ts = [make(l, d, seed) for l, d in grid]
    calls = [dict(label=f'P:{t["id"]}', alias=f'{tag}{i:02d}', kind='answer', prompt=prompt(t)) for i, t in enumerate(ts)]
    os.makedirs(tag, exist_ok=True)
    json.dump(ts, open(f'{tag}/tasks.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(dict(calls=calls), open(f'{tag}/calls.json', 'w'), ensure_ascii=False, indent=1)
    src = open('calib_runner.js').read(); head, body = src.split('\n// args:', 1)
    a = json.dumps(dict(part=tag, calls=calls), ensure_ascii=False)
    open(f'{tag}/runner.js', 'w').write(head.replace("name: 'calib-runner'", f"name: 'calib-{tag}'") + f'\nconst ARGS = {a}\n// args:' + body.replace('args.', 'ARGS.'))
    for t in ts: print(t['id'], t['N'], t['answer'])
