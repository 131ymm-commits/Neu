# EVAL-01 опыт Б: генератор новых задач с точной правдой от кода (правда считается ПОСЛЕ прогона голов, вне репозитория).
#   python3 gen.py <seed> <на_семью> <выход.jsonl>
# Семьи: TWIN (близнецы на отрезке), COLLATZ (варианты правила и счёта), SUBK (k-подмножества с условиями), MODSQ (итерации по модулю, огромный K).
import json, random, sys, math
def logu(r, lo, hi): return int(math.exp(r.uniform(math.log(lo), math.log(hi))))
def twin(r):
    W = r.choice([10**5, 10**6, 10**7, 5 * 10**7]); A = logu(r, 10**6, 10**12); B = A + W; v = r.choice(['pairs', 'members'])
    if v == 'pairs': t = f'Сколько существует простых p, таких что p + 2 тоже простое и {A} ≤ p и p + 2 ≤ {B}?'
    else: t = f'Сколько простых чисел q на отрезке [{A}; {B}] входят хотя бы в одну пару простых-близнецов (q − 2 или q + 2 простое; второе число пары может лежать вне отрезка)?'
    return dict(family='TWIN', variant=v, params=dict(A=A, B=B), task=t)
def collatz(r):
    n = logu(r, 10**6, 10**18); v = r.choice(['steps', 'short', 'odd', 'max'])
    t = {'steps': f'Правило: если n чётно, n → n/2, иначе n → 3n + 1. За сколько применений правила число {n} впервые станет равно 1?',
         'short': f'Правило: если n чётно, n → n/2, иначе n → (3n + 1)/2 (одно применение правила). За сколько применений правила число {n} впервые станет равно 1?',
         'odd': f'Правило: если n чётно, n → n/2, иначе n → 3n + 1. Выпишем путь от {n} до первого появления 1, включая оба конца. Сколько нечётных чисел в этом пути (с повторами, если есть)?',
         'max': f'Правило: если n чётно, n → n/2, иначе n → 3n + 1. Какое наибольшее число встретится на пути от {n} до первого появления 1 (включая само {n})?'}[v]
    return dict(family='COLLATZ', variant=v, params=dict(n=n), task=t)
def subk(r):
    k = r.choice([4, 5, 6]); N = r.randint(25, 160); v = r.choice(['sum', 'nocons', 'mod', 'odd'])
    mid = k * (N + 1) // 2; S = r.randint(max(k * (k + 1) // 2, mid - N), mid + N // 2)
    if v == 'sum': t = f'Сколько существует {k}-элементных подмножеств множества {{1, 2, …, {N}}} с суммой элементов ровно {S}?'; p = dict(k=k, N=N, S=S)
    elif v == 'nocons': t = f'Сколько существует {k}-элементных подмножеств множества {{1, 2, …, {N}}} с суммой ровно {S}, в которых никакие два элемента не являются соседними числами (не отличаются на 1)?'; p = dict(k=k, N=N, S=S)
    elif v == 'mod':
        m = r.choice([7, 11, 13, 17]); res = r.randrange(m); t = f'Сколько существует {k}-элементных подмножеств множества {{1, 2, …, {N}}}, сумма элементов которых даёт остаток {res} при делении на {m}?'; p = dict(k=k, N=N, m=m, r=res)
    else: t = f'Сколько существует {k}-элементных подмножеств множества {{1, 2, …, {N}}} с суммой ровно {S}, все элементы которых нечётны?'; p = dict(k=k, N=N, S=S)
    return dict(family='SUBK', variant=v, params=p, task=t)
def modsq(r):
    v = r.choice(['rho', 'pow2']); K = logu(r, 10**6, 10**18)
    if v == 'rho':
        m = logu(r, 10**6, 10**11); c = r.randrange(1, m); x0 = r.randrange(m)
        t = f'Последовательность: x₀ = {x0}, x_(i+1) = (x_i² + {c}) mod {m}. Найдите x_{K} (индекс {K}).'; p = dict(m=m, c=c, x0=x0, K=K)
    else:
        m = r.randrange(10**8, 10**12); a = r.randrange(2, m)
        t = f'Последовательность: x₀ = {a}, x_(i+1) = x_i² mod {m}. Найдите x_{K} (индекс {K}).'; p = dict(m=m, a=a, K=K)
    return dict(family='MODSQ', variant=v, params=p, task=t)
if __name__ == '__main__':
    seed, per, dst = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]; r = random.Random(seed); out = []
    for fam in (twin, collatz, subk, modsq):
        for i in range(per): d = fam(r); d['id'] = f"{d['family']}-{seed}-{i:03d}"; out.append(d)
    with open(dst, 'w') as f:
        for d in out: f.write(json.dumps(d, ensure_ascii=False) + '\n')
    print(len(out), 'задач →', dst)
