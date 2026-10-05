# Экосистема: классы корма, отложенный набор (эталон ortools один раз, замена вырожденных по правилу), калибровочный набор для отбора поколения 0.
import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import gen_mkp, ortools_ref, greedy
# Редакция 05.10.2026: при n = 250, K = 6 все решатели поколения 0 находят оптимум (eco/ceiling_check.log); классы выбраны подбором трудности (eco/hardness_scan.log)
CLASSES = [(600, 40, 0.6, 'strong'), (1000, 10, 0.5, 'strong'), (2000, 20, 0.5, 'strong'), (3000, 30, 0.3, 'weak')]   # n, K, теснота, связь веса и ценности
def inst(seed, c): n, K, t, k = CLASSES[c]; return gen_mkp(seed, n, K, t, k)
def feed(base, t, M=12):   # корм поколения t: 4 класса × 3, зёрна base + 1000·t + i
    return [dict(inst(base + 1000 * t + i, i % 4), klass=i % 4) for i in range(M)]
if __name__ == '__main__':
    what = sys.argv[1]; D = '/root/solvers_secret'; os.makedirs(D, exist_ok=True)
    if what == 'holdout':   # 20 экземпляров, 5 на класс; вырожденный (ref − greedy < 0,1 % ref) заменяется следующим зерном того же класса
        dst = os.path.join(D, 'eco_holdout2.json'); out = json.load(open(dst)) if os.path.exists(dst) else dict(items=[], replaced=[])
        for c in range(4):
            have = [x for x in out['items'] if x['klass'] == c]; seed = 700000 + 1000 * c + len(have) + len([r for r in out['replaced'] if r['klass'] == c])
            while len(have) < 5:
                I = inst(seed, c); R = ortools_ref(I, 120, 4); g = greedy(I, 10, 0)['value']
                rec = dict(seed=seed, klass=c, ref=R['value'], bound=R['bound'], greedy=g)
                if R['value'] - g < 0.001 * R['value']: out['replaced'].append(rec)
                else: out['items'].append(rec); have.append(rec)
                json.dump(out, open(dst, 'w'), indent=1); print(rec, flush=True); seed += 1
    if what == 'calib':     # 8 экземпляров, 2 на класс, только жадный
        out = []
        for c in range(4):
            for j in range(2):
                I = inst(800000 + 10 * c + j, c); out.append(dict(seed=I['seed'], klass=c, greedy=greedy(I, 10, 0)['value']))
        json.dump(out, open('eco/calib_set.json', 'w'), indent=1); print(out)
