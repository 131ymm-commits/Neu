BRAIN-001 real data: 6 nights Sleep-EDF via GitHub deepbci/combsleepnet (MIT; source PhysioNet Sleep-EDF, ODC-BY).
Hypnograms (.mat, {0:W,1:REM,2:N1,3:N2,4:N3}) included here (tiny). PSG band-power blobs (~280 MB total: 4 bandpassed
Fpz-Cz channels δ/θ/α/σ per 30-s epoch) NOT bundled — re-clone the repo (commit in external/MANIFEST.md) to reproduce.
brain001_run.py reads combsleepnet/example_data/{psg,hyp}; brain002 is self-contained (sleepmodel.py).
