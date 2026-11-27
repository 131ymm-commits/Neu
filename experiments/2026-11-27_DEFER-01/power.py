"""DEFER-01: мощность проверок A, B, C до прогона (оценка Монте-Карло, не точное число).
Проверка — перестановка знаков на 20 сидах, односторонний уровень 0,005. В основной сверке перебор знаков полный (2^20);
здесь, чтобы посчитать тысячи опытов, p оценивается по 20 000 случайных раскладов знаков.
Сценарии взяты из пилота на сидах 996–998 (три сида на задачу — оценка грубая).  python3 power.py → power.json"""
import json, os
import numpy as np
ALPHA, N, SIMS, FLIPS = 0.005, 20, 2000, 20000
r = np.random.default_rng(0)
signs = r.choice([-1.0, 1.0], size=(FLIPS, N))

def power(draw):
    hit = rev = 0
    for _ in range(SIMS):
        m = draw(); s = signs @ m; obs = m.sum()
        p_up = (np.sum(s >= obs - 1e-12) + 1) / (FLIPS + 1); p_dn = (np.sum(s <= obs + 1e-12) + 1) / (FLIPS + 1)
        hit += p_up <= ALPHA; rev += p_dn <= ALPHA
    return round(hit / SIMS, 3), round(rev / SIMS, 3)

out = {'_': 'мощность (доля «подтверждено») и доля «обратный эффект»; оценка Монте-Карло'}
# A (T2): в доле pi сидов разность W(M0) − W(M25) около +0,5 (без свежих застряли, с четвертью свежих решили); в 5 % — обратная; иначе 0
def draw_A(pi):
    def f():
        u = r.random(N); return np.where(u < pi, 0.5 * r.uniform(0.9, 1.1, N), np.where(u > 0.95, -0.5, 0.0))
    return f
out['A_T2'] = {f'доля сидов с эффектом {pi}': power(draw_A(pi)) for pi in (0.3, 0.5, 0.7, 0.9)}
out['A_T2']['нет эффекта (ложный уровень)'] = power(lambda: np.where(r.random(N) < 0.5, 0.5, -0.5) * (r.random(N) < 0.6))
# B (T3): минус наклон по сидам ~ N(mu, 0,33); в пилоте 0,577, 0,273, −0,082 (среднее 0,256)
out['B_T3'] = {f'среднее {mu}': power(lambda mu=mu: r.normal(mu, 0.33, N)) for mu in (0.0, 0.128, 0.256, 0.384)}
# C (все задачи): среднее по задачам внутри сида ~ N(mu, 0,30); в пилоте среднее 0,270
out['C_all'] = {f'среднее {mu}': power(lambda mu=mu: r.normal(mu, 0.30, N)) for mu in (0.0, 0.135, 0.27)}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'power.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
