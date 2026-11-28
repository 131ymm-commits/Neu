"""Описательное измерение на открытой базе Gapminder (Systema Globalis, CC BY 4.0): сколько осталось отбора по выживанию в раннем детстве.
Мера — составляющая смертности индекса Кроу для возраста до 5 лет (и до 1 года для длинного ряда): I = q/(1 − q), q — доля умерших.
Это измерение, а не проверка предсказания. Файлы базы в репозиторий не кладутся; путь — аргументом.
  python3 2026-11-28_databases_gapminder.py <каталог с двумя csv> → 2026-11-28_databases_gapminder.json"""
import csv, json, os, sys, hashlib
import numpy as np
D = sys.argv[1]; out = dict(source='github.com/open-numbers/ddf--gapminder--systema_globalis, ветка master, каталог countries-etc-datapoints; версия базы 2.3.2', files={})
def load(name):
    p = os.path.join(D, f'{name}.csv'); out['files'][name] = hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]
    return {(r['geo'], int(r['time'])): float(r[name]) / 1000 for r in csv.DictReader(open(p))}
crow = lambda q: q / (1 - q)
u5 = load('under_five_mortality_from_cme_per_1000_born'); im = load('infant_mortality_rate_per_1000_births')
out['under5'] = {}
for y in (1960, 1990, 2024):
    q = np.array([v for (g, t), v in u5.items() if t == y])
    out['under5'][str(y)] = dict(countries=len(q), median_q=round(float(np.median(q)), 4), median_index=round(float(np.median(crow(q))), 4),
                                 share_countries_q_above_0_2=round(float(np.mean(q > 0.2)), 3), max_q=round(float(q.max()), 3))
both = sorted({g for (g, t) in u5 if t == 1960} & {g for (g, t) in u5 if t == 2024})
r = np.array([crow(u5[(g, 1960)]) / crow(u5[(g, 2024)]) for g in both])
out['under5_fold_drop_1960_2024'] = dict(countries=len(both), median=round(float(np.median(r)), 1), min=round(float(r.min()), 1), max=round(float(r.max()), 1))
out['infant_long_series'] = {g: {str(t): dict(q=round(im[(g, t)], 4), index=round(crow(im[(g, t)]), 4)) for t in ys if (g, t) in im}
                             for g, ys in (('swe', (1800, 1850, 1900, 1950, 2015)), ('fra', (1830, 1900, 1950, 2015)), ('ind', (1911, 1950, 2015)), ('jpn', (1920, 1950, 2015)))}
s = out['infant_long_series']['swe']; out['sweden_fold_drop_1800_2015'] = round(s['1800']['index'] / s['2015']['index'])
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2026-11-28_databases_gapminder.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
