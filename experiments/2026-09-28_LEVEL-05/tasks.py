# LEVEL-05: задачи «произведение M матриц 2×2 по модулю простого p». Правда — код, вне репозитория (/root/level5_secret).
#
# Ветвь организаций (решение совета 13 + твёрдые требования Скептика 1–2):
#   * ВЛОЖЕННАЯ генерация: на зерно — одно p и 200 матриц; N = 20 берёт все, N = 10 — половины, N = 5 — четверти;
#     лист = 10 матриц. assert: правда(N=20) = правда(первая N=10) · правда(вторая N=10) mod p (и то же для четвертей).
#   * Зёрна оценки — HMAC-SHA256(salt, '<ns>:<i>'); соль лежит вне репозитория (/root/level5_secret/salt),
#     в репозиторий пишется только sha256(соли) — файл salt_sha256.txt (для PREREG).
#   * Публичный файл задач (tasks/<tag>.json) содержит только номер, p и матрицы — без зерна и без правды.
#
#   python3 tasks.py salt                                  → создать соль (если её нет), записать salt_sha256.txt
#   python3 tasks.py nested <tag> <ns> <n> [<offset>]      → n вложенных задач из зёрен HMAC(salt, ns:i), i = offset…
#                                                           ns: eval (оценка), hold (отложенные), mock (сухой прогон)
#   python3 tasks.py calib2 <tag>                          → калибровка на новых зёрнах: 20 сборок, 12 задач M=10, 12 задач M=5
#   python3 tasks.py <tag> <seed> <N> [<N> ...]            → старый формат (smoke/calib), оставлен для воспроизводимости
import json, os, sys, random, hmac, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = '/root/level5_secret'; SALT = f'{SECRET}/salt'; SALT_HASH = f'{HERE}/salt_sha256.txt'
LEAF = 10; NLEAF = 20; NMAT = LEAF * NLEAF
def is_prime(n):
    if n < 2: return False
    for q in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % q == 0: return n == q
    d, s = n - 1, 0
    while d % 2 == 0: d //= 2; s += 1
    for a in (2, 3, 5, 7, 11, 13, 17):
        x = pow(a, d, n)
        if x in (1, n - 1): continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1: break
        else: return False
    return True
def mul(A, B, p): return [[(A[0][0]*B[0][0] + A[0][1]*B[1][0]) % p, (A[0][0]*B[0][1] + A[0][1]*B[1][1]) % p], [(A[1][0]*B[0][0] + A[1][1]*B[1][0]) % p, (A[1][0]*B[0][1] + A[1][1]*B[1][1]) % p]]
def prod_lr(Ms, p):
    R = [[1, 0], [0, 1]]
    for M in Ms: R = mul(R, M, p)
    return R
def prod_tree(Ms, p):
    if len(Ms) == 1: return Ms[0]
    m = len(Ms) // 2; return mul(prod_tree(Ms[:m], p), prod_tree(Ms[m:], p), p)
def tr(A): return [[A[0][0], A[1][0]], [A[0][1], A[1][1]]]

# --- дерево организации: то же правило деления, что в org_step.js (split = lo + floor((hi - lo) / 2)) ---
def split(lo, hi): return lo + (hi - lo) // 2
def tree_spans(lo, hi):
    """Все узлы вложенного дерева над листами [lo, hi): список (lo, hi); листья — hi - lo == 1."""
    out = [(lo, hi)]
    if hi - lo > 1:
        m = split(lo, hi); out += tree_spans(lo, m) + tree_spans(m, hi)
    return out

# --- соль и зёрна (Скептик 2) ---
def make_salt():
    os.makedirs(SECRET, mode=0o700, exist_ok=True)
    if not os.path.exists(SALT):
        fd = os.open(SALT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, os.urandom(32).hex().encode()); os.close(fd); print('новая соль →', SALT)
    h = hashlib.sha256(open(SALT, 'rb').read()).hexdigest()
    open(SALT_HASH, 'w').write(h + '\n'); print('sha256(соли) =', h, '→', SALT_HASH); return h
