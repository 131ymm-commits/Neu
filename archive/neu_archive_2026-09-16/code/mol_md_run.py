"""MOL-001 production: alanine dipeptide (Amber ff from openmmtools prmtop), vacuum, Langevin T, seed, ns; saves phi, psi, Epot, heavy-atom coords."""
import time, sys
import numpy as np
from openmm import app, unit, LangevinMiddleIntegrator, Platform
T = float(sys.argv[1]); seed = int(sys.argv[2]); ns = float(sys.argv[3]); tag = sys.argv[4]
prm = app.AmberPrmtopFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.prmtop")
crd = app.AmberInpcrdFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.crd")
system = prm.createSystem(nonbondedMethod=app.NoCutoff, constraints=app.HBonds, implicitSolvent=None)
integ = LangevinMiddleIntegrator(T * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds); integ.setRandomNumberSeed(seed)
sim = app.Simulation(prm.topology, system, integ, Platform.getPlatformByName("CPU"), {"Threads": "1"})
sim.context.setPositions(crd.positions); sim.minimizeEnergy(); sim.context.setVelocitiesToTemperature(T * unit.kelvin, seed)
atoms = list(prm.topology.atoms()); names = [(a.residue.name, a.name, a.index) for a in atoms]
def idx(res, name): return [i for r, n, i in names if r == res and n == name][0]
phi = (idx("ACE", "C"), idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C")); psi = (idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C"), idx("NME", "N"))
heavy = [a.index for a in atoms if a.element.symbol != "H"]
def dihed(p, a, b, c, d):
    b0 = p[a] - p[b]; b1 = p[c] - p[b]; b2 = p[d] - p[c]
    b1n = b1 / np.linalg.norm(b1); v = b0 - np.dot(b0, b1n) * b1n; w = b2 - np.dot(b2, b1n) * b1n
    return np.arctan2(np.dot(np.cross(b1n, v), w), np.dot(v, w))
stride = 100; nfr = int(ns * 1000 / 0.2); t0 = time.time()
scal = np.empty((nfr, 3)); xyz = np.empty((nfr, len(heavy), 3), np.float32)
for k in range(nfr):
    sim.step(stride)
    st = sim.context.getState(getPositions=True, getEnergy=True)
    p = st.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    scal[k] = (dihed(p, *phi), dihed(p, *psi), st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)); xyz[k] = p[heavy]
    if k % 25000 == 0 and k: print(f"{tag}: {k*0.2/1000:.1f} ns, frac phi>0 so far {np.mean(scal[:k,0]>0):.3f} [{time.time()-t0:.0f}s]", flush=True)
np.savez_compressed(f"/home/claude/mol_ala2_{tag}.npz", scal=scal, xyz=xyz, heavy=np.array(heavy), T=T, seed=seed)
print(f"{tag} done: {ns} ns, frac phi>0 {np.mean(scal[:,0]>0):.3f}, [{time.time()-t0:.0f}s]")
