#!/usr/bin/env python3
"""SCORE-01, сухой прогон цепочки: заглушка выгрузки run_sealed2 (формат export) для выборки, рук и повторов.
Ответ заглушки: p = σ(a_руки · z(правда) + шум) — навык a_руки задаётся, чтобы проверить, что анализ видит заложенный эффект;
задаются доля негодных/потерянных ответов, число повторов на клетку и число задач без единой записи (как задания,
у которых итога нет и которые export не выгружает). Головы не вызываются.
  python3 dry/make_stub.py <выборка> <руки через запятую> <a через запятую> <выход.jsonl> [доля_потерь] [зерно] [повторов] [задач_без_записи]"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import score01 as S  # noqa: E402

sample, arms, skills, out = sys.argv[1], sys.argv[2].split(','), [float(x) for x in sys.argv[3].split(',')], sys.argv[4]
lost = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
rng = random.Random(int(sys.argv[6]) if len(sys.argv) > 6 else 1)
nrep = int(sys.argv[7]) if len(sys.argv) > 7 else 1
n_drop = int(sys.argv[8]) if len(sys.argv) > 8 else 0
tru = json.load(open(os.path.join(HERE, 'truth', f'{sample}.json')))['tasks']
tasks = S.sample_tasks(sample)
drop = set(rng.sample(tasks, n_drop)) if n_drop else set()
with open(out, 'w', encoding='utf-8') as fh:
    for t in tasks:
        if t in drop:
            continue
        tr = tru[t]['truth']; pm = S.perm(t)
        m = sum(tr) / 8; sd = math.sqrt(sum((v - m) ** 2 for v in tr) / 8) or 1.0
        for arm, a in zip(arms, skills):
            for rep in range(nrep):
                jid = f'{t}|{arm}|{rep}'
                u = rng.random()
                if u < lost / 2:
                    fh.write(json.dumps(dict(id=jid, error='потерян (заглушка)', inp=0, out=0, cost_usd=None), ensure_ascii=False) + '\n')
                    continue
                if u < lost:
                    fh.write(json.dumps(dict(id=jid, result={'p': [0.5] * 7}, inp=6000, out=2000, cost_usd=0.07), ensure_ascii=False) + '\n')
                    continue
                # показанный кандидат i — это кандидат пула pm[i]
                p = [round(1 / (1 + math.exp(-(a * (tr[pm[i]] - m) / sd + rng.gauss(0, 1)))), 3) for i in range(8)]
                fh.write(json.dumps(dict(id=jid, result={'p': p}, inp=6000, out=2000 + int(500 * a), cost_usd=0.07), ensure_ascii=False) + '\n')
print('заглушка:', out, 'задач без записи:', len(drop))
