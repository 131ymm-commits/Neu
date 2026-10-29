# Второй пересчёт меток main/rep: своё среднее по R = 4000 (функции sim SELECT-01), своя сортировка с ничьими по sha256,
# сверка top4_4000 с truth/<выборка>.json; плюс доля задач, где метки шатки (z45 < 2), и разброс числа меток.
import hashlib, json, math, os, sys, time
EXP = '/home/claude/neu/experiments'; S2 = f'{EXP}/2026-10-29_SCORE-02'
sys.path.insert(0, f'{EXP}/2026-10-07_SELECT-01')
import sim
SRC = dict(main=f'{EXP}/2026-10-15_THINK-01', rep=f'{EXP}/2026-10-21_PRECOND-01')
for smp in sys.argv[1:]:
    salt = open(f'{S2}/salts/{smp}_salt.txt').read().strip()
    T = json.load(open(f'{S2}/truth/{smp}.json'))
    assert T['salt_sha256'] == hashlib.sha256(salt.encode()).hexdigest()
    bad = []; t0 = time.time(); n = 0
    for t, v in sorted(T['tasks'].items()):
        tk = json.load(open(f'{SRC[smp]}/tasks/{t}.json')); pl = json.load(open(f'{SRC[smp]}/pools/{t}.json'))
        seeds = [int(hashlib.sha256(f'{salt}|{tk["seed"]}|{r}'.encode()).hexdigest()[:12], 16) for r in range(4000)]
        noises = [sim.NOISE['WH'](tk, z) for z in seeds]
        m = [sum(sim.SIM['WH'](tk, c['plan'], nz) for nz in noises) / 4000 for c in pl]
        order = sorted(range(8), key=lambda i: (-m[i], hashlib.sha256(f'{t}|{i}'.encode()).hexdigest()))
        top = sorted(order[:4])
        if top != v['top4_4000'] or max(abs(a - b) for a, b in zip(m, v['truth4000'])) > 1e-9:
            bad.append(t)
        n += 1
    print(smp, 'задач', n, 'расхождений меток/средних', len(bad), bad[:5], f'{time.time() - t0:.0f} с')
