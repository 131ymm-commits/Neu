# Независимый пересчёт меток «в четвёрке лучших» по R = 4000 (проверяльщик SCORE-01, линза 2).
# Свой код: зёрна шума — прямо по формуле sim.noise_seeds (sha256(соль|зерно|r)[:12]), среднее, сортировка, ничьи — sha256(задача|i).
import hashlib, json, os, sys, time
SEL = '/home/claude/neu/experiments/2026-10-07_SELECT-01'
SC = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
sys.path.insert(0, SEL)
import sim
def seeds(salt, tseed, R):
    return [int(hashlib.sha256(f'{salt}|{tseed}|{r}'.encode()).hexdigest()[:12], 16) for r in range(R)]
def salt_of(s):
    return open(os.path.join(SC, 'pilot_salt.txt')).read().strip() if s == 'pilot' else open(os.path.join(SEL, 'salts', f'{s}_salt.txt')).read().strip()
ids = dict(pilot=list(range(7001, 7013)) + list(range(7301, 7313)), main=list(range(8001, 8101)), rep=list(range(8101, 8201)))
sample = sys.argv[1]; only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
s = salt_of(sample)
chk = json.load(open(os.path.join(SC, 'truth', f'check_{sample}.json')))['tasks']
tru = json.load(open(os.path.join(SC, 'truth', f'{sample}.json')))['tasks']
out = {}; t0 = time.time()
for k in ids[sample]:
    t = f'WH_{k}'
    if not os.path.exists(os.path.join(SEL, 'pools', f'{t}.json')): continue
    if only and t not in only: continue
    tk = json.load(open(os.path.join(SEL, 'tasks', f'{t}.json'))); pl = json.load(open(os.path.join(SEL, 'pools', f'{t}.json')))
    sd = seeds(s, tk['seed'], 4000)
    dem = [sim.noise_wh(tk, x) for x in sd]                 # спрос одной реализации общий для всех кандидатов
    V = [[sim.simulate_wh(tk, c['plan'], d) for d in dem] for c in pl]
    m1 = [round(sum(v[:1000]) / 1000, 2) for v in V]; m4 = [sum(v) / 4000 for v in V]
    h = lambda i: hashlib.sha256(f'{t}|{i}'.encode()).hexdigest()
    top4 = sorted(sorted(range(8), key=lambda i: (-m4[i], h(i)))[:4])
    top1 = sorted(sorted(range(8), key=lambda i: (-m1[i], h(i)))[:4])
    out[t] = dict(top4=top4, same_as_check=top4 == chk[t]['top4_4000'], m1_same=m1 == tru[t]['truth'], top1_same_check=top1 == chk[t]['top4_1000'],
                  gap45_4000=sorted(m4, reverse=True)[3] - sorted(m4, reverse=True)[4])
print(sample, 'задач', len(out), 'top4(4000) совпала с check:', sum(v['same_as_check'] for v in out.values()),
      '| первые 1000 = sim.truth:', sum(v['m1_same'] for v in out.values()), '| top4(1000) = check:', sum(v['top1_same_check'] for v in out.values()),
      '| время', round(time.time() - t0, 1), 'с')
json.dump(out, open(f'/tmp/claude-0/-home-claude/8c9bf095-e181-55d3-b75e-353e8e0f2d42/scratchpad/lens/relabel_{sample}.json', 'w'), indent=0)
