while pgrep -f "eq01_train.py 1 " > /dev/null; do sleep 10; done
python3 eq01_train.py 3 8000 > train_s3.log 2>&1
python3 eq01_train.py 5 8000 > train_s5.log 2>&1
python3 eq01b_analyze.py 3 all > anb_s3.log 2>&1
python3 eq01b_analyze.py 5 all > anb_s5.log 2>&1
