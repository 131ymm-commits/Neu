while [ ! -f ckpt_s0/trainlog.pkl ] || [ ! -f ckpt_s1/trainlog.pkl ]; do sleep 10; done
python3 eq01_analyze.py 0 all > an_s0.log 2>&1
python3 eq01_analyze.py 1 all > an_s1.log 2>&1
