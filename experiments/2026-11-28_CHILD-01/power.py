"""CHILD-01: мощность проверок — оценка Монте-Карло до прогона (редакция после совета 48).
Сид — единица (20 сидов). Средние по сидам берутся нормальными; среднее и разброс — из пилота (pilot_seed_stats.json, сиды 990–992).
Главный сценарий (решение совета): эффект как в пилоте, разброс втрое больше пилотного — три сида разброс занижают.
Справочно: половина эффекта при том же тройном разбросе. Проверка с мощностью ниже 0,5 в главном сценарии идёт без вердикта."""
import json, os
import numpy as np
import stats01 as S
H = os.path.dirname(os.path.abspath(__file__)); P = json.load(open(os.path.join(H, 'pilot_seed_stats.json')))
r = np.random.default_rng(0); REPS = 2000
out = {'_': 'доли исходов; оценка Монте-Карло, 2000 повторов; 0,005 на сторону; разброс = 3 × пилотный', 'pilot': {k: dict(mean=v['mean'], sd=v['sd']) for k, v in P.items()}}
def sim(mu, sd, n=20):
    up = dn = 0
    for _ in range(REPS):
        pu, pd = S.signflip_p(r.normal(mu, sd, n)); up += pu <= S.ALPHA_SIDE; dn += pd <= S.ALPHA_SIDE
    return dict(confirmed=round(up / REPS, 3), reverse=round(dn / REPS, 3))
for name, key in (('P1a_dose_slope', 'P1a'), ('P1b_inner_slope', 'P1b'), ('P3_truth_ALT50_vs_NOISE50', 'P3'), ('P5_popmean_truth_ALT25_vs_FINAL25', 'P5_mT')):
    mu, sd = P[key]['mean'], 3 * P[key]['sd']
    out[name] = {'главный: эффект пилота, разброс ×3': sim(mu, sd), 'справка: половина эффекта, разброс ×3': sim(mu / 2, sd), 'эффекта нет': sim(0.0, sd)}
def sim3(mu, sd, lim, n=20):
    """Трёхсторонний исход с границей «нет разницы» ±lim по интервалу 95 % среднего (нормальное приближение; в анализе — бутстреп по сидам)."""
    c = dict(up=0, down=0, same=0, open=0)
    for _ in range(REPS):
        x = r.normal(mu, sd, n); pu, pd = S.signflip_p(x); m, h = x.mean(), 1.96 * x.std(ddof=1) / np.sqrt(n)
        if pu <= S.ALPHA_SIDE: c['up'] += 1
        elif pd <= S.ALPHA_SIDE: c['down'] += 1
        elif -lim < m - h and m + h < lim: c['same'] += 1
        else: c['open'] += 1
    return {k: round(v / REPS, 3) for k, v in c.items()}
m4, s4 = P['P4']['mean'], 3 * P['P4']['sd']
out['P4_purge_NOISE50_minus_ALT50'] = {'_': 'up — «экзамен чистит», down — «обратный эффект», same — «разницы нет» (±0,05), open — «не решено»',
    'главный: как в пилоте, разброс ×3': sim3(m4, s4, 0.05), 'разницы нет, разброс ×3': sim3(0.0, s4, 0.05), 'экзамен чистит на 0,05, разброс ×3': sim3(0.05, s4, 0.05),
    'экзамен чистит на 0,1, разброс ×3': sim3(0.1, s4, 0.05), 'чувствительность ±0,02: разницы нет, разброс ×3': sim3(0.0, s4, 0.02)}
mb, sb, bt = P['P2_bI']['mean'], 3 * P['P2_bI']['sd'], P['P2_bT']['mean']
out['P2_exam_gradient_on_inflation'] = {'_': 'up — «предпочитает завышенных», down — «чистит», same — «слеп» (±0,1 от β_T), open — «не решено»',
    'главный: как в пилоте, разброс ×3': sim3(mb, sb, 0.1 * bt), 'градиент нулевой, разброс ×3': sim3(0.0, sb, 0.1 * bt), 'как в пилоте, разброс пилотный': sim3(mb, sb / 3, 0.1 * bt)}
json.dump(out, open(os.path.join(H, 'power.json'), 'w'), ensure_ascii=False, indent=1)
for k, v in out.items():
    if k not in ('_', 'pilot'): print(k, json.dumps(v, ensure_ascii=False))
