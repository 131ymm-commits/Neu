# Турнир решателей (совет 19): экземпляры, проверка, эталон ortools, жадный контроль, обвязка для кода голов.
# Классы: MAXSAT — взвешенный MaxSAT (максимизировать суммарный вес выполненных дизъюнктов);
#         MKP — множественный рюкзак (предметы с весом и ценностью, K рюкзаков с вместимостями; каждый предмет — не больше чем в один рюкзак; максимизировать ценность).
import json, os, sys, random, subprocess, tempfile, resource, time

def gen_maxsat(seed, n, ratio=4.3, k=3, wmax=100):
    r = random.Random(seed); m = int(ratio * n); cl = []
    for _ in range(m):
        vs = r.sample(range(1, n + 1), k); cl.append([v if r.random() < .5 else -v for v in vs])
    return dict(cls='MAXSAT', seed=seed, n=n, clauses=cl, weights=[r.randint(1, wmax) for _ in range(m)])
def gen_mkp(seed, n, K, tight=0.5, corr='weak'):
    r = random.Random(seed); w = [r.randint(10, 1000) for _ in range(n)]
    if corr == 'strong': v = [int(x * r.uniform(0.95, 1.05)) + 50 for x in w]           # сильно коррелированные — трудные
    else: v = [max(1, int(x * r.uniform(0.6, 1.4) + r.randint(-50, 50))) for x in w]   # слабо коррелированные
    cap_total = int(sum(w) * tight); caps = []
    for i in range(K):
        caps.append(cap_total // K + r.randint(-cap_total // (4 * K), cap_total // (4 * K)))
    return dict(cls='MKP', seed=seed, n=n, K=K, weights=w, values=v, caps=caps, tight=tight, corr=corr)

def score(inst, sol):
    """→ (допустимо, целевая функция). Решение MAXSAT: список 0/1 длины n (значение переменной i+1). MKP: список длины n, элемент — номер рюкзака 0..K-1 или -1."""
    try:
        if inst['cls'] == 'MAXSAT':
            if not isinstance(sol, list) or len(sol) != inst['n'] or any(x not in (0, 1, True, False) for x in sol): return False, 0
            s = 0
            for c, w in zip(inst['clauses'], inst['weights']):
                if any((sol[abs(l) - 1] == 1) == (l > 0) for l in c): s += w
            return True, s
        if not isinstance(sol, list) or len(sol) != inst['n'] or any((not isinstance(x, int)) or x < -1 or x >= inst['K'] for x in sol): return False, 0
        load = [0] * inst['K']; val = 0
        for i, b in enumerate(sol):
            if b >= 0: load[b] += inst['weights'][i]; val += inst['values'][i]
        return all(l <= c for l, c in zip(load, inst['caps'])), val
    except Exception: return False, 0

def ortools_ref(inst, secs=120, workers=1):
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    if inst['cls'] == 'MAXSAT':
        x = [m.NewBoolVar(f'x{i}') for i in range(inst['n'])]; sat = []
        for j, c in enumerate(inst['clauses']):
            s = m.NewBoolVar(f's{j}'); lits = [x[abs(l) - 1] if l > 0 else x[abs(l) - 1].Not() for l in c]
            m.AddBoolOr(lits).OnlyEnforceIf(s); sat.append(s)
        m.Maximize(sum(w * s for w, s in zip(inst['weights'], sat)))
    else:
        n, K = inst['n'], inst['K']; y = [[m.NewBoolVar(f'y{i}_{b}') for b in range(K)] for i in range(n)]
        for i in range(n): m.AddAtMostOne(y[i])
        for b in range(K): m.Add(sum(inst['weights'][i] * y[i][b] for i in range(n)) <= inst['caps'][b])
        m.Maximize(sum(inst['values'][i] * y[i][b] for i in range(n) for b in range(K)))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = secs; s.parameters.num_workers = workers; s.parameters.random_seed = 1
    st = s.Solve(m)
    if inst['cls'] == 'MAXSAT': sol = [int(s.Value(v)) for v in x]
    else: sol = [next((b for b in range(inst['K']) if s.Value(y[i][b])), -1) for i in range(inst['n'])]
    ok, val = score(inst, sol)
    return dict(value=val, ok=ok, optimal=st == cp_model.OPTIMAL, bound=s.BestObjectiveBound())

GREEDY_SRC = r'''
import json, sys, random, time
def main():
    inst = json.load(sys.stdin); t0 = time.process_time(); T = float(sys.argv[1]); r = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    if inst['cls'] == 'MAXSAT':
        n = inst['n']; C = inst['clauses']; W = inst['weights']
        occ = [[] for _ in range(n + 1)]
        for j, c in enumerate(C):
            for l in c: occ[abs(l)].append(j)
        x = [0] * (n + 1)
        # жадный старт: каждая переменная — в сторону большего веса вхождений
        for v in range(1, n + 1):
            p = sum(W[j] for j in occ[v] if v in C[j]); q = sum(W[j] for j in occ[v] if -v in C[j]); x[v] = 1 if p >= q else 0
        sg = [dict() for _ in range(n + 1)]
        for j, c in enumerate(C):
            for l in c: sg[abs(l)][j] = 1 if l > 0 else 0   # переменная делает дизъюнкт j истинным при значении sg
        nt = [sum(1 for l in c if (x[abs(l)] == 1) == (l > 0)) for c in C]
        cur = sum(w for w, k in zip(W, nt) if k > 0); best = cur; bx = x[:]
        def delta(v):
            d = 0
            for jj, want in sg[v].items():
                k = nt[jj] + (1 if (1 - x[v]) == want else -1)
                d += W[jj] * ((k > 0) - (nt[jj] > 0))
            return d
        uns = set(j for j, k in enumerate(nt) if k == 0); steps = 0
        while uns and (steps & 255 or time.process_time() - t0 < T):
            steps += 1
            j = r.choice(tuple(uns)) if len(uns) < 64 or steps & 7 else next(iter(uns))
            if r.random() < 0.3: v = abs(r.choice(C[j]))
            else: v = max((abs(l) for l in C[j]), key=delta)
            d = delta(v)
            for jj, want in sg[v].items():
                nt[jj] += 1 if (1 - x[v]) == want else -1
                if nt[jj] == 0: uns.add(jj)
                else: uns.discard(jj)
            x[v] = 1 - x[v]; cur += d
            if cur > best: best, bx = cur, x[:]
        print(json.dumps(bx[1:]))
    else:
        n, K = inst['n'], inst['K']; w, v, cap = inst['weights'], inst['values'], inst['caps']
        order = sorted(range(n), key=lambda i: -v[i] / w[i]); load = [0] * K; sol = [-1] * n
        for i in order:
            bs = [b for b in range(K) if load[b] + w[i] <= cap[b]]
            if bs: b = min(bs, key=lambda b: cap[b] - load[b] - w[i]); sol[i] = b; load[b] += w[i]
        def tot(): return sum(v[i] for i in range(n) if sol[i] >= 0)
        best = tot(); bsol = sol[:]
        while time.process_time() - t0 < T:
            i = r.randrange(n); j = r.randrange(n)
            if sol[i] >= 0 and sol[j] < 0 and v[j] > v[i]:
                b = sol[i]
                if load[b] - w[i] + w[j] <= cap[b]: load[b] += w[j] - w[i]; sol[j], sol[i] = b, -1
            elif sol[i] < 0:
                bs = [b for b in range(K) if load[b] + w[i] <= cap[b]]
                if bs: b = r.choice(bs); sol[i] = b; load[b] += w[i]
            t = tot()
            if t > best: best, bsol = t, sol[:]
        print(json.dumps(bsol))
main()
'''

def run_solver(src, inst, cpu_s=10, mem_mb=1024, args=(), core=None):
    """исполнить код решателя: stdin — экземпляр JSON, stdout — решение JSON. Лимит CPU и памяти, без сети, пустой каталог; core — ядро (taskset); cpu — процессорное время процесса."""
    def lim():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s + 1, cpu_s + 2)); resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20)); os.setsid()
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'solver.py'); open(f, 'w').write(src)
        env = {'PATH': '/usr/bin:/bin', 'HOME': d, 'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
        cmd = ([ 'taskset', '-c', str(core)] if core is not None else []) + [sys.executable, f, *map(str, args)]
        t0 = time.time(); inp = os.path.join(d, 'in.json'); open(inp, 'w').write(json.dumps(inst))
        outp = os.path.join(d, 'out.txt'); errp = os.path.join(d, 'err.txt')
        with open(inp) as fi, open(outp, 'w') as fo, open(errp, 'w') as fe:
            p = subprocess.Popen(cmd, stdin=fi, stdout=fo, stderr=fe, cwd=d, env=env, preexec_fn=lim)
            deadline = t0 + cpu_s * 3 + 10; st = None
            while st is None:
                pid, status, ru = os.wait4(p.pid, os.WNOHANG)
                if pid: st = status; break
                if time.time() > deadline: os.killpg(p.pid, 9); pid, status, ru = os.wait4(p.pid, 0); st = status; break
                time.sleep(0.05)
        cpu = ru.ru_utime + ru.ru_stime; wall = time.time() - t0
        try: sol = json.loads(open(outp).read().strip().splitlines()[-1])
        except Exception: return dict(ok=False, value=0, err=(open(errp).read() or 'нет вывода')[-300:], wall=wall, cpu=cpu)
        ok, val = score(inst, sol)
        return dict(ok=ok, value=val if ok else 0, err=None if ok else 'недопустимое решение', wall=wall, cpu=cpu)
def greedy(inst, cpu_s=10, seed=0): return run_solver(GREEDY_SRC, inst, cpu_s, args=(cpu_s - 0.5, seed))
def gap(ref, x, gr):
    """g = (ref − x)/(ref − greedy): 0 — как эталон, 1 — как жадный, > 1 — хуже жадного, < 0 — лучше эталона"""
    return (ref - x) / (ref - gr) if ref != gr else None

def run_solver_sb(src, inst, cpu_s=10, mem_mb=1024, args=(), core=None):
    """Песочница редакции 3 (совет 24): одноразовый процесс без сети (unshare -n), корень ФС только для чтения (unshare -m, remount ro),
    права nobody (setpriv), rlimit CPU/AS/NOFILE/NPROC, пустое окружение; stdin/stdout — открытые родителем файлы; CPU по rusage."""
    def lim():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s + 1, cpu_s + 2)); resource.setrlimit(resource.RLIMIT_AS, (mem_mb << 20, mem_mb << 20))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64)); resource.setrlimit(resource.RLIMIT_NPROC, (64, 64)); os.setsid()
    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755); f = os.path.join(d, 'solver.py'); open(f, 'w').write(src); os.chmod(f, 0o644)
        py = ([ 'taskset', '-c', str(core)] if core is not None else []) + [sys.executable, f, *map(str, args)]
        inner = 'mount -o remount,bind,ro / && exec setpriv --reuid=65534 --regid=65534 --clear-groups ' + ' '.join(map(lambda a: "'" + a.replace("'", "") + "'", py))
        cmd = ['unshare', '-n', '-m', 'sh', '-c', inner]
        env = {'PATH': '/usr/bin:/bin', 'HOME': d, 'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
        t0 = time.time(); inp = os.path.join(d, 'in.json'); open(inp, 'w').write(json.dumps(inst))
        outp = os.path.join(d, 'out.txt'); errp = os.path.join(d, 'err.txt')
        with open(inp) as fi, open(outp, 'w') as fo, open(errp, 'w') as fe:
            p = subprocess.Popen(cmd, stdin=fi, stdout=fo, stderr=fe, cwd=d, env=env, preexec_fn=lim)
            deadline = t0 + cpu_s * 3 + 10; st = None
            while st is None:
                pid, status, ru = os.wait4(p.pid, os.WNOHANG)
                if pid: st = status; break
                if time.time() > deadline: os.killpg(p.pid, 9); pid, status, ru = os.wait4(p.pid, 0); st = status; break
                time.sleep(0.05)
        cpu = ru.ru_utime + ru.ru_stime; wall = time.time() - t0
        try: sol = json.loads(open(outp).read().strip().splitlines()[-1])
        except Exception: return dict(ok=False, value=None, err=(open(errp).read() or 'нет вывода')[-300:], wall=wall, cpu=cpu)
        ok, val = score(inst, sol)
        return dict(ok=ok, value=val if ok else None, err=None if ok else 'недопустимое решение', wall=wall, cpu=cpu)
