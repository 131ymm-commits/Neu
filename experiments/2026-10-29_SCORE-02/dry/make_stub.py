#!/usr/bin/env python3
"""SCORE-02, сухой прогон цепочки: заглушка выгрузки run_sealed2 (формат export) для выборки и K вызовов на задачу.
p вызова k для кандидата i = σ(a·z_i + c·u_i + s·e_ik): z_i — нормированная правда (метка — четвёрка лучших), u_i — общая для вызовов
ошибка кандидата, e_ik — своя ошибка вызова. При s > 0 и c малом согласие вызовов несёт сведения о правоте (заложенный эффект);
при s = 0 вызовы одинаковы, и источники совпадают (нуль). Доля потерь — половина «потерян», половина негодный ответ.
Головы не вызываются.
  python3 dry/make_stub.py <выборка> <выход.jsonl> [a] [c] [s] [доля_потерь] [зерно] [K] [задач_без_записи]"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import score02 as S  # noqa: E402


def main():
    a_ = sys.argv
    sample, out = a_[1], a_[2]
    a = float(a_[3]) if len(a_) > 3 else 1.0
    c = float(a_[4]) if len(a_) > 4 else 0.5
    s = float(a_[5]) if len(a_) > 5 else 1.0
    lost = float(a_[6]) if len(a_) > 6 else 0.0
    rng = random.Random(int(a_[7]) if len(a_) > 7 else 1)
    K = int(a_[8]) if len(a_) > 8 else 5
    n_drop = int(a_[9]) if len(a_) > 9 else 0
    lab = S.labels_for(sample)
    tasks = S.sample_tasks(sample)
    drop = set(rng.sample(tasks, n_drop)) if n_drop else set()
    with open(out, 'w', encoding='utf-8') as fh:
        for t in tasks:
            if t in drop:
                continue
            pm = S.perm(t)
            z = [1.0 if i in lab[t] else -1.0 for i in range(8)]
            u = [rng.gauss(0, 1) for _ in range(8)]
            for k in range(K):
                jid = f'{t}|{S.ARM}|{k}'
                r = rng.random()
                if r < lost / 2:
                    fh.write(json.dumps(dict(id=jid, error='потерян (заглушка)', inp=0, out=0, cost_usd=None), ensure_ascii=False) + '\n')
                    continue
                if r < lost:
                    fh.write(json.dumps(dict(id=jid, result={'p': [0.5] * 7}, inp=6000, out=2000, cost_usd=0.07), ensure_ascii=False) + '\n')
                    continue
                # показанный кандидат j — это кандидат пула pm[j]
                p = [round(1 / (1 + math.exp(-(a * z[pm[j]] + c * u[pm[j]] + s * rng.gauss(0, 1)))), 3) for j in range(8)]
                fh.write(json.dumps(dict(id=jid, result={'p': p}, inp=6000, out=3000, cost_usd=0.07), ensure_ascii=False) + '\n')
    print('заглушка:', out, 'задач без записи:', len(drop))


if __name__ == '__main__':
    main()
