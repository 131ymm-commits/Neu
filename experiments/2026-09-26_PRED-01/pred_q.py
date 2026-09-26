# PRED-01: вопросы на предсказание с точной правдой, которую в уме не посчитать.
# Семейства: PRIMES (простые в интервале), DIGSUM (сумма цифр k^n), WALK (вероятность блуждания), SUBSETS (число подмножеств с суммой).
import math, random, json, sys, os
import numpy as np


def primes_in(a, b):
    """Число простых в [a, b] — сегментное решето."""
    lim = int(math.isqrt(b)) + 1
    base = np.ones(lim + 1, bool); base[:2] = False
    for i in range(2, int(lim ** 0.5) + 1):
        if base[i]: base[i * i::i] = False
    seg = np.ones(b - a + 1, bool)
    for p in np.nonzero(base)[0]:
        p = int(p); st = max(p * p, (a + p - 1) // p * p)
        seg[st - a::p] = False
    if a <= 1: seg[:2 - a] = False
    return int(seg.sum())


def walk_prob(A, B, T):
    """Простое симметричное блуждание из 0: вероятность дойти до +A раньше, чем до −B, не позже шага T."""
    dist = {0: 1.0}; hit = 0.0
    for _ in range(T):
        nd = {}
        for x, p in dist.items():
            for y in (x - 1, x + 1):
                if y == A: hit += p / 2
                elif y == -B: pass
                else: nd[y] = nd.get(y, 0) + p / 2
        dist = nd
    return hit


def subsets_count(M, k, S):
    """Число k-элементных подмножеств {1..M} с суммой S."""
    dp = [[0] * (S + 1) for _ in range(k + 1)]; dp[0][0] = 1
    for v in range(1, M + 1):
        for j in range(k, 0, -1):
            row, prev = dp[j], dp[j - 1]
            for s in range(S, v - 1, -1): row[s] += prev[s - v]
    return dp[k][S]


def make(fam, seed):
    r = random.Random(f'{fam}:{seed}')
    if fam == 'PRIMES':
        a = r.randint(10 ** 6, 10 ** 9); L = r.choice([2000, 10000, 50000, 200000])
        return dict(fam=fam, kind='count', text=f'Сколько простых чисел в отрезке от {a} до {a + L} включительно?', truth=primes_in(a, a + L))
    if fam == 'DIGSUM':
        k = r.choice([2, 3, 7, 11]); n = r.randint(300, 3000)
        return dict(fam=fam, kind='count', text=f'Чему равна сумма десятичных цифр числа {k}^{n}?', truth=sum(map(int, str(k ** n))))
    if fam == 'WALK':
        A, B, T = r.randint(3, 15), r.randint(3, 15), r.randint(20, 300)
        return dict(fam=fam, kind='prob', text=(f'Частица начинает в точке 0 и каждый шаг с вероятностью 1/2 сдвигается на +1 или на −1. '
                    f'Какова вероятность, что она достигнет точки +{A} раньше, чем точки −{B}, и не позже чем за {T} шагов?'), truth=walk_prob(A, B, T))
    if fam == 'SUBSETS':
        M, k = r.randint(30, 80), r.randint(4, 8)
        mid = k * (M + 1) // 2; S = mid + r.randint(-k * M // 6, k * M // 6)
        return dict(fam=fam, kind='count', text=f'Сколько существует {k}-элементных подмножеств множества {{1, 2, …, {M}}} с суммой элементов ровно {S}?',
                    truth=subsets_count(M, k, S))
    raise ValueError(fam)


NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'


def prompt(q):
    if q['kind'] == 'count':
        ask = ('Нужна оценка, точный подсчёт в уме не требуется. Верни: estimate — твоя лучшая оценка (число); '
               'lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; reasoning — кратко, как оценивал (до 5 фраз).')
    else:
        ask = ('Нужна оценка вероятности. Верни: estimate — твоя лучшая оценка (от 0 до 1); lo и hi — границы интервала, в который '
               'правильное значение попадает с вероятностью 80 %; reasoning — кратко, как оценивал (до 5 фраз).')
    return f'{NO_TOOLS}\n\nВопрос: {q["text"]}\n\n{ask}'


if __name__ == '__main__':
    tag, seed0 = sys.argv[1], int(sys.argv[2]); fams = sys.argv[3].split(',')
    qs = []
    for i, f in enumerate(fams):
        q = make(f, seed0 + i); q['id'] = f'{f}-{seed0 + i}'; qs.append(q)
        print(q['id'], q['truth'], q['text'][:90])
    os.makedirs(tag, exist_ok=True)
    json.dump(qs, open(f'{tag}/questions.json', 'w'), ensure_ascii=False, indent=1)
