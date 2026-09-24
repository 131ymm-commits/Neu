"""TH-007 — clocks of DO events: CV of stadial waits and recurrence intervals. Per PREREG (frozen 2026-09-02)."""
import json
import numpy as np
exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # ONSETS, XLS
import xlrd
wb = xlrd.open_workbook(XLS); sh = wb.sheet_by_index(0)
ages, d18 = [], []
for r in range(61, sh.nrows):
    a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
    if isinstance(a, float) and isinstance(d, float):
        ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18)
o = np.argsort(-ages); ages, d18 = ages[o], d18[o]          # time forward = decreasing age

names_all = sorted(ONSETS, key=lambda k: -ONSETS[k])          # oldest first
def cv(v): v = np.asarray(v, float); return float(v.std() / v.mean())

def analyze(names):
    rec, stad, flags = [], [], []
    for k in range(len(names) - 1):
        a_old, a_new = ONSETS[names[k]], ONSETS[names[k + 1]]
        rec.append(a_old - a_new)
        m = (ages <= a_old) & (ages >= a_new)
        aw, dw = ages[m], d18[m]                                # forward in time
        inter = dw[aw >= a_old - 300]; stad_lvl = dw[aw <= a_new + 500]
        if len(inter) < 3 or len(stad_lvl) < 3:
            flags.append((names[k], "мало точек")); continue
        li, ls = float(np.median(inter)), float(np.median(stad_lvl))
        if not (li > ls):
            flags.append((names[k], "интерстадиал не выше стадиала")); continue
        mid = 0.5 * (li + ls)
        sm = np.convolve(dw, np.ones(3) / 3, mode="same")
        cand = np.flatnonzero((sm < mid) & (aw <= a_old - 200))
        if cand.size == 0:
            flags.append((names[k], "GS-онсет не найден")); continue
        gs_age = float(aw[cand[0]])
        stad.append(gs_age - a_new)
    return rec, stad, flags

prim = [n for n in names_all if 27000 <= ONSETS[n] <= 60000]
rec_p, stad_p, flags_p = analyze(prim)
rec_f, stad_f, flags_f = analyze(names_all)
print(f"первичная выборка (MIS3): онсетов {len(prim)}, интервалов {len(rec_p)}, стадиальных ожиданий {len(stad_p)}; флаги: {flags_p}")
if len(rec_p) < 8 or len(stad_p) < 8:
    print("СТОП по предрегистрации: < 8 пригодных"); raise SystemExit
cv_rec, cv_stad = cv(rec_p), cv(stad_p)
def jk_side(v, edge_lo=0.15, edge_hi=0.30):
    v = np.asarray(v, float); base = cv(v)
    zone = lambda c: ("low" if c <= edge_lo else ("high" if c >= edge_hi else "grey"))
    return all(zone(cv(np.delete(v, i))) == zone(base) for i in range(len(v)))
print(f"(а) интервалы повторения (лет): {sorted(int(x) for x in rec_p)}")
print(f"    среднее {np.mean(rec_p):.0f}, std {np.std(rec_p):.0f}, CV = {cv_rec:.3f}, джекнайф-зона устойчива: {jk_side(rec_p)}")
print(f"(б) стадиальные ожидания (лет): {sorted(int(x) for x in stad_p)}")
print(f"    среднее {np.mean(stad_p):.0f}, std {np.std(stad_p):.0f}, CV = {cv_stad:.3f}, джекнайф-зона устойчива: {jk_side(stad_p)}")
print(f"полный набор (описательно): интервалы CV = {cv(rec_f):.3f} (n={len(rec_f)}), стадиалы CV = {cv(stad_f):.3f} (n={len(stad_f)})")
def verdict(c):
    return "ПОДТВЕРЖДЁН (крамерсово)" if c >= 0.30 else ("УБИТ (ведомые часы)" if c <= 0.15 else "не установлен (серая зона)")
print(f"P-C1a (стадиальные ожидания): {verdict(cv_stad)}")
print(f"P-C1b (интервалы повторения): {verdict(cv_rec)}")
json.dump(dict(prim=prim, rec=rec_p, stad=stad_p, flags=flags_p, cv_rec=cv_rec, cv_stad=cv_stad,
               full=dict(cv_rec=cv(rec_f), cv_stad=cv(stad_f), n_rec=len(rec_f), n_stad=len(stad_f)),
               PC1a=bool(cv_stad >= 0.30), PC1a_killed=bool(cv_stad <= 0.15),
               PC1b=bool(cv_rec >= 0.30), PC1b_killed=bool(cv_rec <= 0.15)),
          open("/home/claude/th007_results.json", "w"), default=float)
print("-> th007_results.json")
