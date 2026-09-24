"""TH-006 — external leg of the clock certificate: death of measles cycles across US states.
Per PREREG (frozen 2026-09-02)."""
import json
import numpy as np
import pandas as pd

d = pd.read_csv("/home/claude/blogR/data/measles_incidence.csv", skiprows=2, na_values="-")
states = [c for c in d.columns if c not in ("YEAR", "WEEK")]
ann = d.groupby("YEAR")[states].mean()

def onset_of(s, origin=1963):
    pre = s.loc[1950:1962].dropna(); post = s.loc[1975:1985].dropna()
    if len(pre) < 10 or len(post) < 10: return None, "мало данных"
    b, a = float(pre.median()), float(post.median())
    if not (b > a): return None, "база не выше"
    thr = 0.5 * (b + a)
    roll = s.rolling(3, min_periods=2).mean()
    yrs = [y for y in roll.index if y >= origin]
    for i, y in enumerate(yrs):
        w = [roll.get(y + k, np.nan) for k in range(3)]
        if all(np.isfinite(q) and q < thr for q in w):
            return float(y - origin), None
    return None, "коллапс не найден"

def cv_of(waits):
    return float(np.std(waits) / np.mean(waits)) if len(waits) >= 3 and np.mean(waits) > 0 else None

waits, skipped = {}, {}
for st in states:
    w, why = onset_of(ann[st])
    (waits if w is not None else skipped)[st] = w if w is not None else why
n = len(waits)
print(f"пригодных штатов: {n} (исключено {len(skipped)})")
if n < 20:
    print("СТОП по предрегистрации: < 20 пригодных штатов"); raise SystemExit
vals = np.array(list(waits.values()), float)
CV = cv_of(vals)
jk = [cv_of(np.delete(vals, i)) for i in range(n)]
jk_side = all((q is not None and (q <= 0.30) == (CV <= 0.30)) for q in jk)
sens = {}
for orig in (1960, 1966):
    w2 = [onset_of(ann[st], orig)[0] for st in states]
    w2 = [q for q in w2 if q is not None]
    sens[orig] = cv_of(np.array(w2, float))
pt6a = CV <= 0.30; pt6a_kill = CV >= 0.70
print(f"ожидания (годы от 1963): медиана {np.median(vals):.1f}, диапазон {vals.min():.0f}–{vals.max():.0f}")
print(f"CV = {CV:.3f} (случайное назначение дало бы 0.577, крамерсово ≈ 1.0); джекнайф-сторона устойчива: {jk_side}")
print(f"чувствительность к началу отсчёта: 1960 -> {None if sens[1960] is None else round(sens[1960],3)}, "
      f"1966 -> {None if sens[1966] is None else round(sens[1966],3)}")
print(f"P-T6a: {'ПОДТВЕРЖДЁН (часы ведомые)' if pt6a else ('УБИТ (часы шумовые)' if pt6a_kill else 'не установлен (серая зона)')}")
json.dump(dict(n=n, waits=waits, skipped=skipped, CV=CV, jk_side=bool(jk_side), sens=sens,
               PT6a=bool(pt6a), PT6a_killed=bool(pt6a_kill)),
          open("/home/claude/th006_results.json", "w"), default=float)
print("-> th006_results.json")
