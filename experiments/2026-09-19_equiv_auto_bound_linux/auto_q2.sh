for s in 10 11 12; do python3 auto_train.py AW $s > auto/AW_s$s.log 2>&1; python3 auto_train.py AA $s > auto/AA_s$s.log 2>&1; done
