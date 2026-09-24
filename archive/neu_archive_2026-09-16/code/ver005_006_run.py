"""VER-005 archive consistency + VER-006 program scoreboard. Per PREREG (frozen 2026-08-31)."""
import json, glob, os, re
import numpy as np

PRI = open("/home/claude/PRIORITY.md", encoding="utf-8").read()
PRE = open("/home/claude/PREREG.md", encoding="utf-8").read()

# ---------- VER-005 ----------
# 1) IDs derived from result/ckpt files on disk (the "was run" evidence)
files = sorted(glob.glob("/home/claude/*_results.json") + glob.glob("/home/claude/*_ckpt.json")
               + glob.glob("/home/claude/*_thresholds.json") + glob.glob("/home/claude/*_grid.json")
               + glob.glob("/home/claude/*_stage*.json") + glob.glob("/home/claude/*_curves.json")
               + glob.glob("/home/claude/*_cal.json") + glob.glob("/home/claude/*_dagfix.json"))
def ids_from(fn):
    b = os.path.basename(fn)
    m = re.match(r"([a-z]+)(\d{3})_(\d{3})_", b)         # ext003_004, ext005_014
    if m:
        p, a, c = m.group(1).upper(), int(m.group(2)), int(m.group(3))
        return [f"{p}-{i:03d}" for i in range(a, c + 1)]
    m = re.match(r"([a-z]+)(\d{2})_(\d{2})_", b)          # uni05_08
    if m:
        p = m.group(1).upper()
        return [f"{p}-{int(m.group(2)):02d}", f"{p}-{int(m.group(3)):02d}"]
    m = re.match(r"([a-z]+)(\d{3})([a-z]?)", b)
    if m:
        return [f"{m.group(1).upper()}-{m.group(2)}{m.group(3)}"]
    m = re.match(r"([a-z]+)(\d{2})([a-z]?)_", b)          # uni01, uni04b
    if m:
        return [f"{m.group(1).upper()}-{m.group(2)}{m.group(3)}"]
    return []
run_ids = {}
for fn in files:
    for i in ids_from(fn):
        if i.startswith("VER-"): continue                 # this arc itself is excluded
        run_ids.setdefault(i, []).append(os.path.basename(fn))

def base_id(i):  # UNI-04d -> UNI-04 family fallback for prereg lookup
    m = re.match(r"([A-Z]+-\d+)([a-z])$", i)
    return m.group(1) if m else None

rows, holes = [], []
for i in sorted(run_ids):
    in_pre = (i in PRE) or (base_id(i) and base_id(i) in PRE)
    in_pri = (i in PRI) or (base_id(i) and base_id(i) in PRI)
    rows.append((i, in_pre, in_pri, len(run_ids[i])))
    if not (in_pre and in_pri): holes.append((i, "нет PREREG" if not in_pre else "нет PRIORITY", run_ids[i]))
n_ok = sum(1 for (_, a, b, _) in rows if a and b)
frac = n_ok / len(rows)
MAIN = ["UNI-01", "UNI-04d", "UNI-05", "UNI-08", "PRE-006c", "DEL-001", "PRE-008", "ORD-002b",
        "EXT-001", "EXT-003", "EXT-004", "DET-017b", "PRE-009"]
main_bad = [i for i in MAIN if not (((i in PRE) or (base_id(i) and base_id(i) in PRE)) and any(i == r[0] for r in rows))]
pv5 = frac >= 0.95
pv5_kill = len(main_bad) > 0
# manual spot-check 5 random IDs (frozen seed)
rng = np.random.default_rng(20260831)
spot = [sorted(run_ids)[j] for j in rng.choice(len(run_ids), 5, replace=False)]
print(f"VER-005: прогнанных ID (по файлам) {len(rows)}; с обеими ногами (PREREG+PRIORITY) {n_ok} ({frac*100:.0f}%)")
if holes:
    print("  дыры:")
    for h in holes: print("   ", h)
