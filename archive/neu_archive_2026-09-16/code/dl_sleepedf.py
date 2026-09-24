"""Download Sleep-EDF Expanded (age cassette, SC) via MNE from PhysioNet. User granted permission 2026-09-03."""
import mne, sys, os, json
mne.set_log_level('ERROR')
subs=list(range(0,20))   # 20 subjects, night 1 each -> 20 nights
done={}
try:
    paths=mne.datasets.sleep_physionet.age.fetch_data(subjects=subs, recording=[1], on_missing='warn')
    for i,(psg,hyp) in enumerate(paths):
        done[str(subs[i])]=[psg,hyp]
        print('OK', subs[i], os.path.basename(psg), os.path.basename(hyp), flush=True)
except Exception as e:
    print('ERR', repr(e), flush=True)
json.dump(done, open('/home/claude/sleepedf_paths.json','w'), indent=1)
open('/home/claude/sleepedf_done.flag','w').write('done %d\n'%len(done))
print('TOTAL', len(done))