def seed_of(ns, i):
    if not os.path.exists(SALT): raise SystemExit('нет соли: python3 tasks.py salt')
    salt = open(SALT, 'rb').read()
    h = hashlib.sha256(salt).hexdigest()
    if os.path.exists(SALT_HASH) and open(SALT_HASH).read().strip() != h: raise SystemExit('соль не совпадает с salt_sha256.txt')
    return hmac.new(salt, f'{ns}:{i}'.encode(), hashlib.sha256).hexdigest()[:24]

# --- вложенная задача (Скептик 1) ---
def make_nested(seed):
    r = random.Random(f'L5nest:{seed}')
    p = r.randrange(10**8, 10**9)
    while not is_prime(p): p += 1
    Ms = [[[r.randrange(0, 1000), r.randrange(0, 1000)], [r.randrange(0, 1000), r.randrange(0, 1000)]] for _ in range(NMAT)]
    leaves = [prod_lr(Ms[i*LEAF:(i+1)*LEAF], p) for i in range(NLEAF)]
    spans = {}
    for lo, hi in tree_spans(0, NLEAF):
        spans[f'{lo}:{hi}'] = prod_lr(Ms[lo*LEAF:hi*LEAF], p)
    prefix = []; R = [[1, 0], [0, 1]]
    for M in Ms: R = mul(R, M, p); prefix.append(R)                 # prefix[k-1] = M1·…·Mk
    # проверки правды вторым способом
    whole = prod_lr(Ms, p)
    assert whole == prod_tree(Ms, p) == prefix[-1] == spans['0:20']
    h1, h2 = prod_lr(Ms[:100], p), prod_lr(Ms[100:], p)
    assert whole == mul(h1, h2, p), 'N=20 ≠ N=10 · N=10'               # требование Скептика 1
    for a in (0, 100):
        q1, q2 = prod_lr(Ms[a:a+50], p), prod_lr(Ms[a+50:a+100], p)
        assert prod_lr(Ms[a:a+100], p) == mul(q1, q2, p), 'N=10 ≠ N=5 · N=5'
    assert spans['0:10'] == h1 and spans['10:20'] == h2 and spans['0:5'] == prod_lr(Ms[:50], p)
    for lo, hi in tree_spans(0, NLEAF):                              # каждый узел = произведение детей
        if hi - lo > 1:
            m = split(lo, hi); assert spans[f'{lo}:{hi}'] == mul(spans[f'{lo}:{m}'], spans[f'{m}:{hi}'], p)
    for i in range(NLEAF):                                           # путь «транспонированный обратный»: (M1…M10)ᵀ = M10ᵀ…M1ᵀ
        assert tr(prod_lr([tr(M) for M in reversed(Ms[i*LEAF:(i+1)*LEAF])], p)) == leaves[i]
        a = i * LEAF                                                 # путь «половины»: (M1…M5)(M6…M10)
        assert mul(prod_lr(Ms[a:a+5], p), prod_lr(Ms[a+5:a+10], p), p) == leaves[i]
    halves = [[prod_lr(Ms[i*LEAF:i*LEAF+5], p), prod_lr(Ms[i*LEAF+5:(i+1)*LEAF], p)] for i in range(NLEAF)]
    return dict(p=p, matrices=Ms), dict(seed=seed, p=p, leaves=leaves, halves=halves, spans=spans, prefix=prefix, truth=whole)

def nested(tag, ns, n, offset=0):
    os.makedirs(SECRET, mode=0o700, exist_ok=True); os.makedirs(f'{HERE}/tasks', exist_ok=True)
    pub, sec = [], {}
    for i in range(offset, offset + n):
        q, t = make_nested(seed_of(ns, i)); tid = f'{ns[0].upper()}{i}'
        pub.append(dict(id=tid, **q)); sec[tid] = t
    json.dump(pub, open(f'{HERE}/tasks/{tag}.json', 'w')); json.dump(dict(ns=ns, tasks=sec), open(f'{SECRET}/{tag}.json', 'w'))
    print(f'{n} вложенных задач ({pub[0]["id"]}…{pub[-1]["id"]}, ns={ns}) → tasks/{tag}.json; правда (asserts прошли) → {SECRET}/{tag}.json')

