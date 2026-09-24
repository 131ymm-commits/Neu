"""VER-008 — audit of UNI-08: relative time. Per PREREG (frozen 2026-09-01)."""
import json, glob, re
import numpy as np
from scipy.stats import spearmanr

RNG = np.random.default_rng(20260901)
base = "/home/claude/deep-early-warnings-pnas/test_empirical/thermoacoustic/data/thermo_experiments/Rate dependent transitions/pressure data"
log = open(f"{base}/log.txt", encoding="latin-1").read()
rates = {}
for m in re.finditer(r"(\d+)\.txt\s*[-:–]*\s*.*?([\d.]+)\s*mV", log):
    rates[int(m.group(1))] = float(m.group(2))

rows = []
for fp in sorted(glob.glob(f"{base}/[0-9]*.txt"), key=lambda s: int(re.findall(r"(\d+)\.txt", s)[0])):
    idx = int(re.findall(r"(\d+)\.txt", fp)[0])
    if idx not in rates: continue
    try:
        d = np.loadtxt(fp, encoding="latin-1")
    except Exception:
        continue
    if d.ndim != 2 or d.shape[1] < 2: continue
    t, p = d[:, 0], d[:, 1]
    dt = np.median(np.diff(t[:1000]))
    wlen = max(int(0.5 / dt), 10)
    nw = len(p) // wlen
    rms = np.sqrt(np.mean(p[:nw * wlen].reshape(nw, wlen) ** 2, axis=1))
    base_r = np.median(rms[:max(nw // 10, 3)])
    hits = np.flatnonzero((rms[:-1] >= 5 * base_r) & (rms[1:] >= 5 * base_r))
    if hits.size == 0:
        rows.append(dict(idx=idx, rate=rates[idx], t_rel=None)); continue
    t_rel = float(hits[0] * wlen * dt)                 # seconds from file start (FIX)
    V_rel = rates[idx] / 1000.0 * t_rel
    rows.append(dict(idx=idx, rate=rates[idx], t_rel=t_rel, V_rel=float(V_rel),
                     in_range=bool(0.0 <= V_rel <= 2.4)))
ok = [r for r in rows if r.get("V_rel") is not None]
n_bad_range = sum(1 for r in ok if not r["in_range"])
print(f"файлов с онсетом: {len(ok)}/{len(rows)}; вне диапазона [0, 2.4] В: {n_bad_range}")
for r in ok:
    print(f"  #{r['idx']}: R={r['rate']} мВ/с, t_rel={r['t_rel']:.1f} с, V_rel={r['V_rel']:.3f} В{' [ВНЕ ДИАПАЗОНА]' if not r['in_range'] else ''}")

res = dict(rows=rows, n_ok=len(ok), n_bad_range=n_bad_range)
if len(ok) >= 8 and n_bad_range == 0:
    rr = np.array([r["rate"] for r in ok]); vv = np.array([r["V_rel"] for r in ok])
    rho = float(spearmanr(rr, vv).statistic)
    perm = [abs(float(spearmanr(rr, RNG.permutation(vv)).statistic)) for _ in range(1000)]
    p_ = float(np.mean([q >= abs(rho) for q in perm]))
    loo = [float(spearmanr(np.delete(rr, j), np.delete(vv, j)).statistic) for j in range(len(ok))]
    loo_sign = all(np.sign(l) == np.sign(rho) for l in loo) if rho != 0 else False
    pv8a = rho > 0 and p_ < 0.05
    pv8b = not pv8a
    res.update(rho=rho, p=p_, loo_sign=bool(loo_sign), med_V_rel=float(np.median(vv)),
               PV8a=bool(pv8a), PV8b_retract=bool(pv8b))
    print(f"\nP-V8: ρ(V_rel, R) = {rho:.3f} (p = {p_:.4f}, LOO-знак {loo_sign}) | медиана V_rel = {np.median(vv):.3f} В")
    print("вердикт: " + ("P-V8a — rate-delay ВЫЖИВАЕТ пересчётом (величина честная, 1.00 снята как артефакт)"
                         if pv8a else "P-V8b — P-UR1 ОТЗЫВАЕТСЯ (класс C: бухгалтерия), плитка снимается"))
else:
    res.update(rho=None, PV8a=False, PV8b_retract=True, stop="санити/диапазон")
    print("СТОП по санити (диапазон/число файлов) — записано")
json.dump(res, open("/home/claude/ver008_results.json", "w"), default=float)
print("-> ver008_results.json")
