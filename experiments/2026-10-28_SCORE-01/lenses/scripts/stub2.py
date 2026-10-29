# Заглушка выгрузки run_sealed2 для расширенного сухого прогона SCORE-01 (проверяльщик): повторы, выборка rep, потери, выпадение задач.
# p = σ(a·z(правда кандидата пула) + шум·k); у руки свои a (навык), k (разброс) и выходные токены. Головы не вызываются.
import json, math, os, random, sys
X = sys.argv[1]                       # папка копии опыта
sys.path.insert(0, X)
import score01 as S
sample, model, out = sys.argv[2], sys.argv[3], sys.argv[4]
lost = float(sys.argv[5]); drop_tasks = int(sys.argv[6]); seed = int(sys.argv[7])
rng = random.Random(seed)
ARM = dict(opus=dict(LOG=(1.0, 1.0, 4000), WIN=(1.0, 1.0, 4000), NONE=(0.5, 1.0, 3000)),
           haiku=dict(LOG=(0.6, 1.5, 15000), WIN=(0.6, 1.5, 15000), NONE=(1.0, 1.5, 22000)))[model]
reps = ('0',) if model == 'opus' else ('0', '1')
tru = json.load(open(os.path.join(X, 'truth', f'{sample}.json')))['tasks']
tasks = S.sample_tasks(sample)
dropped = set(tasks[-drop_tasks:]) if drop_tasks else set()
n = 0
with open(out, 'w', encoding='utf-8') as fh:
    for t in tasks:
        if t in dropped:
            continue                    # задача целиком без итоговых записей (как прогон, не дошедший до конца)
        tr = tru[t]['truth']; pm = S.perm(t); m = sum(tr) / 8; sd = math.sqrt(sum((v - m) ** 2 for v in tr) / 8) or 1.0
        for arm, (a, k, tok) in ARM.items():
            for rp in reps:
                jid = f'{t}|{arm}|{rp}'; u = rng.random(); n += 1
                if u < lost:
                    fh.write(json.dumps(dict(id=jid, result=None, error='потерян: заглушка', inp=0, out=0, cost_usd=None), ensure_ascii=False) + '\n'); continue
                p = [round(1 / (1 + math.exp(-(a * (tr[pm[i]] - m) / sd + rng.gauss(0, k)))), 3) for i in range(8)]
                fh.write(json.dumps(dict(id=jid, result={'p': p}, inp=7000, out=int(tok + rng.gauss(0, tok * 0.2)), cost_usd=0.05), ensure_ascii=False) + '\n')
print('заглушка', out, 'записей', n, 'выброшено задач', len(dropped))