def calib2(tag, n_asm=20, n10=12, n5=12):
    """Калибровка перед заморозкой макромодели, на НОВЫХ зёрнах (пространство 'L5cal2', не пересекается с оценкой (HMAC соли),
    с прежней калибровкой ('L5:<seed>:<N>', C*-70x) и с моками):
      A0…A{n_asm−1}   — одно произведение A·B, элементы < p (как входы сборки)            → ε сборки
      T0…T{n10−1}     — 10 матриц (как лист): первичный путь P и путь TR                 → ε листа, ε_TR, ρ(P, TR)
      F0…F{n5−1}      — 5 матриц (как половина листа)                                     → ε₅ (путь «половины»)"""
    os.makedirs(SECRET, mode=0o700, exist_ok=True); os.makedirs(f'{HERE}/tasks', exist_ok=True)
    def prime(r):
        p = r.randrange(10**8, 10**9)
        while not is_prime(p): p += 1
        return p
    pub, sec = [], {}
    for i in range(n_asm):
        r = random.Random(f'L5cal2:asm:{i}'); p = prime(r)
        A, B = ([[r.randrange(0, p), r.randrange(0, p)], [r.randrange(0, p), r.randrange(0, p)]] for _ in range(2))
        tt = mul(A, B, p); assert tt == prod_lr([A, B], p) == tr(mul(tr(B), tr(A), p))
        pub.append(dict(id=f'A{i}', kind='asm', p=p, matrices=[A, B])); sec[f'A{i}'] = dict(p=p, truth=tt)
    for M, pre, n in ((10, 'T', n10), (5, 'F', n5)):
        for i in range(n):
            r = random.Random(f'L5cal2:{M}:{i}'); p = prime(r)
            Ms = [[[r.randrange(0, 1000), r.randrange(0, 1000)], [r.randrange(0, 1000), r.randrange(0, 1000)]] for _ in range(M)]
            tt = prod_lr(Ms, p); assert tt == prod_tree(Ms, p) == tr(prod_lr([tr(X) for X in reversed(Ms)], p))
            pub.append(dict(id=f'{pre}{i}', kind=f'm{M}', p=p, matrices=Ms)); sec[f'{pre}{i}'] = dict(p=p, truth=tt)
    json.dump(pub, open(f'{HERE}/tasks/{tag}.json', 'w')); json.dump(dict(ns='L5cal2', tasks=sec), open(f'{SECRET}/{tag}.json', 'w'))
    print(f'калибровка: {n_asm} сборок, {n10} задач M=10, {n5} задач M=5 → tasks/{tag}.json; правда (asserts прошли) → {SECRET}/{tag}.json')

# --- старый формат (smoke, calib) — не менялся ---
def make(seed, N):
    r = random.Random(f'L5:{seed}:{N}')
    p = r.randrange(10**8, 10**9)
    while not is_prime(p): p += 1
    Ms = [[[r.randrange(0, 1000), r.randrange(0, 1000)], [r.randrange(0, 1000), r.randrange(0, 1000)]] for _ in range(LEAF * N)]
    t1, t2 = prod_lr(Ms, p), prod_tree(Ms, p); assert t1 == t2
    leaves = [prod_lr(Ms[i*LEAF:(i+1)*LEAF], p) for i in range(N)]
    return dict(id=f'M{N}-{seed}', N=N, p=p, matrices=Ms), dict(truth=t1, leaves=leaves)

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'salt': make_salt()
    elif a[0] == 'nested': nested(a[1], a[2], int(a[3]), int(a[4]) if len(a) > 4 else 0)
    elif a[0] == 'calib2': calib2(a[1])
    else:
        tag, seed, Ns = a[0], int(a[1]), [int(x) for x in a[2:]]
        os.makedirs(SECRET, exist_ok=True); os.makedirs('tasks', exist_ok=True)
        pub, sec = [], {}
        for N in Ns:
            q, t = make(seed, N); pub.append(q); sec[q['id']] = t
        json.dump(pub, open(f'tasks/{tag}.json', 'w')); json.dump(sec, open(f'{SECRET}/{tag}.json', 'w'))
        print(f"{len(pub)} задач ({', '.join(q['id'] for q in pub)}) → tasks/{tag}.json; правда (два способа совпали) → {SECRET}/{tag}.json")
