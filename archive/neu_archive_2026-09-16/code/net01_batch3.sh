#!/bin/bash
cd /home/claude
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
(python3 net01_sim_long.py 0.25 401 > net01L_a.log 2>&1; python3 net01_sim_long.py 0.28 401 > net01L_c.log 2>&1; python3 net01_sim_long.py 0.25 403 > net01L_e.log 2>&1) &
(python3 net01_sim_long.py 0.25 402 > net01L_b.log 2>&1; python3 net01_sim_long.py 0.28 402 > net01L_d.log 2>&1; python3 net01_sim_long.py 0.28 403 > net01L_f.log 2>&1) &
wait
