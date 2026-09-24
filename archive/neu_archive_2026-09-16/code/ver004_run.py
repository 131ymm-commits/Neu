"""VER-004 — ±20% threshold sweep on 57 stored external events. Per PREREG (frozen 2026-08-31)."""
import json
import itertools
import numpy as np

TH = json.load(open("/home/claude/ext001_ckpt.json"))["th"]   # same values as ext003_004 th

def classify(f, th):
    if f["z"] >= th["thR2"]: return "осциллятор"
    if f["rise"] < th["thRise"]: return "нет рождения"
    if f.get("S") is not None and f["S"] >= th["thS"]: return "фолд"
    return "непрерывный"

evs = []
ck = json.load(open("/home/claude/ext001_ckpt.json"))
FULL = {"YD/PB", "GI-1", "GI-2", "GI-4", "GI-7", "GI-8", "GI-11", "GI-12", "GI-13", "GI-15", "GI-16"}
for e in ck["ngrip"]["events"]:
    if "rise" in e and "исключ" not in e["label"]:
        evs.append(dict(src="NGRIP", name=e["name"], full=e["name"] in FULL, **{k: e[k] for k in ("rise", "S", "z")}, stored=e["label"]))
r34 = json.load(open("/home/claude/ext003_004_results.json"))
for e in r34["ext003"]["events"]:
    if "rise" in e:
        evs.append(dict(src="палео", name=str(e.get("name", e.get("ID", "?"))), full=True, **{k: e.get(k) for k in ("rise", "S", "z")}, stored=e["label"]))
for e in r34["ext004"]["res"]["Mo [ppm]"]["events"]:
    if "rise" in e:
        evs.append(dict(src="аноксия", name=f"{e['ID']}/{e['core']}", full=True, **{k: e.get(k) for k in ("rise", "S", "z")}, stored=e["label"]))
for e in json.load(open("/home/claude/ext005_014_ckpt.json"))["e006"]["rows"]:
    evs.append(dict(src="COVID", name=e["country"], full=True, **{k: e.get(k) for k in ("rise", "S", "z")}, stored=e["label"]))
print(f"событий: {len(evs)} | по источникам: " + str({s: sum(1 for e in evs if e['src'] == s) for s in ('NGRIP', 'палео', 'аноксия', 'COVID')}))

# sanity: base combo reproduces stored labels
base_bad = [e["name"] for e in evs if classify(e, TH) != e["stored"]]
print(f"санити базовой комбинации: {len(evs) - len(base_bad)}/{len(evs)} совпадений" + (f" | РАСХОЖДЕНИЯ: {base_bad}" if base_bad else ""))

MULT = (0.8, 1.0, 1.2)
combos = list(itertools.product(MULT, MULT, MULT))
res = []
for (mS, mR, mZ) in combos:
    th = dict(thS=TH["thS"] * mS, thRise=TH["thRise"] * mR, thR2=TH["thR2"] * mZ)
    labs = [classify(e, th) for e in evs]
    flips = sum(1 for e, l in zip(evs, labs) if l != e["stored"])
    ngrip_fold = sum(1 for e, l in zip(evs, labs) if e["src"] == "NGRIP" and e["full"] and l == "фолд")
    anox_fold = sum(1 for e, l in zip(evs, labs) if e["src"] == "аноксия" and l == "фолд")
    covid_osc = sum(1 for e, l in zip(evs, labs) if e["src"] == "COVID" and l == "осциллятор")
    res.append(dict(m=(mS, mR, mZ), flips=flips, ngrip_fold=ngrip_fold, anox_fold=anox_fold, covid_osc=covid_osc,
                    flip_names=[e["name"] for e, l in zip(evs, labs) if l != e["stored"]]))

maxflip = max(r["flips"] for r in res)
worst = [r for r in res if r["flips"] == maxflip][0]
n_ngrip_hold = sum(1 for r in res if r["ngrip_fold"] >= 6)
n_anox_hold = sum(1 for r in res if r["anox_fold"] >= 7)
n_covid_hold = sum(1 for r in res if r["covid_osc"] >= 11)
pv4a = maxflip <= 11
pv4a_kill = maxflip > 28
pv4b = n_ngrip_hold >= 22 and n_anox_hold >= 22 and n_covid_hold >= 25
pv4b_kill = min(n_ngrip_hold, n_anox_hold, n_covid_hold) < 14

# LOO by source: max flip fraction without each source
loo = {}
for s0 in ("NGRIP", "палео", "аноксия", "COVID"):
    sub = [i for i, e in enumerate(evs) if e["src"] != s0]
    mf = 0
    for (mS, mR, mZ) in combos:
        th = dict(thS=TH["thS"] * mS, thRise=TH["thRise"] * mR, thR2=TH["thR2"] * mZ)
        fl = sum(1 for i in sub if classify(evs[i], th) != evs[i]["stored"])
        mf = max(mf, fl)
    loo[s0] = dict(n=len(sub), max_flips=mf)

# per-event fragility census
frag = {}
for r in res:
    for nm in r["flip_names"]:
        frag[nm] = frag.get(nm, 0) + 1
frag = dict(sorted(frag.items(), key=lambda kv: -kv[1]))

out = dict(n=len(evs), sanity_mismatch=base_bad, maxflip=maxflip, maxflip_frac=maxflip / len(evs),
           worst_combo=worst["m"], worst_flip_names=worst["flip_names"],
           hold=dict(ngrip=n_ngrip_hold, anox=n_anox_hold, covid=n_covid_hold),
           PV4a=bool(pv4a), PV4a_killed=bool(pv4a_kill), PV4b=bool(pv4b), PV4b_killed=bool(pv4b_kill),
           loo=loo, fragile_events=frag, combos=res)
json.dump(out, open("/home/claude/ver004_results.json", "w"), default=float)
print(f"\nP-V4a: макс. флипов {maxflip}/{len(evs)} ({maxflip/len(evs)*100:.0f}%) на комбинации {worst['m']} "
      f"-> {'✓ (≤20%)' if pv4a else ('УБИТ (>50%)' if pv4a_kill else 'не установлен (20–50%)')}")
print(f"   хрупкие события (в скольких комбинациях флипают): {frag}")
print(f"P-V4b: NGRIP фолд-мажоритет держится {n_ngrip_hold}/27, аноксия {n_anox_hold}/27, COVID осц {n_covid_hold}/27 "
      f"-> {'✓' if pv4b else ('УБИТ' if pv4b_kill else 'не установлен')}")
print(f"LOO по источникам: {loo}")
print("-> ver004_results.json")
