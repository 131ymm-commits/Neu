python3 eq01b_analyze.py 3 all > anb_s3.log 2>&1
while [ ! -f ckpt_s5/trainlog.pkl ]; do sleep 15; done
python3 eq01b_analyze.py 5 all > anb_s5.log 2>&1
