for s in 10 11 12; do python3 auto_train.py A0 $s > auto/A0_s$s.log 2>&1; python3 auto_train.py AS $s > auto/AS_s$s.log 2>&1; done
