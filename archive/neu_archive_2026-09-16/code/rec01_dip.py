"""REC-01 — дипептид аланина (OpenMM, Amber, вакуум): 200 пс при 700 K → закалка в 300 K, 1 нс; минимизация каждые 1 пс во втором контексте;
рекорды E_IS (допуск 0.5 кДж/моль), бассейн (φ, ψ) минимума. Сиды 801–810. По PREREG (2026-09-05)."""
import numpy as np, json, os, sys, time
from openmm import app, unit, LangevinMiddleIntegrator, Platform, VerletIntegrator
OUT = '/home/claude/rec01_dip.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
prm = app.AmberPrmtopFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.prmtop")
crd = app.AmberInpcrdFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.crd")
system = prm.createSystem(nonbondedMethod=app.NoCutoff, constraints=app.HBonds, implicitSolvent=None)
atoms = list(prm.topology.atoms()); names = [(a.residue.name, a.name, a.index) for a in atoms]
def idx(res_, name): return [i for r, n, i in names if r == res_ and n == name][0]
PHI = (idx("ACE", "C"), idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C")); PSI = (idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C"), idx("NME", "N"))
def dihed(p, a, b, c, d):
    b0 = p[a] - p[b]; b1 = p[c] - p[b]; b2 = p[d] - p[c]; b1n = b1 / np.linalg.norm(b1); v = b0 - np.dot(b0, b1n) * b1n; w = b2 - np.dot(b2, b1n) * b1n
    return np.arctan2(np.dot(np.cross(b1n, v), w), np.dot(v, w))
t0 = time.time(); TOL = 0.5
for seed in range(801, 811):
    name = f'DIPQ_{seed}'
    if name in res: continue
    integ = LangevinMiddleIntegrator(700 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds); integ.setRandomNumberSeed(seed)
    sim = app.Simulation(prm.topology, system, integ, Platform.getPlatformByName("CPU"), {"Threads": "1"})
    sim.context.setPositions(crd.positions); sim.minimizeEnergy(); sim.context.setVelocitiesToTemperature(700 * unit.kelvin, seed)
    sim.step(100000)                                                   # 200 пс при 700 K
    integ.setTemperature(300 * unit.kelvin); sim.context.setVelocitiesToTemperature(300 * unit.kelvin, seed + 1)   # закалка
    mini = app.Simulation(prm.topology, system, VerletIntegrator(0.001 * unit.picoseconds), Platform.getPlatformByName("CPU"), {"Threads": "1"})
    Eis = []; basins = []
    for k in range(1000):                                              # 1 нс, минимизация каждые 1 пс
        sim.step(500)
        pos = sim.context.getState(getPositions=True).getPositions(asNumpy=True)
        mini.context.setPositions(pos); mini.minimizeEnergy(tolerance=0.01 * unit.kilojoule_per_mole / unit.nanometer, maxIterations=2000)
        st = mini.context.getState(getPositions=True, getEnergy=True); p = st.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
        Eis.append(st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)); basins.append((float(np.degrees(dihed(p, *PHI))), float(np.degrees(dihed(p, *PSI)))))
    Eis = np.array(Eis); rec_t, rec_E, rec_b = [], [], []; cur = np.inf
    for k in range(len(Eis)):
        if Eis[k] < cur - TOL: cur = Eis[k]; rec_t.append(k + 1); rec_E.append(float(cur)); rec_b.append(basins[k])
    res[name] = dict(seed=seed, rec_t=rec_t, rec_E=rec_E, rec_basins=rec_b, n_rec=len(rec_t), last_rec_frac=(rec_t[-1] / 1000 if rec_t else None),
                     n_distinct_E=int(len(np.unique(np.round(Eis / TOL)))), Eis_min=float(Eis.min()), Eis_final=float(Eis[-1]))
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f"{name}: рекордов {len(rec_t)} при t(пс) {rec_t}, E {np.round(rec_E, 1)}, бассейны {[(round(a), round(b)) for a, b in rec_b]}, последний рекорд при {rec_t[-1] / 1000:.2f} нс [{time.time()-t0:.0f}s]", flush=True)
