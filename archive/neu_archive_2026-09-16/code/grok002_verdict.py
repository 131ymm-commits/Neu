"""GROK-002 verdicts from the two arm checkpoints. Per PREREG (frozen 2026-09-02)."""
import json
import numpy as np
exec(open("/home/claude/ext001_run.py").read().split("t0 = time.time()")[0])   # feats, classify, LAG_R2
TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]
b = json.load(open("/home/claude/grok002_birth_ckpt.json")); d = json.load(open("/home/claude/grok002_death_ckpt.json"))
BW = (5e-4, 7e-4, 1e-3, 1.5e-3); DW = (1e-3, 2e-3, 2.5e-3, 3e-3, 4e-3)
birth_both = {w: all(b[f"{w}_{s}"]["born"] for s in (401, 402)) for w in BW}
flagged = {w: [s for s in (401, 402) if not b[f"{w}_{s}"]["train_ok"]] for w in BW}
dead_both = {w: all(d[f"{w}_{s}"]["perm_dead"] for s in (411, 412)) for w in DW}
wd_b = max([w for w in BW if birth_both[w]], default=None)
wd_d = min([w for w in DW if dead_both[w]], default=None)
grid = sorted(set(BW) | set(DW))
gap_nodes = (grid.index(wd_d) - grid.index(wd_b)) if (wd_b is not None and wd_d is not None) else None
pc2a = wd_b is not None and (wd_d is None or wd_d > wd_b) and (gap_nodes is None or gap_nodes >= 1)
pc2a_kill = wd_b is not None and wd_d is not None and wd_d <= wd_b
dips = {w: [d[f"{w}_{s}"]["dip"] for s in (411, 412)] for w in DW}
pc2b = sum(dips[1e-3]) >= 1
pc2b_kill = sum(dips[1e-3]) == 0 and not any(any(dips[w]) for w in DW if w <= 2e-3)

# P-C2c: reversed permanent-death records through the frozen battery (GROK-001 windowing)
def battery_rev(v):
    x = np.asarray(v, float)[::-1]                       # reversed death = birth-like
    cr = np.flatnonzero(x >= 0.5)
    if cr.size == 0 or cr[0] < 5: return "нет пересечения"
    cut = min(3 * int(cr[0]) + 1, len(x))
    seg = x[:cut]
    y = np.interp(np.linspace(0, len(seg) - 1, 200), np.arange(len(seg)), seg)
    c2 = np.flatnonzero(y >= 0.5)
    if c2.size == 0 or c2[0] < 10: return "флаг: ранний кроссинг"
    f = feats(y, int(c2[0]))
    return classify(f, TH), round(f["S"], 2) if f["S"] is not None else None
deaths = [(w, s, battery_rev(d[f"{w}_{s}"]["val_post"])) for w in DW for s in (411, 412) if d[f"{w}_{s}"]["perm_dead"]]
labs = [x[2][0] if isinstance(x[2], tuple) else x[2] for x in deaths]
nf = labs.count("фолд"); nc = labs.count("непрерывный")
pc2c = len(deaths) >= 3 and nf > len(deaths) / 2
pc2c_kill = len(deaths) >= 3 and nc > len(deaths) / 2
print("рождение (оба сида):", birth_both, "| флаги train<0.99:", {w: f for w, f in flagged.items() if f})
print("смерть (оба сида):", dead_both, "| провалы-возрождения:", dips)
print(f"wd_рожд = {wd_b}, wd_смерти = {wd_d}, зазор = {gap_nodes} узлов")
print(f"P-C2a (гистерезис): {'ПОДТВЕРЖДЁН' if pc2a else ('УБИТ' if pc2a_kill else 'не установлен')}")
print(f"P-C2b (провал-и-возрождение при 1e-3): {'ПОДТВЕРЖДЁН' if pc2b else ('УБИТ' if pc2b_kill else 'не установлен')}")
print(f"обращённые записи смерти: {[(w, s, r) for w, s, r in deaths]}")
print(f"P-C2c (маршрут смерти): фолд {nf}, непрерывный {nc} из {len(deaths)} -> "
      f"{'ПОДТВЕРЖДЁН' if pc2c else ('УБИТ' if pc2c_kill else ('не оценимо' if len(deaths) < 3 else 'не установлен'))}")
json.dump(dict(birth_both=birth_both, flagged=flagged, dead_both=dead_both, dips=dips, wd_b=wd_b, wd_d=wd_d, gap=gap_nodes,
               deaths=[(w, s, str(r)) for w, s, r in deaths], PC2a=bool(pc2a), PC2a_killed=bool(pc2a_kill),
               PC2b=bool(pc2b), PC2b_killed=bool(pc2b_kill), PC2c=bool(pc2c), PC2c_killed=bool(pc2c_kill)),
          open("/home/claude/grok002_results.json", "w"), default=float)
