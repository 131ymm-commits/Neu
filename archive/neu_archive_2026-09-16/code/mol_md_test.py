"""Alanine dipeptide in vacuum (Amber prmtop from openmmtools data), Langevin 300 K — speed test + dihedral output."""
import time, sys
import numpy as np
from openmm import app, unit, LangevinMiddleIntegrator, Platform
import openmm
prm = app.AmberPrmtopFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.prmtop")
crd = app.AmberInpcrdFile("/home/claude/openmmtools/openmmtools/data/alanine-dipeptide-gbsa/alanine-dipeptide.crd")
T = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
system = prm.createSystem(nonbondedMethod=app.NoCutoff, constraints=app.HBonds, implicitSolvent=None)
integ = LangevinMiddleIntegrator(T * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds)
integ.setRandomNumberSeed(101)
plat = Platform.getPlatformByName("CPU")
sim = app.Simulation(prm.topology, system, integ, plat, {"Threads": "1"})
sim.context.setPositions(crd.positions); sim.minimizeEnergy(); sim.context.setVelocitiesToTemperature(T * unit.kelvin, 101)
# dihedral atom indices (phi: C(ACE)-N-CA-C ; psi: N-CA-C-N(NME)) from topology
atoms = list(prm.topology.atoms())
names = [(a.residue.name, a.name, a.index) for a in atoms]
def idx(res, name): return [i for r, n, i in names if r == res and n == name][0]
phi = (idx("ACE", "C"), idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C")); psi = (idx("ALA", "N"), idx("ALA", "CA"), idx("ALA", "C"), idx("NME", "N"))
def dihed(p, a, b, c, d):
    b0 = p[a] - p[b]; b1 = p[c] - p[b]; b2 = p[d] - p[c]
    b1n = b1 / np.linalg.norm(b1); v = b0 - np.dot(b0, b1n) * b1n; w = b2 - np.dot(b2, b1n) * b1n
    return np.arctan2(np.dot(np.cross(b1n, v), w), np.dot(v, w))
t0 = time.time(); nsteps = int(sys.argv[2]) if len(sys.argv) > 2 else 20000; stride = 100; out = []
for k in range(nsteps // stride):
    sim.step(stride)
    st = sim.context.getState(getPositions=True, getEnergy=True)
    p = st.getPositions(asNumpy=True).value_in_unit(unit.nanometer)
    out.append((k * stride * 0.002, dihed(p, *phi), dihed(p, *psi), st.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)))
out = np.array(out); dt = time.time() - t0
print(f"T={T}: {nsteps} steps ({nsteps*0.002:.0f} ps) in {dt:.1f}s -> {dt/nsteps*1e6:.0f} us/step; {nsteps*0.002/dt*1000:.0f} ps/s")
print("phi range deg:", np.degrees(out[:,1]).min().round(0), np.degrees(out[:,1]).max().round(0), " psi:", np.degrees(out[:,2]).min().round(0), np.degrees(out[:,2]).max().round(0))
print("phi<0 fraction:", np.mean(out[:,1] < 0).round(3), " Epot mean", out[:,3].mean().round(1))
np.save(f"/home/claude/mol_test_T{T:g}.npy", out)
