while pgrep -f "eq01_train.py 2 " > /dev/null || [ ! -f ckpt_s2/trainlog.pkl ]; do sleep 15; done
python3 eq01_train.py 4 8000 > train_s4.log 2>&1
python3 eq01_analyze.py 2 all > an_s2.log 2>&1
python3 eq01b_analyze.py 4 all > anb_s4.log 2>&1
