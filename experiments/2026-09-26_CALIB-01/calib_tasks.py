# CALIB-01: счётные задачи с точным ответом (правда — count_dp, сверенный с перебором в c01_tasks.selftest).
# Трудность: уровень (число условий) и число цифр N. Головы решают без инструментов.
import random, json, sys
from c01_tasks import count_dp, selftest

NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: реши в уме, опираясь только на текст ниже.'


def make(level, digits, seed):
    for k in range(100):  # вырожденные задачи (ответ < 5) пропускаются детерминированно
        t = _make(level, digits, seed, k)
        if t['answer'] >= 5: return t
    raise RuntimeError('нет невырожденной задачи')


def _make(level, digits, seed, k):
    r = random.Random(f'{level}:{digits}:{seed}:{k}')
    N = r.randint(10 ** (digits - 1), 10 ** digits - 1)
    m_sum, q = r.choice([3, 4, 5, 7, 9]), r.choice([2, 3, 4, 5, 7])
    p = dict(m_sum=m_sum, r_sum=r.randrange(m_sum), q=q if level >= 2 else 1, r_mod=0, bad_digit=r.randrange(10) if level >= 3 else 10)
    if level >= 2: p['r_mod'] = r.randrange(q)
    conds = [f'сумма цифр числа при делении на {p["m_sum"]} даёт остаток {p["r_sum"]}']
    if level >= 2: conds.append(f'само число при делении на {p["q"]} даёт остаток {p["r_mod"]}')
    if level >= 3: conds.append(f'в десятичной записи числа нет цифры {p["bad_digit"]}')
    text = f'Сколько целых чисел x, 1 ≤ x ≤ {N}, удовлетворяют всем условиям: ' + '; '.join(conds) + '?'
    return dict(id=f'L{level}D{digits}s{seed}', level=level, digits=digits, seed=seed, N=N, text=text, params=p, answer=count_dp(N, **p))


def prompt(t):
    return (f'{NO_TOOLS}\n\nЗадача: {t["text"]}\n\nНужен точный ответ — одно целое число. '
            'Верни: answer — целое число (только цифры); confidence — твоя вероятность того, что ответ в точности верен (от 0 до 1); '
            'reasoning — кратко, как считал (до 5 фраз).')


if __name__ == '__main__':
    selftest()
    grid = [(1, 3), (1, 4), (1, 6), (2, 3), (2, 4), (3, 3), (3, 4), (2, 6)]
    ts = [make(l, d, 900) for l, d in grid]  # пилотное зерно 900 в тест не входит
    calls = [dict(label=f'P:{t["id"]}', alias=f'cp{i:02d}', kind='answer', prompt=prompt(t)) for i, t in enumerate(ts)]
    json.dump(ts, open('pilot/tasks.json', 'w'), ensure_ascii=False, indent=1)
    json.dump(dict(calls=calls), open('pilot/calls.json', 'w'), ensure_ascii=False, indent=1)
    for t in ts: print(t['id'], t['N'], t['answer'])