print(f"  главный список: {'все 13 чисты' if not main_bad else 'НАРУШЕНИЕ: ' + str(main_bad)}")
print(f"  выборочная сверка (сид 20260831): {spot}")
print(f"P-V5: {'✓' if pv5 and not pv5_kill else ('УБИТ — протокольное нарушение' if pv5_kill else 'не установлен')}")

# ---------- VER-006 ----------
def outcomes_from(d, fn, acc):
    if not isinstance(d, dict): return
    v = d.get("verdicts", d)
    if not isinstance(v, dict): return
    for k in v:
        if not isinstance(v[k], (bool, np.bool_)): continue
        if k.endswith("_killed") or k in ("loo_ok", "ok", "alive", "S_alive", "sanity", "ctl_ok", "ctl_killed",
                                          "islands", "degen_flag", "mono", "transfer_dead"): continue
        if not re.match(r"^P[A-Z0-9]", k): continue
        killed = bool(v.get(k + "_killed", False))
        ok = bool(v[k])
        acc.append((fn, k, "подтверждён" if ok else ("убит" if killed else "не установлен")))

acc = []
seen = set()
for fn in files:
    b = os.path.basename(fn)
    if b.startswith("ver"): continue
    try: d = json.load(open(fn))
    except Exception: continue
    outcomes_from(d, b, acc)
    if isinstance(d, dict):
        for kk in d:                      # nested per-part verdicts (e.g. ext005_014 e005..e014)
            if isinstance(d[kk], dict) and "verdicts" not in d and kk not in ("th",):
                sub = d[kk]
                if isinstance(sub, dict) and any(re.match(r"^P[A-Z0-9]", q) for q in sub if isinstance(sub[q], bool)):
                    outcomes_from({"verdicts": sub}, f"{b}:{kk}", acc)
# dedupe (same prediction key may appear in ckpt and results twins)
ded = {}
for fn, k, o in acc:
    root = re.sub(r"(_results|_ckpt|_results_full)\.json.*", "", fn)
    ded[(root, k)] = o
cnt = {"подтверждён": 0, "убит": 0, "не установлен": 0}
for o in ded.values(): cnt[o] += 1
stops = len(re.findall(r"(ОСТАНОВЛЕН ПОСТАНОВК|остановлен постановк|стоп постановк|УБИТ ПОСТАНОВК|остановлена постановк)", PRI))
n_pred = sum(cnt.values())
neg = cnt["убит"] + stops
frac_neg = neg / (n_pred + stops)
pv6 = frac_neg >= 0.20
pv6_kill = frac_neg < 0.10
kill_list = sorted({r for (r, k), o in ded.items() if o == "убит"})
print(f"\nVER-006: предрегистрированных прогнозов с исходами {n_pred}: {cnt} + остановок постановкой в PRIORITY: {stops}")
print(f"  доля {{убит+остановлен}} = {neg}/{n_pred + stops} = {frac_neg*100:.0f}% (фон поля: 67.8% позитива)")
print(f"  файлы с убийствами: {kill_list}")
print(f"P-V6: {'✓ (протокол режет)' if pv6 else ('УБИТ — дисциплина декоративна' if pv6_kill else 'не установлен')}")

json.dump(dict(ver005=dict(n_run=len(rows), n_ok=n_ok, frac=frac, holes=holes, main_bad=main_bad,
                           PV5=bool(pv5 and not pv5_kill), PV5_killed=bool(pv5_kill), spot=spot),
               ver006=dict(counts=cnt, stops=stops, frac_neg=frac_neg, PV6=bool(pv6), PV6_killed=bool(pv6_kill),
                           kills=kill_list, per_prediction={f"{r}:{k}": o for (r, k), o in sorted(ded.items())})),
          open("/home/claude/ver005_006_results.json", "w"), default=float)
print("-> ver005_006_results.json")
