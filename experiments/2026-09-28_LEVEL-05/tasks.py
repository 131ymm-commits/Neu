# LEVEL-05: задачи «произведение M матриц 2×2 по модулю простого p». Правда — код, вне репозитория (/root/level5_secret).
# Правда считается двумя способами: слева направо и деревом (ассоциативность) — должны совпасть.
#   python3 tasks.py <tag> <seed> <N> [<N> ...]   → tasks/<tag>.json (матрицы, p, листья по 10), правда в секрете
import json, os, sys, random
SECRET = '/root/level5_secret'; LEAF = 10
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
def make(seed, N):
    r = random.Random(f'L5:{seed}:{N}')
    p = r.randrange(10**8, 10**9)
    while not is_prime(p): p += 1
    Ms = [[[r.randrange(0, 1000), r.randrange(0, 1000)], [r.randrange(0, 1000), r.randrange(0, 1000)]] for _ in range(LEAF * N)]
    t1, t2 = prod_lr(Ms, p), prod_tree(Ms, p); assert t1 == t2
    leaves = [prod_lr(Ms[i*LEAF:(i+1)*LEAF], p) for i in range(N)]
    return dict(id=f'M{N}-{seed}', N=N, p=p, matrices=Ms), dict(truth=t1, leaves=leaves)
if __name__ == '__main__':
    tag, seed, Ns = sys.argv[1], int(sys.argv[2]), [int(x) for x in sys.argv[3:]]
    os.makedirs(SECRET, exist_ok=True); os.makedirs('tasks', exist_ok=True)
    pub, sec = [], {}
    for N in Ns:
        q, t = make(seed, N); pub.append(q); sec[q['id']] = t
    json.dump(pub, open(f'tasks/{tag}.json', 'w')); json.dump(sec, open(f'{SECRET}/{tag}.json', 'w'))
    print(f"{len(pub)} задач ({', '.join(q['id'] for q in pub)}) → tasks/{tag}.json; правда (два способа совпали) → {SECRET}/{tag}.json")
