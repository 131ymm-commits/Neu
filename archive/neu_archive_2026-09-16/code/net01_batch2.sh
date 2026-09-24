#!/bin/bash
cd /home/claude
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
(python3 net01_sim.py 0.28 402 > net01_simC.log 2>&1; python3 net01_sim.py 0.36 401 > net01_simE.log 2>&1) &
(python3 net01_sim.py 0.28 403 > net01_simD.log 2>&1) &
wait
