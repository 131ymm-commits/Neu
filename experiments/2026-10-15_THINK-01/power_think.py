# THINK-01: мощность первичного семейства до регистрации (ворота: «мощность считать до прогона»).
# Модель: регрет H_1 по задаче — один голос C_N@high из пилота (30 голосов, бутстреп); B_blind и D_N — per_task SELECT-01
# (основная выборка и повтор вместе, 199 задач). Эффект ослабляется: H_1' = B + s·(H_1 − B) не годится (шкала), поэтому
# сдвиг: H_1 + (1 − s)·Δ, Δ = среднее (B_blind − H_1) пилота-модели. Тест — знаковые перестановки (M = 4000), Холм на двух.
import json, os, statistics as st, sys
import numpy as np
SEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '2026-10-07_SELECT-01')
pt = {**json.load(open(f'{SEL}/main_an_wh.json'))['per_task'], **json.load(open(f'{SEL}/rep_an_wh.json'))['per_task']}
B = np.array([v['B_blind'] for v in pt.values()]); DN = np.array([v['D_N'] for v in pt.values()])
an = json.load(open('pilot_analysis.json')); sec = '/root/select_secret'
h = [json.loads(l) for l in open('evals/pilot.jsonl') if '"C_N@high"' in l]
H = []
for e in h:
    tr = json.load(open(f'{sec}/truth/{e["task"]}.json')); orc, mean = max(tr), st.mean(tr); H.append((orc - tr[e['choice']]) / (orc - mean))
H = np.array(H); rng = np.random.default_rng(1510); S, M = 2000, 4000
dB, dD = float(B.mean() - H.mean()), float(DN.mean() - H.mean())
def p_le(d, sg): return ((sg @ d / len(d) <= d.mean() + 1e-12).sum() + 1) / (M + 1)
out = dict(note='модель: H_1 — голоса C_N@high пилота (6 задач — грубо); B_blind, D_N — per_task SELECT-01', pilot_H_mean=round(float(H.mean()), 3),
           B_blind_mean=round(float(B.mean()), 3), D_N_mean=round(float(DN.mean()), 3), rows=[])
for n in (40, 50, 60):
    for s in (1.0, 0.5, 0.25):
        hit = [0, 0, 0]
        for _ in range(S):
            i = rng.integers(0, len(B), n); h_ = H[rng.integers(0, len(H), n)] + (1 - s) * dB
            h2 = H[rng.integers(0, len(H), n)] + (1 - s) * dD
            sg = rng.choice((-1.0, 1.0), size=(M, n))
            p1, p2 = p_le(h_ - B[i], sg), p_le(h2 - DN[i], sg)
            lo, hi = sorted((p1, p2)); both = lo <= .025 and hi <= .05
            hit[0] += p1 <= .025 or (p2 <= .025 and p1 <= .05); hit[1] += p2 <= .025 or (p1 <= .025 and p2 <= .05); hit[2] += both
        out['rows'].append(dict(n=n, effect_share=s, power_vs_B_blind=round(hit[0] / S, 3), power_vs_D_N=round(hit[1] / S, 3), power_both=round(hit[2] / S, 3)))
print(json.dumps(out, ensure_ascii=False, indent=1))
